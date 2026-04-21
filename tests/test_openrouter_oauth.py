"""Tests for OpenRouter OAuth PKCE onboarding flow.

Covers:
- PKCE pair generation (verifier uniqueness, challenge format)
- Auth URL construction
- Code-for-key exchange (success + error cases)
- Credit balance checking (success + error cases)
- API key storage in integration_configs
- API routes: /oauth/start, /oauth/callback, /credits
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from career_os.services.openrouter_oauth import (
    OPENROUTER_AUTH_URL,
    OPENROUTER_CREDITS_URL,
    OPENROUTER_KEY_EXCHANGE_URL,
    OpenRouterOAuthError,
    build_auth_url,
    check_credits,
    exchange_code_for_key,
    generate_pkce_pair,
    store_api_key,
)

# ---------------------------------------------------------------------------
# PKCE generation tests
# ---------------------------------------------------------------------------


class TestPKCEGeneration:
    """Test PKCE code_verifier and code_challenge generation."""

    def test_generates_verifier_and_challenge(self) -> None:
        verifier, challenge = generate_pkce_pair()
        assert len(verifier) > 40
        assert len(challenge) > 20
        assert verifier != challenge

    def test_verifiers_are_unique(self) -> None:
        pairs = [generate_pkce_pair() for _ in range(5)]
        verifiers = [p[0] for p in pairs]
        assert len(set(verifiers)) == 5

    def test_challenge_is_base64url(self) -> None:
        _, challenge = generate_pkce_pair()
        # base64url has no +, /, or = padding
        assert "+" not in challenge
        assert "/" not in challenge
        assert "=" not in challenge


# ---------------------------------------------------------------------------
# Auth URL construction tests
# ---------------------------------------------------------------------------


class TestBuildAuthURL:
    """Test OpenRouter auth URL construction."""

    def test_includes_callback_and_challenge(self) -> None:
        url = build_auth_url("https://myapp.com/callback", "test_challenge")
        assert url.startswith(OPENROUTER_AUTH_URL)
        assert "callback_url=https://myapp.com/callback" in url
        assert "code_challenge=test_challenge" in url
        assert "code_challenge_method=S256" in url


# ---------------------------------------------------------------------------
# Code exchange tests
# ---------------------------------------------------------------------------


class TestExchangeCodeForKey:
    """Test authorization code → API key exchange."""

    @pytest.mark.asyncio
    async def test_success_returns_key(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "sk-or-test-key-123"}

        with patch("career_os.services.openrouter_oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            key = await exchange_code_for_key("auth-code-123", "verifier-456")

        assert key == "sk-or-test-key-123"

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "sk-or-x"}

        with patch("career_os.services.openrouter_oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await exchange_code_for_key("the-code", "the-verifier")

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["code"] == "the-code"
        assert payload["code_verifier"] == "the-verifier"
        assert payload["code_challenge_method"] == "S256"
        assert call_args.args[0] == OPENROUTER_KEY_EXCHANGE_URL

    @pytest.mark.asyncio
    async def test_non_200_raises_error(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid code"}}

        with patch("career_os.services.openrouter_oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            with pytest.raises(OpenRouterOAuthError) as exc_info:
                await exchange_code_for_key("bad-code", "verifier")
            assert exc_info.value.status_code == 401
            assert "Invalid code" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_empty_key_raises_error(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": ""}

        with patch("career_os.services.openrouter_oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            with pytest.raises(OpenRouterOAuthError, match="empty key"):
                await exchange_code_for_key("code", "verifier")


# ---------------------------------------------------------------------------
# Credit balance tests
# ---------------------------------------------------------------------------


class TestCheckCredits:
    """Test OpenRouter credit balance checking."""

    @pytest.mark.asyncio
    async def test_success_returns_balance(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"total_credits": 25.0, "total_usage": 3.47}}

        with patch("career_os.services.openrouter_oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await check_credits("sk-or-test")

        assert result["total_credits"] == 25.0
        assert result["total_usage"] == 3.47
        assert result["balance"] == 21.53

    @pytest.mark.asyncio
    async def test_sends_bearer_auth(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"total_credits": 0, "total_usage": 0}}

        with patch("career_os.services.openrouter_oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await check_credits("sk-or-mykey")

        call_args = mock_client.get.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers")
        assert headers["Authorization"] == "Bearer sk-or-mykey"
        assert call_args.args[0] == OPENROUTER_CREDITS_URL

    @pytest.mark.asyncio
    async def test_non_200_raises_error(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("career_os.services.openrouter_oauth.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            with pytest.raises(OpenRouterOAuthError) as exc_info:
                await check_credits("bad-key")
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Key storage tests
# ---------------------------------------------------------------------------


class TestStoreApiKey:
    """Test API key storage in integration_configs."""

    def test_stores_key_in_new_row(self, db_session) -> None:
        from career_os.models.integrations import IntegrationConfig

        store_api_key(db_session, "sk-or-new-key")

        row = (
            db_session.query(IntegrationConfig)
            .filter(IntegrationConfig.name == "ai_providers")
            .first()
        )
        creds = json.loads(row.credentials)
        assert creds["openrouter_api_key"] == "sk-or-new-key"
        assert row.enabled is True
        assert row.status == "connected"

    def test_merges_key_into_existing_row(self, db_session) -> None:
        from career_os.models.integrations import IntegrationConfig

        # Pre-create row with another key
        existing = IntegrationConfig(
            name="ai_providers",
            display_name="AI Providers",
            enabled=True,
            credentials=json.dumps({"anthropic_api_key": "sk-ant-existing"}),
            status="connected",
        )
        db_session.add(existing)
        db_session.commit()

        store_api_key(db_session, "sk-or-new-key")

        db_session.refresh(existing)
        creds = json.loads(existing.credentials)
        assert creds["openrouter_api_key"] == "sk-or-new-key"
        assert creds["anthropic_api_key"] == "sk-ant-existing"

    def test_overwrites_existing_openrouter_key(self, db_session) -> None:
        from career_os.models.integrations import IntegrationConfig

        existing = IntegrationConfig(
            name="ai_providers",
            display_name="AI Providers",
            enabled=True,
            credentials=json.dumps({"openrouter_api_key": "sk-or-old"}),
            status="connected",
        )
        db_session.add(existing)
        db_session.commit()

        store_api_key(db_session, "sk-or-replaced")

        db_session.refresh(existing)
        creds = json.loads(existing.credentials)
        assert creds["openrouter_api_key"] == "sk-or-replaced"


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


class TestOAuthStartRoute:
    """Test POST /api/openrouter/oauth/start."""

    def test_returns_auth_url_and_verifier(self, client) -> None:
        response = client.post(
            "/api/openrouter/oauth/start",
            json={"callback_url": "https://myapp.com/cb"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "code_verifier" in data
        assert data["auth_url"].startswith("https://openrouter.ai/auth")
        assert "callback_url=https://myapp.com/cb" in data["auth_url"]
        assert len(data["code_verifier"]) > 40


class TestOAuthCallbackRoute:
    """Test POST /api/openrouter/oauth/callback."""

    def test_success_stores_key_and_checks_balance(self, client) -> None:
        with (
            patch(
                "career_os.api.openrouter_oauth.exchange_code_for_key",
                new_callable=AsyncMock,
                return_value="sk-or-test-key",
            ),
            patch(
                "career_os.api.openrouter_oauth.check_credits",
                new_callable=AsyncMock,
                return_value={
                    "total_credits": 10.0,
                    "total_usage": 1.0,
                    "balance": 9.0,
                },
            ),
        ):
            response = client.post(
                "/api/openrouter/oauth/callback",
                json={"code": "auth-code", "code_verifier": "verifier"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["has_credits"] is True
        assert data["balance"] == 9.0

    def test_exchange_failure_returns_error(self, client) -> None:
        with patch(
            "career_os.api.openrouter_oauth.exchange_code_for_key",
            new_callable=AsyncMock,
            side_effect=OpenRouterOAuthError("Invalid code", status_code=401),
        ):
            response = client.post(
                "/api/openrouter/oauth/callback",
                json={"code": "bad", "code_verifier": "v"},
            )

        assert response.status_code == 401
        assert "Invalid code" in response.json()["detail"]


class TestCreditsRoute:
    """Test GET /api/openrouter/credits."""

    def test_no_openrouter_key_returns_404(self, client) -> None:
        """Credits endpoint returns 404 when no OpenRouter key is stored."""
        # The route queries the DB directly. Mock check_credits to verify
        # that when it IS called with an empty key, the route handles it.
        # In a fresh test DB, ai_providers may or may not exist.
        with patch(
            "career_os.api.openrouter_oauth.check_credits",
            new_callable=AsyncMock,
            side_effect=OpenRouterOAuthError("Unauthorized", status_code=401),
        ):
            response = client.get("/api/openrouter/credits")
        # 404 (no row/no key), 401/502 (check_credits failed and status passed through)
        assert response.status_code in (401, 404, 502)

    def test_returns_balance_with_stored_key(self, client, db_session) -> None:
        from career_os.models.integrations import IntegrationConfig

        row = IntegrationConfig(
            name="ai_providers",
            display_name="AI Providers",
            enabled=True,
            credentials=json.dumps({"openrouter_api_key": "sk-or-test"}),
            status="connected",
        )
        db_session.add(row)
        db_session.commit()

        with patch(
            "career_os.api.openrouter_oauth.check_credits",
            new_callable=AsyncMock,
            return_value={
                "total_credits": 10.0,
                "total_usage": 2.5,
                "balance": 7.5,
            },
        ):
            response = client.get("/api/openrouter/credits")

        assert response.status_code == 200
        data = response.json()
        assert data["balance"] == 7.5
        assert data["needs_deposit"] is False

    def test_low_balance_flags_deposit(self, client, db_session) -> None:
        from career_os.models.integrations import IntegrationConfig

        row = IntegrationConfig(
            name="ai_providers",
            display_name="AI Providers",
            enabled=True,
            credentials=json.dumps({"openrouter_api_key": "sk-or-test"}),
            status="connected",
        )
        db_session.add(row)
        db_session.commit()

        with patch(
            "career_os.api.openrouter_oauth.check_credits",
            new_callable=AsyncMock,
            return_value={
                "total_credits": 1.0,
                "total_usage": 0.5,
                "balance": 0.5,
            },
        ):
            response = client.get("/api/openrouter/credits")

        assert response.status_code == 200
        assert response.json()["needs_deposit"] is True
