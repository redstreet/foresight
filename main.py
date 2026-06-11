import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import os

    liability_community_property = "Community Prop"
    beancount_file = os.environ.get("BEANCOUNT_FILE", "").strip()
    if not beancount_file:
        beancount_error = "Environment variable `$BEANCOUNT_FILE` not set."
    elif not os.path.exists(beancount_file):
        beancount_error = f"File not found: `{beancount_file}`"
    else:
        beancount_error = ""
    return beancount_error, beancount_file, liability_community_property


@app.cell(hide_code=True)
def _():
    from datetime import datetime
    from html import escape
    import json

    import anywidget
    import marimo as mo
    import polars as pl
    import traitlets
    from beancount.core import convert, prices, realization
    from beancount.loader import load_file
    from beancount.parser import printer
    from beanquery.query import run_query as run_bql_query
    from modules.estate import build_estate_view
    from modules.estate.ownership import (
        build_account_metadata_table,
        build_account_tables,
        build_account_value_table,
        build_ownership_view,
    )
    from modules.estate.beneficiaries import (
        build_beneficiaries_view,
        build_beneficiary_tables,
    )
    from modules.expenses import build_expenses_domain_view
    from modules.expenses.analysis import (
        build_analysis_view,
        build_controls as build_expense_controls,
        build_expense_tree_widget_class,
        build_tree_data as build_expense_tree_data,
        default_controls as default_expense_controls,
        load_expense_tables,
    )
    from modules.investments import build_investments_view
    from modules.investments.asset_allocation import (
        ASSET_ALLOCATION_CONFIG,
        build_asset_allocation_data,
        build_asset_allocation_detail_widget_class,
        build_asset_allocation_tree_widget_class,
        build_asset_allocation_view,
        detail_rows_for_class,
        tree_paths,
        TOTAL_PATH,
    )
    from modules.investments.cash_drag import (
        DEFAULT_CASH_DRAG_CONFIG,
        build_cash_drag_table,
        build_cash_drag_view,
    )
    from modules.investments.account_types import (
        DEFAULT_BREAKDOWN_CONFIG,
        build_account_type_table,
        build_account_types_view,
        build_brokerage_table,
    )
    from common.libbeanmarimo import table as bean_table
    from modules.retirement import build_retirement_view
    from modules.retirement.contributions import (
        build_contributions_view,
        default_year as default_contributions_year,
        load_hsa_and_roth_tables,
        load_limit_tables,
        load_retirement_table,
    )
    from common.shared import (
        COMMON_TABLE_SECTION_STYLES,
        build_common_styles,
        coerce_amount,
        format_amount,
        foresight_config_section,
        get_embedded_query,
        get_foresight_config,
    )
    from modules.taxes import build_taxes_view
    from modules.taxes.gains_minimizer import (
        ACCOUNT_FIELD_OPTIONS,
        DEFAULT_GAINS_MINIMIZER_CONFIG,
        account_field_label,
        build_gains_minimizer_config,
        build_gains_minimizer_lots,
        build_gains_minimizer_table_from_lots,
        build_gains_minimizer_warnings,
        build_gains_minimizer_view,
    )

    return (
        anywidget,
        ASSET_ALLOCATION_CONFIG,
        ACCOUNT_FIELD_OPTIONS,
        account_field_label,
        bean_table,
        build_account_metadata_table,
        build_account_tables,
        build_account_value_table,
        build_analysis_view,
        build_account_type_table,
        build_account_types_view,
        build_beneficiaries_view,
        build_beneficiary_tables,
        build_brokerage_table,
        build_contributions_view,
        build_estate_view,
        build_expense_controls,
        build_expense_tree_data,
        build_expense_tree_widget_class,
        build_expenses_domain_view,
        build_asset_allocation_data,
        build_asset_allocation_detail_widget_class,
        build_asset_allocation_tree_widget_class,
        build_asset_allocation_view,
        build_cash_drag_table,
        build_cash_drag_view,
        build_common_styles,
        COMMON_TABLE_SECTION_STYLES,
        build_gains_minimizer_config,
        build_gains_minimizer_lots,
        build_gains_minimizer_table_from_lots,
        build_gains_minimizer_warnings,
        build_gains_minimizer_view,
        build_investments_view,
        build_ownership_view,
        build_retirement_view,
        build_taxes_view,
        coerce_amount,
        convert,
        datetime,
        DEFAULT_BREAKDOWN_CONFIG,
        DEFAULT_CASH_DRAG_CONFIG,
        DEFAULT_GAINS_MINIMIZER_CONFIG,
        default_contributions_year,
        default_expense_controls,
        detail_rows_for_class,
        escape,
        format_amount,
        foresight_config_section,
        get_embedded_query,
        get_foresight_config,
        json,
        load_expense_tables,
        load_file,
        load_hsa_and_roth_tables,
        load_limit_tables,
        load_retirement_table,
        mo,
        pl,
        prices,
        printer,
        realization,
        run_bql_query,
        TOTAL_PATH,
        tree_paths,
        traitlets,
    )


@app.cell(hide_code=True)
def _(mo):
    top_level_tabs = mo.ui.tabs(
        {
            "Retirement": "",
            "Investments": "",
            "Estate": "",
            "Taxes": "",
            "Expenses": "",
        },
        value="Investments",
    )
    return (top_level_tabs,)


@app.cell(hide_code=True)
def _(top_level_tabs):
    active_top_level_tab = top_level_tabs.value
    return (active_top_level_tab,)


@app.cell(hide_code=True)
def _(beancount_error, beancount_file, load_file, mo, printer):
    mo.stop(
        bool(beancount_error),
        mo.md(f"**Error:** {beancount_error}"),
    )
    entries, errors, options = load_file(beancount_file)
    printer.print_errors(errors)
    return entries, options


@app.cell(hide_code=True)
def _(entries, options, pl, run_bql_query):
    def run_query(query: str):
        cols, rows = run_bql_query(entries, options, query, numberify=True)
        return pl.DataFrame(
            schema=[col.name for col in cols],
            data=rows,
            orient="row",
            infer_schema_length=None,
        )

    return (run_query,)


@app.cell(hide_code=True)
def _(entries, get_embedded_query, mo):
    def embedded_query(query_name: str) -> str:
        return get_embedded_query(entries, mo, query_name)

    return (embedded_query,)


# -------------------------------------------------------------
# Investments / Account Types
# -------------------------------------------------------------


@app.cell(hide_code=True)
def _(
    build_account_type_table,
    convert,
    entries,
    options,
    pl,
    prices,
    realization,
):
    investment_account_type_table = build_account_type_table(
        convert,
        entries,
        options,
        pl,
        prices,
        realization,
    )
    return (investment_account_type_table,)


@app.cell(hide_code=True)
def _(entries, get_foresight_config, mo):
    foresight_config = get_foresight_config(entries, mo)
    return (foresight_config,)


@app.cell(hide_code=True)
def _(DEFAULT_BREAKDOWN_CONFIG, foresight_config, foresight_config_section, mo):
    investment_breakdown_config = foresight_config_section(
        foresight_config,
        "investments.breakdown",
        DEFAULT_BREAKDOWN_CONFIG,
        mo,
    )
    return (investment_breakdown_config,)


@app.cell(hide_code=True)
def _(
    build_brokerage_table,
    convert,
    entries,
    investment_breakdown_config,
    options,
    pl,
    prices,
    realization,
):
    investment_brokerage_table = build_brokerage_table(
        investment_breakdown_config,
        convert,
        entries,
        options,
        pl,
        prices,
        realization,
    )
    return (investment_brokerage_table,)


@app.cell(hide_code=True)
def _(
    build_account_types_view,
    COMMON_TABLE_SECTION_STYLES,
    escape,
    format_amount,
    investment_account_type_table,
    investment_brokerage_table,
    mo,
):
    investment_account_types_view = build_account_types_view(
        investment_account_type_table,
        investment_brokerage_table,
        COMMON_TABLE_SECTION_STYLES,
        escape,
        format_amount,
        mo,
    )
    return (investment_account_types_view,)


# -------------------------------------------------------------
# Investments / Asset Allocation
# -------------------------------------------------------------


@app.cell(hide_code=True)
def _(ASSET_ALLOCATION_CONFIG, foresight_config, foresight_config_section, mo):
    asset_allocation_initial_config = foresight_config_section(
        foresight_config,
        "investments.asset_allocation",
        ASSET_ALLOCATION_CONFIG,
        mo,
    )
    return (asset_allocation_initial_config,)


@app.cell(hide_code=True)
def _(asset_allocation_initial_config, mo):
    asset_allocation_account_pattern = mo.ui.text(
        value=asset_allocation_initial_config["accounts_pattern"],
        debounce=500,
        full_width=True,
    )
    asset_allocation_tax_adjustment = mo.ui.switch(
        value=bool(asset_allocation_initial_config["tax_adjustment"])
    )
    return asset_allocation_account_pattern, asset_allocation_tax_adjustment


@app.cell(hide_code=True)
def _(asset_allocation_account_pattern, asset_allocation_tax_adjustment):
    asset_allocation_config = {
        "accounts_pattern": asset_allocation_account_pattern.value,
        "tax_adjustment": asset_allocation_tax_adjustment.value,
    }
    return (asset_allocation_config,)


@app.cell(hide_code=True)
def _(
    asset_allocation_config,
    build_asset_allocation_data,
    convert,
    entries,
    options,
    prices,
    realization,
):
    asset_allocation_data = build_asset_allocation_data(
        convert,
        entries,
        options,
        prices,
        realization,
        asset_allocation_config,
    )
    return (asset_allocation_data,)


@app.cell(hide_code=True)
def _(anywidget, build_asset_allocation_tree_widget_class, traitlets):
    AssetAllocationTreeWidget = build_asset_allocation_tree_widget_class(
        anywidget,
        traitlets,
    )
    return (AssetAllocationTreeWidget,)


@app.cell(hide_code=True)
def _(anywidget, build_asset_allocation_detail_widget_class, traitlets):
    AssetAllocationDetailWidget = build_asset_allocation_detail_widget_class(
        anywidget,
        traitlets,
    )
    return (AssetAllocationDetailWidget,)


@app.cell(hide_code=True)
def _(AssetAllocationTreeWidget, TOTAL_PATH):
    asset_allocation_tree_widget = AssetAllocationTreeWidget(
        tree_json="{}",
        expanded=[TOTAL_PATH],
        value=TOTAL_PATH,
    )
    return (asset_allocation_tree_widget,)


@app.cell(hide_code=True)
def _(AssetAllocationDetailWidget, TOTAL_PATH):
    asset_allocation_detail_widget = AssetAllocationDetailWidget(
        tree_json="{}",
        expanded=[TOTAL_PATH],
    )
    return (asset_allocation_detail_widget,)


@app.cell(hide_code=True)
def _(asset_allocation_data, asset_allocation_tree_widget, json, mo, tree_paths):
    asset_allocation_tree_widget.tree_json = json.dumps(
        asset_allocation_data["class_tree"]
    )
    asset_allocation_tree_widget.expanded = tree_paths(
        asset_allocation_data["class_tree"]
    )
    asset_allocation_tree = mo.ui.anywidget(asset_allocation_tree_widget)
    return (asset_allocation_tree,)


@app.cell(hide_code=True)
def _(TOTAL_PATH, asset_allocation_tree):
    raw_asset_allocation_selected_class = asset_allocation_tree.value
    if isinstance(raw_asset_allocation_selected_class, dict):
        asset_allocation_selected_class = (
            raw_asset_allocation_selected_class.get("value")
            or raw_asset_allocation_selected_class.get("path")
            or TOTAL_PATH
        )
    elif isinstance(raw_asset_allocation_selected_class, str):
        asset_allocation_selected_class = raw_asset_allocation_selected_class
    else:
        asset_allocation_selected_class = TOTAL_PATH
    return (asset_allocation_selected_class,)


@app.cell(hide_code=True)
def _(
    asset_allocation_data,
    asset_allocation_detail_widget,
    asset_allocation_selected_class,
    detail_rows_for_class,
    json,
    mo,
    tree_paths,
):
    asset_allocation_detail_tree_data, _ = detail_rows_for_class(
        asset_allocation_data["contributions"],
        asset_allocation_selected_class,
    )
    asset_allocation_detail_widget.tree_json = json.dumps(
        asset_allocation_detail_tree_data
    )
    asset_allocation_detail_widget.expanded = tree_paths(
        asset_allocation_detail_tree_data
    )
    asset_allocation_detail_tree = mo.ui.anywidget(asset_allocation_detail_widget)
    return (asset_allocation_detail_tree,)


@app.cell(hide_code=True)
def _(
    asset_allocation_data,
    asset_allocation_account_pattern,
    asset_allocation_detail_tree,
    asset_allocation_selected_class,
    asset_allocation_tax_adjustment,
    asset_allocation_tree,
    build_asset_allocation_view,
    escape,
    format_amount,
    mo,
):
    asset_allocation_view = build_asset_allocation_view(
        asset_allocation_data,
        asset_allocation_account_pattern,
        asset_allocation_tax_adjustment,
        escape,
        format_amount,
        mo,
        asset_allocation_selected_class,
        asset_allocation_detail_tree,
        asset_allocation_tree,
    )
    return (asset_allocation_view,)


# -------------------------------------------------------------
# Investments / Cash Drag
# -------------------------------------------------------------


@app.cell(hide_code=True)
def _(DEFAULT_CASH_DRAG_CONFIG, foresight_config, foresight_config_section, mo):
    cash_drag_config = foresight_config_section(
        foresight_config,
        "investments.cash_drag",
        DEFAULT_CASH_DRAG_CONFIG,
        mo,
    )
    return (cash_drag_config,)


@app.cell(hide_code=True)
def _(
    build_cash_drag_table,
    cash_drag_config,
    convert,
    entries,
    options,
    pl,
    prices,
    realization,
):
    cash_drag_table = build_cash_drag_table(
        cash_drag_config,
        convert,
        entries,
        options,
        pl,
        prices,
        realization,
    )
    return (cash_drag_table,)


@app.cell(hide_code=True)
def _(build_cash_drag_view, cash_drag_table, escape, format_amount, mo):
    cash_drag_view = build_cash_drag_view(
        cash_drag_table,
        escape,
        format_amount,
        mo,
    )
    return (cash_drag_view,)


@app.cell(hide_code=True)
def _(
    asset_allocation_view,
    build_investments_view,
    cash_drag_view,
    investment_account_types_view,
    mo,
):
    investments_view = build_investments_view(
        mo,
        investment_account_types_view,
        asset_allocation_view,
        cash_drag_view,
    )
    return (investments_view,)


# -------------------------------------------------------------
# Estate / Ownership
# -------------------------------------------------------------


@app.cell(hide_code=True)
def _(build_account_metadata_table, entries, liability_community_property, pl):
    ownership_account_metadata_table = build_account_metadata_table(
        entries,
        liability_community_property,
        pl,
    )
    return (ownership_account_metadata_table,)


@app.cell(hide_code=True)
def _(
    build_account_value_table,
    convert,
    entries,
    ownership_account_metadata_table,
    pl,
    prices,
    realization,
):
    ownership_account_value_table = build_account_value_table(
        ownership_account_metadata_table,
        convert,
        entries,
        pl,
        prices,
        realization,
    )
    return (ownership_account_value_table,)


@app.cell(hide_code=True)
def _(
    build_account_tables,
    ownership_account_metadata_table,
    ownership_account_value_table,
    pl,
):
    ownership_accounts_table, ownership_summary_table = build_account_tables(
        ownership_account_metadata_table,
        ownership_account_value_table,
        pl,
    )
    return ownership_accounts_table, ownership_summary_table


@app.cell(hide_code=True)
def _(
    build_ownership_view,
    escape,
    format_amount,
    mo,
    ownership_accounts_table,
    ownership_summary_table,
    pl,
):
    ownership_view = build_ownership_view(
        ownership_accounts_table,
        ownership_summary_table,
        escape,
        format_amount,
        mo,
        pl,
    )
    return (ownership_view,)


@app.cell(hide_code=True)
def _(
    build_beneficiary_tables,
    convert,
    entries,
    pl,
    prices,
    realization,
):
    beneficiary_tables = build_beneficiary_tables(
        convert,
        entries,
        pl,
        prices,
        realization,
    )
    return (beneficiary_tables,)


@app.cell(hide_code=True)
def _(
    beneficiary_tables,
    build_beneficiaries_view,
    COMMON_TABLE_SECTION_STYLES,
    escape,
    format_amount,
    mo,
):
    beneficiaries_view = build_beneficiaries_view(
        beneficiary_tables,
        COMMON_TABLE_SECTION_STYLES,
        escape,
        format_amount,
        mo,
    )
    return (beneficiaries_view,)


@app.cell(hide_code=True)
def _(beneficiaries_view, build_estate_view, mo, ownership_view):
    estate_view = build_estate_view(mo, beneficiaries_view, ownership_view)
    return (estate_view,)


# -------------------------------------------------------------
# Retirement / Contributions
# -------------------------------------------------------------


@app.cell(hide_code=True)
def _():
    retirement_tables_cache = {}
    return (retirement_tables_cache,)


@app.cell(hide_code=True)
def _(active_top_level_tab, load_retirement_table, pl, retirement_tables_cache, run_query):
    if active_top_level_tab == "Retirement" and "retirement_table" not in retirement_tables_cache:
        retirement_tables_cache["retirement_table"] = load_retirement_table(run_query)
    if "retirement_table" in retirement_tables_cache:
        contributions_retirement_table = retirement_tables_cache["retirement_table"]
    else:
        contributions_retirement_table = pl.DataFrame(
            schema={"year": pl.Int64, "account": pl.Utf8, "amount": pl.Float64}
        )
    return (contributions_retirement_table,)


@app.cell(hide_code=True)
def _(
    active_top_level_tab,
    embedded_query,
    entries,
    load_hsa_and_roth_tables,
    options,
    pl,
    retirement_tables_cache,
    run_bql_query,
):
    if active_top_level_tab == "Retirement" and "hsa_and_roth_tables" not in retirement_tables_cache:
        retirement_tables_cache["hsa_and_roth_tables"] = load_hsa_and_roth_tables(
            entries,
            embedded_query,
            options,
            pl,
            run_bql_query,
        )
    if "hsa_and_roth_tables" in retirement_tables_cache:
        (
            contributions_employer_hsa_table,
            contributions_personal_hsa_table,
            contributions_roth_backdoor_table,
        ) = retirement_tables_cache["hsa_and_roth_tables"]
    else:
        contributions_employer_hsa_table = pl.DataFrame(
            schema={"year": pl.Int64, "account": pl.Utf8, "amount": pl.Float64}
        )
        contributions_personal_hsa_table = pl.DataFrame(
            schema={"year": pl.Int64, "amount": pl.Float64}
        )
        contributions_roth_backdoor_table = pl.DataFrame(
            schema={"year": pl.Int64, "account": pl.Utf8, "amount": pl.Float64}
        )
    return (
        contributions_employer_hsa_table,
        contributions_personal_hsa_table,
        contributions_roth_backdoor_table,
    )


@app.cell(hide_code=True)
def _(active_top_level_tab, load_limit_tables, pl, retirement_tables_cache, run_query):
    if active_top_level_tab == "Retirement" and "limit_tables" not in retirement_tables_cache:
        retirement_tables_cache["limit_tables"] = load_limit_tables(run_query)
    if "limit_tables" in retirement_tables_cache:
        (
            contributions_hsa_limits_table,
            contributions_raw_limits_table,
            contributions_roth_limits_table,
        ) = retirement_tables_cache["limit_tables"]
    else:
        contributions_hsa_limits_table = pl.DataFrame(
            schema={"year": pl.Int64, "meta['hsa-limit']": pl.Float64}
        )
        contributions_raw_limits_table = pl.DataFrame(
            schema={
                "year": pl.Int64,
                "meta['after-tax']": pl.Float64,
                "meta['pretax-401k-employee']": pl.Float64,
                "meta['pretax-401k-match']": pl.Float64,
                "meta['total-limit']": pl.Float64,
            }
        )
        contributions_roth_limits_table = pl.DataFrame(
            schema={"year": pl.Int64, "meta['roth']": pl.Float64}
        )
    return (
        contributions_hsa_limits_table,
        contributions_raw_limits_table,
        contributions_roth_limits_table,
    )


@app.cell(hide_code=True)
def _(contributions_retirement_table, default_contributions_year, datetime, mo):
    contributions_year_options, contributions_default_year = default_contributions_year(
        contributions_retirement_table,
        datetime,
    )
    contributions_selected_year = mo.ui.dropdown(
        options=contributions_year_options,
        value=contributions_default_year,
        label="",
        full_width=False,
    )
    return (contributions_selected_year,)


@app.cell(hide_code=True)
def _(
    active_top_level_tab,
    bean_table,
    build_contributions_view,
    contributions_employer_hsa_table,
    contributions_hsa_limits_table,
    contributions_personal_hsa_table,
    contributions_raw_limits_table,
    contributions_retirement_table,
    contributions_roth_backdoor_table,
    contributions_roth_limits_table,
    contributions_selected_year,
    format_amount,
    mo,
    pl,
):
    if active_top_level_tab == "Retirement":
        contributions_view = build_contributions_view(
            bean_table,
            contributions_employer_hsa_table,
            format_amount,
            contributions_hsa_limits_table,
            mo,
            contributions_personal_hsa_table,
            pl,
            contributions_raw_limits_table,
            contributions_retirement_table,
            contributions_roth_backdoor_table,
            contributions_roth_limits_table,
            contributions_selected_year,
        )
    else:
        contributions_view = mo.md("")
    return (contributions_view,)


@app.cell(hide_code=True)
def _(build_retirement_view, contributions_view, mo):
    retirement_view = build_retirement_view(mo, contributions_view)
    return (retirement_view,)


# -------------------------------------------------------------
# Expenses / Analysis
# -------------------------------------------------------------


@app.cell(hide_code=True)
def _(load_expense_tables, run_query):
    expense_summary_df, expense_transactions_df = load_expense_tables(run_query)
    return expense_summary_df, expense_transactions_df


@app.cell(hide_code=True)
def _(anywidget, build_expense_tree_widget_class, traitlets):
    ExpenseTreeWidget = build_expense_tree_widget_class(anywidget, traitlets)
    return (ExpenseTreeWidget,)


@app.cell(hide_code=True)
def _(default_expense_controls, expense_summary_df):
    (
        expense_categories,
        expense_default_excluded,
        expense_default_left_year,
        expense_default_right_year,
        expense_year_options,
    ) = default_expense_controls(expense_summary_df)
    return (
        expense_categories,
        expense_default_excluded,
        expense_default_left_year,
        expense_default_right_year,
        expense_year_options,
    )


@app.cell(hide_code=True)
def _(
    build_expense_controls,
    expense_categories,
    expense_default_excluded,
    expense_default_left_year,
    expense_default_right_year,
    expense_year_options,
    mo,
):
    (
        expense_controls,
        expense_exclude_categories,
        expense_invert_categories,
        expense_left_year,
        expense_right_year,
    ) = build_expense_controls(
        expense_categories,
        expense_default_excluded,
        expense_default_left_year,
        expense_default_right_year,
        mo,
        expense_year_options,
    )
    return (
        expense_controls,
        expense_exclude_categories,
        expense_invert_categories,
        expense_left_year,
        expense_right_year,
    )


@app.cell(hide_code=True)
def _(
    build_expense_tree_data,
    coerce_amount,
    expense_exclude_categories,
    expense_invert_categories,
    expense_left_year,
    expense_right_year,
    expense_summary_df,
):
    (
        expense_leaf_accounts,
        expense_left_year_value,
        expense_right_year_value,
        expense_tree_data,
    ) = build_expense_tree_data(
        coerce_amount,
        expense_exclude_categories,
        expense_invert_categories,
        expense_left_year,
        expense_right_year,
        expense_summary_df,
    )
    return (
        expense_leaf_accounts,
        expense_left_year_value,
        expense_right_year_value,
        expense_tree_data,
    )


@app.cell(hide_code=True)
def _(ExpenseTreeWidget):
    expense_tree_widget = ExpenseTreeWidget(
        tree_json="[]",
        left_label="",
        right_label="",
        expanded=[],
        value="",
    )
    return (expense_tree_widget,)


@app.cell(hide_code=True)
def _(
    expense_left_year_value,
    expense_right_year_value,
    expense_tree_data,
    expense_tree_widget,
    json,
    mo,
):
    expense_tree_widget.tree_json = json.dumps(expense_tree_data)
    expense_tree_widget.left_label = expense_left_year_value
    expense_tree_widget.right_label = expense_right_year_value
    expense_tree_widget.expanded = []
    expense_tree_widget.value = ""
    expense_tree = mo.ui.anywidget(expense_tree_widget)
    return (expense_tree,)


@app.cell(hide_code=True)
def _(expense_tree):
    raw_expense_selected_account = expense_tree.value
    if isinstance(raw_expense_selected_account, dict):
        expense_selected_account = (
            raw_expense_selected_account.get("value")
            or raw_expense_selected_account.get("path")
            or ""
        )
    elif isinstance(raw_expense_selected_account, str):
        expense_selected_account = raw_expense_selected_account
    else:
        expense_selected_account = ""
    return (expense_selected_account,)


@app.cell(hide_code=True)
def _(
    build_analysis_view,
    coerce_amount,
    escape,
    expense_controls,
    expense_leaf_accounts,
    expense_left_year,
    expense_left_year_value,
    expense_right_year,
    expense_right_year_value,
    expense_selected_account,
    expense_transactions_df,
    expense_tree,
    format_amount,
    mo,
):
    expense_analysis_view = build_analysis_view(
        coerce_amount,
        expense_controls,
        escape,
        format_amount,
        expense_leaf_accounts,
        expense_left_year,
        expense_left_year_value,
        mo,
        expense_right_year,
        expense_right_year_value,
        expense_selected_account,
        expense_transactions_df,
        expense_tree,
    )
    return (expense_analysis_view,)


@app.cell(hide_code=True)
def _(build_expenses_domain_view, expense_analysis_view, mo):
    expenses_view = build_expenses_domain_view(mo, expense_analysis_view)
    return (expenses_view,)


# -------------------------------------------------------------
# Taxes
# -------------------------------------------------------------


@app.cell(hide_code=True)
def _(DEFAULT_GAINS_MINIMIZER_CONFIG, foresight_config, foresight_config_section, mo):
    gains_minimizer_initial_config = foresight_config_section(
        foresight_config,
        "taxes.gains_minimizer",
        DEFAULT_GAINS_MINIMIZER_CONFIG,
        mo,
    )
    return (gains_minimizer_initial_config,)


@app.cell(hide_code=True)
def _(ACCOUNT_FIELD_OPTIONS, account_field_label, gains_minimizer_initial_config, mo):
    gains_minimizer_accounts_pattern = mo.ui.text(
        value=gains_minimizer_initial_config["accounts_pattern"],
        debounce=500,
        full_width=True,
    )
    gains_minimizer_currency = mo.ui.text(
        value=gains_minimizer_initial_config["currency"],
        debounce=500,
    )
    gains_minimizer_account_field = mo.ui.dropdown(
        options=list(ACCOUNT_FIELD_OPTIONS),
        value=account_field_label(gains_minimizer_initial_config["account_field"]),
    )
    gains_minimizer_st_tax_rate = mo.ui.number(
        start=0,
        stop=100,
        step=0.1,
        value=gains_minimizer_initial_config["st_tax_rate"],
    )
    gains_minimizer_lt_tax_rate = mo.ui.number(
        start=0,
        stop=100,
        step=0.1,
        value=gains_minimizer_initial_config["lt_tax_rate"],
    )
    return (
        gains_minimizer_account_field,
        gains_minimizer_accounts_pattern,
        gains_minimizer_currency,
        gains_minimizer_lt_tax_rate,
        gains_minimizer_st_tax_rate,
    )


@app.cell(hide_code=True)
def _(
    build_gains_minimizer_config,
    gains_minimizer_account_field,
    gains_minimizer_accounts_pattern,
    gains_minimizer_currency,
    gains_minimizer_lt_tax_rate,
    gains_minimizer_st_tax_rate,
):
    gains_minimizer_config = build_gains_minimizer_config(
        gains_minimizer_accounts_pattern.value,
        gains_minimizer_account_field.value,
        gains_minimizer_currency.value,
        gains_minimizer_st_tax_rate.value,
        gains_minimizer_lt_tax_rate.value,
    )
    return (gains_minimizer_config,)


@app.cell(hide_code=True)
def _(
    build_gains_minimizer_lots,
    entries,
    gains_minimizer_config,
    options,
    run_bql_query,
):
    gains_minimizer_lots = build_gains_minimizer_lots(
        gains_minimizer_config,
        entries,
        options,
        run_bql_query,
    )
    return (gains_minimizer_lots,)


@app.cell(hide_code=True)
def _(
    build_gains_minimizer_table_from_lots,
    gains_minimizer_config,
    gains_minimizer_lots,
    pl,
):
    gains_minimizer_table = build_gains_minimizer_table_from_lots(
        gains_minimizer_config,
        gains_minimizer_lots,
        pl,
    )
    return (gains_minimizer_table,)


@app.cell(hide_code=True)
def _(
    build_gains_minimizer_warnings,
    gains_minimizer_config,
    gains_minimizer_lots,
):
    gains_minimizer_warnings = build_gains_minimizer_warnings(
        gains_minimizer_config,
        gains_minimizer_lots,
    )
    return (gains_minimizer_warnings,)


@app.cell(hide_code=True)
def _(
    build_gains_minimizer_view,
    format_amount,
    gains_minimizer_account_field,
    gains_minimizer_accounts_pattern,
    gains_minimizer_currency,
    gains_minimizer_lt_tax_rate,
    gains_minimizer_st_tax_rate,
    gains_minimizer_table,
    gains_minimizer_warnings,
    mo,
):
    gains_minimizer_view = build_gains_minimizer_view(
        [
            mo.vstack(
                [mo.md("**Account regex**"), gains_minimizer_accounts_pattern],
                gap=0.15,
            ),
            mo.vstack(
                [mo.md("**Account field**"), gains_minimizer_account_field],
                gap=0.15,
            ),
            mo.vstack(
                [mo.md("**Currency**"), gains_minimizer_currency],
                gap=0.15,
            ),
            mo.vstack(
                [mo.md("**Short-term tax rate (%)**"), gains_minimizer_st_tax_rate],
                gap=0.15,
            ),
            mo.vstack(
                [mo.md("**Long-term tax rate (%)**"), gains_minimizer_lt_tax_rate],
                gap=0.15,
            ),
        ],
        gains_minimizer_table,
        gains_minimizer_warnings,
        format_amount,
        mo,
    )
    return (gains_minimizer_view,)


@app.cell(hide_code=True)
def _(build_taxes_view, gains_minimizer_view, mo):
    taxes_view = build_taxes_view(mo, gains_minimizer_view)
    return (taxes_view,)


@app.cell(hide_code=True)
def _(build_common_styles, mo):
    common_styles = build_common_styles(mo)
    return (common_styles,)


@app.cell(hide_code=True)
def _(
    active_top_level_tab,
    common_styles,
    estate_view,
    expenses_view,
    investments_view,
    mo,
    retirement_view,
    taxes_view,
    top_level_tabs,
):
    selected_domain_view = {
        "Retirement": retirement_view,
        "Investments": investments_view,
        "Estate": estate_view,
        "Taxes": taxes_view,
        "Expenses": expenses_view,
    }.get(active_top_level_tab, investments_view)
    mo.vstack(
        [
            common_styles,
            top_level_tabs,
            selected_domain_view,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
