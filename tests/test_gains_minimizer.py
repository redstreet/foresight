import unittest
from datetime import date
from decimal import Decimal

from modules.taxes.gains_minimizer import (
    ACCOUNT_FIELD_OPTIONS,
    DEFAULT_GAINS_MINIMIZER_CONFIG,
    account_field_label,
    build_gains_minimizer_config,
    build_gains_minimizer_warnings,
    gain_term,
    gains_minimizer_query,
    percent,
    taxable_lots,
)


class FakeColumn:
    def __init__(self, name):
        self.name = name


class FakeUnits:
    def __init__(self, number, currency):
        self.number = number
        self.currency = currency


class FakePosition:
    def __init__(self, number, currency):
        self.units = FakeUnits(number, currency)


class FakeInventory:
    def __init__(self, number=None, currency="USD"):
        self.number = number
        self.currency = currency

    def get_only_position(self):
        if self.number is None:
            return None
        return FakePosition(self.number, self.currency)

    def is_empty(self):
        return self.number is None


class GainsMinimizerTest(unittest.TestCase):
    def test_build_config_uses_editable_defaults(self):
        config = build_gains_minimizer_config(None, "parent", None, None, None)

        self.assertEqual(
            config["accounts_pattern"],
            DEFAULT_GAINS_MINIMIZER_CONFIG["accounts_pattern"],
        )
        self.assertEqual(config["account_field"], ACCOUNT_FIELD_OPTIONS["Parent account"])
        self.assertEqual(config["currency"], "USD")
        self.assertEqual(config["st_tax_rate"], Decimal("0.3"))
        self.assertEqual(config["lt_tax_rate"], Decimal("0.15"))
        self.assertEqual(account_field_label("parent"), "Parent account")

    def test_gain_term_matches_one_year_plus_one_day_rule(self):
        self.assertEqual(gain_term(date(2024, 1, 1), date(2025, 1, 1)), "Short")
        self.assertEqual(gain_term(date(2024, 1, 1), date(2025, 1, 2)), "Long")

    def test_percent_handles_zero_denominator(self):
        self.assertEqual(percent(Decimal("3"), Decimal("0")), Decimal("0"))
        self.assertEqual(percent(Decimal("3"), Decimal("12")), Decimal("25.00"))

    def test_build_config_converts_percent_tax_rates_to_decimals(self):
        config = build_gains_minimizer_config(
            None,
            "Parent account",
            "USD",
            9.3,
            15,
        )

        self.assertEqual(config["st_tax_rate"], Decimal("0.093"))
        self.assertEqual(config["lt_tax_rate"], Decimal("0.15"))

    def test_query_uses_configured_filter_and_currency(self):
        config = build_gains_minimizer_config(
            "^Assets:Investments:Taxable",
            "leaf",
            "USD",
            30.0,
            15.0,
        )
        query = gains_minimizer_query(config, "USD")

        self.assertIn("LEAF(account) as account", query)
        self.assertIn("Assets:Investments:Taxable", query)
        self.assertIn("CONVERT(value(sum(position)), 'USD')", query)

    def test_taxable_lots_accepts_tuple_rows(self):
        config = build_gains_minimizer_config(
            "^Assets:Investments:Taxable",
            "Parent account",
            "USD",
            30.0,
            15.0,
        )

        def run_bql_query(_entries, _options, _query, numberify=False):
            self.assertFalse(numberify)
            return (
                [
                    FakeColumn("account"),
                    FakeColumn("units"),
                    FakeColumn("market_value"),
                    FakeColumn("acq_date"),
                    FakeColumn("basis"),
                ],
                [
                    (
                        "Assets:Investments:Taxable:Brokerage",
                        FakeInventory("10", "VTI"),
                        FakeInventory("1000", "USD"),
                        date(2020, 1, 1),
                        FakeInventory("700", "USD"),
                    )
                ],
            )

        lots = taxable_lots(config, "USD", [], {}, run_bql_query)

        self.assertEqual(len(lots), 1)
        self.assertEqual(lots[0]["account"], "Assets:Investments:Taxable:Brokerage")
        self.assertEqual(lots[0]["ticker"], "VTI")
        self.assertEqual(lots[0]["market_value"], Decimal("1000"))
        self.assertEqual(lots[0]["gain"], Decimal("300"))

    def test_build_gains_minimizer_warnings_flags_unexpected_currency(self):
        warnings = build_gains_minimizer_warnings(
            {"currency": "USD"},
            [
                {
                    "account": "Assets:Investments:Taxable:Brokerage",
                    "ticker": "VTI",
                    "acq_date": date(2020, 1, 1),
                    "market_value_currency": "CAD",
                    "basis_currency": "USD",
                }
            ],
        )

        self.assertEqual(
            warnings,
            [
                "Assets:Investments:Taxable:Brokerage VTI 2020-01-01 "
                "has market value in CAD, expected USD."
            ],
        )


if __name__ == "__main__":
    unittest.main()
