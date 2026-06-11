import unittest

from modules.estate.beneficiaries import (
    BENEFICIARY_EXCLUDED_ACCOUNTS,
    BENEFICIARY_TABLES,
    BENEFICIARY_WARNING_ACCOUNT_PATTERN,
    account_display_prefix,
    account_or_ancestor_included,
    active_open_asset_accounts,
    beneficiary_column_labels,
    beneficiary_excluded_account,
    beneficiary_column_width_style,
    beneficiary_highlighted_row_ids,
    beneficiary_row_has_trust_or_na,
    beneficiary_table_cell_style,
    beneficiary_title_summary,
    column_has_value,
    commodity_leaf_account,
    display_account,
    included_open_accounts,
    metadata_truthy,
    metadata_value,
    uncovered_asset_accounts,
    visible_columns,
    wrapped_columns,
)


class Balance:
    def __init__(self, positions):
        self._positions = positions

    def get_positions(self):
        return self._positions


class Position:
    def __init__(self, currency):
        self.units = Units(currency)


class RealAccount:
    def __init__(self, positions, children=0):
        self.balance = Balance(positions)
        self._children = children

    def __len__(self):
        return self._children


class Realization:
    def __init__(self, accounts):
        self.accounts = accounts

    def get(self, real_accounts, account_name):
        return self.accounts.get(account_name)


class Units:
    def __init__(self, currency):
        self.currency = currency


class Entry:
    def __init__(self, name, account, meta=None):
        self.account = account
        self.meta = meta or {}
        self.__class__ = type(name, (), {})


class Table:
    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = rows

    def is_empty(self):
        return not self.rows

    def __getitem__(self, column):
        return Column([row.get(column) for row in self.rows])

    def iter_rows(self, named=False):
        if named:
            return iter(self.rows)
        return iter(tuple(row.get(column) for column in self.columns) for row in self.rows)


class Column:
    def __init__(self, values):
        self.values = values

    def to_list(self):
        return self.values


class BeneficiariesTest(unittest.TestCase):
    def test_beneficiary_configs_use_defaults_without_override(self):
        self.assertEqual(
            [config["title"] for config in BENEFICIARY_TABLES],
            [
                "Beneficiaries: Taxable",
                "Beneficiaries: Tax Advantaged",
                "Beneficiaries: Tax Deferred",
                "Beneficiaries: Other",
            ],
        )
        for config in BENEFICIARY_TABLES:
            self.assertNotIn("community_property", config["columns"])
        self.assertEqual(
            BENEFICIARY_EXCLUDED_ACCOUNTS,
            {
                "Assets:Investments:HSA",
                "Assets:Investments:Tax-Deferred",
                "Assets:Investments:Tax-Free",
                "Assets:Investments:Taxable",
            },
        )

    def test_metadata_helpers_match_estate_prefix_and_skip_values(self):
        meta = {"estate_info_beneficiary_primary": "Person A"}
        self.assertEqual(
            metadata_value(meta, "estate_info_", "beneficiary_primary"),
            "Person A",
        )
        self.assertEqual(metadata_value(meta, "estate_info_", "notes"), "")
        self.assertTrue(metadata_truthy("yes"))
        self.assertFalse(metadata_truthy("false"))

    def test_display_account_removes_table_prefix(self):
        config = BENEFICIARY_TABLES[0]
        self.assertEqual(
            account_display_prefix(config),
            "Assets:Investments:Taxable",
        )
        self.assertEqual(
            display_account(
                "Assets:Investments:Taxable:Fidelity:Brokerage",
                config,
            ),
            "Fidelity:Brokerage",
        )

    def test_commodity_leaf_account_uses_declared_commodity(self):
        self.assertTrue(
            commodity_leaf_account(
                "Assets:Investments:Taxable:Fidelity:AAPL",
                {"Assets:Investments:Taxable:Fidelity"},
                None,
                Realization({}),
                {"AAPL"},
            )
        )

    def test_commodity_leaf_account_handles_multiple_lots(self):
        account = "Assets:Investments:Taxable:Fidelity:VTI"
        self.assertTrue(
            commodity_leaf_account(
                account,
                {"Assets:Investments:Taxable:Fidelity"},
                None,
                Realization({account: RealAccount([Position("VTI"), Position("VTI")])}),
                set(),
            )
        )

    def test_included_open_accounts_excludes_closed_accounts(self):
        config = BENEFICIARY_TABLES[0]
        self.assertEqual(
            included_open_accounts(
                [
                    Entry("Open", "Assets:Investments:Taxable"),
                    Entry("Open", "Assets:Investments:Taxable:Closed"),
                    Entry("Close", "Assets:Investments:Taxable:Closed"),
                    Entry("Open", "Assets:Investments:Taxable:Open"),
                ],
                config,
            ),
            {"Assets:Investments:Taxable:Open"},
        )
        self.assertTrue(beneficiary_excluded_account("Assets:Investments:Taxable"))
        self.assertFalse(
            beneficiary_excluded_account("Assets:Investments:Taxable:Open")
        )

    def test_visible_columns_drops_empty_optional_columns(self):
        table = Table(
            ["account", "balance", "todo", "notes", "legal_points"],
            [
                {
                    "account": "A",
                    "balance": 1,
                    "todo": "",
                    "notes": None,
                    "legal_points": "Review",
                }
            ],
        )
        self.assertFalse(column_has_value(table, "todo"))
        self.assertEqual(
            visible_columns(table),
            ["account", "balance", "legal_points"],
        )
        self.assertEqual(
            beneficiary_column_labels(["beneficiary_last_verified", "trusted_contacts"]),
            {
                "beneficiary_last_verified": "Last Verified",
                "trusted_contacts": "Trusted Contacts",
            },
        )
        self.assertEqual(
            wrapped_columns(["Account", "Balance", "Title", "Notes"]),
            ["Notes"],
        )

    def test_beneficiary_table_cell_style_removes_borders(self):
        even_style = beneficiary_table_cell_style("0", "balance", 1)
        odd_style = beneficiary_table_cell_style("1", "balance", 1, {"1"})
        self.assertEqual(even_style["borderLeft"], "0")
        self.assertEqual(even_style["padding"], "0.12rem 0.18rem")
        self.assertEqual(beneficiary_column_width_style("Balance")["width"], "6.5rem")
        self.assertEqual(beneficiary_column_width_style("Account")["minWidth"], "18rem")
        self.assertEqual(beneficiary_column_width_style("Account")["maxWidth"], "none")
        self.assertEqual(beneficiary_column_width_style("Notes")["whiteSpace"], "normal")
        self.assertNotIn("backgroundColor", even_style)
        self.assertEqual(odd_style["backgroundColor"], "#f3d36b")

    def test_beneficiary_highlighted_row_ids_flags_taxable_non_trust_titles(self):
        table = Table(
            ["Title", "Beneficiary Primary", "Beneficiary Contingent"],
            [
                {
                    "Title": "Revocable Trust",
                    "Beneficiary Primary": "",
                    "Beneficiary Contingent": "",
                },
                {
                    "Title": "Individual",
                    "Beneficiary Primary": "Family Trust",
                    "Beneficiary Contingent": "",
                },
                {
                    "Title": "Individual",
                    "Beneficiary Primary": "",
                    "Beneficiary Contingent": "N/A",
                },
                {
                    "Title": "Individual",
                    "Beneficiary Primary": "Person",
                    "Beneficiary Contingent": "",
                },
                {
                    "Title": "",
                    "Beneficiary Primary": "",
                    "Beneficiary Contingent": "",
                },
            ],
        )
        self.assertEqual(
            beneficiary_highlighted_row_ids("Beneficiaries: Taxable", table),
            {"3", "4"},
        )
        self.assertTrue(
            beneficiary_row_has_trust_or_na(
                {"Title": "", "Beneficiary Primary": "Family Trust"}
            )
        )
        self.assertEqual(
            beneficiary_highlighted_row_ids("Beneficiaries: Other", table),
            set(),
        )

    def test_uncovered_asset_accounts_uses_ancestor_coverage(self):
        entries = [
            Entry("Open", "Assets:Investments:Taxable:Fidelity"),
            Entry("Open", "Assets:Investments:Taxable:Fidelity:AAPL"),
            Entry("Open", "Assets:Investments:Taxable"),
            Entry("Open", "Assets:Crypto:Wallet"),
            Entry("Open", "Assets:Banks:Checking"),
            Entry(
                "Open",
                "Assets:Banks:Skipped",
                {"estate_info_beneficiary_skip": "TRUE"},
            ),
            Entry("Open", "Liabilities:Card"),
            Entry("Open", "Assets:Banks:Closed"),
            Entry("Close", "Assets:Banks:Closed"),
        ]
        self.assertTrue(
            account_or_ancestor_included(
                "Assets:Investments:Taxable:Fidelity:AAPL",
                {"Assets:Investments:Taxable:Fidelity"},
            )
        )
        self.assertEqual(
            active_open_asset_accounts(entries),
            {
                "Assets:Investments:Taxable:Fidelity",
                "Assets:Investments:Taxable:Fidelity:AAPL",
                "Assets:Banks:Checking",
            },
        )
        self.assertEqual(
            uncovered_asset_accounts(
                entries,
                {"Assets:Investments:Taxable:Fidelity"},
            ),
            ["Assets:Banks:Checking"],
        )
        self.assertEqual(
            BENEFICIARY_WARNING_ACCOUNT_PATTERN,
            r"^Assets:(Investments|Banks|RealEstate)(:|$)",
        )

    def test_beneficiary_title_summary_sorts_positive_balances_by_title(self):
        tables = [
            {
                "table": Table(
                    ["title", "balance"],
                    [
                        {"title": "Trust", "balance": 25},
                        {"title": "Joint", "balance": 100},
                        {"title": "Trust", "balance": 75},
                        {"title": "", "balance": 10},
                        {"title": "Ignored", "balance": 0},
                    ],
                )
            }
        ]
        self.assertEqual(
            beneficiary_title_summary(tables),
            [
                {"title": "Trust", "balance": 100.0},
                {"title": "Joint", "balance": 100.0},
                {"title": "(missing)", "balance": 10.0},
            ],
        )


if __name__ == "__main__":
    unittest.main()
