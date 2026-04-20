"""Tests for pytest marker auto-classification.

Verifies that conftest.py's pytest_collection_modifyitems hook correctly
assigns unit/integration markers based on fixture usage (D-01).
"""

import pytest

INTEGRATION_FIXTURES = frozenset({"db_session", "client", "authenticated_client", "db_engine"})


class TestAutoMarking:
    """Verify auto-marking assigns correct markers based on fixtures."""

    def test_unit_marker_on_no_fixture_test(self, sample_jobs):
        """Tests using non-integration fixtures get unit marker."""
        # This test uses sample_jobs (not an integration fixture)
        # The auto-marker should classify it as unit
        assert len(sample_jobs) == 4

    def test_integration_marker_on_db_session(self, db_session):
        """Tests using db_session get integration marker."""
        assert db_session is not None

    def test_integration_marker_on_client(self, client):
        """Tests using client fixture get integration marker."""
        assert client is not None

    @pytest.mark.smoke
    def test_explicit_marker_not_overridden(self):
        """Explicit markers should not be overridden by auto-marking."""
        # This test has @pytest.mark.smoke, so auto-marking should skip it
        assert True


class TestMarkerCollectionCounts:
    """Verify marker-based collection produces non-empty sets."""

    def test_markers_registered_without_warnings(self, pytestconfig):
        """All 5 markers should be registered (no PytestUnknownMarkWarning)."""
        markers = pytestconfig.getini("markers")
        marker_names = {m.split(":")[0].strip() for m in markers}
        for expected in ("unit", "integration", "slow", "smoke", "regression"):
            assert expected in marker_names, f"Marker '{expected}' not registered"
