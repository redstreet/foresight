import re
from math import cos, pi, sin


BENEFICIARY_WARNING_ACCOUNT_PATTERN = r"^Assets:(Investments|Banks|RealEstate)(:|$)"


BENEFICIARY_EXCLUDED_ACCOUNTS = {
    "Assets:Investments:HSA",
    "Assets:Investments:Tax-Deferred",
    "Assets:Investments:Tax-Free",
    "Assets:Investments:Taxable",
}


BENEFICIARY_TABLES = [
    {
        "title": "Beneficiaries: Taxable",
        "directive_type": "accounts",
        "acc_pattern": "^Assets:Investments:Taxable",
        "meta_prefix": "estate_info_",
        "meta_skip": "estate_info_beneficiary_skip",
        "columns": [
            "account",
            "balance",
            "beneficiary_last_verified",
            "trusted_contacts",
            "title",
            "todo",
            "notes",
            "legal_points",
            "beneficiary_primary",
            "beneficiary_contingent",
        ],
        "sort_by": 1,
        "sort_reverse": True,
    },
    {
        "title": "Beneficiaries: Tax Advantaged",
        "directive_type": "accounts",
        "acc_pattern": "^Assets:Investments:Tax-Free",
        "meta_prefix": "estate_info_",
        "meta_skip": "estate_info_beneficiary_skip",
        "columns": [
            "account",
            "balance",
            "beneficiary_last_verified",
            "trusted_contacts",
            "title",
            "todo",
            "notes",
            "legal_points",
            "beneficiary_primary",
            "beneficiary_contingent",
        ],
        "sort_by": 1,
        "sort_reverse": True,
    },
    {
        "title": "Beneficiaries: Tax Deferred",
        "directive_type": "accounts",
        "acc_pattern": "^Assets:Investments:(?!Taxable|Tax-Free).+",
        "meta_prefix": "estate_info_",
        "meta_skip": "estate_info_beneficiary_skip",
        "columns": [
            "account",
            "balance",
            "beneficiary_last_verified",
            "trusted_contacts",
            "title",
            "todo",
            "notes",
            "legal_points",
            "beneficiary_primary",
            "beneficiary_contingent",
        ],
        "sort_by": 1,
        "sort_reverse": True,
    },
    {
        "title": "Beneficiaries: Other",
        "directive_type": "accounts",
        "acc_pattern": "^Assets:(Banks|RealEstate)",
        "meta_prefix": "estate_info_",
        "meta_skip": "estate_info_beneficiary_skip",
        "columns": [
            "account",
            "balance",
            "beneficiary_last_verified",
            "trusted_contacts",
            "title",
            "todo",
            "notes",
            "legal_points",
            "beneficiary_primary",
            "beneficiary_contingent",
        ],
        "sort_by": 1,
        "sort_reverse": True,
    },
]


def build_beneficiary_tables(
    convert,
    entries,
    pl,
    prices,
    realization,
):
    price_map = prices.build_price_map(entries)
    real_accounts = realization.realize(entries)
    commodity_names = declared_commodities(entries)
    table_payloads = []

    for table_config in BENEFICIARY_TABLES:
        if table_config.get("directive_type") != "accounts":
            continue
        table_payloads.append(
            {
                "title": table_config["title"],
                "table": build_beneficiary_table(
                    table_config,
                    convert,
                    entries,
                    pl,
                    price_map,
                    real_accounts,
                    realization,
                    commodity_names,
                ),
            }
        )

    covered_accounts = covered_beneficiary_accounts(
        entries,
        real_accounts,
        realization,
        commodity_names,
    )
    uncovered_accounts = uncovered_asset_accounts(entries, covered_accounts)
    if table_payloads:
        table_payloads[0]["warnings"] = uncovered_accounts
    return table_payloads


def build_beneficiary_table(
    table_config,
    convert,
    entries,
    pl,
    price_map,
    real_accounts,
    realization,
    commodity_names,
):
    columns = table_config["columns"]
    included_accounts = included_open_accounts(entries, table_config)
    rows = []

    for entry in entries:
        if entry.__class__.__name__ != "Open":
            continue
        if entry.account not in included_accounts:
            continue
        if commodity_leaf_account(
            entry.account,
            included_accounts,
            real_accounts,
            realization,
            commodity_names,
        ):
            continue

        row = {}
        for column in columns:
            if column == "account":
                row[column] = display_account(entry.account, table_config)
            elif column == "balance":
                row[column] = account_market_value(
                    entry.account,
                    convert,
                    price_map,
                    real_accounts,
                    realization,
                )
            else:
                row[column] = metadata_value(
                    entry.meta,
                    table_config["meta_prefix"],
                    column,
                )
        rows.append(row)

    table = pl.DataFrame(rows, schema=columns, orient="row")
    sort_column = columns[table_config.get("sort_by", 0)]
    return table.sort(
        sort_column,
        descending=bool(table_config.get("sort_reverse")),
        nulls_last=True,
    )


def declared_commodities(entries):
    return {
        entry.currency
        for entry in entries
        if entry.__class__.__name__ == "Commodity"
    }


def covered_beneficiary_accounts(entries, real_accounts, realization, commodity_names):
    covered_accounts = set()
    for table_config in BENEFICIARY_TABLES:
        if table_config.get("directive_type") != "accounts":
            continue
        included_accounts = included_open_accounts(entries, table_config)
        for account_name in included_accounts:
            if commodity_leaf_account(
                account_name,
                included_accounts,
                real_accounts,
                realization,
                commodity_names,
            ):
                continue
            covered_accounts.add(account_name)
    return covered_accounts


def uncovered_asset_accounts(entries, covered_accounts):
    open_asset_accounts = active_open_asset_accounts(entries)
    return [
        account_name
        for account_name in sorted(open_asset_accounts)
        if not account_or_ancestor_included(account_name, covered_accounts)
    ]


def active_open_asset_accounts(entries):
    closed_accounts = {
        entry.account
        for entry in entries
        if entry.__class__.__name__ == "Close"
    }
    return {
        entry.account
        for entry in entries
        if entry.__class__.__name__ == "Open"
        and re.search(BENEFICIARY_WARNING_ACCOUNT_PATTERN, entry.account)
        and entry.account not in closed_accounts
        and not beneficiary_excluded_account(entry.account)
        and not metadata_truthy(entry.meta.get("estate_info_beneficiary_skip"))
    }


def account_or_ancestor_included(account_name, included_accounts):
    parts = account_name.split(":")
    for index in range(len(parts), 0, -1):
        if ":".join(parts[:index]) in included_accounts:
            return True
    return False


def included_open_accounts(entries, table_config):
    accounts = set()
    closed_accounts = {
        entry.account
        for entry in entries
        if entry.__class__.__name__ == "Close"
    }
    for entry in entries:
        if entry.__class__.__name__ != "Open":
            continue
        if entry.account in closed_accounts:
            continue
        if beneficiary_excluded_account(entry.account):
            continue
        if not re.search(table_config["acc_pattern"], entry.account):
            continue
        if metadata_truthy(entry.meta.get(table_config["meta_skip"])):
            continue
        accounts.add(entry.account)
    return accounts


def beneficiary_excluded_account(account_name):
    return account_name in BENEFICIARY_EXCLUDED_ACCOUNTS


def commodity_leaf_account(
    account_name,
    included_accounts,
    real_accounts,
    realization,
    commodity_names,
):
    parent_account = account_name.rsplit(":", 1)[0] if ":" in account_name else ""
    if parent_account not in included_accounts:
        return False
    account_leaf = account_name.rsplit(":", 1)[-1]

    if account_leaf in commodity_names:
        return True

    subtree = realization.get(real_accounts, account_name)
    if subtree is None or len(subtree) > 0:
        return False

    positions = list(subtree.balance.get_positions())
    return bool(positions) and all(
        position.units.currency == account_leaf
        for position in positions
    )


def display_account(account_name, table_config):
    prefix = account_display_prefix(table_config)
    if account_name == prefix:
        return account_name.rsplit(":", 1)[-1]
    if account_name.startswith(f"{prefix}:"):
        return account_name[len(prefix) + 1:]
    return account_name


def account_display_prefix(table_config):
    pattern = table_config["acc_pattern"]
    if pattern.startswith("^Assets:Investments:Taxable"):
        return "Assets:Investments:Taxable"
    if pattern.startswith("^Assets:Investments:Tax-Free"):
        return "Assets:Investments:Tax-Free"
    if pattern.startswith("^Assets:Investments:"):
        return "Assets:Investments"
    if pattern.startswith("^Assets:"):
        return "Assets"
    return ""


def metadata_truthy(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no"}
    return bool(value)


def metadata_value(meta, prefix, column):
    value = meta.get(f"{prefix}{column}")
    return "" if value is None else str(value)


def account_market_value(account_name, convert, price_map, real_accounts, realization):
    subtree = realization.get(real_accounts, account_name)
    if subtree is None:
        return 0.0
    balance = realization.compute_balance(subtree)
    units_balance = balance.reduce(convert.get_units)
    market_value = units_balance.reduce(convert.convert_position, "USD", price_map)
    return inventory_value(market_value)


def inventory_value(inventory):
    if inventory is not None:
        position = inventory.get_only_position()
        if position is not None:
            return float(position.units.number)
    if inventory.is_empty():
        return 0.0
    return None


def build_beneficiaries_view(
    beneficiary_tables,
    common_table_section_styles,
    escape,
    format_amount,
    mo,
):
    warnings = []
    for table_data in beneficiary_tables:
        warnings.extend(table_data.get("warnings", []))
    warning_view = beneficiary_warning_view(warnings, escape, mo)
    title_summary = beneficiary_title_summary(beneficiary_tables)
    donut_chart = build_title_donut_chart(title_summary, escape, format_amount)
    table_views = []
    for table_data in beneficiary_tables:
        table = table_data["table"]
        columns = visible_columns(table)
        total = table["balance"].sum() if "balance" in columns and not table.is_empty() else 0
        column_labels = beneficiary_column_labels(columns)
        visible_table = table.select(columns).rename(column_labels)
        display_columns = [column_labels[column] for column in columns]
        highlighted_row_ids = beneficiary_highlighted_row_ids(
            table_data["title"],
            visible_table,
        )

        def table_cell_style(
            row_id,
            column_name,
            value,
            highlighted_row_ids=highlighted_row_ids,
        ):
            return beneficiary_table_cell_style(
                row_id,
                column_name,
                value,
                highlighted_row_ids,
            )

        table_views.append(
            mo.vstack(
                [
                    mo.Html(
                        f"""
                        <section class="beneficiaries-section foresight-table-section">
                          <h2>{escape(table_data["title"])}</h2>
                        </section>
                        """
                    ),
                    mo.ui.table(
                        visible_table,
                        pagination=False,
                        selection=None,
                        show_column_summaries=False,
                        show_data_types=False,
                        format_mapping={"Balance": format_amount},
                        freeze_columns_left=["Account"],
                        text_justify_columns={"Balance": "right"},
                        wrapped_columns=wrapped_columns(display_columns),
                        show_download=False,
                        max_columns=None,
                        style_cell=table_cell_style,
                    ),
                    mo.Html(
                        f"""
                        <div class="beneficiaries-total-row">
                          <span>Total</span>
                          <span>{format_amount(total)}</span>
                        </div>
                        """
                    ),
                ]
            )
        )

    return mo.vstack(
        [
            mo.md("# Beneficiaries"),
            *([warning_view] if warning_view is not None else []),
            *([mo.Html(donut_chart)] if donut_chart else []),
            mo.Html('<div class="beneficiaries-table-scope"></div>'),
            mo.Html(
                f"""
                <style>
                {common_table_section_styles}
                .beneficiaries-section {{
                  margin-top: 1.75rem;
                }}
                .beneficiaries-table-scope ~ marimo-ui-element marimo-table,
                .beneficiaries-table-scope ~ div marimo-table {{
                  border: 0 !important;
                  font-size: 0.98rem;
                  outline: 0 !important;
                  box-shadow: none !important;
                }}
                .beneficiaries-table-scope ~ marimo-ui-element table,
                .beneficiaries-table-scope ~ div table {{
                  border-collapse: collapse;
                  border-spacing: 0;
                  border: 0 !important;
                  font-size: 0.98rem;
                }}
                .beneficiaries-table-scope ~ marimo-ui-element [role="table"],
                .beneficiaries-table-scope ~ div [role="table"],
                .beneficiaries-table-scope ~ marimo-ui-element [role="grid"],
                .beneficiaries-table-scope ~ div [role="grid"] {{
                  border: 0 !important;
                  box-shadow: none !important;
                  outline: 0 !important;
                }}
                .beneficiaries-table-scope ~ marimo-ui-element th,
                .beneficiaries-table-scope ~ div th {{
                  color: #000 !important;
                  font-size: 1.02rem !important;
                  font-weight: 650 !important;
                }}
                .beneficiaries-table-scope ~ marimo-ui-element th,
                .beneficiaries-table-scope ~ marimo-ui-element td,
                .beneficiaries-table-scope ~ div th,
                .beneficiaries-table-scope ~ div td {{
                  border-left: 0 !important;
                  border-right: 0 !important;
                  border-top: 0 !important;
                  border-bottom: 0 !important;
                  box-shadow: none !important;
                  line-height: 1.15 !important;
                  padding: 0.12rem 0.18rem !important;
                }}
                .beneficiaries-total-row {{
                  display: grid;
                  grid-template-columns: minmax(10rem, max-content) 8rem;
                  gap: 1rem;
                  width: fit-content;
                  margin: 0.35rem 0 1.75rem;
                  font-weight: 600;
                }}
                .beneficiaries-total-row span:last-child {{
                  text-align: right;
                }}
                .beneficiaries-donut {{
                  display: flex;
                  align-items: center;
                  gap: 1.5rem;
                  flex-wrap: wrap;
                  margin: 0.5rem 0 1.5rem;
                }}
                .beneficiaries-donut svg {{
                  flex: 0 0 auto;
                }}
                .beneficiaries-donut-legend {{
                  display: grid;
                  gap: 0.35rem;
                  font-size: 0.9rem;
                }}
                .beneficiaries-donut-legend-row {{
                  display: grid;
                  grid-template-columns: 1rem minmax(10rem, max-content) 7rem 4rem;
                  gap: 0.5rem;
                  align-items: center;
                }}
                .beneficiaries-donut-swatch {{
                  width: 0.75rem;
                  height: 0.75rem;
                  border-radius: 999px;
                }}
                .beneficiaries-donut-value,
                .beneficiaries-donut-percent {{
                  text-align: right;
                  white-space: nowrap;
                }}
                @media print {{
                  @page {{
                    size: landscape;
                  }}
                  body,
                  body * {{
                    overflow: visible !important;
                    max-width: none !important;
                  }}
                  .beneficiaries-section,
                  .beneficiaries-total-row {{
                    break-inside: avoid;
                    page-break-inside: avoid;
                    width: max-content !important;
                  }}
                }}
                </style>
                """
            ),
            *table_views,
        ]
    )


def beneficiary_title_summary(beneficiary_tables):
    totals = {}
    for table_data in beneficiary_tables:
        table = table_data["table"]
        if table.is_empty() or "title" not in table.columns or "balance" not in table.columns:
            continue
        for row in table.iter_rows(named=True):
            title = str(row.get("title") or "(missing)").strip() or "(missing)"
            balance = row.get("balance")
            if balance is None or balance <= 0:
                continue
            totals[title] = totals.get(title, 0.0) + float(balance)
    return sorted(
        [{"title": title, "balance": balance} for title, balance in totals.items()],
        key=lambda row: (row["balance"], row["title"]),
        reverse=True,
    )


def build_title_donut_chart(summary_rows, escape, format_amount):
    if not summary_rows:
        return ""

    total = sum(row["balance"] for row in summary_rows)
    if total <= 0:
        return ""

    colors = [
        "#4e79a7",
        "#59a14f",
        "#f28e2b",
        "#e15759",
        "#76b7b2",
        "#edc948",
        "#b07aa1",
        "#9c755f",
        "#bab0ab",
    ]
    center = 96
    outer_radius = 86
    inner_radius = 46
    start_angle = -pi / 2
    slices = []
    legend_rows = []

    for index, row in enumerate(summary_rows):
        percentage = row["balance"] / total
        end_angle = start_angle + percentage * 2 * pi
        color = colors[index % len(colors)]
        slices.append(
            donut_slice_path(
                center,
                outer_radius,
                inner_radius,
                start_angle,
                end_angle,
                color,
                escape(row["title"]),
                format_amount(row["balance"]),
                percentage,
            )
        )
        legend_rows.append(
            f"""
            <div class="beneficiaries-donut-legend-row">
              <span class="beneficiaries-donut-swatch" style="background: {color};"></span>
              <span>{escape(row["title"])}</span>
              <span class="beneficiaries-donut-value">{format_amount(row["balance"])}</span>
              <span class="beneficiaries-donut-percent">{percentage * 100:.0f}%</span>
            </div>
            """
        )
        start_angle = end_angle

    return f"""
    <section class="beneficiaries-donut">
      <svg viewBox="0 0 192 192" width="192" height="192" role="img" aria-label="Beneficiary assets by title">
        {''.join(slices)}
        <circle cx="{center}" cy="{center}" r="{inner_radius - 1}" fill="white" />
        <text x="{center}" y="{center - 2}" text-anchor="middle" font-size="14" font-weight="600">Total</text>
        <text x="{center}" y="{center + 18}" text-anchor="middle" font-size="13">{format_amount(total)}</text>
      </svg>
      <div class="beneficiaries-donut-legend">
        {''.join(legend_rows)}
      </div>
    </section>
    """


def donut_slice_path(
    center,
    outer_radius,
    inner_radius,
    start_angle,
    end_angle,
    color,
    title,
    amount,
    percentage,
):
    large_arc = 1 if end_angle - start_angle > pi else 0
    outer_start = polar_to_cartesian(center, outer_radius, start_angle)
    outer_end = polar_to_cartesian(center, outer_radius, end_angle)
    inner_end = polar_to_cartesian(center, inner_radius, end_angle)
    inner_start = polar_to_cartesian(center, inner_radius, start_angle)
    path = (
        f"M {outer_start[0]:.3f} {outer_start[1]:.3f} "
        f"A {outer_radius} {outer_radius} 0 {large_arc} 1 {outer_end[0]:.3f} {outer_end[1]:.3f} "
        f"L {inner_end[0]:.3f} {inner_end[1]:.3f} "
        f"A {inner_radius} {inner_radius} 0 {large_arc} 0 {inner_start[0]:.3f} {inner_start[1]:.3f} Z"
    )
    return f"""
    <path d="{path}" fill="{color}" stroke="white" stroke-width="2">
      <title>{title}: {amount} ({percentage * 100:.0f}%)</title>
    </path>
    """


def polar_to_cartesian(center, radius, angle):
    return (
        center + radius * cos(angle),
        center + radius * sin(angle),
    )


def beneficiary_warning_view(warnings, escape, mo):
    if not warnings:
        return None
    warning_items = "".join(
        f"<li>{escape(account_name)}</li>"
        for account_name in warnings
    )
    return mo.Html(
        f"""
        <div style="border-left: 4px solid #b54708; padding: 0.5rem 0.75rem; background: rgba(181, 71, 8, 0.08);">
          <strong>Open Assets accounts not covered by Beneficiaries tables</strong>
          <ul>{warning_items}</ul>
        </div>
        """
    )


def visible_columns(table):
    columns = table.columns
    optional_columns = {"todo", "notes", "legal_points"}
    return [
        column
        for column in columns
        if column not in optional_columns or column_has_value(table, column)
    ]


def column_has_value(table, column):
    if table.is_empty():
        return False
    for value in table[column].to_list():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return True
    return False


def wrapped_columns(columns):
    nowrap_columns = {"Account", "Balance", "Title"}
    return [column for column in columns if column not in nowrap_columns]


def beneficiary_column_labels(columns):
    overrides = {
        "beneficiary_last_verified": "Last Verified",
    }
    return {
        column: overrides.get(column, column.replace("_", " ").title())
        for column in columns
    }


def beneficiary_table_cell_style(row_id, column_name, value, highlighted_row_ids=None):
    del value
    highlighted_row_ids = highlighted_row_ids or set()
    style = {
        "borderLeft": "0",
        "borderRight": "0",
        "borderTop": "0",
        "borderBottom": "0",
        "boxShadow": "none",
        "fontSize": "0.98rem",
        "lineHeight": "1.15",
        "padding": "0.12rem 0.18rem",
    }
    style.update(beneficiary_column_width_style(column_name))
    if row_id in highlighted_row_ids:
        style["backgroundColor"] = "#f3d36b"
    return style


def beneficiary_highlighted_row_ids(table_title, table):
    if table_title != "Beneficiaries: Taxable" or "Title" not in table.columns:
        return set()
    return {
        str(index)
        for index, row in enumerate(table.iter_rows(named=True))
        if not beneficiary_row_has_trust_or_na(row)
    }


def beneficiary_row_has_trust_or_na(row):
    return any(
        "Trust" in value or "N/A" in value
        for value in (
            str(row.get("Title") or ""),
            str(row.get("Beneficiary Primary") or ""),
            str(row.get("Beneficiary Contingent") or ""),
        )
    )


def beneficiary_column_width_style(column_name):
    widths = {
        "Account": "18rem",
        "Balance": "6.5rem",
        "Last Verified": "6.5rem",
        "Trusted Contacts": "10rem",
        "Title": "9rem",
        "Beneficiary Primary": "14rem",
        "Beneficiary Contingent": "16rem",
    }
    width = widths.get(column_name, "9rem")
    style = {
        "minWidth": width,
        "maxWidth": "none",
    }
    if column_name == "Balance":
        style["width"] = width
        style["maxWidth"] = width
    elif column_name in {"Account", "Last Verified", "Title"}:
        style["whiteSpace"] = "nowrap"
    else:
        style["whiteSpace"] = "normal"
        style["overflowWrap"] = "anywhere"
    return style
