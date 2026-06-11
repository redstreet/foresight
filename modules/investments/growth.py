from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import re

from beancount.core.inventory import Inventory


DEFAULT_GROWTH_CONFIG = {
    "accounts_pattern": "^Assets:Investments",
    "currency": "USD",
    "dividend_income_pattern": "^Income:.*Dividend",
    "frequency": "monthly",
    "reinvestment_match_tolerance": 0.01,
    "start_date": None,
    "end_date": None,
}


def normalize_growth_config(config):
    normalized = {**DEFAULT_GROWTH_CONFIG, **(config or {})}
    normalized["currency"] = str(normalized.get("currency") or "USD").strip().upper()
    normalized["reinvestment_match_tolerance"] = Decimal(
        str(normalized.get("reinvestment_match_tolerance") or 0)
    )
    normalized["start_date"] = parse_date(normalized.get("start_date"))
    normalized["end_date"] = parse_date(normalized.get("end_date"))
    return normalized


def default_growth_start_date(today):
    return date(today.year - 2, 1, 1)


def parse_date(value):
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def selectable_growth_accounts(entries, config):
    normalized = normalize_growth_config(config)
    pattern = normalized["accounts_pattern"]
    accounts = set()
    closed_accounts = {
        entry.account
        for entry in entries
        if entry.__class__.__name__ == "Close"
    }
    for entry in entries:
        if entry.__class__.__name__ == "Open":
            if entry.account not in closed_accounts and re.search(
                pattern,
                entry.account,
            ):
                accounts.add(entry.account)
            continue
        if entry.__class__.__name__ != "Transaction":
            continue
        for posting in entry.postings:
            if re.search(pattern, posting.account):
                accounts.add(posting.account)
    return sorted(accounts)


def build_growth_data(
    config,
    selected_account,
    convert,
    entries,
    options,
    pl,
    prices,
):
    normalized = normalize_growth_config(config)
    price_map = prices.build_price_map(entries)
    currency = normalized["currency"]
    start_date = normalized["start_date"] or default_growth_start_date(date.today())
    end_date = normalized["end_date"] or date.today()
    transactions = [
        entry for entry in entries if entry.__class__.__name__ == "Transaction"
    ]
    transactions.sort(key=lambda entry: entry.date)

    warnings = []
    inventory = Inventory()
    month_end_values = {}
    months = month_starts(start_date, end_date)
    pending_dividends_by_date = defaultdict(list)
    audit_rows = []
    transaction_index = process_transactions_before_start(
        transactions,
        selected_account,
        normalized,
        currency,
        convert,
        price_map,
        inventory,
        pending_dividends_by_date,
        audit_rows,
        warnings,
        start_date,
    )
    previous_value = inventory_market_value(
        inventory,
        currency,
        convert,
        price_map,
        start_date - timedelta(days=1),
        warnings,
    )

    for current_month in months:
        month_end = min(end_of_month(current_month), end_date)
        while transaction_index < len(transactions):
            txn = transactions[transaction_index]
            if txn.date > month_end:
                break
            process_growth_transaction(
                txn,
                selected_account,
                normalized,
                currency,
                convert,
                price_map,
                inventory,
                pending_dividends_by_date,
                audit_rows,
                warnings,
            )
            transaction_index += 1
        month_end_values[current_month] = inventory_market_value(
            inventory,
            currency,
            convert,
            price_map,
            month_end,
            warnings,
        )

    rows = []
    for current_month in months:
        month_end = min(end_of_month(current_month), end_date)
        ending_value = month_end_values.get(current_month, Decimal("0"))
        contributions = audit_total(audit_rows, "contributions", current_month)
        dividends = audit_total(audit_rows, "dividends", current_month)
        total_growth = ending_value - previous_value
        appreciation = total_growth - contributions - dividends
        audit_rows.append(
            audit_row(
                month_end,
                "appreciation",
                appreciation,
                "market_value_residual",
                None,
                [],
                selected_account,
                currency,
            )
        )
        cumulative_contributions = audit_total(
            audit_rows,
            "contributions",
            None,
            end_date=month_end,
        )
        cumulative_dividends = audit_total(
            audit_rows,
            "dividends",
            None,
            end_date=month_end,
        )
        rows.append(
            {
                "month": current_month,
                "ending_value": float(round(ending_value, 0)),
                "contributions": float(round(contributions, 0)),
                "dividends": float(round(dividends, 0)),
                "appreciation": float(round(appreciation, 0)),
                "total_growth": float(round(total_growth, 0)),
                "cumulative_contributions": float(round(cumulative_contributions, 0)),
                "cumulative_dividends": float(round(cumulative_dividends, 0)),
            }
        )
        previous_value = ending_value

    return {
        "table": pl.DataFrame(
            rows,
            schema=[
                "month",
                "ending_value",
                "contributions",
                "dividends",
                "appreciation",
                "total_growth",
                "cumulative_contributions",
                "cumulative_dividends",
            ],
            orient="row",
        ),
        "audit_table": pl.DataFrame(
            audit_rows,
            schema=[
                "month",
                "component",
                "amount",
                "date",
                "reason",
                "payee",
                "narration",
                "selected_postings",
                "other_accounts",
            ],
            orient="row",
        ),
        "audit_rows": audit_rows,
        "warnings": unique_preserve_order(warnings),
    }


def process_growth_transaction(
    txn,
    selected_account,
    config,
    currency,
    convert,
    price_map,
    inventory,
    pending_dividends_by_date,
    audit_rows,
    warnings,
):
    selected_postings = [
        posting
        for posting in txn.postings
        if account_in_subtree(posting.account, selected_account)
    ]
    if not selected_postings:
        external_dividend = collect_external_dividend(
            txn, config, currency, convert, price_map, warnings
        )
        if external_dividend > 0:
            pending_dividends_by_date[txn.date].append(external_dividend)
        return

    for posting in selected_postings:
        inventory.add_position(posting)

    selected_value = sum(
        posting_value(posting, currency, convert, price_map, txn.date, warnings)
        for posting in selected_postings
    )
    dividend_value = dividend_income_value(
        txn,
        config,
        currency,
        convert,
        price_map,
        warnings,
    )
    if dividend_value > 0:
        audit_rows.append(
            audit_row(
                txn.date,
                "dividends",
                dividend_value,
                "same_transaction_dividend",
                txn,
                selected_postings,
                selected_account,
                currency,
            )
        )
        pending_dividends_by_date[txn.date].append(dividend_value)

    contribution = selected_value - dividend_value
    if contribution > 0:
        matched_dividend = None
        if dividend_value == 0:
            matched_dividend = match_pending_dividend(
                pending_dividends_by_date[txn.date],
                contribution,
                config["reinvestment_match_tolerance"],
            )
        if matched_dividend is not None:
            audit_rows.append(
                audit_row(
                    txn.date,
                    "dividends",
                    contribution,
                    "matched_reinvestment",
                    txn,
                    selected_postings,
                    selected_account,
                    currency,
                )
            )
        else:
            audit_rows.append(
                audit_row(
                    txn.date,
                    "contributions",
                    contribution,
                    "external_transfer",
                    txn,
                    selected_postings,
                    selected_account,
                    currency,
                )
            )


def collect_external_dividend(txn, config, currency, convert, price_map, warnings):
    dividend_value = dividend_income_value(
        txn,
        config,
        currency,
        convert,
        price_map,
        warnings,
    )
    return dividend_value


def dividend_income_value(txn, config, currency, convert, price_map, warnings):
    total = Decimal("0")
    for posting in txn.postings:
        if not re.search(config["dividend_income_pattern"], posting.account):
            continue
        value = posting_value(posting, currency, convert, price_map, txn.date, warnings)
        if value < 0:
            total += -value
    return total


def match_pending_dividend(pending_values, contribution, tolerance):
    for index, dividend_value in enumerate(pending_values):
        denominator = max(abs(dividend_value), Decimal("1"))
        if abs(dividend_value - contribution) / denominator <= tolerance:
            return pending_values.pop(index)
    return None


def account_in_subtree(account_name, selected_account):
    return account_name == selected_account or account_name.startswith(
        f"{selected_account}:"
    )


def process_transactions_before_start(
    transactions,
    selected_account,
    config,
    currency,
    convert,
    price_map,
    inventory,
    pending_dividends_by_date,
    audit_rows,
    warnings,
    start_date,
):
    transaction_index = 0
    while transaction_index < len(transactions):
        txn = transactions[transaction_index]
        if txn.date >= start_date:
            break
        process_growth_transaction(
            txn,
            selected_account,
            config,
            currency,
            convert,
            price_map,
            inventory,
            pending_dividends_by_date,
            audit_rows,
            warnings,
        )
        transaction_index += 1
    return transaction_index


def audit_row(
    row_date,
    component,
    amount,
    reason,
    txn,
    selected_postings,
    selected_account,
    currency,
):
    selected_postings = selected_postings or []
    all_postings = getattr(txn, "postings", []) if txn is not None else []
    other_accounts = sorted(
        {
            posting.account
            for posting in all_postings
            if not account_in_subtree(posting.account, selected_account)
        }
    )
    return {
        "month": month_start(row_date),
        "component": component,
        "amount": float(round(Decimal(amount), 0)),
        "date": row_date,
        "reason": reason,
        "payee": getattr(txn, "payee", "") or "",
        "narration": getattr(txn, "narration", "") if txn is not None else "",
        "selected_postings": posting_summary(selected_postings),
        "other_accounts": ", ".join(other_accounts),
    }


def posting_summary(postings):
    parts = []
    for posting in postings:
        units = getattr(posting, "units", None)
        if units is None:
            amount_text = ""
        else:
            amount_text = f"{units.number} {units.currency}"
        parts.append(f"{posting.account} {amount_text}".strip())
    return "; ".join(parts)


def audit_total(audit_rows, component, month, end_date=None):
    total = Decimal("0")
    for row in audit_rows:
        if row["component"] != component:
            continue
        if month is not None and row["month"] != month:
            continue
        if end_date is not None and row["date"] > end_date:
            continue
        total += Decimal(str(row["amount"]))
    return total


def month_starts(start_date, end_date):
    if start_date is None or end_date is None or start_date > end_date:
        return []
    current = month_start(start_date)
    last = month_start(end_date)
    months = []
    while current <= last:
        months.append(current)
        current = next_month(current)
    return months


def month_start(value):
    return date(value.year, value.month, 1)


def next_month(value):
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def end_of_month(value):
    return next_month(value) - timedelta(days=1)


def posting_value(posting, currency, convert, price_map, value_date, warnings):
    units = getattr(posting, "units", None)
    if units is None:
        return Decimal("0")
    if units.currency == currency:
        return Decimal(units.number)
    cost = getattr(posting, "cost", None)
    if cost is not None and cost.number is not None:
        amount = Decimal(units.number) * Decimal(cost.number)
        if cost.currency == currency:
            return amount
    converted = converted_amount(units, currency, convert, price_map, value_date)
    if converted is not None:
        return Decimal(converted.number)
    warnings.append(f"Unable to convert {units} to {currency} on {value_date}.")
    return Decimal("0")


def inventory_market_value(inventory, currency, convert, price_map, value_date, warnings):
    total = Decimal("0")
    for position in inventory.get_positions():
        converted = converted_position(position, currency, convert, price_map, value_date)
        amount = getattr(converted, "units", converted)
        if getattr(amount, "currency", None) == currency:
            total += Decimal(amount.number)
        else:
            warnings.append(f"Unable to value {position} in {currency} on {value_date}.")
    return total


def converted_amount(amount, currency, convert, price_map, value_date):
    try:
        converted = convert.convert_amount(
            amount,
            currency,
            price_map,
            date=value_date,
        )
    except TypeError:
        converted = convert.convert_amount(amount, currency, price_map)
    return converted if getattr(converted, "currency", None) == currency else None


def converted_position(position, currency, convert, price_map, value_date):
    try:
        return convert.convert_position(position, currency, price_map, date=value_date)
    except TypeError:
        return convert.convert_position(position, currency, price_map)


def unique_preserve_order(values):
    seen = set()
    unique_values = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def build_growth_view(
    account_selector,
    account_pattern_control,
    currency_control,
    start_date_control,
    end_date_control,
    month_selector,
    component_selector,
    growth_data,
    growth_detail_table,
    escape,
    format_amount,
    mo,
):
    table = growth_data["table"]
    warnings = growth_data["warnings"]
    return mo.vstack(
        [
            mo.md("# Growth"),
            mo.hstack(
                [
                    mo.vstack(
                        [mo.md("**Selected account (graphed)**"), account_selector],
                        gap=0.15,
                    ),
                    mo.vstack(
                        [mo.md("**Account regex (eligible accounts)**"), account_pattern_control],
                        gap=0.15,
                    ),
                    mo.vstack([mo.md("**Currency**"), currency_control], gap=0.15),
                    mo.vstack([mo.md("**Start date**"), start_date_control], gap=0.15),
                    mo.vstack([mo.md("**End date**"), end_date_control], gap=0.15),
                ],
                align="end",
                justify="start",
                gap=1,
            ),
            warning_view(warnings, mo),
            mo.Html(build_growth_chart(table, escape, format_amount)),
            mo.ui.table(
                table.rename(growth_column_labels()),
                pagination=False,
                selection=None,
                show_column_summaries=False,
                show_data_types=False,
                format_mapping={
                    "Ending Value": format_amount,
                    "Contributions": format_amount,
                    "Dividends": format_amount,
                    "Appreciation": format_amount,
                    "Total Growth": format_amount,
                    "Cumulative Contributions": format_amount,
                    "Cumulative Dividends": format_amount,
                },
            ),
            mo.md("## Drilldown"),
            mo.hstack(
                [
                    mo.vstack([mo.md("**Month**"), month_selector], gap=0.15),
                    mo.vstack([mo.md("**Component**"), component_selector], gap=0.15),
                ],
                align="end",
                justify="start",
                gap=1,
            ),
            mo.ui.table(
                growth_detail_table.rename(growth_detail_column_labels()),
                pagination=False,
                selection=None,
                show_column_summaries=False,
                show_data_types=False,
                format_mapping={"Amount": format_amount},
            ),
        ]
    )


def warning_view(warnings, mo):
    if not warnings:
        return mo.md("")
    items = "\n".join(f"- {warning}" for warning in warnings)
    return mo.md(f"**Growth warnings**\n\n{items}")


def build_growth_chart(table, escape, format_amount):
    rows = cumulative_growth_rows(table.to_dicts() if hasattr(table, "to_dicts") else [])
    if not rows:
        return "<div>No growth data.</div>"
    width = max(720, len(rows) * 28)
    height = 320
    padding_left = 56
    padding_bottom = 34
    padding_top = 18
    plot_width = width - padding_left - 16
    plot_height = height - padding_top - padding_bottom
    values = (
        [
            float(row[column] or 0)
            for row in rows
            for column in (
                "cumulative_contributions",
                "cumulative_dividends_line",
                "market_value",
                "zero",
            )
        ]
        or [1]
    )
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        max_value += 1
        min_value -= 1

    def x_for_index(index):
        if len(rows) == 1:
            return padding_left + plot_width / 2
        return padding_left + index * plot_width / (len(rows) - 1)

    def y_for_value(value):
        return padding_top + (max_value - value) / (max_value - min_value) * plot_height

    zero_y = y_for_value(0)
    contribution_points = [
        (x_for_index(index), y_for_value(row["cumulative_contributions"]))
        for index, row in enumerate(rows)
    ]
    dividend_points = [
        (x_for_index(index), y_for_value(row["cumulative_dividends_line"]))
        for index, row in enumerate(rows)
    ]
    market_points = [
        (x_for_index(index), y_for_value(row["market_value"]))
        for index, row in enumerate(rows)
    ]
    zero_points = [(x_for_index(index), zero_y) for index, _ in enumerate(rows)]
    colors = {
        "contributions": "#4f7cac",
        "dividends": "#58a55c",
        "appreciation": "#d18f32",
        "market_value": "#222222",
    }
    labels = []
    tooltips = []
    label_every = max(1, len(rows) // 8)
    for index, row in enumerate(rows):
        x = x_for_index(index)
        if index % label_every == 0 or index == len(rows) - 1:
            labels.append(
                f'<text x="{x:.1f}" y="{height - 12}" font-size="10" '
                f'text-anchor="middle">{escape(str(row["month"])[:7])}</text>'
            )
        tooltips.append(
            f'<circle cx="{x:.1f}" cy="{y_for_value(row["market_value"]):.1f}" '
            f'r="3" fill="{colors["market_value"]}">'
            f'<title>{escape(str(row["month"])[:7])}: '
            f'Market value {format_amount(row["market_value"])}, '
            f'Contributions {format_amount(row["cumulative_contributions"])}, '
            f'Dividends {format_amount(row["cumulative_dividends"])}, '
            f'Appreciation {format_amount(row["appreciation_residual"])}</title>'
            "</circle>"
        )
    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:0.25rem;'
        f'margin-right:1rem;">'
        f'<span style="width:0.75rem;height:0.75rem;background:{color};display:inline-block;"></span>'
        f'{escape(label)}</span>'
        for label, color in [
            ("Contributions", colors["contributions"]),
            ("Dividends", colors["dividends"]),
            ("Appreciation", colors["appreciation"]),
            ("Market Value", colors["market_value"]),
        ]
    )
    return f"""
    <div style="overflow-x:auto; max-width:100%;">
      <div style="margin:0.5rem 0;">{legend}</div>
      <svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Investment growth attribution">
        <line x1="{padding_left}" y1="{zero_y:.1f}" x2="{width - 16}" y2="{zero_y:.1f}" stroke="rgba(128,128,128,0.45)" />
        <text x="{padding_left - 8}" y="{zero_y - 4:.1f}" font-size="10" text-anchor="end">0</text>
        <path d="{area_path(contribution_points, zero_points)}" fill="{colors["contributions"]}" opacity="0.35" />
        <path d="{area_path(dividend_points, contribution_points)}" fill="{colors["dividends"]}" opacity="0.35" />
        <path d="{area_path(market_points, dividend_points)}" fill="{colors["appreciation"]}" opacity="0.35" />
        <polyline points="{points_attr(contribution_points)}" fill="none" stroke="{colors["contributions"]}" stroke-width="2" />
        <polyline points="{points_attr(dividend_points)}" fill="none" stroke="{colors["dividends"]}" stroke-width="2" />
        <polyline points="{points_attr(market_points)}" fill="none" stroke="{colors["market_value"]}" stroke-width="2.4" />
        {''.join(tooltips)}
        {''.join(labels)}
      </svg>
    </div>
    """


def cumulative_growth_rows(rows):
    cumulative_contributions = 0.0
    cumulative_dividends = 0.0
    cumulative_rows = []
    for row in rows:
        if "cumulative_contributions" in row:
            cumulative_contributions = float(row.get("cumulative_contributions") or 0)
        else:
            cumulative_contributions += float(row.get("contributions") or 0)
        if "cumulative_dividends" in row:
            cumulative_dividends = float(row.get("cumulative_dividends") or 0)
        else:
            cumulative_dividends += float(row.get("dividends") or 0)
        market_value = float(row.get("ending_value") or 0)
        dividends_line = cumulative_contributions + cumulative_dividends
        cumulative_rows.append(
            {
                **row,
                "zero": 0.0,
                "market_value": market_value,
                "cumulative_contributions": cumulative_contributions,
                "cumulative_dividends": cumulative_dividends,
                "cumulative_dividends_line": dividends_line,
                "appreciation_residual": market_value - dividends_line,
            }
        )
    return cumulative_rows


def area_path(upper_points, lower_points):
    if not upper_points:
        return ""
    upper = " ".join(f"L {x:.1f} {y:.1f}" for x, y in upper_points[1:])
    lower = " ".join(f"L {x:.1f} {y:.1f}" for x, y in reversed(lower_points))
    first_x, first_y = upper_points[0]
    return f"M {first_x:.1f} {first_y:.1f} {upper} {lower} Z"


def points_attr(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def growth_column_labels():
    return {
        "month": "Month",
        "ending_value": "Ending Value",
        "contributions": "Contributions",
        "dividends": "Dividends",
        "appreciation": "Appreciation",
        "total_growth": "Total Growth",
        "cumulative_contributions": "Cumulative Contributions",
        "cumulative_dividends": "Cumulative Dividends",
    }


def growth_month_options(growth_data):
    table = growth_data["table"]
    rows = table.to_dicts() if hasattr(table, "to_dicts") else []
    return [str(row["month"])[:7] for row in rows]


def growth_component_options():
    return ["contributions", "dividends", "appreciation"]


def build_growth_detail_table(growth_data, selected_month, selected_component, pl):
    selected_month = selected_month or ""
    selected_component = selected_component or ""
    rows = [
        row
        for row in growth_data.get("audit_rows", [])
        if str(row["month"])[:7] == selected_month
        and row["component"] == selected_component
    ]
    return pl.DataFrame(
        rows,
        schema=[
            "month",
            "component",
            "amount",
            "date",
            "reason",
            "payee",
            "narration",
            "selected_postings",
            "other_accounts",
        ],
        orient="row",
    )


def growth_detail_column_labels():
    return {
        "month": "Month",
        "component": "Component",
        "amount": "Amount",
        "date": "Date",
        "reason": "Reason",
        "payee": "Payee",
        "narration": "Narration",
        "selected_postings": "Selected Postings",
        "other_accounts": "Other Accounts",
    }
