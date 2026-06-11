from decimal import Decimal
import unittest

from modules.investments.asset_allocation import (
    ASSET_ALLOCATION_CONFIG,
    TOTAL_PATH,
    allocations_for_commodity,
    build_class_tree,
    detail_rows_for_class,
    normalize_config,
)


class AssetAllocationTest(unittest.TestCase):
    def test_normalize_config_uses_baked_in_default(self):
        config = normalize_config()
        self.assertEqual(ASSET_ALLOCATION_CONFIG["accounts_pattern"], "^Assets:Investments")
        self.assertEqual(config["accounts_patterns"], ["^Assets:Investments"])
        self.assertTrue(config["skip_tax_adjustment"])

    def test_normalize_config_accepts_canonical_keys(self):
        config = normalize_config(
            {
                "accounts_pattern": "Assets:Investments",
                "tax_adjustment": True,
            }
        )

        self.assertEqual(config["accounts_patterns"], ["Assets:Investments"])
        self.assertFalse(config["skip_tax_adjustment"])

    def test_underallocated_commodity_pads_unknown(self):
        warnings = []
        allocations = allocations_for_commodity(
            "FUND",
            {"FUND": {"asset_allocation_equity": Decimal("60")}},
            warnings,
        )

        self.assertEqual(
            allocations,
            [("equity", Decimal("60")), ("unknown", Decimal("40"))],
        )
        self.assertEqual(len(warnings), 1)

    def test_class_tree_rolls_up_nested_classes(self):
        tree = build_class_tree(
            [
                {"class_path": "equity_domestic", "amount": Decimal("60")},
                {"class_path": "bond", "amount": Decimal("40")},
            ]
        )

        self.assertEqual(tree["amount"], 100.0)
        self.assertEqual(tree["children"][0]["path"], "equity")
        self.assertEqual(tree["children"][0]["amount"], 60.0)
        self.assertEqual(tree["children"][0]["children"][0]["path"], "equity_domestic")

    def test_detail_rows_are_prorated_to_selected_class(self):
        contributions = [
            {
                "account": "Assets:Investments:Brokerage:AAPL",
                "commodity": "AAPL",
                "class_path": "equity_domestic",
                "amount": Decimal("60"),
            },
            {
                "account": "Assets:Investments:Brokerage:BND",
                "commodity": "BND",
                "class_path": "bond",
                "amount": Decimal("40"),
            },
        ]

        tree, total = detail_rows_for_class(contributions, "equity")

        self.assertEqual(total, Decimal("60"))
        self.assertEqual(tree["amount"], 60.0)
        self.assertEqual(tree["children"][0]["name"], "Assets")
        self.assertEqual(tree["children"][0]["children"][0]["name"], "Investments")
        brokerage = tree["children"][0]["children"][0]["children"][0]
        aapl = brokerage["children"][0]
        self.assertEqual(aapl["name"], "AAPL")
        self.assertEqual(aapl["children"], [])

        tree, total = detail_rows_for_class(contributions, TOTAL_PATH)
        self.assertEqual(total, Decimal("100"))
        self.assertEqual(tree["amount"], 100.0)


if __name__ == "__main__":
    unittest.main()
