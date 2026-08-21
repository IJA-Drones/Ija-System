from pathlib import Path

from scripts.build_css_bundle import BUNDLE_OUTPUT, IMPORT_RE, check_css_bundle


CSS_ROOT = Path("app/static/css")


def test_global_css_bundle_is_current():
    assert check_css_bundle(), (
        "CSS bundle is stale. Run: python scripts/build_css_bundle.py"
    )


def test_global_css_bundle_has_no_local_import_chain():
    import_lines = [
        line
        for line in BUNDLE_OUTPUT.read_text(encoding="utf-8").splitlines()
        if IMPORT_RE.match(line)
    ]
    assert import_lines == []


def test_button_variants_are_owned_by_button_component():
    buttons_css = (CSS_ROOT / "components/buttons.css").read_text(encoding="utf-8")
    listing_css = (CSS_ROOT / "components/listing.css").read_text(encoding="utf-8")

    variants = {
        "btn-primary",
        "btn-success",
        "btn-secondary",
        "btn-danger",
        "btn-warning",
        "btn-info",
        "btn-light",
        "btn-dark",
        "btn-outline-primary",
        "btn-outline-success",
        "btn-outline-secondary",
        "btn-outline-danger",
        "btn-outline-warning",
        "btn-outline-info",
        "btn-outline-light",
        "btn-outline-dark",
    }

    for variant in variants:
        assert f".{variant}" in buttons_css
        assert f".{variant}" not in listing_css
