"""The pilot audit uses saved public pages and makes no paid API requests."""

from datetime import date

from experiments.karen_search_ab.claim_audit import audit_amount_claim, monetary_numbers


def test_extracts_both_ends_of_cent_range() -> None:
    assert monetary_numbers("20,957–25,331 cent/kWh en €600") == {"20,957", "25,331", "600"}


def test_expired_official_deadline_overrides_literal_amount_match() -> None:
    pages = [{
        "url": "https://energie.wallonie.be/prime-habitation",
        "content": (
            "TOUTE DEMANDE DE PRIME DEVRA ETRE INTRODUITE AU PLUS TARD LE 30 SEPTEMBRE 2026 ! "
            "Pompe à chaleur pour le chauffage 600 €/appareil."
        ),
    }]
    result = audit_amount_claim("De premie bedraagt €600.", pages, on_date=date(2026, 10, 13))
    assert result["status"] == "EXPIRED_DEADLINE"
    assert result["missing_amounts"] == []
    assert result["expired_deadlines"] == ["2026-09-30"]


def test_commercial_amount_does_not_count_as_original_official_passage() -> None:
    pages = [{"url": "https://example.com/premie", "content": "600 €/appareil"}]
    result = audit_amount_claim("€600", pages, on_date=date(2026, 10, 13))
    assert result["status"] == "MISSING_ORIGINAL_PASSAGE"


def test_matching_official_number_is_only_a_text_match() -> None:
    pages = [{"url": "https://www.creg.be/tarief.pdf", "content": "Totaal 5,738 c€/kWh"}]
    result = audit_amount_claim("5,738 cent/kWh", pages, on_date=date(2026, 10, 13))
    assert result["status"] == "TEXT_MATCH_ONLY"
