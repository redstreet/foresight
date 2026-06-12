#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "foresight_molab.py"
SAMPLE_LEDGER = ROOT / "examples" / "sample.beancount"

DEPENDENCIES = [
    "anywidget",
    "beancount",
    "beanquery",
    "marimo",
    "polars",
    "python-dateutil",
    "traitlets",
]

INLINE_FILES = [
    "common/libbeanmarimo.py",
    "common/shared.py",
    "modules/expenses/analysis.py",
    "modules/expenses/index.py",
    "modules/estate/ownership.py",
    "modules/estate/beneficiaries.py",
    "modules/estate/index.py",
    "modules/investments/account_types.py",
    "modules/investments/asset_allocation.py",
    "modules/investments/cash_drag.py",
    "modules/investments/growth.py",
    "modules/investments/index.py",
    "modules/retirement/contributions.py",
    "modules/retirement/index.py",
    "modules/taxes/gains_minimizer.py",
    "modules/taxes/index.py",
]

INLINE_EXPORTS = [
    ("common/libbeanmarimo.py", "table", "bean_table"),
    ("common/shared.py", "COMMON_TABLE_SECTION_STYLES", "COMMON_TABLE_SECTION_STYLES"),
    ("common/shared.py", "build_common_styles", "build_common_styles"),
    ("common/shared.py", "coerce_amount", "coerce_amount"),
    ("common/shared.py", "format_amount", "format_amount"),
    ("common/shared.py", "foresight_config_section", "foresight_config_section"),
    ("common/shared.py", "get_embedded_query", "get_embedded_query"),
    ("common/shared.py", "get_foresight_config", "get_foresight_config"),
    ("modules/estate/index.py", "build_estate_view", "build_estate_view"),
    ("modules/estate/ownership.py", "build_account_metadata_table", "build_account_metadata_table"),
    ("modules/estate/ownership.py", "build_account_tables", "build_account_tables"),
    ("modules/estate/ownership.py", "build_account_value_table", "build_account_value_table"),
    ("modules/estate/ownership.py", "build_ownership_view", "build_ownership_view"),
    ("modules/estate/beneficiaries.py", "build_beneficiaries_view", "build_beneficiaries_view"),
    ("modules/estate/beneficiaries.py", "build_beneficiary_tables", "build_beneficiary_tables"),
    ("modules/expenses/index.py", "build_expenses_domain_view", "build_expenses_domain_view"),
    ("modules/expenses/analysis.py", "build_analysis_view", "build_analysis_view"),
    ("modules/expenses/analysis.py", "build_controls", "build_expense_controls"),
    ("modules/expenses/analysis.py", "build_tree_data", "build_expense_tree_data"),
    ("modules/expenses/analysis.py", "build_expense_tree_widget_class", "build_expense_tree_widget_class"),
    ("modules/expenses/analysis.py", "default_controls", "default_expense_controls"),
    ("modules/expenses/analysis.py", "load_expense_tables", "load_expense_tables"),
    ("modules/investments/index.py", "build_investments_view", "build_investments_view"),
    ("modules/investments/asset_allocation.py", "ASSET_ALLOCATION_CONFIG", "ASSET_ALLOCATION_CONFIG"),
    ("modules/investments/asset_allocation.py", "TOTAL_PATH", "TOTAL_PATH"),
    ("modules/investments/asset_allocation.py", "build_asset_allocation_data", "build_asset_allocation_data"),
    ("modules/investments/asset_allocation.py", "build_asset_allocation_detail_widget_class", "build_asset_allocation_detail_widget_class"),
    ("modules/investments/asset_allocation.py", "build_asset_allocation_tree_widget_class", "build_asset_allocation_tree_widget_class"),
    ("modules/investments/asset_allocation.py", "build_asset_allocation_view", "build_asset_allocation_view"),
    ("modules/investments/asset_allocation.py", "detail_rows_for_class", "detail_rows_for_class"),
    ("modules/investments/asset_allocation.py", "tree_paths", "tree_paths"),
    ("modules/investments/cash_drag.py", "DEFAULT_CASH_DRAG_CONFIG", "DEFAULT_CASH_DRAG_CONFIG"),
    ("modules/investments/cash_drag.py", "build_cash_drag_table", "build_cash_drag_table"),
    ("modules/investments/cash_drag.py", "build_cash_drag_view", "build_cash_drag_view"),
    ("modules/investments/account_types.py", "DEFAULT_BREAKDOWN_CONFIG", "DEFAULT_BREAKDOWN_CONFIG"),
    ("modules/investments/account_types.py", "build_account_type_table", "build_account_type_table"),
    ("modules/investments/account_types.py", "build_account_types_view", "build_account_types_view"),
    ("modules/investments/account_types.py", "build_brokerage_table", "build_brokerage_table"),
    ("modules/retirement/index.py", "build_retirement_view", "build_retirement_view"),
    ("modules/retirement/contributions.py", "build_contributions_view", "build_contributions_view"),
    ("modules/retirement/contributions.py", "default_year", "default_contributions_year"),
    ("modules/retirement/contributions.py", "load_hsa_and_roth_tables", "load_hsa_and_roth_tables"),
    ("modules/retirement/contributions.py", "load_limit_tables", "load_limit_tables"),
    ("modules/retirement/contributions.py", "load_retirement_table", "load_retirement_table"),
    ("modules/taxes/index.py", "build_taxes_view", "build_taxes_view"),
    ("modules/taxes/gains_minimizer.py", "ACCOUNT_FIELD_OPTIONS", "ACCOUNT_FIELD_OPTIONS"),
    ("modules/taxes/gains_minimizer.py", "DEFAULT_GAINS_MINIMIZER_CONFIG", "DEFAULT_GAINS_MINIMIZER_CONFIG"),
    ("modules/taxes/gains_minimizer.py", "account_field_label", "account_field_label"),
    ("modules/taxes/gains_minimizer.py", "build_gains_minimizer_config", "build_gains_minimizer_config"),
    ("modules/taxes/gains_minimizer.py", "build_gains_minimizer_lots", "build_gains_minimizer_lots"),
    ("modules/taxes/gains_minimizer.py", "build_gains_minimizer_table_from_lots", "build_gains_minimizer_table_from_lots"),
    ("modules/taxes/gains_minimizer.py", "build_gains_minimizer_warnings", "build_gains_minimizer_warnings"),
    ("modules/taxes/gains_minimizer.py", "build_gains_minimizer_view", "build_gains_minimizer_view"),
]

INTERNAL_IMPORT_PREFIXES = (
    "from common.",
    "from modules.",
)


def build_artifact(output: Path = DEFAULT_OUTPUT) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    source = "\n\n".join(
        [
            build_header(),
            build_app_preamble(),
            build_app_source(),
        ]
    )
    output.write_text(source, encoding="utf-8")
    return output


def build_header() -> str:
    dependency_lines = "\n".join(f'#   "{dependency}",' for dependency in DEPENDENCIES)
    return f'''# /// script
# dependencies = [
{dependency_lines}
# ]
# ///
#
# Generated by scripts/build_molab.py. Do not edit by hand.
# Run with:
#   marimo run foresight_molab.py
# If BEANCOUNT_FILE is not set, this file writes and uses the bundled sample ledger.
'''


def build_inline_sources() -> str:
    source_entries = []
    for relative_path in INLINE_FILES:
        source = strip_relative_imports(
            (ROOT / relative_path).read_text(encoding="utf-8")
        ).rstrip()
        source_entries.append(f"        {relative_path!r}: {source!r},")

    export_lines = [
        (
            f"    {alias_name} = "
            f"__foresight_namespaces[{relative_path!r}][{source_name!r}]"
        )
        for relative_path, source_name, alias_name in INLINE_EXPORTS
    ]

    return "\n".join(
        [
            "    __foresight_sources = {",
            *source_entries,
            "    }",
            "    __foresight_namespaces = {}",
            "    for __foresight_name, __foresight_source in __foresight_sources.items():",
            "        __foresight_namespace = {'__name__': f'foresight_molab.{__foresight_name}'}",
            "        exec(__foresight_source, __foresight_namespace)",
            "        __foresight_namespaces[__foresight_name] = __foresight_namespace",
            "",
            *export_lines,
            "    del __foresight_name, __foresight_namespace, __foresight_namespaces, __foresight_source, __foresight_sources",
        ]
    )


def build_app_preamble() -> str:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    return "# ---- BEGIN app.py preamble ----\n" + app_preamble(source).rstrip()


def strip_relative_imports(source: str) -> str:
    return "\n".join(
        line for line in source.splitlines() if not line.startswith("from .")
    )


def build_app_source() -> str:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    source = app_cells(source)
    source = strip_internal_import_blocks(source)
    source = insert_inline_sources(source)
    source = add_sample_ledger_fallback(source)
    return "# ---- BEGIN app.py cells ----\n" + source.rstrip() + "\n# ---- END app.py ----\n"


def app_preamble(source: str) -> str:
    marker = "\n\n@app.cell"
    if marker not in source:
        raise ValueError("Could not find first marimo cell in app.py")
    return source.split(marker, 1)[0]


def app_cells(source: str) -> str:
    marker = "\n\n@app.cell"
    if marker not in source:
        raise ValueError("Could not find first marimo cell in app.py")
    return "@app.cell" + source.split(marker, 1)[1]


def insert_inline_sources(source: str) -> str:
    marker = "    return (\n        anywidget,"
    if marker not in source:
        raise ValueError("Could not find import cell return block in app.py")
    replacement = (
        "    # ---- BEGIN inlined project modules ----\n"
        f"{build_inline_sources()}\n"
        "    # ---- END inlined project modules ----\n\n"
        f"{marker}"
    )
    return source.replace(marker, replacement, 1)


def strip_internal_import_blocks(source: str) -> str:
    lines = source.splitlines()
    stripped = []
    skip_block = False

    for line in lines:
        stripped_line = line.lstrip()
        if skip_block:
            if stripped_line == ")":
                skip_block = False
            continue

        if stripped_line.startswith(INTERNAL_IMPORT_PREFIXES):
            if stripped_line.endswith("("):
                skip_block = True
            continue

        stripped.append(line)

    return "\n".join(stripped)


def add_sample_ledger_fallback(source: str) -> str:
    sample = SAMPLE_LEDGER.read_text(encoding="utf-8")
    original = '''    import os

    liability_community_property = "Community Prop"
    beancount_file = os.environ.get("BEANCOUNT_FILE", "").strip()
    if not beancount_file:
        beancount_error = "Environment variable `$BEANCOUNT_FILE` not set."
    elif not os.path.exists(beancount_file):
        beancount_error = f"File not found: `{beancount_file}`"
    else:
        beancount_error = ""'''
    replacement = f'''    import os
    from pathlib import Path

    sample_beancount = {sample!r}
    liability_community_property = "Community Prop"
    beancount_file = os.environ.get("BEANCOUNT_FILE", "").strip()
    if not beancount_file:
        sample_path = Path("/tmp/foresight_sample.beancount")
        sample_path.write_text(sample_beancount, encoding="utf-8")
        beancount_file = str(sample_path)
        beancount_error = ""
    elif not os.path.exists(beancount_file):
        beancount_error = f"File not found: `{{beancount_file}}`"
    else:
        beancount_error = ""'''
    if original not in source:
        raise ValueError("Could not find BEANCOUNT_FILE setup block in app.py")
    return source.replace(original, replacement, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a single-file Foresight artifact for molab.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output file path. Defaults to {DEFAULT_OUTPUT.relative_to(ROOT)}.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = build_artifact(args.output)
    print(output)


if __name__ == "__main__":
    main()
