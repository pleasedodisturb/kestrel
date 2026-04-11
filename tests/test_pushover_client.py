"""Unit tests for `career_os.services.pushover_client.PushoverClient`.

Direct tests for the HTTP client class. Existing `tests/test_pushover.py`
tests the higher-level service wrappers (alerts, ghost notifications);
this file isolates the raw client class so its body-building and HTTP
error handling are exercised independently.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from career_os.services.pushover_client import (
    PRIORITY_EMERGENCY,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PushoverAPIError,
    PushoverAuthError,
    PushoverClient,
)


def _resp(status_code=200, payload=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or ("ok" if payload is None else "json")
    resp.json.return_value = payload if payload is not None else {"status": 1, "request": "abc"}
    return resp


# ---------------------------------------------------------------------------
# _build_pushover_body — pure-function tests
# ---------------------------------------------------------------------------


def test_build_body_includes_required_fields_only_by_default():
    body = PushoverClient._build_pushover_body("tok", "user", "Hello")
    assert body == {"token": "tok", "user": "user", "message": "Hello"}


def test_build_body_includes_optional_fields_when_set():
    body = PushoverClient._build_pushover_body(
        "tok",
        "user",
        "Hello",
        title="T",
        url="https://example.com",
        url_title="example",
        sound="cosmic",
        html=True,
    )
    assert body["title"] == "T"
    assert body["url"] == "https://example.com"
    assert body["url_title"] == "example"
    assert body["sound"] == "cosmic"
    assert body["html"] == 1


def test_build_body_emergency_priority_sets_retry_and_expire():
    body = PushoverClient._build_pushover_body("tok", "user", "boom", priority=PRIORITY_EMERGENCY)
    assert body["priority"] == PRIORITY_EMERGENCY
    assert body["retry"] == 60
    assert body["expire"] == 3600


def test_build_body_normal_priority_omits_priority_field():
    body = PushoverClient._build_pushover_body("tok", "user", "msg", priority=PRIORITY_NORMAL)
    assert "priority" not in body
    assert "retry" not in body
    assert "expire" not in body


def test_build_body_high_priority_no_retry_expire():
    body = PushoverClient._build_pushover_body("tok", "user", "msg", priority=PRIORITY_HIGH)
    assert body["priority"] == PRIORITY_HIGH
    assert "retry" not in body
    assert "expire" not in body


# ---------------------------------------------------------------------------
# send_notification
# ---------------------------------------------------------------------------


def test_send_notification_happy_path_returns_response_dict():
    client = PushoverClient("user-key", "app-token")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=_resp(200, {"status": 1, "request": "req-id"}),
    ) as post:
        result = client.send_notification(message="Hi", title="t")
    assert result == {"status": 1, "request": "req-id"}
    args, kwargs = post.call_args
    assert args[0].endswith("messages.json")
    body = kwargs["data"]
    assert body["message"] == "Hi"
    assert body["title"] == "t"
    assert body["token"] == "app-token"
    assert body["user"] == "user-key"


def test_send_notification_401_raises_auth_error():
    client = PushoverClient("u", "t")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=_resp(401, text="unauthorized"),
    ):
        with pytest.raises(PushoverAuthError):
            client.send_notification(message="x")


def test_send_notification_429_raises_api_error_with_status():
    client = PushoverClient("u", "t")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=_resp(429, text="too many"),
    ):
        with pytest.raises(PushoverAPIError) as exc_info:
            client.send_notification(message="x")
    assert exc_info.value.status_code == 429


def test_send_notification_4xx_parses_error_messages():
    client = PushoverClient("u", "t")
    resp = MagicMock()
    resp.status_code = 400
    resp.text = '{"errors": ["bad message"]}'
    resp.json.return_value = {"errors": ["bad message"]}
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=resp,
    ):
        with pytest.raises(PushoverAPIError) as exc_info:
            client.send_notification(message="x")
    assert "bad message" in str(exc_info.value)


def test_send_notification_status_zero_raises_api_error():
    """Pushover returns HTTP 200 with status=0 on validation failures."""
    client = PushoverClient("u", "t")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=_resp(200, {"status": 0, "errors": ["bad user key"]}),
    ):
        with pytest.raises(PushoverAPIError) as exc_info:
            client.send_notification(message="x")
    assert "bad user key" in str(exc_info.value)


def test_send_notification_wraps_httpx_errors():
    client = PushoverClient("u", "t")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        side_effect=httpx.ConnectError("dns"),
    ):
        with pytest.raises(PushoverAPIError) as exc_info:
            client.send_notification(message="x")
    assert "HTTP error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# validate_credentials
# ---------------------------------------------------------------------------


def test_validate_credentials_happy_path():
    client = PushoverClient("u", "t")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=_resp(200, {"status": 1}),
    ) as post:
        ok = client.validate_credentials()
    assert ok is True
    assert post.call_args.args[0].endswith("validate.json")


def test_validate_credentials_401_raises_auth_error():
    client = PushoverClient("u", "t")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=_resp(401, text="bad"),
    ):
        with pytest.raises(PushoverAuthError):
            client.validate_credentials()


def test_validate_credentials_status_zero_raises_auth_error():
    client = PushoverClient("u", "t")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=_resp(200, {"status": 0, "errors": ["bad"]}),
    ):
        with pytest.raises(PushoverAuthError):
            client.validate_credentials()


def test_validate_credentials_invalid_json_raises_api_error():
    client = PushoverClient("u", "t")
    resp = MagicMock()
    resp.status_code = 200
    resp.text = "<html>not json</html>"
    resp.json.side_effect = ValueError("bad json")
    with patch(
        "career_os.services.pushover_client.httpx.post",
        return_value=resp,
    ):
        with pytest.raises(PushoverAPIError):
            client.validate_credentials()
