## Time Handling
- Preferred year for tax-sensitive contribution queries:
  - use `tax_year` when present
  - otherwise fall back to `year`
- Limits queries should run once across all years, then filter locally.

### Tax Year Normalization
```python
normalized = raw.with_columns(
    pl.coalesce([pl.col("tax_year"), pl.col("year")]).alias("year")
)
```

### Total-Row Table
```python
bean_table(
    rows,
    total_row=total_row,
    total_position="top",
    cell_style_fn=style_fn,
)
```
