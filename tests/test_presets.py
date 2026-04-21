"""Tests for the cost presets system (G-442)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from career_os.main import app
from career_os.services.presets import (
    DEFAULT_PRESET,
    PRESETS,
    CostPreset,
    apply_preset,
    get_active_preset_name,
    get_preset,
    list_presets,
)

# ---------------------------------------------------------------------------
# Service layer tests
# ---------------------------------------------------------------------------


class TestListPresets:
    """list_presets() returns all defined presets."""

    def test_returns_all_five_presets(self):
        result = list_presets()
        assert len(result) == 5
        assert all(isinstance(p, CostPreset) for p in result)

    def test_preset_names_match_keys(self):
        result = list_presets()
        names = {p.name for p in result}
        assert names == {"free", "budget", "quality", "private", "custom"}


class TestGetPreset:
    """get_preset() looks up a single preset by name."""

    def test_known_preset_returns_dataclass(self):
        preset = get_preset("budget")
        assert preset is not None
        assert preset.name == "budget"
        assert preset.provider == "openrouter"

    def test_unknown_preset_returns_none(self):
        result = get_preset("nonexistent")
        assert result is None


class TestApplyPreset:
    """apply_preset() activates a preset and mutates runtime settings."""

    def test_apply_budget_sets_provider_and_model(self):
        preset = apply_preset("budget")
        assert preset.name == "budget"
        assert preset.provider == "openrouter"
        assert preset.model == "openai/gpt-4o-mini"

    def test_apply_quality_sets_moderate_prefilter(self):
        preset = apply_preset("quality")
        assert preset.prefilter_strategy == "moderate"
        assert preset.batch_size == 15

    def test_apply_free_sets_strict_prefilter(self):
        preset = apply_preset("free")
        assert preset.prefilter_strategy == "strict"
        assert preset.batch_size == 5

    def test_apply_private_uses_together(self):
        preset = apply_preset("private")
        assert preset.provider == "together"
        assert "Llama" in preset.model

    def test_apply_custom_does_not_crash(self):
        preset = apply_preset("custom")
        assert preset.name == "custom"
        assert preset.estimated_cost == "varies"

    def test_apply_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown preset 'bogus'"):
            apply_preset("bogus")

    def test_apply_changes_active_preset_name(self):
        apply_preset("quality")
        assert get_active_preset_name() == "quality"
        # Reset to default for other tests
        apply_preset(DEFAULT_PRESET)


class TestGetActivePresetName:
    """get_active_preset_name() resolves from settings or returns default."""

    def test_returns_string(self):
        name = get_active_preset_name()
        assert isinstance(name, str)
        assert name in PRESETS


class TestPresetDataIntegrity:
    """Every preset has required fields populated (except custom)."""

    @pytest.mark.parametrize("name", ["free", "budget", "quality", "private"])
    def test_non_custom_presets_have_provider_and_model(self, name: str):
        preset = PRESETS[name]
        assert preset.provider != ""
        assert preset.model != ""

    def test_custom_preset_has_empty_provider(self):
        preset = PRESETS["custom"]
        assert preset.provider == ""
        assert preset.model == ""

    def test_all_presets_have_description_and_cost(self):
        for name, preset in PRESETS.items():
            assert preset.description, f"{name} missing description"
            assert preset.estimated_cost, f"{name} missing estimated_cost"


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


class TestPresetsAPI:
    """HTTP tests for /api/presets endpoints."""

    def test_list_presets_returns_200(self, api_client: TestClient):
        resp = api_client.get("/api/presets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 5
        assert len(body["presets"]) == 5

    def test_list_presets_contains_budget(self, api_client: TestClient):
        resp = api_client.get("/api/presets")
        names = [p["name"] for p in resp.json()["presets"]]
        assert "budget" in names
        assert "free" in names

    def test_get_active_preset_returns_200(self, api_client: TestClient):
        resp = api_client.get("/api/presets/active")
        assert resp.status_code == 200
        body = resp.json()
        assert "active" in body
        assert "preset" in body
        assert body["preset"]["name"] == body["active"]

    def test_set_active_preset_budget(self, api_client: TestClient):
        resp = api_client.put("/api/presets/active", json={"name": "budget"})
        assert resp.status_code == 200
        assert resp.json()["active"] == "budget"
        assert resp.json()["preset"]["provider"] == "openrouter"

    def test_set_active_preset_quality(self, api_client: TestClient):
        resp = api_client.put("/api/presets/active", json={"name": "quality"})
        assert resp.status_code == 200
        assert resp.json()["active"] == "quality"
        assert resp.json()["preset"]["prefilter_strategy"] == "moderate"
        # Reset
        api_client.put("/api/presets/active", json={"name": "budget"})

    def test_set_unknown_preset_returns_400(self, api_client: TestClient):
        resp = api_client.put("/api/presets/active", json={"name": "nonexistent"})
        assert resp.status_code == 400
        assert "Unknown preset" in resp.json()["detail"]

    def test_set_preset_missing_name_returns_422(self, api_client: TestClient):
        resp = api_client.put("/api/presets/active", json={})
        assert resp.status_code == 422
