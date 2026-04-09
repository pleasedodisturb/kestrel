"""Pushover API client.

Wraps the Pushover HTTP API (https://pushover.net/api).
All methods are synchronous (httpx) for simplicity.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_VALIDATE_URL = "https://api.pushover.net/1/users/validate.json"

# Pushover priority levels
PRIORITY_LOWEST = -2
PRIORITY_LOW = -1
PRIORITY_NORMAL = 0
PRIORITY_HIGH = 1
PRIORITY_EMERGENCY = 2


class PushoverAPIError(Exception):
    """Raised when a Pushover API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PushoverAuthError(PushoverAPIError):
    """Raised when Pushover credentials are invalid."""


class PushoverClient:
    """Synchronous client for the Pushover API."""

    def __init__(self, user_key: str, app_token: str, timeout: float = 30.0) -> None:
        self._user_key = user_key
        self._app_token = app_token
        self._timeout = timeout

    @staticmethod
    def _build_pushover_body(
        token: str,
        user: str,
        message: str,
        *,
        title: str | None = None,
        url: str | None = None,
        url_title: str | None = None,
        priority: int = PRIORITY_NORMAL,
        sound: str | None = None,
        html: bool = False,
    ) -> dict:
        """Build the Pushover API request body with all conditional fields."""
        body: dict = {
            "token": token,
            "user": user,
            "message": message,
        }
        if title:
            body["title"] = title
        if url:
            body["url"] = url
        if url_title:
            body["url_title"] = url_title
        if priority != PRIORITY_NORMAL:
            body["priority"] = priority
            if priority == PRIORITY_EMERGENCY:
                body["retry"] = 60
                body["expire"] = 3600
        if sound:
            body["sound"] = sound
        if html:
            body["html"] = 1
        return body

    def send_notification(
        self,
        *,
        message: str,
        title: str | None = None,
        url: str | None = None,
        url_title: str | None = None,
        priority: int = PRIORITY_NORMAL,
        sound: str | None = None,
        html: bool = False,
    ) -> dict:
        """Send a push notification via Pushover.

        Returns the API response dict on success.
        Raises PushoverAuthError for invalid credentials (401).
        Raises PushoverAPIError for other errors.
        """
        body = self._build_pushover_body(
            self._app_token,
            self._user_key,
            message,
            title=title,
            url=url,
            url_title=url_title,
            priority=priority,
            sound=sound,
            html=html,
        )

        try:
            resp = httpx.post(
                PUSHOVER_API_URL,
                data=body,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise PushoverAPIError(f"HTTP error: {exc}") from exc

        if resp.status_code == 401:
            raise PushoverAuthError("Invalid Pushover credentials (user key or app token)", 401)
        if resp.status_code == 429:
            raise PushoverAPIError("Rate limited by Pushover API", 429)
        if resp.status_code >= 400:
            # Parse error details from response
            try:
                error_data = resp.json()
                errors = error_data.get("errors", [])
                msg = "; ".join(errors) if errors else resp.text
            except Exception:
                msg = resp.text
            raise PushoverAPIError(
                f"Pushover API error {resp.status_code}: {msg}",
                resp.status_code,
            )

        result = resp.json()
        if result.get("status") != 1:
            errors = result.get("errors", [])
            raise PushoverAPIError(f"Pushover rejected message: {'; '.join(errors)}")

        logger.info("Pushover notification sent successfully (request=%s)", result.get("request"))
        return result

    def validate_credentials(self) -> bool:
        """Validate user key and app token against Pushover API.

        Returns True if credentials are valid.
        Raises PushoverAuthError if invalid.
        """
        try:
            resp = httpx.post(
                PUSHOVER_VALIDATE_URL,
                data={
                    "token": self._app_token,
                    "user": self._user_key,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise PushoverAPIError(f"HTTP error: {exc}") from exc

        if resp.status_code == 401:
            raise PushoverAuthError("Invalid Pushover credentials", 401)

        try:
            data = resp.json()
        except Exception as exc:
            raise PushoverAPIError(f"Invalid response: {resp.text}") from exc

        if data.get("status") != 1:
            errors = data.get("errors", [])
            raise PushoverAuthError(f"Validation failed: {'; '.join(errors)}", resp.status_code)

        return True
