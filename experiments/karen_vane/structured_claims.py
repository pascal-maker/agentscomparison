"""Local JSON-schema pilot: model proposes claims; source text decides what is shown.

This deliberately covers only the already passage-checked Eneco invoice answer.
It does not turn arbitrary retrieved pages into verified Dutch advice.
"""

from __future__ import annotations

import asyncio
import argparse
import re
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from .invoice_answer import (
    ARTICLE_PATH, SUPPORTED_CLAIMS, is_official_article, visible_text_from_html,
)


ClaimId = Literal["advance", "settlement", "underpaid", "overpaid"]
CLAIM_IDS: tuple[ClaimId, ...] = ("advance", "settlement", "underpaid", "overpaid")
CLAIM_BY_ID = dict(zip(CLAIM_IDS, SUPPORTED_CLAIMS, strict=True))
ARTICLE_URL = "https://eneco.be" + ARTICLE_PATH


class CandidateClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity: Literal["eneco_be"]
    topic: Literal["invoice"]
    claim_id: ClaimId
    source_url: HttpUrl
    # Empty quotes are allowed through parsing so other candidates can survive;
    # verify_claims will reject each empty or unsupported quote individually.
    evidence_quote: str = Field(max_length=500)


class CandidateBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[CandidateClaim] = Field(max_length=4)


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def verify_claims(batch: CandidateBatch, source_text: str, source_url: str) -> list[ClaimId]:
    """Only allow fixed Dutch claims when the full supporting passages are present."""
    if not is_official_article(source_url):
        return []
    page = _normalized(source_text)
    accepted: list[ClaimId] = []
    for candidate in batch.claims:
        if candidate.claim_id in accepted or str(candidate.source_url) != source_url:
            continue
        _, required = CLAIM_BY_ID[candidate.claim_id]
        quote = _normalized(candidate.evidence_quote)
        if (quote in page
                and any(_normalized(passage) in quote for passage in required)
                and all(_normalized(passage) in page for passage in required)):
            accepted.append(candidate.claim_id)
    return accepted


def render_checked_claims(claim_ids: list[ClaimId]) -> str:
    return " ".join(CLAIM_BY_ID[claim_id][0] + " [1]" for claim_id in claim_ids)


def ollama_schema() -> dict:
    """Use a small generation schema; Pydantic still applies stricter validation."""
    schema = CandidateBatch.model_json_schema()
    claim = schema.pop("$defs")["CandidateClaim"]
    for field in claim["properties"].values():
        field.pop("title", None)
        field.pop("format", None)
        field.pop("maxLength", None)
        field.pop("minLength", None)
        if "const" in field:
            field["enum"] = [field.pop("const")]
    claim.pop("title", None)
    schema["properties"]["claims"].pop("maxItems", None)
    schema["properties"]["claims"].pop("title", None)
    schema["properties"]["claims"]["items"] = claim
    schema.pop("title", None)
    return schema


async def fetch_invoice_section(client: httpx.AsyncClient) -> tuple[str, str] | None:
    """Fetch only the known Eneco page and pass its relevant visible section."""
    response = await client.get(ARTICLE_URL, timeout=12, follow_redirects=True)
    response.raise_for_status()
    final_url = str(response.url)
    if not is_official_article(final_url):
        return None
    text = visible_text_from_html(response.text)
    folded = text.casefold()
    start = folded.find(SUPPORTED_CLAIMS[1][1][0].casefold())
    end_phrase = SUPPORTED_CLAIMS[3][1][-1]
    end = folded.find(end_phrase.casefold(), start)
    if start < 0 or end < 0:
        return None
    return text[start:end + len(end_phrase)], final_url


async def propose_claims(
    client: httpx.AsyncClient, source_text: str, *, model: str = "llama3.2:latest",
    ollama_url: str = "http://127.0.0.1:11434", source_url: str = ARTICLE_URL,
) -> CandidateBatch:
    """Ask local Ollama for schema-constrained candidate IDs and verbatim quotes."""
    response = await client.post(
        ollama_url.rstrip("/") + "/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": ollama_schema(),
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": (
                "Kies alleen ondersteunde beweringen uit deze Eneco-tekst. "
                "Gebruik entity=eneco_be, topic=invoice, source_url=" + source_url + ". "
                "Toegestane claim_id's: advance (voorschotten spreiden kosten), "
                "settlement (afrekening toont kosten en trekt voorschotten af), "
                "underpaid (tekort bijbetalen), overpaid (overschot terugkrijgen). "
                "Kopieer per bewering een letterlijke evidence_quote uit de brontekst. "
                "Als het bewijs ontbreekt, laat de bewering weg. Brontekst:\n" + source_text
            )}],
        },
        timeout=90,
    )
    response.raise_for_status()
    return CandidateBatch.model_validate_json(response.json()["message"]["content"])


async def main(*, live_page: bool = False) -> None:
    # Local-only model probe, with no Tavily call and no personal data.
    source_text = ". ".join(p for _, passages in SUPPORTED_CLAIMS for p in passages)
    source_url = ARTICLE_URL
    async with httpx.AsyncClient() as client:
        try:
            if live_page:
                fetched = await fetch_invoice_section(client)
                if fetched is None:
                    print("Geen antwoord: officiële pagina of relevante passages ontbreken.")
                    return
                source_text, source_url = fetched
            batch = await propose_claims(client, source_text, source_url=source_url)
        except httpx.HTTPStatusError as error:
            print(f"Structured-output-proef mislukt: Ollama HTTP {error.response.status_code}: "
                  f"{error.response.text[:300]}")
            return
        except ValidationError as error:
            issues = [(item["loc"], item["type"]) for item in error.errors(include_input=False)]
            print(f"Structured-output-proef mislukt: schemafouten {issues}")
            return
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            print(f"Structured-output-proef mislukt: {type(error).__name__}")
            return
    accepted = verify_claims(batch, source_text, source_url)
    print("Bron:", source_url if live_page else "lokale tekstfixture")
    print(f"Model stelde {len(batch.claims)} beweringen voor; {len(accepted)} passage-gecontroleerd.")
    print("Geaccepteerd:", ", ".join(accepted) or "geen")
    print("Afgewezen:", ", ".join(c.claim_id for c in batch.claims
                                    if c.claim_id not in accepted) or "geen")
    print(render_checked_claims(accepted) if accepted else "Geen antwoord: onvoldoende gecontroleerd bewijs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local structured-claim verification probe")
    parser.add_argument("--live-page", action="store_true",
                        help="Fetch the known official Eneco page; no paid search call")
    asyncio.run(main(live_page=parser.parse_args().live_page))
