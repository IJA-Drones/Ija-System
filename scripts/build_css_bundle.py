import argparse
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSS_ROOT = PROJECT_ROOT / "app" / "static" / "css"
BUNDLE_ENTRY = CSS_ROOT / "style.css"
BUNDLE_OUTPUT = CSS_ROOT / "style.bundle.css"

IMPORT_RE = re.compile(
    r"^\s*@import\s+(?:url\(\s*)?[\"'](?P<target>[^\"']+)[\"']\s*\)?\s*;\s*$"
)
GENERATED_HEADER = """/*
 * Generated file. Do not edit directly.
 * Source entry: app/static/css/style.css
 * Run: python scripts/build_css_bundle.py
 */

"""
_bundle_dependencies = None


def _relative_label(path):
    return path.relative_to(PROJECT_ROOT).as_posix()


def _resolve_local_import(source_path, line):
    match = IMPORT_RE.match(line)
    if not match:
        return None

    target = match.group("target").strip()
    if target.startswith(("data:", "http://", "https://", "//", "/")):
        return None

    imported_path = (source_path.parent / target).resolve()
    try:
        imported_path.relative_to(CSS_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(
            f"CSS import outside static/css: {_relative_label(source_path)} -> {target}"
        ) from exc

    if not imported_path.is_file():
        raise FileNotFoundError(
            f"CSS import not found: {_relative_label(source_path)} -> {target}"
        )
    return imported_path


def _expand_css(source_path, stack, dependencies):
    source_path = source_path.resolve()
    if source_path in stack:
        cycle = " -> ".join(_relative_label(path) for path in (*stack, source_path))
        raise ValueError(f"Circular CSS import: {cycle}")

    dependencies.add(source_path)
    expanded = []
    next_stack = (*stack, source_path)
    for line in source_path.read_text(encoding="utf-8").splitlines(keepends=True):
        imported_path = _resolve_local_import(source_path, line)
        if imported_path is None:
            expanded.append(line)
            continue

        label = _relative_label(imported_path)
        expanded.append(f"\n/* bundle-source: {label} */\n")
        expanded.append(_expand_css(imported_path, next_stack, dependencies))
        expanded.append(f"\n/* bundle-source-end: {label} */\n")

    return "".join(expanded)


def render_css_bundle():
    global _bundle_dependencies

    dependencies = set()
    content = GENERATED_HEADER + _expand_css(BUNDLE_ENTRY, (), dependencies)
    if not content.endswith("\n"):
        content += "\n"
    _bundle_dependencies = dependencies
    return content, dependencies


def build_css_bundle():
    content, dependencies = render_css_bundle()
    current = BUNDLE_OUTPUT.read_text(encoding="utf-8") if BUNDLE_OUTPUT.exists() else None
    if current == content:
        return False

    temporary_output = BUNDLE_OUTPUT.with_suffix(".css.tmp")
    temporary_output.write_text(content, encoding="utf-8")
    temporary_output.replace(BUNDLE_OUTPUT)
    return True


def build_css_bundle_if_stale():
    global _bundle_dependencies

    if not BUNDLE_OUTPUT.exists():
        return build_css_bundle()

    if _bundle_dependencies is None:
        _content, _bundle_dependencies = render_css_bundle()

    output_mtime = BUNDLE_OUTPUT.stat().st_mtime_ns
    if any(path.stat().st_mtime_ns > output_mtime for path in _bundle_dependencies):
        return build_css_bundle()
    return False


def check_css_bundle():
    expected, _dependencies = render_css_bundle()
    if not BUNDLE_OUTPUT.exists():
        return False
    return BUNDLE_OUTPUT.read_text(encoding="utf-8") == expected


def parse_args():
    parser = argparse.ArgumentParser(description="Build the global CSS bundle.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with an error when the committed bundle is stale.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.check:
        if check_css_bundle():
            print(f"CSS bundle is current: {_relative_label(BUNDLE_OUTPUT)}")
            return 0
        print("CSS bundle is missing or stale. Run: python scripts/build_css_bundle.py")
        return 1

    changed = build_css_bundle()
    status = "updated" if changed else "already current"
    print(f"CSS bundle {status}: {_relative_label(BUNDLE_OUTPUT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
