from .contributions import build_contributions_view


def build_retirement_view(mo, contributions_view):
    return mo.ui.tabs(
        {
            "Contributions": contributions_view,
        }
    )
