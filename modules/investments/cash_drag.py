from decimal import Decimal, InvalidOperation
import re


DEFAULT_CASH_DRAG_CONFIG = {
    "accounts_pattern": "^Assets",
    "accounts_exclude_pattern": "",
    "metadata_label_cash": "asset_allocation_Bond_Cash",
    "min_threshold": 0,
}


def normalize_cash_drag_config(config):
    normalized = {**DEFAULT_CASH_DRAG_CONFIG, **(config or {})}
    normalized["min_threshold"] = Decimal(str(normalized.get("min_threshold") or 0))
    return normalized


def cash_commodities(entries, options, metadata_label):
    commodities = set(operating_currencies(options))
    for entry in entries:
        if entry.__class__.__name__ != "Commodity":
            continue
        if metadata_is_100(entry.meta.get(metadata_label)):
            commodities.add(entry.currency)
    return commodities


def metadata_is_100(value):
    try:
        return Decimal(str(value)) == Decimal("100")
    except (InvalidOperation, TypeError, ValueError):
        return False


def operating_currencies(options):
    currencies = options.get("operating_currency", None) if isinstance(options, dict) else None
    if currencies:
        return list(currencies)
    return ["USD"]


def build_cash_drag_table(config, convert, entries, options, pl, prices, realization):
    normalized_config = normalize_cash_drag_config(config)
    price_map = prices.build_price_map(entries)
    real_accounts = realization.realize(entries)
    base_currency = operating_currencies(options)[0]
    cash_currency_set = cash_commodities(
        entries,
        options,
        normalized_config["metadata_label_cash"],
    )

    rows = []
    for real_account in realization.iter_children(real_accounts):
        account_name = real_account.account
        if not included_account(account_name, normalized_config):
            continue

        amount = account_cash_value(
            real_account.balance,
            cash_currency_set,
            base_currency,
            convert,
            price_map,
        )
        if amount is None or amount == 0:
            continue
        if amount < normalized_config["min_threshold"]:
            continue
        rows.append({"account": account_name, "cash": float(amount)})

    return pl.DataFrame(rows, schema=["account", "cash"], orient="row").sort(
        "cash",
        descending=True,
    )


def included_account(account_name, config):
    if not re.search(config["accounts_pattern"], account_name):
        return False
    exclude_pattern = config.get("accounts_exclude_pattern") or ""
    return not (exclude_pattern and re.search(exclude_pattern, account_name))


def account_cash_value(balance, cash_currency_set, base_currency, convert, price_map):
    total = Decimal("0")
    for position in balance.get_positions():
        units = convert.get_units(position)
        if units.currency not in cash_currency_set:
            continue
        amount = converted_position_amount(position, base_currency, convert, price_map)
        if amount is None:
            continue
        total += Decimal(amount.number)
    return total


def converted_position_amount(position, base_currency, convert, price_map):
    converted = convert.convert_position(position, base_currency, price_map)
    amount = getattr(converted, "units", converted)
    if getattr(amount, "currency", None) != base_currency:
        return None
    return amount


def build_cash_drag_view(cash_drag_table, escape, format_amount, mo):
    total_cash = cash_drag_table["cash"].sum() if not cash_drag_table.is_empty() else 0
    rows = []
    for row in cash_drag_table.iter_rows(named=True):
        rows.append(
            f"""
            <tr>
              <td>{escape(row["account"])}</td>
              <td class="numeric">{format_amount(row["cash"])}</td>
            </tr>
            """
        )

    return mo.vstack(
        [
            mo.md("# Cash Drag"),
            mo.Html(
                f"""
                <style>
                .cash-drag-table {{
                  border-collapse: collapse;
                  font-size: 0.95rem;
                  line-height: 1.35;
                  width: fit-content;
                  max-width: 100%;
                }}
                .cash-drag-table th,
                .cash-drag-table td {{
                  border-bottom: 1px solid rgba(128, 128, 128, 0.18);
                  padding: 0.35rem 0.75rem;
                  white-space: nowrap;
                }}
                .cash-drag-table th {{
                  font-weight: 600;
                  text-align: left;
                }}
                .cash-drag-table .numeric {{
                  text-align: right;
                }}
                .cash-drag-table tfoot td {{
                  font-weight: 600;
                }}
                </style>
                <table class="cash-drag-table">
                  <thead>
                    <tr>
                      <th>Account</th>
                      <th class="numeric">Cash</th>
                    </tr>
                  </thead>
                  <tbody>
                    {''.join(rows)}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td>Total</td>
                      <td class="numeric">{format_amount(total_cash)}</td>
                    </tr>
                  </tfoot>
                </table>
                """
            ),
        ]
    )
