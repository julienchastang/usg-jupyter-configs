from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pytest


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not set")
    return value


def _signed_launch_url(*, base_url: str, notebook_id: str, secret: str) -> str:
    ts = int(time.time())
    message = f"nb={notebook_id}&ts={ts}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"{base_url.rstrip('/')}/launch?{urlencode({'nb': notebook_id, 'ts': ts, 'sig': sig})}"


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def test_signed_launch_through_hub_path() -> None:
    base_url = _required_env("NBLAUNCH_E2E_BASE_URL")
    hmac_secret = _required_env("NBLAUNCH_E2E_HMAC_SECRET")
    notebook_id = _required_env("NBLAUNCH_E2E_NOTEBOOK_ID")
    expected_redirect_prefix = _required_env("NBLAUNCH_E2E_EXPECT_REDIRECT_PREFIX")
    cookie_header = os.environ.get("NBLAUNCH_E2E_COOKIE_HEADER", "").strip()

    request = Request(_signed_launch_url(base_url=base_url, notebook_id=notebook_id, secret=hmac_secret))
    if cookie_header:
        request.add_header("Cookie", cookie_header)

    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=20) as response:
            final_url = response.geturl()
            status_code = response.status
            headers = response.headers
    except HTTPError as exc:
        final_url = exc.headers.get("Location", "")
        status_code = exc.code
        headers = exc.headers

    redirect_target = headers.get("Location", final_url)
    parsed = urlparse(redirect_target)

    assert status_code in {302, 303, 307}
    assert redirect_target.startswith(expected_redirect_prefix), redirect_target
    assert parsed.path
