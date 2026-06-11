ACCOUNT_TYPE_GROUPS = [
    ("Taxable", ["Assets:Investments:Taxable"]),
    (
        "Tax-Deferred",
        [
            "Assets:Investments:TaxDeferred",
            "Assets:Investments:Tax-Deferred",
            "Assets:Investments:Tax Deferred",
        ],
    ),
    (
        "Tax-Free",
        [
            "Assets:Investments:TaxFree",
            "Assets:Investments:Tax-Free",
            "Assets:Investments:Tax Free",
        ],
    ),
    ("HSA", ["Assets:Investments:HSA"]),
]
OTHER_BROKERAGES = "Other Brokerages"
DEFAULT_BREAKDOWN_CONFIG = {
    "brokerages": [],
}


def build_account_type_table(convert, entries, options, pl, prices, realization):
    price_map = prices.build_price_map(entries)
    real_accounts = realization.realize(entries)
    base_currency = operating_currency(options)

    def inventory_value(inventory):
        if inventory is not None:
            position = inventory.get_only_position()
            if position is not None:
                return float(position.units.number)
        if inventory.is_empty():
            return 0.0
        return None

    def account_market_value(account_name):
        subtree = realization.get(real_accounts, account_name)
        if subtree is None:
            return 0.0
        balance = realization.compute_balance(subtree)
        units_balance = balance.reduce(convert.get_units)
        market_value = units_balance.reduce(
            convert.convert_position, base_currency, price_map
        )
        value = inventory_value(market_value)
        return 0.0 if value is None else value

    rows = []
    for label, accounts in ACCOUNT_TYPE_GROUPS:
        rows.append(
            {
                "type": label,
                "market_value": sum(account_market_value(account) for account in accounts),
            }
        )

    table = pl.DataFrame(rows, schema=["type", "market_value"], orient="row")
    total = table["market_value"].sum()
    return (
        table
        .with_columns(
            (
                pl.when(total == 0)
                .then(0.0)
                .otherwise(pl.col("market_value") / total * 100)
            ).alias("percentage")
        )
        .sort("market_value", descending=True)
    )


def build_brokerage_table(config, convert, entries, options, pl, prices, realization):
    brokerage_names = configured_brokerages(config)
    price_map = prices.build_price_map(entries)
    real_accounts = realization.realize(entries)
    base_currency = operating_currency(options)
    rows_by_brokerage = {
        brokerage_name: 0.0
        for brokerage_name in [*brokerage_names, OTHER_BROKERAGES]
    }

    for real_account in realization.iter_children(real_accounts):
        account_name = real_account.account
        if not account_name.startswith("Assets:Investments:"):
            continue
        if real_account.balance.is_empty():
            continue
        brokerage_name = brokerage_for_account(account_name, brokerage_names)
        rows_by_brokerage[brokerage_name] += inventory_market_value(
            real_account.balance,
            base_currency,
            convert,
            price_map,
        )

    rows = [
        {"brokerage": brokerage_name, "market_value": market_value}
        for brokerage_name, market_value in rows_by_brokerage.items()
    ]
    table = pl.DataFrame(rows, schema=["brokerage", "market_value"], orient="row")
    total = table["market_value"].sum()
    return (
        table
        .with_columns(
            (
                pl.when(total == 0)
                .then(0.0)
                .otherwise(pl.col("market_value") / total * 100)
            ).alias("percentage")
        )
        .sort("market_value", descending=True)
    )


def configured_brokerages(config):
    values = config.get("brokerages", []) if isinstance(config, dict) else []
    return [value for value in values if isinstance(value, str) and value.strip()]


def brokerage_for_account(account_name, brokerage_names):
    account_name_lower = account_name.lower()
    for brokerage_name in brokerage_names:
        if brokerage_name.lower() in account_name_lower:
            return brokerage_name
    return OTHER_BROKERAGES


def inventory_market_value(balance, base_currency, convert, price_map):
    market_value = 0.0
    for position in balance.get_positions():
        converted = convert.convert_position(position, base_currency, price_map)
        amount = getattr(converted, "units", converted)
        if getattr(amount, "currency", None) == base_currency:
            market_value += float(amount.number)
    return market_value


def operating_currency(options):
    currencies = options.get("operating_currency", None) if isinstance(options, dict) else None
    if currencies:
        return list(currencies)[0]
    return "USD"


def table_rows(table, label_column, escape, format_amount):
    rows = []
    for row in table.iter_rows(named=True):
        if (
            row[label_column] == OTHER_BROKERAGES
            and float(row["market_value"] or 0) == 0
        ):
            continue
        rows.append(
            f"""
            <tr>
              <td>{escape(row[label_column])}</td>
              <td class="numeric">{format_amount(row["market_value"])}</td>
              <td class="numeric">{row["percentage"]:.0f}%</td>
            </tr>
            """
        )
    return "".join(rows)


def table_total_row(table, label, amount_column, format_amount):
    total = table[amount_column].sum() if not table.is_empty() else 0
    percentage = "100%" if total else "0%"
    return f"""
    <tr>
      <td>{label}</td>
      <td class="numeric">{format_amount(total)}</td>
      <td class="numeric">{percentage}</td>
    </tr>
    """


def build_account_types_view(
    account_type_table,
    brokerage_table,
    common_table_section_styles,
    escape,
    format_amount,
    mo,
):
    account_type_rows = table_rows(account_type_table, "type", escape, format_amount)
    brokerage_rows = table_rows(brokerage_table, "brokerage", escape, format_amount)
    account_type_total_row = table_total_row(
        account_type_table,
        "Total",
        "market_value",
        format_amount,
    )
    brokerage_total_row = table_total_row(
        brokerage_table,
        "Total",
        "market_value",
        format_amount,
    )

    return mo.vstack(
        [
            mo.md("# Breakdown"),
            mo.Html(
                f"""
                <style>
                {common_table_section_styles}
                .investment-summary-section {{
                  margin-bottom: 1.5rem;
                }}
                .investment-summary-table {{
                  border-collapse: collapse;
                  font-size: 0.95rem;
                  line-height: 1.35;
                  width: fit-content;
                  max-width: 100%;
                }}
                .investment-summary-table th,
                .investment-summary-table td {{
                  border-bottom: 1px solid rgba(128, 128, 128, 0.18);
                  padding: 0.35rem 0.75rem;
                  white-space: nowrap;
                }}
                .investment-summary-table th {{
                  font-weight: 600;
                  text-align: left;
                }}
                .investment-summary-table .numeric {{
                  text-align: right;
                }}
                .investment-summary-table tfoot td {{
                  font-weight: 600;
                }}
                </style>
                <div class="investment-summary-section foresight-table-section">
                  <h2>Tax Treatment</h2>
                  <table class="investment-summary-table">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th class="numeric">Amount</th>
                        <th class="numeric">Percent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {account_type_rows}
                    </tbody>
                    <tfoot>
                      {account_type_total_row}
                    </tfoot>
                  </table>
                </div>
                <div class="investment-summary-section foresight-table-section">
                  <h2>Brokerages</h2>
                  <table class="investment-summary-table">
                    <thead>
                      <tr>
                        <th>Brokerage</th>
                        <th class="numeric">Amount</th>
                        <th class="numeric">Percent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {brokerage_rows}
                    </tbody>
                    <tfoot>
                      {brokerage_total_row}
                    </tfoot>
                  </table>
                </div>
                """
            ),
        ]
    )
