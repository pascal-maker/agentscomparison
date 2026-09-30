"""Temporary, structured offer-comparison inputs for Karen's public answer API."""

from __future__ import annotations

import asyncio
import json
import math
import re
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .provider_comparison import COMPARATORS, EXTRA_FIELDS, compare_energy_offers, requested_fields, validate_extra_inputs

SESSION_TTL_SECONDS = 60 * 60
MAX_SESSIONS = 64
FIELDS = ("region", "postcode", "energy_type", "annual_consumption_kwh")
PROMPTS = {
    "region": "In welk gewest woon je: Vlaanderen, Brussel of Wallonië?",
    "postcode": "Wat is je Belgische postcode van vier cijfers?",
    "energy_type": "Wil je elektriciteit of aardgas vergelijken? Kies één energietype.",
    "annual_consumption_kwh": "Hoeveel kWh verbruik je per jaar voor dat energietype? Geef een positief jaarverbruik in kWh.",
    "meter_type": "Heb je een enkelvoudige, tweevoudige (dag/nacht) of uitsluitend nachtmeter?",
    "meter_technology": "Heb je een digitale of analoge meter?",
    "annual_day_consumption_kwh": "Hoeveel kWh verbruik je jaarlijks overdag? Geef het jaarcijfer voor dagverbruik.",
    "annual_night_consumption_kwh": "Hoeveel kWh verbruik je jaarlijks 's nachts? Geef het jaarcijfer voor nachtverbruik.",
    "is_prosumer": "Ben je prosument (produceer je zelf elektriciteit)? Antwoord ja of nee.",
}
REGIONS = {
    "flanders": r"\b(?:vlaanderen|vlaams(?:e)?(?: gewest)?|flanders)\b",
    "brussels": r"\b(?:brussel(?:s)?|bruxelles|brussels)\b",
    "wallonia": r"\b(?:walloni[eë]|waals(?:e)?(?: gewest)?|wallonia|wallonie)\b",
}
ENERGIES = {
    "electricity": r"\b(?:elektriciteit|elektriciteits\w*|stroom|electricity|electriciteit)\b",
    "gas": r"\b(?:aardgas\w*|gas(?:aanbiedingen|contracten|tarieven)?)\b",
}
NUMBER = r"[-+]?(?:\d{1,3}(?:[. ]\d{3})+|\d+)(?:[,.]\d+)?"


def is_offer_comparison_question(question: str) -> bool:
    text = question.casefold()
    action = re.search(r"\b(?:vergelijk\w*|compar(?:e|ing|ison)|goedkoop\w*|voordelig\w*|cheapest|best(?:e)?)\b", text)
    subject = re.search(r"\b(?:energie\w*|elektriciteit|elektriciteits\w*|stroom|aardgas\w*|gas(?:aanbiedingen|contracten|tarieven)?|electricity|leveranciers?|providers?|offers?|aanbiedingen|contracten?|tarieven|v-test|brusim|compacwape|kwh)\b", text)
    return bool(action and subject)


def _number(text: str, *, allow_zero: bool = False) -> float | None:
    compact = re.sub(r"\s", "", text)
    if re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})+(?:,\d+)?", compact):
        compact = compact.replace(".", "")
    try:
        value = float(compact.replace(",", "."))
    except ValueError:
        return None
    return value if math.isfinite(value) and (value >= 0 if allow_zero else value > 0) else None


def extract_inputs(question: str, pending: str | None = None) -> dict:
    """Accept explicit values only; ambiguous/invalid mentions clear older values."""
    text = question.casefold().strip()
    values: dict = {}
    for name, patterns in (("region", REGIONS), ("energy_type", ENERGIES)):
        found = [value for value, pattern in patterns.items() if re.search(pattern, text)]
        if found:
            match = re.search(patterns[found[0]], text)
            negated = re.search(r"\b(?:niet|not|geen)\s+(?:(?:in|het|voor)\s+)?$", text[:match.start()])
            values[name] = found[0] if len(found) == 1 and not negated else None

    consumption = list(re.finditer(rf"(?<![\w.,+-])({NUMBER})\s*k\s*w\s*h\b", text))
    if consumption:
        # Monthly figures and day/night splits cannot be treated as annual totals.
        nonannual = re.search(r"\b(?:maand\w*|monthly|months?|kwartaal|dag\w*|nacht\w*|daily|days?|night)\b", text)
        annual = pending == "annual_consumption_kwh" or re.search(r"\b(?:jaar\w*|annual\w*|year\w*)\b", text)
        values["annual_consumption_kwh"] = _number(consumption[0][1]) if len(consumption) == 1 and annual and not nonannual else None
    labelled = re.search(r"\b(?:postcode|postal code)\s*(?:is|:|=)?\s*(\S+)", text)
    if labelled:
        code = labelled[1].rstrip(",.;?!")
        values["postcode"] = code if re.fullmatch(r"[1-9][0-9]{3}", code) else None
    else:
        codes = [m[0] for m in re.finditer(r"(?<![\w.,+-])[1-9][0-9]{3}(?!\w|[.,]\d)", text)
                 if not any(c.start() <= m.start() < c.end() for c in consumption)]
        if codes:
            # A bare number is only a postcode in the postcode prompt or a full request.
            if pending == "postcode" or (pending != "annual_consumption_kwh" and consumption and not re.search(r"\b(?:dag\w*|nacht\w*|day|night)\b", text)):
                values["postcode"] = codes[0] if len(codes) == 1 else None
    if pending == "annual_consumption_kwh" and re.fullmatch(NUMBER, text):
        values["annual_consumption_kwh"] = _number(text)
    if values.get("energy_type", "") is None:
        values["annual_consumption_kwh"] = None
    return values


def extract_additional_inputs(question: str, pending: str | None = None) -> dict:
    """Parse only supported, explicit comparator details; never store the question."""
    text = question.casefold().strip().rstrip(".?!")
    values = {}
    meters = {
        "single_rate": r"\b(?:enkelvoudig\w*|single[_ -]rate)\b",
        "dual_rate": r"\b(?:tweevoudig\w*|dubbel\w*|dual[_ -]rate|dag/nachtmeter)\b",
        "exclusive_night": r"\b(?:uitsluitend\w* nacht\w*|exclusief nacht\w*|exclusive[_ -]night)\b",
    }
    technologies = {"digital": r"\b(?:digita(?:al|le)|digital)\b", "analogue": r"\b(?:analo(?:og|ge)|analogue|analog)\b"}
    for field, patterns in (("meter_type", meters), ("meter_technology", technologies)):
        found = [name for name, pattern in patterns.items() if re.search(pattern, text)]
        if found:
            match = re.search(patterns[found[0]], text)
            negated = re.search(r"\b(?:niet|not|geen)\s+(?:een\s+)?$", text[:match.start()])
            values[field] = found[0] if len(found) == 1 and not negated else None
    monthly = re.search(r"\b(?:maand\w*|monthly|kwartaal|daily)\b", text)
    annual = pending in {"annual_day_consumption_kwh", "annual_night_consumption_kwh"} or re.search(r"\b(?:jaar\w*|annual\w*|year\w*)\b", text)
    for field, label in (("annual_day_consumption_kwh", r"(?:dag(?:verbruik)?|day)"),
                         ("annual_night_consumption_kwh", r"(?:nacht(?:verbruik)?|night)")):
        matches = re.findall(rf"\b{label}\s*(?:is|:|=)?\s*({NUMBER})\s*(?:kwh)?", text)
        matches += re.findall(rf"(?<![\w.,+-])({NUMBER})\s*kwh\s*{label}\b", text)
        if matches:
            values[field] = _number(matches[0], allow_zero=True) if len(matches) == 1 and annual and not monthly else None
    if pending in {"annual_day_consumption_kwh", "annual_night_consumption_kwh"}:
        bare = re.fullmatch(rf"({NUMBER})(?:\s*kwh)?(?:\s*(?:per jaar|jaarlijks|annual(?:ly)?))?", text)
        if bare:
            values[pending] = _number(bare[1], allow_zero=True)
    labelled_prosumer = re.findall(r"\b(?:prosument|prosumer)\s*:\s*(ja|yes|nee|no)\b", text)
    if labelled_prosumer:
        answers = {answer in {"ja", "yes"} for answer in labelled_prosumer}
        values["is_prosumer"] = answers.pop() if len(answers) == 1 else None
    elif pending == "is_prosumer" and text in {"ja", "yes", "nee", "no"}:
        values["is_prosumer"] = text in {"ja", "yes"}
    elif re.search(r"\b(?:prosument|prosumer)\b", text):
        positive = re.fullmatch(r"(?:ik ben (?:een )?|i am (?:a )?)?(?:prosument|prosumer)(?:\s*:\s*(?:ja|yes))?", text)
        negative = re.fullmatch(r"(?:ik ben |i am )?(?:geen prosument|niet (?:een )?prosument|not (?:a )?prosumer)|(?:prosument|prosumer)\s*:\s*(?:nee|no)", text)
        values["is_prosumer"] = True if positive else False if negative else None
    return values


def is_comparison_followup(question: str, pending: str | None) -> bool:
    """Allow short field answers without permitting unrelated prose via a number."""
    text = question.casefold().strip()
    if text.rstrip(".?!") in {"stop", "annuleer", "cancel"}:
        return True
    values = (extract_additional_inputs(question, pending) if pending in EXTRA_FIELDS else extract_inputs(question, pending))
    if not any(value is not None for value in values.values()):
        return False
    words = re.findall(r"[a-zà-ÿ_]+", text)
    allowed = {
        "ik", "ben", "heb", "een", "is", "mijn", "i", "am", "have", "a", "my", "the", "meter",
        "postcode", "postal", "code", "vlaanderen", "flanders", "brussel", "brussels", "bruxelles",
        "wallonië", "wallonie", "wallonia", "elektriciteit", "electricity", "stroom", "gas", "aardgas",
        "ja", "nee", "yes", "no", "geen", "niet", "not", "prosument", "prosumer",
        "enkelvoudig", "enkelvoudige", "tweevoudig", "tweevoudige", "dubbele", "uitsluitend", "nachtmeter",
        "single_rate", "dual_rate", "exclusive_night", "single", "dual", "rate", "exclusive", "night",
        "digitaal", "digitale", "digital", "analoog", "analoge", "analogue", "analog",
        "kwh", "per", "jaar", "jaarlijks", "annual", "annually", "year", "day", "dag", "nacht",
        "dagverbruik", "nachtverbruik", "en", "and", "overdag", "s", "nachts",
    }
    return len(words) <= 16 and all(word in allowed for word in words)


def _reply(answer: str, status: str, session_id: str | None = None, **extra) -> dict:
    return {
        "answer": answer, "sources": [], "suggested_sources": [],
        "processing": "regional-offer-comparison", "comparison_status": status,
        "comparison_session_id": session_id, "live_source_status": "not-needed", **extra,
    }


def pdf_comparison_reply() -> dict:
    return _reply("Verwijder eerst je PDF via ‘Verwijder’ om energieaanbiedingen te vergelijken. Je PDF blijft alleen op Karen’s backend verwerkt.", "pdf-blocked", processing="local-only")


def _format_result(raw: str, inputs: dict) -> dict:
    comparator = COMPARATORS[inputs["region"]]
    suggested = [{"title": comparator.name, "url": comparator.url,
                  "detail": "Officiële vergelijker · zelf raadplegen, geen bevestigd aanbod"}]
    failed = _reply("De live vergelijking is mislukt of niet beschikbaar. Er zijn geen jaarprijzen bevestigd. Probeer later opnieuw of raadpleeg de officiële vergelijker.", "failed",
                    live_source_status="failed", suggested_sources=suggested)
    try:
        result = json.loads(raw)
        status = result["status"]
        if status in {"needs_input", "unavailable"}:
            details = result.get("required_information" if status == "needs_input" else "notes", [])
            if not isinstance(details, list) or not all(isinstance(item, str) for item in details):
                return failed
            explanation = "De officiële vergelijker vraagt extra informatie" if status == "needs_input" else "De officiële vergelijker kon geen aanbiedingen tonen"
            suffix = ": " + "; ".join(details) if details else ". Raadpleeg de officiële vergelijker"
            return _reply(explanation + suffix + ". Er zijn geen jaarprijzen bevestigd. Deze vergelijking is afgesloten; je kunt een nieuwe starten.", status,
                          suggested_sources=suggested, live_source_status="failed")
        if status != "success" or not isinstance(result["offers"], list) or not result["offers"]:
            return failed
        checked = datetime.fromisoformat(result["checked_at_utc"])
        if checked.tzinfo is None:
            return failed
        checked_label = checked.astimezone(ZoneInfo("Europe/Brussels")).strftime("%d-%m-%Y om %H:%M %Z")
        lines = [f"{comparator.name} toont deze geraamde jaarkosten voor {inputs['annual_consumption_kwh']:g} kWh per jaar. Gecontroleerd op {checked_label}."]
        sources = []
        for offer in result["offers"][:3]:
            cost = offer["estimated_annual_cost_eur"]
            url = urlparse(offer["source_url"])
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                return failed
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                return failed
            supplier, product = offer["supplier"], offer["product"]
            if not isinstance(supplier, str) or not supplier.strip() or not isinstance(product, str) or not product.strip():
                return failed
            price = f"{cost:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
            line = f"{len(sources) + 1}. {supplier} — {product}: € {price} per jaar."
            lines.append(line)
            sources.append({"title": f"{supplier} · {product}", "url": offer["source_url"],
                            "detail": f"{comparator.name} · gecontroleerd {checked_label}"})
        lines.append("Dit zijn de getoonde ramingen van de vergelijker; controleer de voorwaarden voor je een contract kiest.")
        return _reply("\n\n".join(lines), "success", sources=sources, live_source_status="checked", checked_at_utc=result["checked_at_utc"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return failed


@dataclass
class ComparisonSession:
    inputs: dict = field(default_factory=dict)
    expires_at: float = 0
    required_fields: tuple[str, ...] = ()
    in_flight: bool = False


class ComparisonSessions:
    """Bounded process-local state; no questions, PDF text, or results are retained."""

    def __init__(self) -> None:
        self.sessions: OrderedDict[str, ComparisonSession] = OrderedDict()
        self._expiry_handles: dict[str, asyncio.TimerHandle] = {}

    def discard(self, session_id: str | None) -> None:
        self.sessions.pop(session_id, None)
        handle = self._expiry_handles.pop(session_id, None)
        if handle:
            handle.cancel()

    def prune(self) -> None:
        now = time.monotonic()
        for key, session in list(self.sessions.items()):
            if session.expires_at <= now:
                self.discard(key)

    async def answer(self, question: str, session_id: str | None) -> dict | None:
        self.prune()
        explicit = is_offer_comparison_question(question)
        session = self.sessions.get(session_id)
        general_question = re.match(r"(?:wat|hoe|waarom|wanneer|wie|what|how|why)\b", question.casefold().strip())
        if not explicit and general_question:
            return None
        if session_id and session is None:
            return _reply("Deze vergelijkingssessie is verlopen of afgesloten. Start een nieuwe vergelijking en geef opnieuw je gewest, postcode, energietype en jaarverbruik in kWh.", "expired")
        if session and re.fullmatch(r"(?:stop|annuleer|cancel)(?: de vergelijking)?[.!]?", question.casefold().strip()):
            self.discard(session_id)
            return _reply("De vergelijking is geannuleerd. Je vergelijkingsgegevens zijn gewist.", "cancelled")
        if not session and not explicit:
            return None
        if session and session.in_flight:
            return _reply("De vergelijking loopt nog. Wacht op het resultaat; er is geen nieuwe opzoeking gestart.", "running", session_id)
        if explicit and session and session.required_fields:
            # An explicit new comparison must not silently reuse the previous household inputs.
            self.discard(session_id)
            session_id, session = None, None
        fields = FIELDS + (session.required_fields if session else ())
        pending = next((name for name in fields if not session or name not in session.inputs), None)
        values = (extract_additional_inputs(question, pending) if session and session.required_fields
                  else {**extract_inputs(question, pending), **extract_additional_inputs(question)})
        # A normal FAQ/CREG question remains on the existing route, even mid-comparison.
        if session and not explicit and not values and len(question.split()) > 4:
            return None
        return await self.submit(values, session_id)

    async def submit(self, values: dict, session_id: str | None) -> dict:
        """Apply explicit structured tool inputs using the same collector as the API."""
        self.prune()
        session = self.sessions.get(session_id)
        if session_id and session is None:
            return _reply("Deze vergelijking is verlopen of afgesloten. Start een nieuwe vergelijking.", "expired")
        if session and session.in_flight:
            return _reply("De vergelijking loopt nog. Wacht op het resultaat; er is geen nieuwe opzoeking gestart.", "running", session_id)
        fields = FIELDS + (session.required_fields if session else ())
        values = {name: value for name, value in values.items() if name in FIELDS + EXTRA_FIELDS}
        if not session:
            while len(self.sessions) >= MAX_SESSIONS:
                self.discard(next(iter(self.sessions)))
            session_id = secrets.token_urlsafe(32)
            session = ComparisonSession(expires_at=time.monotonic() + SESSION_TTL_SECONDS)
            self.sessions[session_id] = session
            self._expiry_handles[session_id] = asyncio.get_running_loop().call_later(SESSION_TTL_SECONDS, self.discard, session_id)
        for name, value in values.items():
            if name == "region" and value not in REGIONS:
                value = None
            if name == "energy_type" and value not in ENERGIES:
                value = None
            if name == "postcode" and (not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{3}", value)):
                value = None
            if name == "annual_consumption_kwh" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
                value = None
            if name in EXTRA_FIELDS and value is not None and validate_extra_inputs({name: value}):
                value = None
                session.required_fields = tuple(dict.fromkeys((*session.required_fields, name)))
            if name in {"region", "energy_type"} and name in session.inputs and value != session.inputs[name]:
                for extra in EXTRA_FIELDS:
                    session.inputs.pop(extra, None)
                session.required_fields = ()
                if name == "energy_type" and "annual_consumption_kwh" not in values:
                    session.inputs.pop("annual_consumption_kwh", None)
            if value is None:
                session.inputs.pop(name, None)
            else:
                session.inputs[name] = value
        fields = FIELDS + session.required_fields
        missing = [name for name in fields if name not in session.inputs]
        if missing:
            return _reply(PROMPTS[missing[0]], "collecting", session_id, required_information=missing)
        error = validate_extra_inputs(session.inputs)
        if error:
            invalid = tuple(name for name in EXTRA_FIELDS if name in session.inputs
                            and validate_extra_inputs({name: session.inputs[name]}))
            if not invalid:
                invalid = ("annual_day_consumption_kwh", "annual_night_consumption_kwh")
            for name in invalid:
                session.inputs.pop(name, None)
            session.required_fields = tuple(dict.fromkeys((*session.required_fields, *invalid)))
            return _reply(error, "collecting", session_id, required_information=list(session.required_fields))
        inputs = dict(session.inputs)
        # Mark before awaiting: duplicate/concurrent requests cannot repeat a paid lookup.
        session.in_flight = True
        try:
            raw = await compare_energy_offers(**inputs)
        except Exception:
            raw = ""
        session.in_flight = False
        self.prune()
        if self.sessions.get(session_id) is not session:
            return _reply("Deze vergelijking is verlopen of geannuleerd. De vergelijkingsgegevens zijn gewist.", "expired")
        try:
            result = json.loads(raw)
            required = requested_fields(result) if result.get("status") == "needs_input" else None
        except (ValueError, AttributeError, TypeError):
            required = None
        if required and any(name not in inputs for name in required):
            session.required_fields = tuple(dict.fromkeys((*session.required_fields, *required)))
            missing = [name for name in session.required_fields if name not in inputs]
            return _reply("De officiële vergelijker vraagt extra informatie. " + PROMPTS[missing[0]]
                          + " Er zijn geen jaarprijzen bevestigd.", "collecting", session_id, required_information=missing)
        self.discard(session_id)
        return _format_result(raw, inputs)
