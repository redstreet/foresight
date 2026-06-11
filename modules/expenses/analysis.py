def load_expense_tables(run_query):
    summary_df = run_query(
        """
        SELECT
            year(date) as year,
            account,
            SUM(convert(position,'USD')) as amount
        WHERE account ~ '^Expenses'
        GROUP BY year, account
        """
    ).rename({"amount (USD)": "amount"})
    transactions_df = run_query(
        """
        SELECT
            date,
            year(date) as year,
            account,
            payee,
            narration,
            convert(position,'USD') as amount
        WHERE account ~ '^Expenses'
        """
    ).rename({"amount (USD)": "amount"})
    return summary_df, transactions_df


def build_expense_tree_widget_class(anywidget, traitlets):
    class ExpenseTreeWidget(anywidget.AnyWidget):
        _esm = """
        function formatAmount(value, showSign = false) {
          const rounded = Math.round(Number(value || 0));
          const absText = Math.abs(rounded).toLocaleString();
          if (showSign) {
            const sign = rounded >= 0 ? "+" : "-";
            return `${sign}${absText}`;
          }
          return rounded.toLocaleString();
        }

        function deltaColor(value) {
          if (value > 0) return "#b42318";
          if (value < 0) return "#18794e";
          return "inherit";
        }

        function toggleExpanded(model, path) {
          const expanded = new Set(model.get("expanded") || []);
          if (expanded.has(path)) {
            expanded.delete(path);
          } else {
            expanded.add(path);
          }
          model.set("expanded", [...expanded]);
          if (expanded.size === 0) {
            model.set("value", "");
          }
          model.save_changes();
        }

        function renderRows(model, tbody, nodes, depth = 0) {
          const expanded = new Set(model.get("expanded") || []);
          const selected = model.get("value");

          for (const node of nodes) {
            const hasChildren = node.children && node.children.length > 0;
            const isExpanded = expanded.has(node.path);
            const isTotal = !!node.is_total;

            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid rgba(128, 128, 128, 0.2)";
            if (isTotal) tr.style.background = "rgba(128, 128, 128, 0.08)";

            const categoryTd = document.createElement("td");
            categoryTd.style.padding = "0.35rem 0.75rem";
            categoryTd.style.whiteSpace = "nowrap";

            const rowButton = document.createElement("button");
            rowButton.type = "button";
            rowButton.style.display = "flex";
            rowButton.style.alignItems = "center";
            rowButton.style.gap = "0.35rem";
            rowButton.style.padding = "0";
            rowButton.style.border = "none";
            rowButton.style.background = "transparent";
            rowButton.style.cursor = isTotal ? "default" : "pointer";
            rowButton.style.font = "inherit";
            rowButton.style.color = selected === node.path ? "#0f62fe" : "inherit";
            rowButton.style.fontWeight = isTotal ? "700" : (selected === node.path ? "600" : "400");
            rowButton.style.marginLeft = `${depth * 18}px`;

            const caret = document.createElement("span");
            caret.textContent = isTotal ? "Σ" : (hasChildren ? (isExpanded ? "▾" : "▸") : "•");
            caret.style.display = "inline-block";
            caret.style.width = "1rem";
            caret.style.textAlign = "center";
            if (isTotal) {
              caret.style.fontWeight = "700";
            } else if (hasChildren) {
              caret.style.color = "#344054";
              caret.style.fontSize = "1rem";
              caret.style.fontWeight = "700";
            } else {
              caret.style.color = "#98a2b3";
              caret.style.fontSize = "0.75rem";
            }

            const label = document.createElement("span");
            label.textContent = node.name;
            rowButton.appendChild(caret);
            rowButton.appendChild(label);
            rowButton.onclick = () => {
              if (isTotal) return;
              if (hasChildren) {
                toggleExpanded(model, node.path);
              } else {
                model.set("value", node.path);
                model.save_changes();
              }
            };

            categoryTd.appendChild(rowButton);
            tr.appendChild(categoryTd);

            for (const [value, isDelta] of [
              [node.left_amount, false],
              [node.right_amount, false],
              [node.delta, true],
            ]) {
              const td = document.createElement("td");
              td.style.padding = "0.35rem 0.75rem";
              td.style.whiteSpace = "nowrap";
              td.style.textAlign = "right";
              td.textContent = formatAmount(value, isDelta);
              if (isTotal && !isDelta) td.style.fontWeight = "700";
              if (isDelta) {
                td.style.color = deltaColor(value);
                td.style.fontWeight = isTotal ? "700" : "600";
              }
              tr.appendChild(td);
            }

            tbody.appendChild(tr);
            if (hasChildren && isExpanded) renderRows(model, tbody, node.children, depth + 1);
          }
        }

        function render({ model, el }) {
          const tree = JSON.parse(model.get("tree_json") || "[]");
          const leftLabel = model.get("left_label");
          const rightLabel = model.get("right_label");
          const modelId = model.model_id || model.cid || "";

          if (el.dataset.boundModelId !== modelId) {
            model.on("change:tree_json", () => render({ model, el }));
            model.on("change:expanded", () => render({ model, el }));
            model.on("change:value", () => render({ model, el }));
            model.on("change:left_label", () => render({ model, el }));
            model.on("change:right_label", () => render({ model, el }));
            el.dataset.boundModelId = modelId;
          }

          el.innerHTML = "";
          const wrapper = document.createElement("div");
          wrapper.style.width = "fit-content";
          wrapper.style.maxWidth = "100%";
          const table = document.createElement("table");
          table.style.borderCollapse = "collapse";
          table.style.fontSize = "0.9rem";
          table.style.lineHeight = "1.3";
          const thead = document.createElement("thead");
          const headerRow = document.createElement("tr");
          for (const header of ["Category", leftLabel, rightLabel, "Delta"]) {
            const th = document.createElement("th");
            th.textContent = header;
            th.style.textAlign = header === "Category" ? "left" : "right";
            th.style.padding = "0.35rem 0.75rem";
            th.style.fontWeight = "600";
            th.style.whiteSpace = "nowrap";
            headerRow.appendChild(th);
          }
          thead.appendChild(headerRow);
          table.appendChild(thead);
          const tbody = document.createElement("tbody");
          renderRows(model, tbody, tree);
          table.appendChild(tbody);
          wrapper.appendChild(table);
          el.appendChild(wrapper);
        }

        export default { render };
        """

        tree_json = traitlets.Unicode("[]").tag(sync=True)
        left_label = traitlets.Unicode("").tag(sync=True)
        right_label = traitlets.Unicode("").tag(sync=True)
        expanded = traitlets.List(default_value=[]).tag(sync=True)
        value = traitlets.Unicode("").tag(sync=True)

    return ExpenseTreeWidget


def default_controls(summary_df):
    available_years = sorted(summary_df["year"].unique().to_list()) if len(summary_df) else []
    year_options = [str(year) for year in available_years]
    current_year = max(available_years) if available_years else None
    completed_year_options = [str(year) for year in available_years if year != current_year]

    if len(completed_year_options) >= 2:
        default_left_year = completed_year_options[-2]
        default_right_year = completed_year_options[-1]
    elif completed_year_options:
        default_left_year = completed_year_options[0]
        default_right_year = completed_year_options[0]
    elif len(year_options) >= 2:
        default_left_year = year_options[-2]
        default_right_year = year_options[-1]
    elif year_options:
        default_left_year = year_options[0]
        default_right_year = year_options[0]
    else:
        default_left_year = None
        default_right_year = None

    all_accounts = summary_df["account"].unique().to_list()
    categories = sorted(
        {
            account.split(":")[1]
            for account in all_accounts
            if account.startswith("Expenses:")
            and len(account.split(":")) > 1
        }
    )
    default_excluded = [
        "Housing",
        "Interest",
        "PZ",
        "Healthcare",
        "Renovation",
        "Charitable-Giving",
    ]
    default_excluded = [category for category in default_excluded if category in categories]
    return categories, default_excluded, default_left_year, default_right_year, year_options


def build_controls(
    categories,
    default_excluded,
    default_left_year,
    default_right_year,
    mo,
    year_options,
):
    left_year = mo.ui.dropdown(
        options=year_options,
        value=default_left_year,
        label="",
        full_width=False,
    )
    right_year = mo.ui.dropdown(
        options=year_options,
        value=default_right_year,
        label="",
        full_width=False,
    )
    exclude_categories = mo.ui.multiselect(
        options=categories,
        value=default_excluded,
        label="Exclude categories from analysis",
        full_width=False,
    )
    invert_categories = mo.ui.switch(
        value=False,
        label="Invert category selection",
    )
    controls = mo.vstack(
        [
            mo.md("_Compare expenses between two years, sorted by the largest changes._"),
            mo.Html(
                """
                <details style="margin-top: -0.25rem;">
                  <summary style="cursor: pointer;">More</summary>
                  <div style="margin-top: 0.5rem; font-style: italic;">
                    Quickly see where spending increased or decreased, with the
                    ability to drill down from top-level expense accounts to
                    subaccounts and individual transactions.
                  </div>
                </details>
                """
            ),
            mo.md("### Category filter"),
            exclude_categories,
            invert_categories,
        ]
    )
    return controls, exclude_categories, invert_categories, left_year, right_year


def build_tree_data(
    coerce_amount,
    exclude_categories,
    invert_categories,
    left_year,
    right_year,
    summary_df,
):
    def category_enabled(category: str) -> bool:
        return (
            category in exclude_categories.value
            if invert_categories.value
            else category not in exclude_categories.value
        )

    left_year_value = left_year.value
    right_year_value = right_year.value
    summary_rows = [
        {
            "year": str(entry["year"]),
            "account": entry["account"],
            "amount": coerce_amount(entry["amount"]),
        }
        for entry in summary_df.iter_rows(named=True)
        if entry["account"].startswith("Expenses:")
        and category_enabled(entry["account"].split(":")[1])
    ]

    roots = {}
    leaf_accounts = set()
    for summary_row in summary_rows:
        parts = summary_row["account"].split(":")[1:]
        current_level = roots
        path_parts = []
        leaf_accounts.add(summary_row["account"])

        for part in parts:
            path_parts.append(part)
            path = f"Expenses:{':'.join(path_parts)}"
            node = current_level.setdefault(
                part,
                {
                    "name": part,
                    "path": path,
                    "left_amount": 0.0,
                    "right_amount": 0.0,
                    "children": {},
                },
            )
            if summary_row["year"] == left_year_value:
                node["left_amount"] += summary_row["amount"]
            if summary_row["year"] == right_year_value:
                node["right_amount"] += summary_row["amount"]
            current_level = node["children"]

    def finalize(nodes):
        finalized = []
        for node in nodes.values():
            children = finalize(node["children"])
            finalized.append(
                {
                    "name": node["name"],
                    "path": node["path"],
                    "left_amount": node["left_amount"],
                    "right_amount": node["right_amount"],
                    "delta": node["right_amount"] - node["left_amount"],
                    "children": children,
                }
            )
        finalized.sort(key=lambda item: (item["delta"], item["name"]), reverse=True)
        return finalized

    tree_children = finalize(roots)
    total_row = {
        "name": "TOTAL",
        "path": "__total__",
        "left_amount": sum(node["left_amount"] for node in tree_children),
        "right_amount": sum(node["right_amount"] for node in tree_children),
        "delta": sum(node["delta"] for node in tree_children),
        "children": [],
        "is_total": True,
    }
    return leaf_accounts, left_year_value, right_year_value, [total_row, *tree_children]


def build_analysis_view(
    coerce_amount,
    controls,
    escape,
    format_amount,
    leaf_accounts,
    left_year,
    left_year_value,
    mo,
    right_year,
    right_year_value,
    selected_account,
    transactions_df,
    tree,
):
    show_transactions = selected_account in leaf_accounts
    transaction_table_rows = []
    if show_transactions:
        for txn_entry in transactions_df.iter_rows(named=True):
            if str(txn_entry["year"]) not in {left_year_value, right_year_value}:
                continue
            if txn_entry["account"] != selected_account:
                continue
            transaction_table_rows.append(
                f"""
                <tr>
                    <td>{escape(str(txn_entry["date"]))}</td>
                    <td>{escape(str(txn_entry["payee"] or ""))}</td>
                    <td>{escape(str(txn_entry["narration"] or ""))}</td>
                    <td class="numeric">{format_amount(coerce_amount(txn_entry["amount"]), show_sign=True)}</td>
                </tr>
                """
            )

    transactions_view = mo.Html(
        f"""
        <style>
          .expense-transactions {{
            width: 100%;
            max-width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            line-height: 1.3;
            margin-top: 1rem;
          }}
          .expense-transactions th,
          .expense-transactions td {{
            padding: 0.35rem 0.6rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
            vertical-align: top;
          }}
          .expense-transactions th {{
            text-align: left;
            font-weight: 600;
          }}
          .expense-transactions .numeric {{
            text-align: right;
            white-space: nowrap;
          }}
        </style>
        <div>
          <table class="expense-transactions">
            <thead>
              <tr>
                <th>Date</th>
                <th>Payee</th>
                <th>Narration</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {''.join(transaction_table_rows)}
            </tbody>
          </table>
        </div>
        """
    )

    return mo.vstack(
        [
            mo.md("# Expense Analysis"),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            mo.md("### Comparison"),
                            mo.hstack([left_year, right_year], justify="start"),
                            tree,
                            *((
                                [
                                    mo.md("### Transactions"),
                                    mo.md(
                                        f"Showing postings booked to `{selected_account}` for {left_year_value} and {right_year_value}."
                                    ),
                                    transactions_view,
                                ]
                            ) if show_transactions else []),
                        ]
                    ),
                    mo.vstack([controls]),
                ],
                widths=[2.2, 1],
                align="start",
                justify="start",
            ),
        ]
    )
