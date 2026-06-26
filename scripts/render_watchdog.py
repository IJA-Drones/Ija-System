import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone


def _env_int(name, default, *, minimum=1):
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, value)


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request(url, *, method="GET", timeout=10, headers=None, json_body=None):
    body = None
    request_headers = {
        "User-Agent": "ija-render-watchdog/1.0",
    }
    if headers:
        request_headers.update(headers)
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        method=method,
        headers=request_headers,
        data=body,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(2048).decode("utf-8", errors="replace")
        return response.status, body


def _health_is_ok(health_url, timeout):
    try:
        status, body = _request(health_url, timeout=timeout)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"Health check falhou: {exc}")
        return False

    print(f"Health check respondeu HTTP {status}: {body[:200]}")
    return 200 <= status < 300


def _trigger_render_deploy(deploy_hook_url, timeout):
    try:
        status, body = _request(deploy_hook_url, method="POST", timeout=timeout)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"Falha ao chamar deploy hook do Render: {exc}")
        return False

    print(f"Deploy hook respondeu HTTP {status}: {body[:500]}")
    return 200 <= status < 300


def _wait_for_recovery(health_url, attempts, delay, timeout):
    for attempt in range(1, attempts + 1):
        print(json.dumps({"recovery_attempt": attempt, "health_url": health_url}))
        if _health_is_ok(health_url, timeout):
            return True
        if attempt < attempts and delay > 0:
            time.sleep(delay)
    return False


def _record_watchdog_event(event_url, event_token, payload, timeout):
    if not event_url or not event_token:
        print("WATCHDOG_EVENT_URL/WATCHDOG_EVENT_TOKEN nao configurados. Evento nao registrado no painel DEV.")
        return True

    try:
        status, body = _request(
            event_url,
            method="POST",
            timeout=timeout,
            headers={"X-Watchdog-Token": event_token},
            json_body=payload,
        )
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"Falha ao registrar evento do watchdog: {exc}")
        return False

    print(f"Registro do evento respondeu HTTP {status}: {body[:500]}")
    return 200 <= status < 300


def main():
    health_url = (os.getenv("WATCHDOG_HEALTH_URL") or "").strip()
    deploy_hook_url = (os.getenv("RENDER_DEPLOY_HOOK_URL") or "").strip()
    event_url = (os.getenv("WATCHDOG_EVENT_URL") or "").strip()
    event_token = (os.getenv("WATCHDOG_EVENT_TOKEN") or "").strip()
    retries = _env_int("WATCHDOG_RETRIES", 3)
    retry_delay = _env_int("WATCHDOG_RETRY_DELAY_SECONDS", 20, minimum=0)
    timeout = _env_int("WATCHDOG_TIMEOUT_SECONDS", 10)
    recovery_retries = _env_int("WATCHDOG_RECOVERY_RETRIES", 45)
    recovery_delay = _env_int("WATCHDOG_RECOVERY_DELAY_SECONDS", 10, minimum=0)

    if not health_url:
        print("WATCHDOG_HEALTH_URL nao foi configurada.")
        return 2
    if not deploy_hook_url:
        print("RENDER_DEPLOY_HOOK_URL nao foi configurada.")
        return 2

    started_at = _utcnow_iso()
    failures = 0
    for attempt in range(1, retries + 1):
        print(json.dumps({"attempt": attempt, "health_url": health_url}))
        if _health_is_ok(health_url, timeout):
            print("Aplicacao saudavel. Nenhum deploy necessario.")
            return 0

        failures += 1
        if attempt < retries and retry_delay > 0:
            time.sleep(retry_delay)

    print(f"Aplicacao falhou {failures}/{retries} vezes. Disparando deploy do ultimo commit.")
    if not _trigger_render_deploy(deploy_hook_url, timeout):
        return 1

    recovered = _wait_for_recovery(health_url, recovery_retries, recovery_delay, timeout)
    event_payload = {
        "event_id": uuid.uuid4().hex,
        "status": "redeploy_triggered" if recovered else "redeploy_triggered_unconfirmed",
        "source": "github-actions",
        "health_url": health_url,
        "failures": failures,
        "attempts": retries,
        "started_at": started_at,
        "recovered_at": _utcnow_iso() if recovered else None,
    }
    if not _record_watchdog_event(event_url, event_token, event_payload, timeout):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
