def load_retirement_table(run_query):
    return run_query(
        """
        SELECT
          year,
          LEAF(account),
          sum(position)
        WHERE
          account~'Assets:Z.*:Transfers:.*Paycheck:Y401k.*'
          AND NOT account~':Loan'
          AND STR(FINDFIRST('^Income:Employment:.*', other_accounts)) != 'None'
        GROUP BY year, LEAF(account)
        ORDER BY year, LEAF(account)
        """
    ).rename({
        "LEAF(account)": "account",
        "sum(position) (USD)": "amount",
    })


def load_hsa_and_roth_tables(entries, get_embedded_query, options, pl, run_bql_query):
    def embedded_query_table(query_name: str):
        embedded_query = get_embedded_query(query_name)
        cols, rows = run_bql_query(entries, options, embedded_query, numberify=True)
        return pl.DataFrame(
            schema=[col.name for col in cols],
            data=rows,
            orient="row",
            infer_schema_length=None,
        )

    personal_hsa_raw = embedded_query_table(
        "Annual contributions: HSA via Personal Contributions"
    )
    personal_hsa_amount_column = next(
        column
        for column in personal_hsa_raw.columns
        if column not in {"year", "tax_year", "account", "LEAF(account)"}
    )
    personal_hsa_table = personal_hsa_raw.select(
        pl.coalesce([pl.col("tax_year"), pl.col("year")]).alias("year"),
        pl.col(personal_hsa_amount_column).alias("amount"),
    )

    employer_hsa_raw = embedded_query_table(
        "Annual contributions: HSA via Paycheck Deductions"
    )
    employer_hsa_amount_column = next(
        column
        for column in employer_hsa_raw.columns
        if column not in {"year", "tax_year", "account", "LEAF(account)"}
    )
    employer_hsa_account_column = (
        "account"
        if "account" in employer_hsa_raw.columns
        else "LEAF(account)"
    )
    employer_hsa_table = employer_hsa_raw.select(
        pl.coalesce([pl.col("tax_year"), pl.col("year")]).alias("year"),
        pl.col(employer_hsa_account_column).alias("account"),
        pl.col(employer_hsa_amount_column).alias("amount"),
    )

    roth_raw = embedded_query_table("Annual contributions: Roth")
    roth_backdoor_table = roth_raw.select(
        pl.coalesce([pl.col("tax_year"), pl.col("year")]).alias("year"),
        pl.col("account"),
        pl.col("number").alias("amount"),
    )
    return employer_hsa_table, personal_hsa_table, roth_backdoor_table


def load_limit_tables(run_query):
    roth_limits_table = run_query(
        """
        SELECT
          year,
          meta['roth']
        FROM entries
        WHERE type = 'custom'
        """
    )
    raw_limits_table = run_query(
        """
        SELECT
          year,
          meta['after-tax'],
          meta['pretax-401k-employee'],
          meta['pretax-401k-match'],
          meta['total-limit']
        FROM entries
        WHERE type = 'custom'
        """
    )
    hsa_limits_table = run_query(
        """
        SELECT
          year,
          meta['hsa-limit']
        FROM entries
        WHERE type = 'custom'
        """
    )
    return hsa_limits_table, raw_limits_table, roth_limits_table


def default_year(retirement_table, datetime):
    available_years = (
        sorted(retirement_table["year"].unique().to_list())
        if len(retirement_table)
        else []
    )
    year_options = [str(year) for year in available_years]
    current_year = str(datetime.now().year)
    selected = (
        current_year
        if current_year in year_options
        else (year_options[-1] if year_options else None)
    )
    return year_options, selected


def build_contributions_view(
    bean_table,
    employer_hsa_table,
    format_amount,
    hsa_limits_table,
    mo,
    personal_hsa_table,
    pl,
    raw_limits_table,
    retirement_table,
    roth_backdoor_table,
    roth_limits_table,
    selected_year,
):
    def cell_style(column_name, value, is_total) -> str:
        if column_name != "Remaining" or not is_total or value is None:
            return ""
        return "color: #b42318;" if int(round(float(value))) != 0 else ""

    selected_year_value = selected_year.value

    retirement_filtered = retirement_table.filter(
        pl.col("year").cast(pl.Utf8) == selected_year_value
    ).select(pl.col("account"), pl.col("amount"))
    retirement_year_limits_filtered = (
        raw_limits_table.filter(pl.col("year").cast(pl.Utf8) == selected_year_value)
        if selected_year_value is not None and len(raw_limits_table)
        else raw_limits_table.head(0)
    )
    retirement_year_limits = (
        retirement_year_limits_filtered.row(0, named=True)
        if len(retirement_year_limits_filtered)
        else None
    )

    def retirement_account_limit(account_name: str):
        if retirement_year_limits is None:
            return None
        normalized = account_name.lower().replace("_", "").replace("-", "").replace(" ", "")
        if "match" in normalized:
            return retirement_year_limits["meta['pretax-401k-match']"]
        if "after" in normalized:
            return retirement_year_limits["meta['after-tax']"]
        if "pretaxemployee" in normalized or "employee" in normalized or "pretax401kemployee" in normalized:
            return retirement_year_limits["meta['pretax-401k-employee']"]
        return None

    retirement_rows = []
    retirement_total_amount = sum(
        item["amount"] for item in retirement_filtered.iter_rows(named=True)
    )
    retirement_total_limit = (
        retirement_year_limits["meta['total-limit']"]
        if retirement_year_limits is not None
        and "meta['total-limit']" in retirement_year_limits
        else None
    )
    retirement_total_remaining = (
        retirement_total_limit - retirement_total_amount
        if retirement_total_limit is not None
        else None
    )
    for retirement_item in retirement_filtered.iter_rows(named=True):
        retirement_limit_value = retirement_account_limit(retirement_item["account"])
        retirement_rows.append(
            {
                "Account": retirement_item["account"],
                "Amount": retirement_item["amount"],
                "Limit": retirement_limit_value,
                "Remaining": (
                    retirement_limit_value - retirement_item["amount"]
                    if retirement_limit_value is not None
                    else None
                ),
            }
        )

    retirement_table_view = bean_table(
        retirement_rows,
        total_row={
            "Account": "TOTAL",
            "Amount": retirement_total_amount,
            "Limit": retirement_total_limit,
            "Remaining": retirement_total_remaining,
        },
        cell_style_fn=cell_style,
        formatters={
            "Amount": format_amount,
            "Limit": format_amount,
            "Remaining": format_amount,
        },
    )

    hsa_personal_amount = 0.0
    hsa_employer_amount = 0.0
    if selected_year_value is not None:
        personal_hsa_filtered = personal_hsa_table.filter(
            pl.col("year").cast(pl.Utf8) == selected_year_value
        )
        employer_hsa_filtered = employer_hsa_table.filter(
            pl.col("year").cast(pl.Utf8) == selected_year_value
        )
        if len(personal_hsa_filtered):
            hsa_personal_amount = float(personal_hsa_filtered["amount"].sum())
        if len(employer_hsa_filtered):
            hsa_employer_amount = float(employer_hsa_filtered["amount"].sum())

    hsa_limit_filtered = (
        hsa_limits_table.filter(pl.col("year").cast(pl.Utf8) == selected_year_value)
        if selected_year_value is not None and len(hsa_limits_table)
        else hsa_limits_table.head(0)
    )
    hsa_limit_row = hsa_limit_filtered.row(0, named=True) if len(hsa_limit_filtered) else None
    hsa_limit = (
        float(hsa_limit_row["meta['hsa-limit']"])
        if hsa_limit_row is not None
        and "meta['hsa-limit']" in hsa_limit_row
        and hsa_limit_row["meta['hsa-limit']"] is not None
        else None
    )
    hsa_total_amount = hsa_personal_amount + hsa_employer_amount
    hsa_table_view = bean_table(
        [
            {"Account": "Personal", "Amount": hsa_personal_amount, "Limit": None, "Remaining": None},
            {"Account": "Paycheck", "Amount": hsa_employer_amount, "Limit": None, "Remaining": None},
        ],
        total_row={
            "Account": "TOTAL",
            "Amount": hsa_total_amount,
            "Limit": hsa_limit,
            "Remaining": hsa_limit - hsa_total_amount if hsa_limit is not None else None,
        },
        cell_style_fn=cell_style,
        formatters={
            "Amount": format_amount,
            "Limit": format_amount,
            "Remaining": format_amount,
        },
    )

    roth_filtered = roth_backdoor_table.filter(
        pl.col("year").cast(pl.Utf8) == selected_year_value
    ).select(pl.col("account"), pl.col("amount"))
    roth_limit_filtered = (
        roth_limits_table.filter(pl.col("year").cast(pl.Utf8) == selected_year_value)
        if selected_year_value is not None and len(roth_limits_table)
        else roth_limits_table.head(0)
    )
    roth_limit_row = roth_limit_filtered.row(0, named=True) if len(roth_limit_filtered) else None
    roth_limit = (
        float(roth_limit_row["meta['roth']"])
        if roth_limit_row is not None
        and "meta['roth']" in roth_limit_row
        and roth_limit_row["meta['roth']"] is not None
        else None
    )
    roth_rows = []
    roth_total_amount = float(
        sum(item["amount"] for item in roth_filtered.iter_rows(named=True))
    )
    for roth_item in roth_filtered.iter_rows(named=True):
        roth_rows.append(
            {
                "Account": roth_item["account"],
                "Amount": roth_item["amount"],
                "Limit": roth_limit,
                "Remaining": roth_limit - float(roth_item["amount"]) if roth_limit is not None else None,
            }
        )
    roth_total_limit = roth_limit * 2 if roth_limit is not None else None
    roth_table_view = (
        bean_table(
            roth_rows,
            total_row={
                "Account": "TOTAL",
                "Amount": roth_total_amount,
                "Limit": roth_total_limit,
                "Remaining": roth_total_limit - roth_total_amount if roth_total_limit is not None else None,
            },
            cell_style_fn=cell_style,
            formatters={
                "Amount": format_amount,
                "Limit": format_amount,
                "Remaining": format_amount,
            },
        )
        if roth_rows
        else mo.vstack(
            [
                mo.md("No Roth contributions found for this year."),
                mo.md(
                    f"Individual contribution limit: {int(round(roth_limit)) if roth_limit is not None else 6000}."
                ),
            ]
        )
    )

    return mo.vstack(
        [
            mo.md("# Annual Contributions Tracker"),
            selected_year,
            mo.md("## Retirement Account Contributions"),
            retirement_table_view,
            mo.md("## HSA Contributions"),
            hsa_table_view,
            mo.md("## Roth (Backdoor)"),
            roth_table_view,
        ]
    )
