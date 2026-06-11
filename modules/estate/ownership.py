def build_account_metadata_table(entries, liability_community_property, pl):
    def estate_account(account_name: str) -> bool:
        return (
            account_name == "Assets:Banks"
            or account_name.startswith("Assets:Banks:")
            or account_name == "Assets:Investments"
            or account_name.startswith("Assets:Investments:")
            or account_name == "Assets:RealEstate"
            or account_name.startswith("Assets:RealEstate:")
        )

    def liability_account(account_name: str) -> bool:
        return (
            account_name == "Liability"
            or account_name.startswith("Liability:")
            or account_name == "Liabilities"
            or account_name.startswith("Liabilities:")
        )

    liability_open_accounts = [
        entry.account
        for entry in entries
        if entry.__class__.__name__ == "Open"
        and liability_account(entry.account)
    ]
    liability_leaf_accounts = {
        account
        for account in liability_open_accounts
        if not any(
            other_account != account
            and other_account.startswith(f"{account}:")
            for other_account in liability_open_accounts
        )
    }

    account_metadata_table = pl.DataFrame(
        [
            {
                "account": entry.account,
                "community_property": (
                    liability_community_property
                    if liability_account(entry.account)
                    else entry.meta.get("estate_info_community_property")
                ),
                "has_community_property": (
                    entry.account in liability_leaf_accounts
                    or "estate_info_community_property" in entry.meta
                ),
            }
            for entry in entries
            if entry.__class__.__name__ == "Open"
            and (
                estate_account(entry.account)
                or entry.account in liability_leaf_accounts
            )
        ],
        schema=["account", "community_property", "has_community_property"],
        orient="row",
    ).sort("account")
    return account_metadata_table.with_columns(
        pl.col("community_property").cast(pl.Utf8)
    )


def build_account_value_table(
    account_metadata_table,
    convert,
    entries,
    pl,
    prices,
    realization,
):
    price_map = prices.build_price_map(entries)
    real_accounts = realization.realize(entries)

    def inventory_value(inventory):
        if inventory is not None:
            position = inventory.get_only_position()
            if position is not None:
                return float(position.units.number)
        if inventory.is_empty():
            return 0.0
        return None

    def account_market_value(account_name: str):
        subtree = realization.get(real_accounts, account_name)
        balance = realization.compute_balance(subtree)
        units_balance = balance.reduce(convert.get_units)
        market_value = units_balance.reduce(
            convert.convert_position, "USD", price_map
        )
        return inventory_value(market_value)

    return pl.DataFrame(
        [
            {
                "account": row["account"],
                "market_value": account_market_value(row["account"]),
            }
            for row in account_metadata_table
            .filter(pl.col("has_community_property"))
            .iter_rows(named=True)
        ],
        schema=["account", "market_value"],
        orient="row",
    )


def build_account_tables(account_metadata_table, account_value_table, pl):
    accounts_table = (
        account_metadata_table
        .filter(pl.col("has_community_property"))
        .select("account", "community_property")
        .join(account_value_table, on="account", how="left")
        .with_columns(
            pl.col("community_property")
            .fill_null("(missing)")
            .cast(pl.Utf8)
            .alias("community_property"),
            pl.col("market_value").cast(pl.Float64),
        )
        .sort("market_value", descending=True, nulls_last=True)
    )
    summary_table = (
        accounts_table
        .group_by("community_property")
        .agg(
            pl.len().alias("accounts"),
            pl.col("market_value").sum().alias("market_value"),
        )
        .sort("market_value", descending=True, nulls_last=True)
    )
    return accounts_table, summary_table


def build_ownership_view(accounts_table, summary_table, escape, format_amount, mo, pl):
    total_accounts = 0
    total_market_value = 0.0
    group_rows = []

    for summary_row in summary_table.iter_rows(named=True):
        classification = summary_row["community_property"]
        accounts = summary_row["accounts"]
        market_value = summary_row["market_value"]
        total_accounts += accounts
        if market_value is not None:
            total_market_value += market_value

        account_row_html = []
        account_rows = (
            accounts_table
            .filter(pl.col("community_property") == classification)
            .iter_rows(named=True)
        )
        for account_row in account_rows:
            account_row_html.append(
                f"""
                <div class="ownership-account-row">
                  <div>{escape(str(account_row["account"]))}</div>
                  <div></div>
                  <div>{format_amount(account_row["market_value"])}</div>
                </div>
                """
            )

        group_rows.append(
            f"""
            <details class="ownership-group">
              <summary>
                <span class="ownership-grid ownership-summary-row">
                  <span>{escape(str(classification))}</span>
                  <span>{accounts:,}</span>
                  <span>{format_amount(market_value)}</span>
                </span>
              </summary>
              {"".join(account_row_html)}
            </details>
            """
        )

    return mo.vstack(
        [
            mo.md("# Ownership Assets and Liabilities"),
            mo.Html(
                f"""
                <style>
                  .ownership-table {{
                    font-size: 0.95rem;
                    max-width: 100%;
                    width: fit-content;
                  }}
                  .ownership-grid {{
                    display: grid;
                    grid-template-columns: minmax(34rem, 1fr) 6rem 10rem;
                    align-items: start;
                    column-gap: 2.5rem;
                    padding: 0.35rem 0;
                  }}
                  .ownership-grid > span:nth-child(2),
                  .ownership-grid > span:nth-child(3),
                  .ownership-account-row > div:nth-child(2),
                  .ownership-account-row > div:nth-child(3) {{
                    text-align: right;
                    white-space: nowrap;
                  }}
                  .ownership-header {{
                    font-weight: 600;
                  }}
                  .ownership-group {{
                    margin: 0;
                  }}
                  .ownership-group summary {{
                    cursor: pointer;
                    list-style-position: outside;
                  }}
                  .ownership-group summary .ownership-summary-row {{
                    display: inline-grid;
                    width: calc(100% - 1.25rem);
                    background: rgba(128, 128, 128, 0.08);
                    font-weight: 700;
                  }}
                  .ownership-total-row {{
                    background: rgba(128, 128, 128, 0.12);
                    font-weight: 700;
                  }}
                  .ownership-account-row {{
                    display: grid;
                    grid-template-columns: minmax(34rem, 1fr) 6rem 10rem;
                    column-gap: 2.5rem;
                    padding: 0.35rem 0 0.35rem 1.5rem;
                  }}
                </style>
                <div class="ownership-table">
                  <div class="ownership-grid ownership-header">
                    <span>Classification</span>
                    <span>Accounts</span>
                    <span>Market Value</span>
                  </div>
                  <div class="ownership-grid ownership-total-row">
                    <span>TOTAL</span>
                    <span>{total_accounts:,}</span>
                    <span>{format_amount(total_market_value)}</span>
                  </div>
                  {"".join(group_rows)}
                </div>
                """
            ),
        ]
    )
