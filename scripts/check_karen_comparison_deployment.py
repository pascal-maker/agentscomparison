#!/usr/bin/env python3
"""Live smoke check using incomplete comparisons and a synthetic PDF only.

Never submits a complete comparison or calls the public FAQ/Gemma route.
"""

from __future__ import annotations

import argparse
import json
from io import BytesIO
from urllib.request import Request, urlopen

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def synthetic_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 40 750 Td (SYNTHETIC TEST. Leverancier: Luminus. Totaal voorschotten reeds aangerekend: 900,00 EUR.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="Karen's HTTPS backend origin")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    if not base.startswith("https://"):
        parser.error("Use an HTTPS backend origin.")
    pending: set[str] = set()
    pdf_id: str | None = None

    def request(path: str, *, method: str = "GET", body: bytes | None = None,
                content_type: str | None = None) -> dict:
        headers = {"Content-Type": content_type} if content_type else {}
        with urlopen(Request(base + path, data=body, headers=headers, method=method), timeout=30) as response:
            return json.load(response)

    def answer(question: str, token: str | None = None, session: str | None = None) -> dict:
        body = {"question": question}
        if token:
            body["comparison_session_id"] = token
        if session:
            body["session_id"] = session
        result = request("/api/answer", method="POST", body=json.dumps(body).encode(), content_type="application/json")
        if result.get("comparison_session_id"):
            pending.add(result["comparison_session_id"])
        return result

    # Refuse to send any test turn until the new routing contract is deployed.
    schema = request("/openapi.json")
    properties = schema["components"]["schemas"]["AnswerRequest"]["properties"]
    if "comparison_session_id" not in properties:
        raise RuntimeError("Comparison routing is not deployed; no questions were submitted.")
    health = request("/api/health")
    assert health["status"] == "ok"
    assert health["uploaded_pdf_processing"] == "local-only"
    try:
        first = answer("Vergelijk energieaanbiedingen")
        token = first["comparison_session_id"]
        assert first["comparison_status"] == "collecting"
        assert first["required_information"][0] == "region"
        assert answer("Vlaanderen", token)["required_information"][0] == "postcode"
        second = answer("Vergelijk gas in Brussel")
        other = second["comparison_session_id"]
        assert token != other
        assert answer("9000", token)["required_information"][0] == "energy_type"
        assert answer("elektriciteit", token)["required_information"] == ["annual_consumption_kwh"]
        monthly = answer("300 kWh per maand", token)
        assert monthly["comparison_status"] == "collecting"
        assert monthly["required_information"] == ["annual_consumption_kwh"]
        assert answer("1000", other)["required_information"] == ["annual_consumption_kwh"]
        for key in (token, other):
            cancelled = answer("annuleer", key)
            assert cancelled["comparison_status"] == "cancelled"
            assert cancelled["comparison_session_id"] is None
            pending.discard(key)
        assert answer("Vlaanderen", token)["comparison_status"] == "expired"

        boundary = "karen-synthetic-smoke-check"
        multipart = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"synthetic-smoke.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
                     + synthetic_pdf() + f"\r\n--{boundary}--\r\n".encode())
        upload = request("/api/upload", method="POST", body=multipart, content_type=f"multipart/form-data; boundary={boundary}")
        pdf_id = upload["session_id"]
        assert upload["processing"] == "local-only"
        assert "900,00" in upload["answer"]
        pdf_reply = answer("Hoeveel voorschotten zijn aangerekend?", session=pdf_id)
        assert pdf_reply["processing"] == "local-only"
        assert "900,00" in pdf_reply["answer"]
        assert pdf_reply["sources"][0]["detail"] == "PDF · pagina 1"
        blocked = answer("Vergelijk gas in Brussel", session=pdf_id)
        assert blocked["comparison_status"] == "pdf-blocked"
        assert blocked["processing"] == "local-only"
        assert not blocked["sources"]
        print(json.dumps({
            "health": "ok", "comparison_collection": "passed", "isolated_sessions": "passed",
            "monthly_consumption_rejected": "passed", "cancellation": "passed",
            "synthetic_pdf_upload_and_follow_up": "local-only", "pdf_comparison_block": "passed",
            "paid_comparator_calls": 0,
        }))
    finally:
        for key in pending:
            request(f"/api/comparison-session/{key}", method="DELETE")
        if pdf_id:
            request(f"/api/session/{pdf_id}", method="DELETE")


if __name__ == "__main__":
    main()
