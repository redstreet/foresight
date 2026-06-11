import unittest
from collections import defaultdict
from datetime import date
from decimal import Decimal

from beancount.core.amount import Amount
from beancount.core.data import Posting, Transaction
from beancount.core.inventory import Inventory

from modules.investments.growth import (
    DEFAULT_GROWTH_CONFIG,
    audit_total,
    build_growth_data,
    build_growth_detail_table,
    cumulative_growth_rows,
    default_growth_start_date,
    match_pending_dividend,
    month_starts,
    process_growth_transaction,
    selectable_growth_accounts,
)


class Entry:
    def __init__(self, name, account=None, entry_date=None):
        self.account = account
        self.date = entry_date
        self.__class__ = type(name, (), {})


class Convert:
    def convert_amount(self, amount, currency, price_map, date=None):
        return amount

    def convert_position(self, position, currency, price_map, date=None):
        return position


class Prices:
    def build_price_map(self, entries):
        return {}


class Polars:
    def DataFrame(self, rows, schema, orient="row"):
        return Table(rows, schema)


class Table:
    def __init__(self, rows, columns):
        self.rows = rows
        self.columns = columns

    def to_dicts(self):
        return self.rows


def txn(entry_date, postings):
    return Transaction(
        {},
        entry_date,
        "*",
        None,
        "",
        frozenset(),
        frozenset(),
        postings,
    )


def posting(account, number, currency="USD"):
    return Posting(
        account,
        Amount(Decimal(str(number)), currency),
        None,
        None,
        None,
        None,
    )


class GrowthTest(unittest.TestCase):
    def test_selectable_growth_accounts_uses_open_and_historical_accounts(self):
        entries = [
            Entry("Open", "Assets:Investments:Taxable", date(2024, 1, 1)),
            Entry("Open", "Assets:Banks:Checking", date(2024, 1, 1)),
            txn(
                date(2024, 1, 2),
                [
                    posting("Assets:Investments:Taxable:Brokerage", 10),
                    posting("Equity:Opening-Balances", -10),
                ],
            ),
        ]

        self.assertEqual(
            selectable_growth_accounts(entries, DEFAULT_GROWTH_CONFIG),
            [
                "Assets:Investments:Taxable",
                "Assets:Investments:Taxable:Brokerage",
            ],
        )

    def test_process_growth_transaction_classifies_external_contribution(self):
        audit_rows = []

        process_growth_transaction(
            txn(
                date(2024, 1, 2),
                [
                    posting("Assets:Investments:Taxable:Brokerage", 100),
                    posting("Assets:Banks:Checking", -100),
                ],
            ),
            "Assets:Investments:Taxable",
            DEFAULT_GROWTH_CONFIG,
            "USD",
            Convert(),
            {},
            Inventory(),
            defaultdict(list),
            audit_rows,
            [],
        )

        self.assertEqual(audit_rows[0]["component"], "contributions")
        self.assertEqual(audit_rows[0]["amount"], 100.0)
        self.assertEqual(audit_rows[0]["reason"], "external_transfer")

    def test_process_growth_transaction_classifies_same_transaction_dividend(self):
        audit_rows = []

        process_growth_transaction(
            txn(
                date(2024, 1, 2),
                [
                    posting("Assets:Investments:Taxable:Brokerage", 12),
                    posting("Income:Dividends:Brokerage", -12),
                ],
            ),
            "Assets:Investments:Taxable",
            DEFAULT_GROWTH_CONFIG,
            "USD",
            Convert(),
            {},
            Inventory(),
            defaultdict(list),
            audit_rows,
            [],
        )

        self.assertEqual(audit_rows[0]["component"], "dividends")
        self.assertEqual(audit_rows[0]["amount"], 12.0)
        self.assertEqual(audit_rows[0]["reason"], "same_transaction_dividend")

    def test_match_pending_dividend_uses_configured_tolerance(self):
        pending = [Decimal("100")]

        self.assertEqual(
            match_pending_dividend(pending, Decimal("100.50"), Decimal("0.01")),
            Decimal("100"),
        )
        self.assertEqual(pending, [])

    def test_default_growth_date_range_starts_two_years_back(self):
        self.assertEqual(default_growth_start_date(date(2026, 6, 10)), date(2024, 1, 1))
        self.assertEqual(
            month_starts(date(2024, 1, 15), date(2024, 3, 2)),
            [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)],
        )

    def test_cumulative_growth_rows_stack_to_market_value(self):
        rows = cumulative_growth_rows(
            [
                {
                    "month": date(2024, 1, 1),
                    "ending_value": 110,
                    "contributions": 100,
                    "dividends": 5,
                },
                {
                    "month": date(2024, 2, 1),
                    "ending_value": 130,
                    "contributions": 10,
                    "dividends": 2,
                },
            ]
        )

        self.assertEqual(rows[1]["cumulative_contributions"], 110.0)
        self.assertEqual(rows[1]["cumulative_dividends"], 7.0)
        self.assertEqual(rows[1]["cumulative_dividends_line"], 117.0)
        self.assertEqual(rows[1]["market_value"], 130.0)
        self.assertEqual(rows[1]["appreciation_residual"], 13.0)

    def test_audit_total_includes_pre_start_history_for_cumulative_basis(self):
        audit_rows = [
            {
                "date": date(2020, 1, 1),
                "month": date(2020, 1, 1),
                "component": "contributions",
                "amount": 100.0,
            },
            {
                "date": date(2024, 2, 1),
                "month": date(2024, 2, 1),
                "component": "contributions",
                "amount": 25.0,
            },
        ]

        self.assertEqual(
            audit_total(
                audit_rows,
                "contributions",
                None,
                end_date=date(2024, 2, 29),
            ),
            Decimal("125.0"),
        )
        self.assertEqual(
            audit_total(audit_rows, "contributions", date(2024, 2, 1)),
            Decimal("25.0"),
        )

    def test_build_growth_detail_table_filters_month_and_component(self):
        table = build_growth_detail_table(
            {
                "audit_rows": [
                    {
                        "month": date(2024, 1, 1),
                        "component": "contributions",
                        "amount": 100.0,
                        "date": date(2024, 1, 2),
                        "reason": "external_transfer",
                        "payee": "",
                        "narration": "",
                        "selected_postings": "",
                        "other_accounts": "",
                    },
                    {
                        "month": date(2024, 1, 1),
                        "component": "dividends",
                        "amount": 5.0,
                        "date": date(2024, 1, 3),
                        "reason": "same_transaction_dividend",
                        "payee": "",
                        "narration": "",
                        "selected_postings": "",
                        "other_accounts": "",
                    },
                ]
            },
            "2024-01",
            "dividends",
            Polars(),
        )

        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0]["reason"], "same_transaction_dividend")

    def test_build_growth_data_carries_pre_start_contributions_forward(self):
        data = build_growth_data(
            {
                **DEFAULT_GROWTH_CONFIG,
                "start_date": date(2024, 1, 1),
                "end_date": date(2024, 1, 31),
            },
            "Assets:Investments:Taxable",
            Convert(),
            [
                txn(
                    date(2020, 1, 1),
                    [
                        posting("Assets:Investments:Taxable", 100),
                        posting("Assets:Banks:Checking", -100),
                    ],
                )
            ],
            {},
            Polars(),
            Prices(),
        )

        row = data["table"].rows[0]
        self.assertEqual(row["contributions"], 0.0)
        self.assertEqual(row["cumulative_contributions"], 100.0)
        self.assertEqual(row["ending_value"], 100.0)


if __name__ == "__main__":
    unittest.main()
