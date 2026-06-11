import unittest

from modules.investments.cash_drag import (
    cash_commodities,
    included_account,
    normalize_cash_drag_config,
)


class Commodity:
    def __init__(self, currency, meta):
        self.currency = currency
        self.meta = meta


class CashDragTest(unittest.TestCase):
    def test_normalize_cash_drag_config_uses_foresight_defaults(self):
        config = normalize_cash_drag_config({})
        self.assertEqual(config["accounts_pattern"], "^Assets")
        self.assertEqual(config["accounts_exclude_pattern"], "")
        self.assertEqual(config["metadata_label_cash"], "asset_allocation_Bond_Cash")
        self.assertEqual(config["min_threshold"], 0)

    def test_cash_commodities_include_operating_and_metadata_cash(self):
        commodities = cash_commodities(
            [
                Commodity("MMF", {"asset_allocation_Bond_Cash": "100"}),
                Commodity("VTI", {"asset_allocation_stocks_us": "100"}),
            ],
            {"operating_currency": ["USD"]},
            "asset_allocation_Bond_Cash",
        )
        self.assertEqual(commodities, {"USD", "MMF"})

    def test_included_account_applies_exclude_after_include(self):
        config = {
            "accounts_pattern": "^Assets",
            "accounts_exclude_pattern": "^Assets:Cash",
        }
        self.assertTrue(included_account("Assets:Investments:Taxable", config))
        self.assertFalse(included_account("Assets:Cash", config))
        self.assertFalse(included_account("Liabilities:CreditCard", config))


if __name__ == "__main__":
    unittest.main()
