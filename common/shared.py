import ast


COMMON_TABLE_SECTION_STYLES = """
.foresight-table-section > h2 {
  font-size: 1.5rem;
  line-height: 1.25;
  font-weight: 600;
  margin: 1rem 0 0.5rem;
}
"""


def format_amount(value, show_sign: bool = False) -> str:
    if value is None:
        return ""
    rounded = int(round(float(value)))
    if show_sign:
        sign = "+" if rounded >= 0 else "-"
        return f"{sign}{abs(rounded):,}"
    return f"{rounded:,}"


def coerce_amount(value) -> float:
    return 0.0 if value is None else float(value)


def build_common_styles(mo):
    return mo.Html(
        f"""
        <style>
        {COMMON_TABLE_SECTION_STYLES}
        </style>
        """
    )


def get_embedded_query(entries, mo, query_name: str) -> str:
    embedded_query = None

    for entry in entries:
        if entry.__class__.__name__ == "Query" and getattr(entry, "name", None) == query_name:
            for attribute_name in ("query_string", "query"):
                attribute_value = getattr(entry, attribute_name, None)
                if isinstance(attribute_value, str) and attribute_value.strip():
                    embedded_query = attribute_value.strip()
                    break
            if embedded_query is not None:
                break

    mo.stop(
        embedded_query is None,
        mo.md(f"**Error:** Embedded Beancount query `{query_name}` not found."),
    )
    return embedded_query


def get_foresight_config(entries, mo):
    config = {}

    for entry in entries:
        if entry.__class__.__name__ != "Custom":
            continue
        if getattr(entry, "type", None) != "foresight":
            continue

        values = []
        for value in getattr(entry, "values", []):
            values.append(getattr(value, "value", value))

        if len(values) < 2 or values[0] != "foresight":
            continue
        if not isinstance(values[1], str):
            continue

        try:
            parsed_config = ast.literal_eval(values[1])
        except (SyntaxError, ValueError) as exc:
            stop_with_error(mo, f"**Error:** Invalid foresight config: `{exc}`")
        config = parsed_config
        break

    if not isinstance(config, dict):
        stop_with_error(mo, "**Error:** foresight config must be a dict.")
    return config


def foresight_config_section(config, path, defaults, mo=None):
    section = config
    for part in path.split("."):
        if not isinstance(section, dict):
            stop_with_error(mo, f"**Error:** foresight config `{path}` must be a dict.")
        section = section.get(part, {})

    if section is None:
        section = {}
    if not isinstance(section, dict):
        stop_with_error(mo, f"**Error:** foresight config `{path}` must be a dict.")
    return {**defaults, **section}


def stop_with_error(mo, message):
    if mo is None:
        raise ValueError(message.replace("**Error:** ", ""))
    mo.stop(True, mo.md(message))
