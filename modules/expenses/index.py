from .analysis import build_analysis_view


def build_expenses_domain_view(mo, analysis_view):
    return mo.ui.tabs(
        {
            "Analysis": analysis_view,
        }
    )
