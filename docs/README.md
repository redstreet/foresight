# Foresight

Foresight is a marimo dashboard for Beancount. It loads the ledger from
`BEANCOUNT_FILE` once in `app.py` and shares the parsed entries/options across
the domain tabs.

## Running

```sh
BEANCOUNT_FILE=/path/to/main.beancount marimo run app.py
```

A small demonstration ledger is available at `examples/sample.beancount`:

```sh
BEANCOUNT_FILE=examples/sample.beancount marimo run app.py
```

## GitHub Pages Demo

The repository includes a GitHub Actions workflow that exports the sample ledger
as static HTML and publishes it to GitHub Pages. In GitHub, enable Pages with
Source set to **GitHub Actions**.

For local export:

```sh
python -m pip install -r requirements.txt
BEANCOUNT_FILE=examples/sample.beancount marimo export html app.py \
  -o site/index.html \
  --no-include-code \
  -f
```

## molab Demo

To build a single-file artifact for <https://molab.marimo.io>:

```sh
python scripts/build_molab.py
```

This writes `dist/foresight_molab.py`. The generated file inlines Foresight's
modules and the sample ledger, so it can run without the repository layout. If
`BEANCOUNT_FILE` is not set, it uses the bundled sample ledger.

## Foresight Config

Foresight configuration is read from a Beancount custom directive:

```beancount
2010-01-01 custom "foresight" "foresight" "{
  'investments': {
    'breakdown': {
      'brokerages': ['Fidelity', 'Vanguard', 'Schwab', 'IBKR', 'Etrade']
    },
    'asset_allocation': {
      'accounts_pattern': '^Assets:Investments',
      'tax_adjustment': False
    },
    'cash_drag': {
      'accounts_pattern': '^Assets',
      'accounts_exclude_pattern': '',
      'metadata_label_cash': 'asset_allocation_Bond_Cash',
      'min_threshold': 0
    }
  },
  'taxes': {
    'gains_minimizer': {
      'accounts_pattern': '^Assets:Investments:Taxable',
      'account_field': 'parent',
      'currency': 'USD',
      'st_tax_rate': 30.0,
      'lt_tax_rate': 15.0
    }
  }
}"
```

`investments.breakdown.brokerages` is used by Investments > Breakdown. Each
`Assets:Investments:*` account with a balance is assigned to the first brokerage
whose configured string appears in the account name, case-insensitively.
Unmatched accounts are grouped into `Other Brokerages`.

## Investment Account Types

Investments > Breakdown also groups investment balances from the account
hierarchy:

- `Assets:Investments:Taxable`
- `Assets:Investments:TaxDeferred`, `Assets:Investments:Tax-Deferred`, or
  `Assets:Investments:Tax Deferred`
- `Assets:Investments:TaxFree`, `Assets:Investments:Tax-Free`, or
  `Assets:Investments:Tax Free`
- `Assets:Investments:HSA`

## Asset Allocation

Investments > Asset Allocation follows commodity metadata named
`asset_allocation_*`. The suffix is the allocation class path, with `_` creating
nested classes.

```beancount
2010-01-01 commodity VTI
  asset_allocation_stocks_us: "100"
```

The asset allocation account filter is editable at the top of the module. It
defaults to `^Assets:Investments`.
Tax adjustment is also controlled at the top of the module and defaults to off.

## Cash Drag

Investments > Cash Drag reads `investments.cash_drag` from the Foresight config.
Cash commodities are operating currencies plus commodities whose
`metadata_label_cash` metadata is set to `100`. The table groups cash by account,
sorts largest to smallest, and excludes rows below `min_threshold`.

## Taxes

Taxes > Gains Minimizer lists taxable lots in the order that minimizes estimated
capital gains tax if sold. The configuration is editable at the top of the page:

- Account regex defaults to `Assets:Investments:Taxable`
- Account field defaults to the parent account
- Currency defaults to `USD`
- Short-term tax rate defaults to `30.0` percent
- Long-term tax rate defaults to `15.0` percent

## Estate Ownership

Estate > Beneficiaries uses built-in tables for taxable, tax-advantaged,
tax-deferred, and other assets. Each table reads account metadata with the
`estate_info_` prefix, skips accounts with `estate_info_beneficiary_skip`, hides
commodity leaf accounts when their parent account is included, and shows the
same columns except `community_property`.

Estate > Ownership classifies asset accounts using account metadata:

```beancount
2010-01-01 open Assets:Investments:Taxable:Vanguard
  estate_info_community_property: "Community Prop"
```

Liability accounts do not need this metadata. Their default ownership label is
set in `app.py` by `liability_community_property`.
