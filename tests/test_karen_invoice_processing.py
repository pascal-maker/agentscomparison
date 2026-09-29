from decimal import Decimal

from luminus_harness.invoice_analysis import analyze_invoice_chunks, answer_uploaded_pdf_question
from luminus_harness.knowledge import KnowledgeChunk
from luminus_harness.rate_limit import SlidingWindowRateLimiter


def test_local_invoice_analysis_extracts_page_linked_facts_and_reconciles_clear_totals() -> None:
    chunks = [
        KnowledgeChunk(
            page=2,
            source="sample-bill.pdf",
            urls=(),
            text=(
                "Leverancier: Luminus. Factuurperiode: 01/01/2025 tot 31/12/2025. "
                "Elektriciteitsverbruik: 2.340 kWh. Totale energiekosten: € 1.234,56. "
                "Totaal voorschotten reeds aangerekend: € 900,00."
            ),
        )
    ]

    analysis = analyze_invoice_chunks(chunks)

    assert analysis["facts"]["supplier"]["value"] == "Luminus"
    assert analysis["facts"]["billing_period"]["value"] == "01/01/2025 tot 31/12/2025"
    assert analysis["facts"]["electricity_kwh"]["value"] == Decimal("2340")
    assert analysis["facts"]["total_energy_cost"]["value"] == Decimal("1234.56")
    assert analysis["facts"]["advances_paid"]["value"] == Decimal("900.00")
    assert analysis["facts"]["calculated_difference"]["value"] == Decimal("334.56")
    assert all(fact["page"] == 2 and fact["excerpt"] for fact in analysis["facts"].values() if fact)


def test_local_invoice_analysis_does_not_calculate_without_both_labeled_amounts() -> None:
    chunks = [
        KnowledgeChunk(
            page=1,
            source="sample-bill.pdf",
            urls=(),
            text="Te betalen saldo: € 125,00. Er staan ook meterreferenties 2025 en 2026.",
        )
    ]

    analysis = analyze_invoice_chunks(chunks)

    assert analysis["facts"]["amount_due"]["value"] == Decimal("125.00")
    assert analysis["facts"]["calculated_difference"] is None
    assert "- Rekenverschil: niet betrouwbaar gevonden." in analysis["answer"]


def test_local_invoice_analysis_labels_negative_difference_as_credit() -> None:
    chunks = [
        KnowledgeChunk(
            page=1,
            source="sample-bill.pdf",
            urls=(),
            text=(
                "Totale energiekosten: € 800,00. "
                "Totaal voorschotten reeds aangerekend: € 900,00."
            ),
        )
    ]

    analysis = analyze_invoice_chunks(chunks)

    assert analysis["facts"]["calculated_difference"]["value"] == Decimal("-100.00")
    assert "Rekenverschil (voorschotten hoger dan kosten): € 100,00" in analysis["answer"]
    assert "bevestigt niet op zichzelf het uiteindelijke afrekensaldo" in analysis["answer"]


def test_local_invoice_analysis_does_not_treat_a_due_date_as_an_amount() -> None:
    chunks = [
        KnowledgeChunk(
            page=1,
            source="sample-bill.pdf",
            urls=(),
            text="Te betalen vóór 01/05/2025. Het bedrag staat niet leesbaar op deze pagina.",
        )
    ]

    analysis = analyze_invoice_chunks(chunks)

    assert analysis["facts"]["amount_due"] is None


def test_uploaded_pdf_follow_up_returns_only_retrieved_local_evidence() -> None:
    chunks = [
        KnowledgeChunk(
            page=3,
            source="sample-bill.pdf",
            urls=(),
            text="Totaal voorschotten reeds aangerekend: € 900,00 voor elektriciteit.",
        ),
        KnowledgeChunk(
            page=1,
            source="sample-bill.pdf",
            urls=(),
            text="Dit is de algemene informatie over verhuis en klantendienst.",
        ),
    ]

    result = answer_uploaded_pdf_question("Hoeveel voorschotten zijn aangerekend?", chunks)

    assert result["sources"]
    assert result["sources"][0]["detail"] == "PDF · pagina 3"
    assert "€ 900,00" in result["sources"][0]["excerpt"]
    assert "€ 900,00" in result["answer"]


def test_rate_limiter_evicts_expired_and_caps_unique_clients() -> None:
    limiter = SlidingWindowRateLimiter(requests=2, window_seconds=60, max_clients=2)

    assert limiter.allow("client-a", 0)
    assert limiter.allow("client-b", 0)
    assert limiter.allow("client-c", 1)
    assert limiter.tracked_clients == 2
    assert limiter.allow("client-a", 61)
    assert limiter.tracked_clients == 1


def test_rate_limiter_rejects_excess_requests_inside_window() -> None:
    limiter = SlidingWindowRateLimiter(requests=2, window_seconds=60, max_clients=2)

    assert limiter.allow("client-a", 0)
    assert limiter.allow("client-a", 1)
    assert not limiter.allow("client-a", 2)
    assert limiter.allow("client-a", 61)
