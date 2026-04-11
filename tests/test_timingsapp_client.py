"""Unit tests for `career_os.services.timingsapp_client.TimingsAppClient`.

Patches `httpx.request` to exercise the HTTP surface in isolation. The
existing `tests/test_timingsapp.py` covers the higher-level service
functions; this file targets the raw client class directly so that
network/error handling is verified independently.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from career_os.services.timingsapp_client import (
    TimingsAppAPIError,
    TimingsAppClient,
)


def _resp(status_code=200, payload=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or ("ok" if payload is None else "json")
    resp.json.return_value = payload if payload is not None else {}
    return resp


# ---------------------------------------------------------------------------
# start_timer / stop_timer / create_time_entry
# ---------------------------------------------------------------------------


def test_start_timer_unwraps_data_field():
    client = TimingsAppClient("tkn")
    payload = {"data": {"id": "te-1", "title": "Researching"}}
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(200, payload),
    ) as req:
        result = client.start_timer(project="P1", title="Researching", notes="n")
    assert result == {"id": "te-1", "title": "Researching"}
    args, kwargs = req.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/time-entries/start")
    assert kwargs["json"]["project"] == "P1"
    assert kwargs["json"]["title"] == "Researching"
    assert kwargs["json"]["notes"] == "n"
    assert kwargs["headers"]["Authorization"] == "Bearer tkn"


def test_start_timer_minimal_omits_notes():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(200, {"data": {"id": "x"}}),
    ) as req:
        client.start_timer(project="P", title="T")
    assert "notes" not in req.call_args.kwargs["json"]


def test_stop_timer_uses_put_method():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(200, {"data": {"id": "stopped"}}),
    ) as req:
        client.stop_timer()
    assert req.call_args.args[0] == "PUT"
    assert req.call_args.args[1].endswith("/time-entries/stop")


def test_create_time_entry_serializes_dates():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(200, {"data": {"id": "e1"}}),
    ) as req:
        client.create_time_entry(
            project="P",
            title="T",
            start_date=datetime(2026, 4, 11, 9, 0, 0),
            end_date=datetime(2026, 4, 11, 10, 0, 0),
            notes="x",
        )
    body = req.call_args.kwargs["json"]
    assert body["start_date"] == "2026-04-11T09:00:00+00:00"
    assert body["end_date"] == "2026-04-11T10:00:00+00:00"
    assert body["notes"] == "x"


# ---------------------------------------------------------------------------
# get_running_timer / list_time_entries / test_connection
# ---------------------------------------------------------------------------


def test_get_running_timer_returns_none_on_404():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(404, text="not running"),
    ):
        result = client.get_running_timer()
    assert result is None


def test_get_running_timer_returns_data_on_hit():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(200, {"data": {"id": "running"}}),
    ):
        result = client.get_running_timer()
    assert result == {"id": "running"}


def test_get_running_timer_propagates_other_errors():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(500, text="boom"),
    ):
        with pytest.raises(TimingsAppAPIError):
            client.get_running_timer()


def test_list_time_entries_passes_date_params():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(200, {"data": [{"id": "e1"}, {"id": "e2"}]}),
    ) as req:
        out = client.list_time_entries(start_date="2026-04-01", end_date="2026-04-30")
    assert [e["id"] for e in out] == ["e1", "e2"]
    assert req.call_args.kwargs["params"]["start_date_min"] == "2026-04-01"
    assert req.call_args.kwargs["params"]["start_date_max"] == "2026-04-30"


def test_list_time_entries_returns_empty_list_when_no_data():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(204, text=""),
    ):
        out = client.list_time_entries()
    assert out == []


def test_test_connection_true_when_data_present():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(200, {"data": [{"id": "p1"}]}),
    ):
        assert client.test_connection() is True


def test_test_connection_false_on_error():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(401, text="bad token"),
    ):
        assert client.test_connection() is False


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "snippet"),
    [
        (401, "Unauthorized"),
        (403, "Forbidden"),
        (404, "Not found"),
        (429, "Rate limited"),
        (500, "TimingsApp API error 500"),
    ],
)
def test_request_maps_errors_to_api_error(status, snippet):
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(status, text="oops"),
    ):
        with pytest.raises(TimingsAppAPIError) as exc_info:
            client.start_timer(project="p", title="t")
    assert snippet in str(exc_info.value)
    assert exc_info.value.status_code == status


def test_request_wraps_httpx_connection_error():
    client = TimingsAppClient("tkn")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        side_effect=httpx.ConnectError("nope"),
    ):
        with pytest.raises(TimingsAppAPIError) as exc_info:
            client.start_timer(project="p", title="t")
    assert "HTTP error" in str(exc_info.value)


def test_custom_base_url_strips_trailing_slash():
    client = TimingsAppClient("tkn", base_url="http://localhost:1234/")
    with patch(
        "career_os.services.timingsapp_client.httpx.request",
        return_value=_resp(200, {"data": [{"id": "p1"}]}),
    ) as req:
        client.test_connection()
    url = req.call_args.args[1]
    assert url == "http://localhost:1234/projects"
