from urllib.parse import urlparse

from flask import redirect, request, url_for


def _is_safe_internal_url(target: str) -> bool:
    parsed = urlparse(target)
    if not parsed.netloc and not parsed.scheme:
        return target.startswith("/") and not target.startswith("//")
    return parsed.scheme in {"http", "https"} and parsed.netloc == request.host


def get_safe_return_url(default_endpoint: str, **values) -> str:
    candidates = (
        (request.form.get("next") or "").strip(),
        (request.values.get("next") or "").strip(),
        (request.referrer or "").strip(),
    )
    for target in candidates:
        if target and _is_safe_internal_url(target):
            return target
    return url_for(default_endpoint, **values)


def redirect_back(default_endpoint: str, **values):
    return redirect(get_safe_return_url(default_endpoint, **values))
