def build_taxes_view(mo, gains_minimizer_view):
    return mo.ui.tabs(
        {
            "Gains Minimizer": gains_minimizer_view,
        }
    )
