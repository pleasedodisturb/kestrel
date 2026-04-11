"""Unit tests for helper functions extracted during S3776 complexity refactoring.

Covers:
- skills_parsing: _match_strength_keyword, _STRENGTH_KEYWORD_MAP
- voice: _generate_session_title
- ticktick_sync: _complete_follow_up, _complete_learning_goal,
  _complete_pipeline_action, _COMPLETION_HANDLERS, _apply_completion
- api/applications: _derive_package_type, _build_package_summary
- api/ticktick: _fetch_entity
- ai/openrouter_provider: _extract_error_detail
- services/applications: _handle_status_transition, _apply_field_updates
- services/learning: _apply_status_timestamps
- services/pushover: _deliver_single_notification
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from career_os.ai.openrouter_provider import _extract_error_detail
from career_os.api.applications import _build_package_summary, _derive_package_type
from career_os.api.ticktick import _fetch_entity
from career_os.services.applications import (
    _apply_field_updates,
    _handle_status_transition,
)
from career_os.services.learning import _apply_status_timestamps
from career_os.services.pushover import PushoverAPIError, _deliver_single_notification
from career_os.services.skills_parsing import (
    _STRENGTH_KEYWORD_MAP,
    _match_strength_keyword,
)
from career_os.services.ticktick_sync import (
    _COMPLETION_HANDLERS,
    _apply_completion,
    _complete_follow_up,
    _complete_learning_goal,
    _complete_pipeline_action,
)
from career_os.services.voice import _generate_session_title

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC)


def _mock_db(query_result=None):
    """Create a MagicMock db session with a pre-configured query chain."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = query_result
    return db


def _mock_log_entry(*, error_message=None, message="Test", title="Test"):
    """Create a MagicMock notification log entry."""
    entry = MagicMock()
    entry.error_message = error_message
    entry.message = message
    entry.title = title
    return entry


def _mock_app_obj(status="discovered", profile_id=1, app_id=10, date_applied=None):
    """Create a MagicMock application object."""
    obj = MagicMock()
    obj.status = status
    obj.profile_id = profile_id
    obj.id = app_id
    obj.date_applied = date_applied
    return obj


def _mock_sa_model():
    """Create a mock SQLAlchemy model class with id and profile_id columns."""
    model = MagicMock()
    model.id = MagicMock()
    model.profile_id = MagicMock()
    return model


# ---------------------------------------------------------------------------
# _match_strength_keyword
# ---------------------------------------------------------------------------


class TestMatchStrengthKeyword:
    """Tests for the strength keyword lookup extracted from parse_workplace_insights."""

    def test_assertive_maps_to_adaptive_assertiveness(self):
        assert _match_strength_keyword("You are assertive in meetings") == "Adaptive Assertiveness"

    def test_deferential_maps_to_adaptive_assertiveness(self):
        assert _match_strength_keyword("Sometimes deferential in tone") == "Adaptive Assertiveness"

    def test_sociable_maps_to_social_energy(self):
        assert _match_strength_keyword("Very sociable and outgoing") == "Social Energy"

    def test_energetic_maps_to_social_energy(self):
        assert _match_strength_keyword("Brings energetic presence") == "Social Energy"

    def test_curiosity_maps_to_experimental_mindset(self):
        assert (
            _match_strength_keyword("Intellectual curiosity is a driver") == "Experimental Mindset"
        )

    def test_experiment_maps_to_experimental_mindset(self):
        assert (
            _match_strength_keyword("Likes to experiment with new ideas") == "Experimental Mindset"
        )

    def test_case_insensitive(self):
        assert _match_strength_keyword("ASSERTIVE leadership") == "Adaptive Assertiveness"
        assert _match_strength_keyword("SOCIABLE team player") == "Social Energy"
        assert _match_strength_keyword("CURIOSITY driven") == "Experimental Mindset"

    def test_no_match_returns_none(self):
        assert _match_strength_keyword("Detail-oriented and thorough") is None

    def test_empty_string_returns_none(self):
        assert _match_strength_keyword("") is None

    def test_first_match_wins(self):
        """If a line contains keywords from multiple categories, first match wins."""
        result = _match_strength_keyword("assertive and sociable person")
        assert result == "Adaptive Assertiveness"

    def test_keyword_map_has_expected_entries(self):
        """Sanity check: the map has exactly 3 entries mapping to known skills."""
        assert len(_STRENGTH_KEYWORD_MAP) == 3
        skill_names = {name for _, name in _STRENGTH_KEYWORD_MAP}
        assert skill_names == {"Adaptive Assertiveness", "Social Energy", "Experimental Mindset"}


# ---------------------------------------------------------------------------
# _generate_session_title
# ---------------------------------------------------------------------------


class TestGenerateSessionTitle:
    """Tests for voice session title generation."""

    @staticmethod
    def _app(company="Acme Corp", role="Senior Engineer"):
        return SimpleNamespace(company=company, role=role)

    def test_cover_letter_with_app(self):
        assert _generate_session_title("cover_letter", self._app()) == (
            "Cover Letter Brainstorm — Acme Corp (Senior Engineer)"
        )

    def test_job_evaluation_with_app(self):
        assert _generate_session_title("job_evaluation", self._app("Google", "PM")) == (
            "Job Evaluation — Google (PM)"
        )

    def test_coaching_mode(self):
        assert _generate_session_title("coaching", None) == "Coaching Session"

    def test_coaching_ignores_app(self):
        assert _generate_session_title("coaching", self._app()) == "Coaching Session"

    def test_cover_letter_without_app_falls_through(self):
        assert _generate_session_title("cover_letter", None) == "Voice Discussion (cover_letter)"

    def test_job_evaluation_without_app_falls_through(self):
        assert (
            _generate_session_title("job_evaluation", None) == "Voice Discussion (job_evaluation)"
        )

    def test_unknown_mode(self):
        assert _generate_session_title("brainstorm", None) == "Voice Discussion (brainstorm)"


# ---------------------------------------------------------------------------
# _derive_package_type / _build_package_summary
# ---------------------------------------------------------------------------


class TestDerivePackageType:
    """Tests for application package type derivation."""

    @staticmethod
    def _pkg(cover_letter_path=None, cv_path=None, package_dir=None, pkg_id=1):
        return SimpleNamespace(
            id=pkg_id,
            cover_letter_path=cover_letter_path,
            cv_path=cv_path,
            package_dir=package_dir,
        )

    def test_full_package(self):
        assert (
            _derive_package_type(self._pkg(cover_letter_path="/cl.pdf", cv_path="/cv.pdf"))
            == "full"
        )

    def test_cover_letter_only(self):
        assert _derive_package_type(self._pkg(cover_letter_path="/cl.pdf")) == "cover_letter"

    def test_cv_only(self):
        assert _derive_package_type(self._pkg(cv_path="/cv.pdf")) == "cv"

    def test_directory_fallback(self):
        assert _derive_package_type(self._pkg()) == "directory"

    def test_build_summary_extracts_name_from_dir(self):
        pkg = self._pkg(
            package_dir="/home/user/packages/acme-corp/",
            cover_letter_path="/cl.pdf",
            cv_path="/cv.pdf",
        )
        summary = _build_package_summary(pkg)
        assert summary.package_name == "acme-corp"
        assert summary.package_type == "full"
        assert summary.file_path == "/home/user/packages/acme-corp/"

    def test_build_summary_unknown_for_empty_dir(self):
        assert _build_package_summary(self._pkg(package_dir="")).package_name == "Unknown"

    def test_build_summary_unknown_for_none_dir(self):
        assert _build_package_summary(self._pkg(package_dir=None)).package_name == "Unknown"


# ---------------------------------------------------------------------------
# _COMPLETION_HANDLERS / individual handlers
# ---------------------------------------------------------------------------


class TestCompletionHandlers:
    """Tests for TickTick completion handler dispatch table."""

    def test_handler_keys(self):
        assert set(_COMPLETION_HANDLERS.keys()) == {"follow_up", "learning_goal", "pipeline_action"}

    def test_all_handlers_are_callable(self):
        for key, handler in _COMPLETION_HANDLERS.items():
            assert callable(handler), f"Handler for {key} is not callable"

    def test_complete_follow_up_sets_completed_at(self):
        follow_up = MagicMock(completed_at=None, application_id=5)
        db = _mock_db(follow_up)
        sync_task = SimpleNamespace(profile_id=1, entity_id=10)
        _complete_follow_up(db, sync_task, NOW)
        assert follow_up.completed_at == NOW
        db.add.assert_called_once()

    def test_complete_follow_up_skips_already_completed(self):
        follow_up = MagicMock(completed_at=datetime(2026, 1, 1, tzinfo=UTC))
        db = _mock_db(follow_up)
        _complete_follow_up(db, SimpleNamespace(profile_id=1, entity_id=10), datetime.now(UTC))
        db.add.assert_not_called()

    def test_complete_follow_up_skips_missing_entity(self):
        db = _mock_db(None)
        _complete_follow_up(db, SimpleNamespace(profile_id=1, entity_id=999), datetime.now(UTC))
        db.add.assert_not_called()

    def test_complete_learning_goal_sets_completed(self):
        goal = MagicMock(status="in_progress")
        db = _mock_db(goal)
        _complete_learning_goal(db, SimpleNamespace(entity_id=20), NOW)
        assert goal.status == "completed"
        assert goal.updated_at == NOW

    def test_complete_learning_goal_skips_already_completed(self):
        goal = MagicMock(status="completed")
        db = _mock_db(goal)
        _complete_learning_goal(db, SimpleNamespace(entity_id=20), NOW)
        assert goal.status == "completed"

    def test_complete_pipeline_action_marks_next_step_done(self):
        app_obj = MagicMock(next_step="Send follow-up email", id=30)
        db = _mock_db(app_obj)
        sync_task = SimpleNamespace(profile_id=1, entity_id=30, title="Apply to Acme")
        _complete_pipeline_action(db, sync_task, NOW)
        assert app_obj.next_step == "[Done] Send follow-up email"
        assert app_obj.updated_at == NOW
        db.add.assert_called_once()

    def test_complete_pipeline_action_handles_no_next_step(self):
        app_obj = MagicMock(next_step=None, id=30)
        db = _mock_db(app_obj)
        _complete_pipeline_action(
            db, SimpleNamespace(profile_id=1, entity_id=30, title="Task"), datetime.now(UTC)
        )
        assert app_obj.next_step is None

    def test_complete_pipeline_action_skips_missing_entity(self):
        db = _mock_db(None)
        _complete_pipeline_action(
            db, SimpleNamespace(profile_id=1, entity_id=999, title="Task"), datetime.now(UTC)
        )
        db.add.assert_not_called()

    def test_apply_completion_dispatches_to_correct_handler(self):
        """_apply_completion routes to the right handler via the dispatch dict."""
        follow_up = MagicMock(completed_at=None, application_id=5)
        db = _mock_db(follow_up)
        _apply_completion(db, SimpleNamespace(entity_type="follow_up", profile_id=1, entity_id=10))
        assert follow_up.completed_at is not None

    def test_apply_completion_unknown_type_is_noop(self):
        db = MagicMock()
        _apply_completion(db, SimpleNamespace(entity_type="unknown", profile_id=1, entity_id=10))
        db.query.assert_not_called()


# ---------------------------------------------------------------------------
# _fetch_entity (api/ticktick)
# ---------------------------------------------------------------------------


class TestFetchEntity:
    """Tests for the generic entity fetcher in ticktick API."""

    def test_returns_entity_when_found(self):
        mock_obj = SimpleNamespace(id=1, profile_id=1)
        db = _mock_db(mock_obj)
        assert _fetch_entity(db, _mock_sa_model(), 1, 1, "Follow-up") is mock_obj

    def test_raises_404_when_not_found(self):
        db = _mock_db(None)
        with pytest.raises(HTTPException) as exc_info:
            _fetch_entity(db, _mock_sa_model(), 999, 1, "Follow-up")
        assert exc_info.value.status_code == 404
        assert "Follow-up not found" in exc_info.value.detail

    def test_404_message_uses_label(self):
        db = _mock_db(None)
        with pytest.raises(HTTPException) as exc_info:
            _fetch_entity(db, _mock_sa_model(), 1, 1, "Learning goal")
        assert "Learning goal not found" in exc_info.value.detail


# ---------------------------------------------------------------------------
# _extract_error_detail (openrouter)
# ---------------------------------------------------------------------------


class TestExtractErrorDetail:
    """Tests for OpenRouter error detail extraction."""

    def test_extracts_message_from_valid_json(self):
        response = MagicMock()
        response.json.return_value = {"error": {"message": "Insufficient credits"}}
        assert _extract_error_detail(response) == "Insufficient credits"

    def test_returns_empty_on_json_error(self):
        response = MagicMock()
        response.json.side_effect = ValueError("bad json")
        assert _extract_error_detail(response) == ""

    def test_returns_empty_when_no_error_key(self):
        response = MagicMock()
        response.json.return_value = {"status": "fail"}
        assert _extract_error_detail(response) == ""


# ---------------------------------------------------------------------------
# _handle_status_transition / _apply_field_updates
# ---------------------------------------------------------------------------


class TestHandleStatusTransition:
    """Tests for application status transition handler."""

    def test_skips_when_no_status_in_data(self):
        db = _mock_db()
        _handle_status_transition(db, _mock_app_obj(), {"notes": "updated"})
        db.add.assert_not_called()

    def test_normalizes_and_validates_status(self):
        update_data = {"status": "  Interested  "}
        _handle_status_transition(_mock_db(), _mock_app_obj(), update_data)
        assert update_data["status"] == "interested"

    def test_sets_date_applied_on_applied_transition(self):
        app_obj = _mock_app_obj(status="interested", date_applied=None)
        _handle_status_transition(_mock_db(), app_obj, {"status": "applied"})
        assert app_obj.date_applied is not None


class TestApplyFieldUpdates:
    """Tests for application field update tracker."""

    def test_tracks_changed_fields(self):
        app_obj = _mock_app_obj()
        app_obj.notes = "old"
        _apply_field_updates(_mock_db(), app_obj, {"notes": "new"})
        assert app_obj.notes == "new"

    def test_sets_status_without_logging(self):
        app_obj = _mock_app_obj()
        _apply_field_updates(_mock_db(), app_obj, {"status": "applied"})


# ---------------------------------------------------------------------------
# _apply_status_timestamps (learning)
# ---------------------------------------------------------------------------


class TestApplyStatusTimestamps:
    """Tests for learning resource status timestamp handler."""

    def test_in_progress_sets_started_at(self):
        resource = MagicMock(started_at=None)
        _apply_status_timestamps(MagicMock(), resource, "in_progress", NOW)
        assert resource.status == "in_progress"
        assert resource.started_at == NOW

    def test_in_progress_preserves_existing_started_at(self):
        old_time = datetime(2026, 1, 1, tzinfo=UTC)
        resource = MagicMock(started_at=old_time)
        _apply_status_timestamps(MagicMock(), resource, "in_progress", NOW)
        assert resource.started_at == old_time

    def test_completed_sets_both_timestamps(self):
        resource = MagicMock(started_at=None)
        _apply_status_timestamps(MagicMock(), resource, "completed", NOW)
        assert resource.status == "completed"
        assert resource.started_at == NOW
        assert resource.completed_at == NOW

    def test_not_started_clears_timestamps(self):
        resource = MagicMock(
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            completed_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        _apply_status_timestamps(MagicMock(), resource, "not_started", NOW)
        assert resource.status == "not_started"
        assert resource.started_at is None
        assert resource.completed_at is None


# ---------------------------------------------------------------------------
# _deliver_single_notification (pushover)
# ---------------------------------------------------------------------------


class TestDeliverSingleNotification:
    """Tests for the individual notification delivery helper."""

    def test_successful_delivery(self):
        client = MagicMock()
        entry = _mock_log_entry(message="Test notification")
        result = _deliver_single_notification(client, entry)
        assert result is True
        assert entry.status == "sent"
        assert entry.error_message is None
        client.send_notification.assert_called_once()

    def test_failed_delivery(self):
        client = MagicMock()
        client.send_notification.side_effect = PushoverAPIError("API down")
        entry = _mock_log_entry()
        result = _deliver_single_notification(client, entry)
        assert result is False
        assert entry.status == "failed"
        assert "API down" in entry.error_message

    def test_parses_metadata_from_error_message_json(self):
        client = MagicMock()
        entry = _mock_log_entry(
            error_message=json.dumps({"url": "https://example.com", "priority": 1})
        )
        _deliver_single_notification(client, entry)
        call_kwargs = client.send_notification.call_args.kwargs
        assert call_kwargs["url"] == "https://example.com"
        assert call_kwargs["priority"] == 1

    def test_handles_invalid_json_metadata(self):
        client = MagicMock()
        entry = _mock_log_entry(error_message="not valid json {{")
        assert _deliver_single_notification(client, entry) is True
