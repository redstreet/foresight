from datetime import date
from decimal import Decimal

from dateutil import relativedelta


DEFAULT_GAINS_MINIMIZER_CONFIG = {
    "accounts_pattern": "Assets:Investments:Taxable",
    "account_field": "parent",
    "currency": "USD",
    "st_tax_rate": 30.0,
    "lt_tax_rate": 15.0,
}


ACCOUNT_FIELD_OPTIONS = {
    "Full account": "account",
    "Leaf account": "LEAF(account)",
    "Parent account": 'GREPN("(.*):([^:]*):", account, 2)',
}


ACCOUNT_FIELD_ALIASES = {
    "full": "Full account",
    "leaf": "Leaf account",
    "parent": "Parent account",
}


def build_gains_minimizer_config(
    accounts_pattern,
    account_field,
    currency,
    st_tax_rate,
    lt_tax_rate,
):
    return {
        "accounts_pattern": (
            accounts_pattern or DEFAULT_GAINS_MINIMIZER_CONFIG["accounts_pattern"]
        ),
        "account_field": account_field_expression(account_field),
        "currency": normalize_currency(currency),
        "st_tax_rate": tax_percent_to_rate(st_tax_rate, "st_tax_rate"),
        "lt_tax_rate": tax_percent_to_rate(lt_tax_rate, "lt_tax_rate"),
    }


def normalize_currency(currency):
    value = str(currency or DEFAULT_GAINS_MINIMIZER_CONFIG["currency"]).strip()
    return value.upper() or DEFAULT_GAINS_MINIMIZER_CONFIG["currency"]


def account_field_expression(account_field):
    label = ACCOUNT_FIELD_ALIASES.get(
        str(account_field or "").strip().lower(),
        account_field,
    )
    return ACCOUNT_FIELD_OPTIONS.get(label, ACCOUNT_FIELD_OPTIONS["Parent account"])


def account_field_label(account_field):
    value = str(account_field or "").strip().lower()
    if value in ACCOUNT_FIELD_ALIASES:
        return ACCOUNT_FIELD_ALIASES[value]
    if account_field in ACCOUNT_FIELD_OPTIONS:
        return account_field
    return "Parent account"


def tax_percent_to_rate(value, default_key):
    percent_value = (
        value if value is not None else DEFAULT_GAINS_MINIMIZER_CONFIG[default_key]
    )
    return Decimal(str(percent_value)) / Decimal("100")


def build_gains_minimizer_table(
    config,
    entries,
    options,
    pl,
    run_bql_query,
):
    lots = build_gains_minimizer_lots(config, entries, options, run_bql_query)
    return build_gains_minimizer_table_from_lots(config, lots, pl)


def build_gains_minimizer_lots(config, entries, options, run_bql_query):
    return taxable_lots(config, config["currency"], entries, options, run_bql_query)


def build_gains_minimizer_table_from_lots(config, lots, pl):
    rows = []
    cumulative_proceeds = Decimal("0")
    cumulative_taxes = Decimal("0")
    cumulative_gains = Decimal("0")
    previous_proceeds = Decimal("0")
    previous_taxes = Decimal("0")

    for lot in sorted(lots, key=lambda row: row["est_tax_percent"]):
        market_value = lot["market_value"]
        if market_value == 0:
            continue
        cumulative_proceeds += market_value
        cumulative_taxes += lot["est_tax"]
        cumulative_gains += lot["gain"]
        tax_avg = percent(cumulative_taxes, cumulative_proceeds)
        tax_marg = percent(
            cumulative_taxes - previous_taxes,
            cumulative_proceeds - previous_proceeds,
        )
        rows.append(
            {
                "cumu_proceeds": float(round(cumulative_proceeds, 0)),
                "cumu_taxes": float(round(cumulative_taxes, 0)),
                "tax_avg": float(round(tax_avg, 1)),
                "tax_marg": float(round(tax_marg, 2)),
                "account": lot["account"],
                "units": float(lot["units"]),
                "ticker": lot["ticker"],
                "market_value": float(lot["market_value"]),
                "acq_date": lot["acq_date"],
                "term": lot["term"],
                "gain": float(lot["gain"]),
                "cumu_gains": float(round(cumulative_gains, 0)),
            }
        )
        previous_proceeds = cumulative_proceeds
        previous_taxes = cumulative_taxes

    return pl.DataFrame(
        rows,
        schema=[
            "cumu_proceeds",
            "cumu_taxes",
            "tax_avg",
            "tax_marg",
            "account",
            "units",
            "ticker",
            "market_value",
            "acq_date",
            "term",
            "gain",
            "cumu_gains",
        ],
        orient="row",
    )


def build_gains_minimizer_warnings(config, lots):
    currency = config["currency"]
    warnings = []
    for lot in lots:
        for field in ("market_value_currency", "basis_currency"):
            row_currency = lot.get(field)
            if row_currency and row_currency != currency:
                warnings.append(
                    f"{lot['account']} {lot['ticker']} {lot['acq_date']} "
                    f"has {field.removesuffix('_currency').replace('_', ' ')} "
                    f"in {row_currency}, expected {currency}."
                )
    return unique_preserve_order(warnings)


def taxable_lots(config, currency, entries, options, run_bql_query):
    query = gains_minimizer_query(config, currency)
    cols, rows = run_bql_query(entries, options, query, numberify=False)
    column_names = [col.name for col in cols]
    lots = []
    tax_rates = {
        "Short": Decimal(config["st_tax_rate"]),
        "Long": Decimal(config["lt_tax_rate"]),
    }
    today = date.today()

    for raw_row in rows:
        row = result_row_dict(column_names, raw_row)
        market_value, market_value_currency = inventory_value_and_currency(
            row.get("market_value")
        )
        basis, basis_currency = inventory_value_and_currency(row.get("basis"))
        units, ticker = split_inventory(row.get("units"))
        if market_value is None or basis is None or units is None:
            continue
        gain = market_value - basis
        term = gain_term(row.get("acq_date"), today)
        est_tax = gain * tax_rates[term]
        lots.append(
            {
                "account": row.get("account"),
                "units": units,
                "ticker": ticker,
                "market_value": market_value,
                "market_value_currency": market_value_currency,
                "acq_date": row.get("acq_date"),
                "term": term,
                "gain": gain,
                "basis_currency": basis_currency,
                "est_tax": est_tax,
                "est_tax_percent": percent(est_tax, market_value),
            }
        )

    return lots


def result_row_dict(column_names, row):
    if isinstance(row, dict):
        return row
    if hasattr(row, "_asdict"):
        return row._asdict()
    if isinstance(row, (list, tuple)):
        return {
            column_name: row[index] if index < len(row) else None
            for index, column_name in enumerate(column_names)
        }
    return {column_name: getattr(row, column_name) for column_name in column_names}


def gains_minimizer_query(config, currency):
    accounts_pattern = sql_string(config["accounts_pattern"])
    account_field = config["account_field"]
    currency = sql_string(currency)
    return f"""
    SELECT
        {account_field} as account,
        units(sum(position)) as units,
        CONVERT(value(sum(position)), '{currency}') as market_value,
        cost_date as acq_date,
        CONVERT(cost(sum(position)), '{currency}') as basis
      WHERE account_sortkey(account) ~ "^[01]" AND
        account ~ '{accounts_pattern}'
      GROUP BY
        {account_field},
        cost_date,
        currency,
        cost_currency,
        cost_number,
        account_sortkey(account)
      ORDER BY account_sortkey(account), currency, cost_date
    """


def sql_string(value):
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def inventory_value(inventory):
    value, _ = inventory_value_and_currency(inventory)
    return value


def inventory_value_and_currency(inventory):
    if inventory is None:
        return None, None
    position = inventory.get_only_position()
    if position is not None:
        return Decimal(position.units.number), position.units.currency
    if inventory.is_empty():
        return Decimal("0"), None
    return None, None


def split_inventory(inventory):
    position = inventory.get_only_position() if inventory is not None else None
    if position is None:
        return None, None
    return Decimal(position.units.number), position.units.currency


def gain_term(acquired, sold):
    if acquired is None:
        return "Short"
    diff = relativedelta.relativedelta(sold, acquired)
    if diff.years > 1 or (diff.years == 1 and (diff.months >= 1 or diff.days >= 1)):
        return "Long"
    return "Short"


def percent(numerator, denominator):
    if denominator == 0:
        return Decimal("0")
    return numerator / denominator * Decimal("100")


def unique_preserve_order(values):
    seen = set()
    unique_values = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def warning_view(warnings, mo):
    if not warnings:
        return mo.md("")
    items = "\n".join(f"- {warning}" for warning in warnings)
    return mo.md(f"**Currency warnings**\n\n{items}")


def build_gains_minimizer_view(
    config_controls,
    gains_minimizer_table,
    gains_minimizer_warnings,
    format_amount,
    mo,
):
    return mo.vstack(
        [
            mo.md("# Gains Minimizer"),
            mo.hstack(config_controls, align="end", justify="start", gap=1),
            warning_view(gains_minimizer_warnings, mo),
            mo.ui.table(
                gains_minimizer_table.rename(gains_minimizer_column_labels()),
                pagination=False,
                selection=None,
                show_column_summaries=False,
                show_data_types=False,
                format_mapping={
                    "Cumu Proceeds": format_amount,
                    "Cumu Taxes": format_amount,
                    "Market Value": format_amount,
                    "Gain": format_amount,
                    "Cumu Gains": format_amount,
                    "Tax Avg": lambda value: f"{value:.0f}%",
                    "Tax Marg": lambda value: f"{value:.0f}%",
                },
                text_justify_columns={
                    "Cumu Proceeds": "right",
                    "Cumu Taxes": "right",
                    "Tax Avg": "right",
                    "Tax Marg": "right",
                    "Units": "right",
                    "Market Value": "right",
                    "Gain": "right",
                    "Cumu Gains": "right",
                },
                show_download=True,
                max_columns=None,
            ),
        ]
    )


def gains_minimizer_column_labels():
    return {
        "cumu_proceeds": "Cumu Proceeds",
        "cumu_taxes": "Cumu Taxes",
        "tax_avg": "Tax Avg",
        "tax_marg": "Tax Marg",
        "account": "Account",
        "units": "Units",
        "ticker": "Ticker",
        "market_value": "Market Value",
        "acq_date": "Acq Date",
        "term": "Term",
        "gain": "Gain",
        "cumu_gains": "Cumu Gains",
    }
