from collections import defaultdict
from decimal import Decimal
import re


META_PREFIX = "asset_allocation_"
UNKNOWN_CLASS = "unknown"
TOTAL_PATH = "__total__"
ASSET_ALLOCATION_CONFIG = {
    "accounts_pattern": "^Assets:Investments",
    "tax_adjustment": False,
}


def normalize_config(config=None):
    config = ASSET_ALLOCATION_CONFIG if config is None else config
    accounts_patterns = config.get(
        "accounts_patterns",
        config.get("accounts_pattern", [".*"]),
    )
    if isinstance(accounts_patterns, str):
        accounts_patterns = [accounts_patterns]
    return {
        "accounts_patterns": list(accounts_patterns or [".*"]),
        "skip_tax_adjustment": not bool(config.get("tax_adjustment", False)),
    }


def build_asset_allocation_data(
    convert,
    entries,
    options,
    prices,
    realization,
    config=None,
):
    normalized_config = normalize_config(config)
    base_currency = operating_currencies(options)[0]
    price_map = prices.build_price_map(entries)
    commodity_meta = commodity_metadata(entries)
    tax_adjustments = account_tax_adjustments(entries)
    end_date = latest_entry_date(entries)
    real_accounts = realization.realize(entries)

    contributions = []
    warnings = []

    for real_account in realization.iter_children(real_accounts):
        account_name = real_account.account
        if not included_account(account_name, normalized_config["accounts_patterns"]):
            continue
        if real_account.balance.is_empty():
            continue

        tax_factor = Decimal("1")
        if not normalized_config["skip_tax_adjustment"]:
            tax_factor = tax_adjustment_for_account(account_name, tax_adjustments)

        for position in real_account.balance.get_positions():
            units = convert.get_units(position)
            if units.number < 0:
                warnings.append(f"Skipping negative balance in {account_name}: {units}")
                continue

            scaled_position = position
            if tax_factor != Decimal("1"):
                scaled_position = position * tax_factor

            converted_amount = convert_position_to_base(
                scaled_position,
                base_currency,
                convert,
                end_date,
                operating_currencies(options),
                price_map,
            )
            if converted_amount is None:
                warnings.append(
                    f"Unable to convert {units} in {account_name} to {base_currency}."
                )
                continue

            commodity = units.currency
            allocations = allocations_for_commodity(commodity, commodity_meta, warnings)
            full_value = converted_amount.number
            for class_path, percentage in allocations:
                amount = full_value * percentage / Decimal("100")
                if amount == 0:
                    continue
                contributions.append(
                    {
                        "account": account_name,
                        "commodity": commodity,
                        "class_path": class_path,
                        "amount": amount,
                        "full_value": full_value,
                        "units": units.number,
                    }
                )

    class_tree = build_class_tree(contributions)
    return {
        "base_currency": base_currency,
        "class_tree": class_tree,
        "config": normalized_config,
        "contributions": contributions,
        "warnings": unique_preserve_order(warnings),
    }


def operating_currencies(options):
    currencies = options.get("operating_currency", None) if isinstance(options, dict) else None
    if currencies:
        return list(currencies)
    return ["USD"]


def latest_entry_date(entries):
    dates = [getattr(entry, "date", None) for entry in entries if getattr(entry, "date", None)]
    return max(dates) if dates else None


def commodity_metadata(entries):
    metadata = {}
    for entry in entries:
        if entry.__class__.__name__ == "Commodity":
            metadata[entry.currency] = entry.meta
    return metadata


def account_tax_adjustments(entries):
    adjustments = {}
    for entry in entries:
        if entry.__class__.__name__ != "Open":
            continue
        value = entry.meta.get("asset_allocation_tax_adjustment")
        if value is None:
            continue
        adjustments[entry.account] = Decimal(value) / Decimal("100")
    return adjustments


def tax_adjustment_for_account(account_name, tax_adjustments):
    parts = account_name.split(":")
    for index in range(len(parts), 0, -1):
        candidate = ":".join(parts[:index])
        if candidate in tax_adjustments:
            return tax_adjustments[candidate]
    return Decimal("1")


def included_account(account_name, patterns):
    return any(re.match(pattern, account_name) for pattern in patterns)


def convert_position_to_base(
    position,
    base_currency,
    convert,
    end_date,
    operating_currency_list,
    price_map,
):
    try:
        converted = convert.convert_position(
            position,
            base_currency,
            price_map,
            date=end_date,
        )
    except TypeError:
        converted = convert.convert_position(position, base_currency, price_map)

    amount = amount_from_converted(converted)
    if amount is not None and amount.currency == base_currency:
        return amount

    units = convert.get_units(position)
    try:
        converted_amount = convert.convert_amount(
            units,
            base_currency,
            price_map,
            via=operating_currency_list,
            date=end_date,
        )
    except TypeError:
        converted_amount = convert.convert_amount(
            units,
            base_currency,
            price_map,
            via=operating_currency_list,
        )
    if converted_amount.currency == base_currency:
        return converted_amount
    return None


def amount_from_converted(converted):
    if hasattr(converted, "number") and hasattr(converted, "currency"):
        return converted
    if hasattr(converted, "units"):
        return converted.units
    return None


def allocations_for_commodity(commodity, commodity_meta, warnings):
    meta = commodity_meta.get(commodity, {})
    allocations = []
    allocated = Decimal("0")

    for key, value in meta.items():
        if not key.startswith(META_PREFIX):
            continue
        percentage = Decimal(value)
        allocations.append((key[len(META_PREFIX):], percentage))
        allocated += percentage

    if allocated != Decimal("100"):
        warnings.append(
            f"{commodity} asset_allocation_* metadata does not add up to 100%. Padding with 'unknown'."
        )
        allocations.append((UNKNOWN_CLASS, Decimal("100") - allocated))
    return allocations


def build_class_tree(contributions):
    root = {
        "name": "Total",
        "path": TOTAL_PATH,
        "amount": Decimal("0"),
        "children": {},
    }

    for contribution in contributions:
        amount = contribution["amount"]
        root["amount"] += amount
        node = root
        path_parts = []
        for part in contribution["class_path"].split("_"):
            path_parts.append(part)
            path = "_".join(path_parts)
            child = node["children"].setdefault(
                part,
                {
                    "name": part,
                    "path": path,
                    "amount": Decimal("0"),
                    "children": {},
                },
            )
            child["amount"] += amount
            node = child

    total = root["amount"]

    def finalize(node):
        children = [finalize(child) for child in node["children"].values()]
        children.sort(key=lambda child: (child["amount"], child["name"]), reverse=True)
        amount = node["amount"]
        return {
            "name": node["name"],
            "path": node["path"],
            "amount": float(amount),
            "percentage": float((amount / total * Decimal("100")) if total else 0),
            "children": children,
        }

    return finalize(root)


def build_asset_allocation_tree_widget_class(anywidget, traitlets):
    class AssetAllocationTreeWidget(anywidget.AnyWidget):
        _esm = """
        function formatAmount(value) {
          return Math.round(Number(value || 0)).toLocaleString();
        }

        function formatPercent(value) {
          return `${Number(value || 0).toFixed(1)}%`;
        }

        function toggleExpanded(model, path) {
          const expanded = new Set(model.get("expanded") || []);
          if (expanded.has(path)) {
            expanded.delete(path);
          } else {
            expanded.add(path);
          }
          model.set("expanded", [...expanded]);
          model.save_changes();
        }

        function descendantPaths(node) {
          const paths = [];
          for (const child of node.children || []) {
            paths.push(child.path);
            paths.push(...descendantPaths(child));
          }
          return paths;
        }

        function toggleExpandedRecursive(model, node) {
          const expanded = new Set(model.get("expanded") || []);
          const paths = [node.path, ...descendantPaths(node)];
          const shouldCollapse = expanded.has(node.path);
          for (const path of paths) {
            if (shouldCollapse) {
              expanded.delete(path);
            } else {
              expanded.add(path);
            }
          }
          model.set("expanded", [...expanded]);
          model.save_changes();
        }

        function selectPath(model, path) {
          model.set("value", path);
          model.save_changes();
        }

        function renderRows(model, tbody, nodes, depth = 0) {
          const expanded = new Set(model.get("expanded") || []);
          const selected = model.get("value") || "__total__";

          for (const node of nodes) {
            const hasChildren = node.children && node.children.length > 0;
            const isExpanded = expanded.has(node.path);
            const isSelected = selected === node.path;

            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid rgba(128, 128, 128, 0.18)";
            if (isSelected) {
              tr.style.background = "rgba(15, 98, 254, 0.08)";
            }

            const nameTd = document.createElement("td");
            nameTd.style.padding = "0.35rem 0.75rem";
            nameTd.style.whiteSpace = "nowrap";

            const rowButton = document.createElement("button");
            rowButton.type = "button";
            rowButton.style.display = "flex";
            rowButton.style.alignItems = "center";
            rowButton.style.gap = "0.35rem";
            rowButton.style.padding = "0";
            rowButton.style.border = "none";
            rowButton.style.background = "transparent";
            rowButton.style.cursor = "pointer";
            rowButton.style.font = "inherit";
            rowButton.style.color = isSelected ? "#0f62fe" : "inherit";
            rowButton.style.fontWeight = isSelected ? "700" : (hasChildren && isExpanded ? "600" : "400");
            rowButton.style.marginLeft = `${depth * 18}px`;

            const caret = document.createElement("span");
            caret.textContent = hasChildren ? (isExpanded ? "▾" : "▸") : "•";
            caret.style.display = "inline-block";
            caret.style.width = "1rem";
            caret.style.textAlign = "center";
            caret.style.color = hasChildren ? "#344054" : "#98a2b3";
            caret.onclick = (event) => {
              event.stopPropagation();
              if (!hasChildren) return;
              if (event.shiftKey) {
                toggleExpandedRecursive(model, node);
              } else {
                toggleExpanded(model, node.path);
              }
            };

            const label = document.createElement("span");
            label.textContent = node.name;
            rowButton.appendChild(caret);
            rowButton.appendChild(label);
            rowButton.onclick = (event) => {
              selectPath(model, node.path);
              if (!hasChildren) return;
              if (event.shiftKey) {
                toggleExpandedRecursive(model, node);
              } else {
                toggleExpanded(model, node.path);
              }
            };

            nameTd.appendChild(rowButton);
            tr.appendChild(nameTd);

            for (const text of [formatAmount(node.amount), formatPercent(node.percentage)]) {
              const td = document.createElement("td");
              td.style.padding = "0.35rem 0.75rem";
              td.style.whiteSpace = "nowrap";
              td.style.textAlign = "right";
              td.style.fontWeight = hasChildren && isExpanded ? "600" : "400";
              td.textContent = text;
              tr.appendChild(td);
            }
            tbody.appendChild(tr);

            if (hasChildren && isExpanded) {
              renderRows(model, tbody, node.children, depth + 1);
            }
          }
        }

        function render({ model, el }) {
          const tree = JSON.parse(model.get("tree_json") || "{}");
          const modelId = model.model_id || model.cid || "";
          if (el.dataset.boundModelId !== modelId) {
            model.on("change:tree_json", () => render({ model, el }));
            model.on("change:expanded", () => render({ model, el }));
            model.on("change:value", () => render({ model, el }));
            el.dataset.boundModelId = modelId;
          }

          el.innerHTML = "";
          const wrapper = document.createElement("div");
          wrapper.style.width = "fit-content";
          wrapper.style.maxWidth = "100%";

          const table = document.createElement("table");
          table.style.borderCollapse = "collapse";
          table.style.fontSize = "0.95rem";
          table.style.lineHeight = "1.3";

          const thead = document.createElement("thead");
          const headerRow = document.createElement("tr");
          for (const header of ["Asset Class", "Amount", "Percent"]) {
            const th = document.createElement("th");
            th.textContent = header;
            th.style.textAlign = header === "Asset Class" ? "left" : "right";
            th.style.padding = "0.35rem 0.75rem";
            th.style.fontWeight = "600";
            th.style.whiteSpace = "nowrap";
            headerRow.appendChild(th);
          }
          thead.appendChild(headerRow);
          table.appendChild(thead);

          const tbody = document.createElement("tbody");
          if (tree && tree.path) renderRows(model, tbody, [tree]);
          table.appendChild(tbody);
          wrapper.appendChild(table);
          el.appendChild(wrapper);
        }

        export default { render };
        """

        tree_json = traitlets.Unicode("{}").tag(sync=True)
        expanded = traitlets.List(default_value=[TOTAL_PATH]).tag(sync=True)
        value = traitlets.Unicode(TOTAL_PATH).tag(sync=True)

    return AssetAllocationTreeWidget


def build_asset_allocation_detail_widget_class(anywidget, traitlets):
    class AssetAllocationDetailWidget(anywidget.AnyWidget):
        _esm = """
        function formatAmount(value) {
          return Math.round(Number(value || 0)).toLocaleString();
        }

        function toggleExpanded(model, path) {
          const expanded = new Set(model.get("expanded") || []);
          if (expanded.has(path)) {
            expanded.delete(path);
          } else {
            expanded.add(path);
          }
          model.set("expanded", [...expanded]);
          model.save_changes();
        }

        function descendantPaths(node) {
          const paths = [];
          for (const child of node.children || []) {
            paths.push(child.path);
            paths.push(...descendantPaths(child));
          }
          return paths;
        }

        function toggleExpandedRecursive(model, node) {
          const expanded = new Set(model.get("expanded") || []);
          const paths = [node.path, ...descendantPaths(node)];
          const shouldCollapse = expanded.has(node.path);
          for (const path of paths) {
            if (shouldCollapse) {
              expanded.delete(path);
            } else {
              expanded.add(path);
            }
          }
          model.set("expanded", [...expanded]);
          model.save_changes();
        }

        function renderRows(model, tbody, nodes, depth = 0) {
          const expanded = new Set(model.get("expanded") || []);

          for (const node of nodes) {
            const hasChildren = node.children && node.children.length > 0;
            const isExpanded = expanded.has(node.path);

            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid rgba(128, 128, 128, 0.18)";

            const nameTd = document.createElement("td");
            nameTd.style.padding = "0.35rem 0.75rem";
            nameTd.style.whiteSpace = "nowrap";

            const rowButton = document.createElement("button");
            rowButton.type = "button";
            rowButton.style.display = "flex";
            rowButton.style.alignItems = "center";
            rowButton.style.gap = "0.35rem";
            rowButton.style.padding = "0";
            rowButton.style.border = "none";
            rowButton.style.background = "transparent";
            rowButton.style.cursor = hasChildren ? "pointer" : "default";
            rowButton.style.font = "inherit";
            rowButton.style.fontWeight = hasChildren && isExpanded ? "600" : "400";
            rowButton.style.marginLeft = `${depth * 18}px`;

            const caret = document.createElement("span");
            caret.textContent = hasChildren ? (isExpanded ? "▾" : "▸") : "•";
            caret.style.display = "inline-block";
            caret.style.width = "1rem";
            caret.style.textAlign = "center";
            caret.style.color = hasChildren ? "#344054" : "#98a2b3";

            const label = document.createElement("span");
            label.textContent = node.name;
            rowButton.appendChild(caret);
            rowButton.appendChild(label);
            rowButton.onclick = (event) => {
              if (!hasChildren) return;
              if (event.shiftKey) {
                toggleExpandedRecursive(model, node);
              } else {
                toggleExpanded(model, node.path);
              }
            };

            nameTd.appendChild(rowButton);
            tr.appendChild(nameTd);

            const amountTd = document.createElement("td");
            amountTd.style.padding = "0.35rem 0.75rem";
            amountTd.style.whiteSpace = "nowrap";
            amountTd.style.textAlign = "right";
            amountTd.style.fontWeight = hasChildren && isExpanded ? "600" : "400";
            amountTd.textContent = formatAmount(node.amount);
            tr.appendChild(amountTd);
            tbody.appendChild(tr);

            if (hasChildren && isExpanded) {
              renderRows(model, tbody, node.children, depth + 1);
            }
          }
        }

        function render({ model, el }) {
          const tree = JSON.parse(model.get("tree_json") || "{}");
          const modelId = model.model_id || model.cid || "";
          if (el.dataset.boundModelId !== modelId) {
            model.on("change:tree_json", () => render({ model, el }));
            model.on("change:expanded", () => render({ model, el }));
            el.dataset.boundModelId = modelId;
          }

          el.innerHTML = "";
          const wrapper = document.createElement("div");
          wrapper.style.width = "fit-content";
          wrapper.style.maxWidth = "100%";

          const table = document.createElement("table");
          table.style.borderCollapse = "collapse";
          table.style.fontSize = "0.95rem";
          table.style.lineHeight = "1.3";

          const thead = document.createElement("thead");
          const headerRow = document.createElement("tr");
          for (const header of ["Account / Holding", "Amount"]) {
            const th = document.createElement("th");
            th.textContent = header;
            th.style.textAlign = header === "Account / Holding" ? "left" : "right";
            th.style.padding = "0.35rem 0.75rem";
            th.style.fontWeight = "600";
            th.style.whiteSpace = "nowrap";
            headerRow.appendChild(th);
          }
          thead.appendChild(headerRow);
          table.appendChild(thead);

          const tbody = document.createElement("tbody");
          if (tree && tree.path) renderRows(model, tbody, [tree]);
          table.appendChild(tbody);
          wrapper.appendChild(table);
          el.appendChild(wrapper);
        }

        export default { render };
        """

        tree_json = traitlets.Unicode("{}").tag(sync=True)
        expanded = traitlets.List(default_value=[TOTAL_PATH]).tag(sync=True)

    return AssetAllocationDetailWidget


def detail_rows_for_class(contributions, selected_path):
    selected_path = selected_path or TOTAL_PATH
    selected_all = selected_path == TOTAL_PATH
    account_tree = {}
    total = Decimal("0")

    for contribution in contributions:
        class_path = contribution["class_path"]
        if not selected_all and not (
            class_path == selected_path or class_path.startswith(f"{selected_path}_")
        ):
            continue
        amount = contribution["amount"]
        total += amount

        current_level = account_tree
        node = None
        path_parts = []
        for part in contribution["account"].split(":"):
            path_parts.append(part)
            account_path = ":".join(path_parts)
            node = current_level.setdefault(
                part,
                {
                    "name": part,
                    "path": account_path,
                    "amount": Decimal("0"),
                    "children": {},
                    "holdings": defaultdict(Decimal),
                },
            )
            node["amount"] += amount
            current_level = node["children"]
        node["holdings"][contribution["commodity"]] += amount

    children = finalize_detail_nodes(account_tree)
    return {
        "name": "TOTAL",
        "path": TOTAL_PATH,
        "amount": float(total),
        "children": children,
    }, total


def tree_paths(tree):
    paths = []

    def collect(node):
        paths.append(node["path"])
        for child in node.get("children", []):
            collect(child)

    if tree:
        collect(tree)
    return paths


def finalize_detail_nodes(nodes):
    finalized = []
    for node in nodes.values():
        children = finalize_detail_nodes(node["children"])
        holdings = []
        collapse_only_holding = (
            not children
            and len(node["holdings"]) == 1
            and next(iter(node["holdings"])) == node["name"]
        )
        if not collapse_only_holding:
            holdings = [
                {
                    "name": commodity,
                    "path": f"{node['path']}:{commodity}",
                    "amount": float(amount),
                    "children": [],
                }
                for commodity, amount in node["holdings"].items()
            ]
        holdings.sort(key=lambda row: (row["amount"], row["name"]), reverse=True)
        finalized.append(
            {
                "name": node["name"],
                "path": node["path"],
                "amount": float(node["amount"]),
                "children": [*children, *holdings],
            }
        )
    finalized.sort(key=lambda row: (row["amount"], row["name"]), reverse=True)
    return finalized


def display_class_name(selected_path):
    if selected_path == TOTAL_PATH:
        return "Total"
    return selected_path.replace("_", " / ")


def build_icicle_chart(class_tree, escape, format_amount):
    level_width = 190
    chart_height = 360
    label_min_width = 58
    palette = [
        "#d6e4ff",
        "#d9f0e3",
        "#fde7c7",
        "#eadcf8",
        "#f7d7da",
        "#d9edf7",
        "#e7e0d4",
    ]
    nodes = []

    def max_depth(node, depth=0):
        return max([depth, *(max_depth(child, depth + 1) for child in node["children"])])

    depth_count = max_depth(class_tree) + 1
    chart_width = depth_count * level_width

    def add_nodes(node, y, height, depth):
        nodes.append(
            {
                "name": node["name"],
                "path": node["path"],
                "amount": node["amount"],
                "percentage": node["percentage"],
                "y": y,
                "height": height,
                "depth": depth,
            }
        )
        child_y = y
        total = sum(child["amount"] for child in node["children"])
        for child in node["children"]:
            child_height = height * (child["amount"] / total) if total else 0
            add_nodes(child, child_y, child_height, depth + 1)
            child_y += child_height

    add_nodes(class_tree, 0, chart_height, 0)
    rects = []

    for node in nodes:
        height = max(node["height"] - 1, 0)
        if height <= 0:
            continue
        x = node["depth"] * level_width
        y = node["y"]
        width = level_width - 2
        color = palette[node["depth"] % len(palette)]
        label = node["name"]
        title = (
            f"{display_class_name(node['path'])}: {format_amount(node['amount'])} "
            f"({node['percentage']:.1f}%)"
        )
        text = ""
        if width >= label_min_width and height >= 20:
            text = f"""
            <text x="{x + 6:.2f}" y="{y + 20:.2f}" font-size="12" fill="#202124">
              {escape(label)}
            </text>
            """
        rects.append(
            f"""
            <g>
              <title>{escape(title)}</title>
              <rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}"
                    rx="2" fill="{color}" stroke="rgba(80, 80, 80, 0.35)" />
              {text}
            </g>
            """
        )

    return f"""
    <div style="max-width: 100%; overflow-x: auto;">
      <svg viewBox="0 0 {chart_width} {chart_height}" width="100%" height="{chart_height}"
           role="img" aria-label="Asset allocation icicle chart">
        {''.join(rects)}
      </svg>
    </div>
    """


def build_asset_allocation_view(
    allocation_data,
    account_pattern_control,
    tax_adjustment_control,
    escape,
    format_amount,
    mo,
    selected_path,
    detail_tree,
    tree,
):
    warning_view = (
        mo.Html(
            f"""
            <div style="border-left: 4px solid #b54708; padding: 0.5rem 0.75rem; background: rgba(181, 71, 8, 0.08);">
              <strong>Warnings</strong>
              <ul>
                {''.join(f'<li>{escape(warning)}</li>' for warning in allocation_data["warnings"])}
              </ul>
            </div>
            """
        )
        if allocation_data["warnings"]
        else None
    )
    selected_label = display_class_name(selected_path)
    icicle_chart = build_icicle_chart(
        allocation_data["class_tree"],
        escape,
        format_amount,
    )

    return mo.vstack(
        [
            mo.md("# Asset Allocation"),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            mo.md("**Account regex**"),
                            account_pattern_control,
                        ],
                        gap=0.15,
                    ),
                    mo.vstack(
                        [
                            mo.md("**Tax adjustment**"),
                            tax_adjustment_control,
                        ],
                        gap=0.15,
                    ),
                ],
                align="end",
                justify="start",
                gap=1.5,
            ),
            *([warning_view] if warning_view is not None else []),
            mo.Html(
                f"""
                <details style="margin: 0.5rem 0;">
                  <summary style="cursor: pointer; font-size: 1.25rem; font-weight: 600;">
                    Allocation Icicle
                  </summary>
                  <div style="margin-top: 0.5rem;">
                    {icicle_chart}
                  </div>
                </details>
                """
            ),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            mo.md("## Allocation by Class"),
                            tree,
                        ]
                    ),
                    mo.vstack(
                        [
                            mo.md(f"## {selected_label} Holdings"),
                            detail_tree,
                        ]
                    ),
                ],
                widths=[1, 1],
                align="start",
                justify="start",
            ),
        ]
    )


def unique_preserve_order(items):
    seen = set()
    unique_items = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique_items.append(item)
    return unique_items
