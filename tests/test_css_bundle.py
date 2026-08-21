from scripts.build_css_bundle import BUNDLE_OUTPUT, IMPORT_RE, check_css_bundle


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
