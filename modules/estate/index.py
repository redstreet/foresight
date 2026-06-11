from .ownership import build_ownership_view


def build_estate_view(mo, beneficiaries_view, ownership_view):
    return mo.ui.tabs(
        {
            "Beneficiaries": beneficiaries_view,
            "Ownership": ownership_view,
        }
    )
