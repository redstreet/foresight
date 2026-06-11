def build_investments_view(
    mo,
    account_types_view,
    asset_allocation_view,
    cash_drag_view,
):
    return mo.ui.tabs(
        {
            "Asset Allocation": asset_allocation_view,
            "Cash Drag": cash_drag_view,
            "Breakdown": account_types_view,
        }
    )
