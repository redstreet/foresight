from decimal import Decimal
from html import escape

import marimo as mo


def table(
    data,
    *args,
    total_row=None,
    total_position="bottom",
    cell_style_fn=None,
    column_labels=None,
    formatters=None,
    **kwargs,
):
    if total_row is None:
        return mo.ui.table(data, *args, **kwargs)

    rows, columns = _normalize_rows_and_columns(data, kwargs.get("columns"))
    total_row_dict = _normalize_total_row(total_row, columns)
    displayed_rows = list(rows)
    if total_position == "top":
        displayed_rows = [total_row_dict, *displayed_rows]
    else:
        displayed_rows = [*displayed_rows, total_row_dict]

    formatters = formatters or {}
    column_labels = column_labels or {}
    numeric_columns = _infer_numeric_columns(displayed_rows, columns)

    header_html = "".join(
        _header_cell(column_name, column_labels.get(column_name, column_name), column_name in numeric_columns)
        for column_name in columns
    )
    body_html = "".join(
        _render_row(
            row_dict,
            columns,
            cell_style_fn,
            numeric_columns,
            formatters,
            is_total=index == 0 if total_position == "top" else index == len(displayed_rows) - 1,
        )
        for index, row_dict in enumerate(displayed_rows)
    )

    return mo.Html(
        f"""
        <div style="width: fit-content; max-width: 100%;">
          <table style="border-collapse: collapse; font-size: 0.95rem;">
            <thead>
              <tr>{header_html}</tr>
            </thead>
            <tbody>
              {body_html}
            </tbody>
          </table>
        </div>
        """
    )


def _normalize_rows_and_columns(data, columns_override):
    if _is_polars_dataframe(data):
        columns = list(data.columns)
        rows = data.to_dicts()
    elif _is_pandas_dataframe(data):
        columns = list(data.columns)
        rows = data.to_dict(orient="records")
    elif isinstance(data, list):
        if not data:
            columns = list(columns_override or [])
            rows = []
        elif all(isinstance(item, dict) for item in data):
            columns = list(columns_override or data[0].keys())
            rows = [
                {column_name: item.get(column_name) for column_name in columns}
                for item in data
            ]
        else:
            columns = list(columns_override or [f"column_{idx + 1}" for idx in range(len(data[0]))])
            rows = [
                {
                    column_name: item[idx] if idx < len(item) else None
                    for idx, column_name in enumerate(columns)
                }
                for item in data
            ]
    elif isinstance(data, dict):
        columns = list(columns_override or data.keys())
        row_count = max((len(values) for values in data.values()), default=0)
        rows = []
        for row_index in range(row_count):
            rows.append(
                {
                    column_name: data.get(column_name, [None] * row_count)[row_index]
                    if row_index < len(data.get(column_name, []))
                    else None
                    for column_name in columns
                }
            )
    else:
        raise TypeError("Unsupported table data type for libbeanmarimo.table")

    return rows, columns


def _normalize_total_row(total_row, columns):
    if isinstance(total_row, dict):
        return {column_name: total_row.get(column_name) for column_name in columns}
    if isinstance(total_row, (list, tuple)):
        return {
            column_name: total_row[index] if index < len(total_row) else None
            for index, column_name in enumerate(columns)
        }
    raise TypeError("total_row must be a dict, list, or tuple")


def _infer_numeric_columns(rows, columns):
    numeric_columns = set()
    for column_name in columns:
        for row_dict in rows:
            value = row_dict.get(column_name)
            if value is None or value == "":
                continue
            if isinstance(value, bool):
                break
            if isinstance(value, (int, float, Decimal)):
                numeric_columns.add(column_name)
            break
    return numeric_columns


def _header_cell(column_name, label, is_numeric):
    padding = "0.35rem 0 0.35rem 2.5rem" if is_numeric else "0.35rem 2rem 0.35rem 0"
    align = "right" if is_numeric else "left"
    return (
        f'<th style="text-align: {align}; padding: {padding};">'
        f"{escape(str(label))}"
        "</th>"
    )


def _render_row(row_dict, columns, cell_style_fn, numeric_columns, formatters, is_total):
    row_style = ' style="background: rgba(128, 128, 128, 0.08); font-weight: 700;"' if is_total else ""
    cells_html = "".join(
        _render_cell(
            column_name,
            row_dict.get(column_name),
            cell_style_fn,
            column_name in numeric_columns,
            formatters.get(column_name),
            is_total,
        )
        for column_name in columns
    )
    return f"<tr{row_style}>{cells_html}</tr>"


def _render_cell(column_name, value, cell_style_fn, is_numeric, formatter, is_total):
    if value is None:
        text = ""
    elif formatter is not None:
        text = str(formatter(value))
    else:
        text = str(value)

    padding = "padding-left: 2.5rem;" if is_numeric else "padding-right: 2rem;"
    align = "right" if is_numeric else "left"
    nowrap = " white-space: nowrap;" if is_numeric else ""
    extra_style = cell_style_fn(column_name, value, is_total) if cell_style_fn is not None else ""
    extra_style = f" {extra_style}" if extra_style else ""
    return (
        f'<td style="text-align: {align};{nowrap} {padding}{extra_style}">'
        f"{escape(text)}"
        "</td>"
    )


def _is_polars_dataframe(data):
    return hasattr(data, "to_dicts") and hasattr(data, "columns")


def _is_pandas_dataframe(data):
    return hasattr(data, "to_dict") and hasattr(data, "columns")
