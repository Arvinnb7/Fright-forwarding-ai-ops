from datetime import date

from app.services.margin import MarginInput, MarkupType, calculate_margin


def test_spec_example_percent_markup():
    # Spec §6: Cost $1,500, 20% markup -> $1,800, margin $300, 16.7%.
    r = calculate_margin(MarginInput(cost_amount=1500, markup_value=20))
    assert r.selling_price == 1800.0
    assert r.gross_margin == 300.0
    assert round(r.gross_margin_percentage, 1) == 16.7
    assert r.warnings == []


def test_fixed_markup():
    r = calculate_margin(
        MarginInput(cost_amount=1000, markup_type=MarkupType.FIXED, markup_value=250)
    )
    assert r.selling_price == 1250.0
    assert r.gross_margin == 250.0


def test_below_cost_and_negative_margin_warn():
    r = calculate_margin(MarginInput(cost_amount=1000, selling_price_override=900))
    assert "Selling price is below cost." in r.warnings
    assert "Margin is zero or negative." in r.warnings


def test_low_margin_warning():
    r = calculate_margin(MarginInput(cost_amount=1000, markup_value=3))
    assert any("very low" in w for w in r.warnings)


def test_min_profit_threshold():
    r = calculate_margin(MarginInput(cost_amount=1000, markup_value=10, min_profit=200))
    assert any("minimum profit" in w for w in r.warnings)


def test_currency_mismatch_and_expired_validity():
    r = calculate_margin(
        MarginInput(
            cost_amount=1000,
            markup_value=20,
            currency="USD",
            cost_currency="EUR",
            validity_date=date(2020, 1, 1),
        ),
        today=date(2026, 6, 26),
    )
    assert any("Currency mismatch" in w for w in r.warnings)
    assert any("validity expired" in w for w in r.warnings)
