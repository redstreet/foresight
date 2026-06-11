import unittest

from modules.investments.account_types import (
    OTHER_BROKERAGES,
    brokerage_for_account,
    configured_brokerages,
)


class AccountTypesTest(unittest.TestCase):
    def test_configured_brokerages_reads_canonical_dict(self):
        self.assertEqual(
            configured_brokerages({"brokerages": ["Fidelity", "Vanguard"]}),
            ["Fidelity", "Vanguard"],
        )
        self.assertEqual(
            configured_brokerages(["Fidelity", "Vanguard"]),
            [],
        )

    def test_brokerage_for_account_uses_case_insensitive_substring(self):
        self.assertEqual(
            brokerage_for_account(
                "Assets:Investments:Taxable:fidelity:VTI",
                ["Fidelity", "Vanguard"],
            ),
            "Fidelity",
        )
        self.assertEqual(
            brokerage_for_account(
                "Assets:Investments:Taxable:Brokerage:VTI",
                ["Fidelity", "Vanguard"],
            ),
            OTHER_BROKERAGES,
        )


if __name__ == "__main__":
    unittest.main()
