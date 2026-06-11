## Main Files
- `main.py`
  - main marimo app with top-level tabs for retirement, investments, estate, taxes, and expenses
  - loads `BEANCOUNT_FILE` once and shares `entries` / `options` across tabs
- `retirement/`
  - retirement domain views
  - `contributions.py` contains the contributions subtab
- `investments/`
  - investments domain views
  - `asset_allocation.py` contains the asset allocation subtab
- `estate/`
  - estate domain views
  - `ownership.py` contains the ownership subtab
- `expenses/`
  - expenses domain views
  - `analysis.py` contains the expense analysis subtab
- `taxes/`
  - taxes domain placeholder
- `common/libbeanmarimo.py`
  - shared marimo table helper with total-row support
- `shared.py`
  - shared formatting and Beancount query helpers

## Data Sources
- Primary ledger input:
  - Beancount file from `BEANCOUNT_FILE`
- Beancount runtime objects:
  - `entries`
  - `options`
- Query execution:
  - BeanQuery / BQL against loaded Beancount ledger
- Optional branch-only alternative:
  - DuckDB export derived from `BEANCOUNT_FILE`
  - not on `main`

## Shared Table Helper
- `table(data, *args, total_row=None, total_position="bottom", column_labels=None, formatters=None, cell_style_fn=None, **kwargs)`
- behavior:
  - no `total_row`: delegate to `mo.ui.table(...)`
  - with `total_row`: render compact HTML table
