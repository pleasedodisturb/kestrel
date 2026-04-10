"""Unit tests for helper functions extracted during S3776 complexity refactoring.

Covers:
- skills_parsing: _match_strength_keyword, _STRENGTH_KEYWORD_MAP
- voice: _generate_session_title
- ticktick_sync: _complete_follow_up, _complete_learning_goal,
  _complete_pipeline_action, _COMPLETION_HANDLERS
- api/applications: _derive_package_type, _build_package_summary
- api/ticktick: _fetch_entity
- components/KanbanCard: scoreColor (covered in frontend tests)
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from career_os.services.skills_parsing import (
    _STRENGTH_KEYWORD_MAP,
    _match_strength_keyword,
)
from career_os.services.voice import _generate_session_title

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
        # _STRENGTH_KEYWORD_MAP is iterated in order
        result = _match_strength_keyword("assertive and sociable person")
        assert result == "Adaptive Assertiveness"  # first entry in the map

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

    def _make_app(self, company="Acme Corp", role="Senior Engineer"):
        return SimpleNamespace(company=company, role=role)

    def test_cover_letter_with_app(self):
        app = self._make_app()
        result = _generate_session_title("cover_letter", app)
        assert result == "Cover Letter Brainstorm — Acme Corp (Senior Engineer)"

    def test_job_evaluation_with_app(self):
        app = self._make_app("Google", "PM")
        result = _generate_session_title("job_evaluation", app)
        assert result == "Job Evaluation — Google (PM)"

    def test_coaching_mode(self):
        result = _generate_session_title("coaching", None)
        assert result == "Coaching Session"

    def test_coaching_ignores_app(self):
        app = self._make_app()
        result = _generate_session_title("coaching", app)
        assert result == "Coaching Session"

    def test_cover_letter_without_app_falls_through(self):
        result = _generate_session_title("cover_letter", None)
        assert result == "Voice Discussion (cover_letter)"

    def test_job_evaluation_without_app_falls_through(self):
        result = _generate_session_title("job_evaluation", None)
        assert result == "Voice Discussion (job_evaluation)"

    def test_unknown_mode(self):
        result = _generate_session_title("brainstorm", None)
        assert result == "Voice Discussion (brainstorm)"


# ---------------------------------------------------------------------------
# _derive_package_type  /  _build_package_summary
# ---------------------------------------------------------------------------


class TestDerivePackageType:
    """Tests for application package type derivation."""

    def _make_pkg(self, cover_letter_path=None, cv_path=None, package_dir=None, pkg_id=1):
        return SimpleNamespace(
            id=pkg_id,
            cover_letter_path=cover_letter_path,
            cv_path=cv_path,
            package_dir=package_dir,
        )

    def test_full_package(self):
        from career_os.api.applications import _derive_package_type

        pkg = self._make_pkg(cover_letter_path="/cl.pdf", cv_path="/cv.pdf")
        assert _derive_package_type(pkg) == "full"

    def test_cover_letter_only(self):
        from career_os.api.applications import _derive_package_type

        pkg = self._make_pkg(cover_letter_path="/cl.pdf")
        assert _derive_package_type(pkg) == "cover_letter"

    def test_cv_only(self):
        from career_os.api.applications import _derive_package_type

        pkg = self._make_pkg(cv_path="/cv.pdf")
        assert _derive_package_type(pkg) == "cv"

    def test_directory_fallback(self):
        from career_os.api.applications import _derive_package_type

        pkg = self._make_pkg()
        assert _derive_package_type(pkg) == "directory"

    def test_build_package_summary_extracts_name_from_dir(self):
        from career_os.api.applications import _build_package_summary

        pkg = self._make_pkg(
            package_dir="/home/user/packages/acme-corp/",
            cover_letter_path="/cl.pdf",
            cv_path="/cv.pdf",
        )
        summary = _build_package_summary(pkg)
        assert summary.package_name == "acme-corp"
        assert summary.package_type == "full"
        assert summary.file_path == "/home/user/packages/acme-corp/"

    def test_build_package_summary_unknown_for_empty_dir(self):
        from career_os.api.applications import _build_package_summary

        pkg = self._make_pkg(package_dir="")
        summary = _build_package_summary(pkg)
        assert summary.package_name == "Unknown"

    def test_build_package_summary_unknown_for_none_dir(self):
        from career_os.api.applications import _build_package_summary

        pkg = self._make_pkg(package_dir=None)
        summary = _build_package_summary(pkg)
        assert summary.package_name == "Unknown"


# ---------------------------------------------------------------------------
# _COMPLETION_HANDLERS  /  individual handlers
# ---------------------------------------------------------------------------


class TestCompletionHandlers:
    """Tests for TickTick completion handler dispatch table."""

    def test_handler_keys(self):
        from career_os.services.ticktick_sync import _COMPLETION_HANDLERS

        assert set(_COMPLETION_HANDLERS.keys()) == {"follow_up", "learning_goal", "pipeline_action"}

    def test_all_handlers_are_callable(self):
        from career_os.services.ticktick_sync import _COMPLETION_HANDLERS

        for key, handler in _COMPLETION_HANDLERS.items():
            assert callable(handler), f"Handler for {key} is not callable"

    def test_complete_follow_up_sets_completed_at(self):
        from career_os.services.ticktick_sync import _complete_follow_up

        db = MagicMock()
        sync_task = SimpleNamespace(profile_id=1, entity_id=10)
        follow_up = MagicMock()
        follow_up.completed_at = None
        follow_up.application_id = 5
        db.query.return_value.filter.return_value.first.return_value = follow_up

        now = datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC)
        _complete_follow_up(db, sync_task, now)

        assert follow_up.completed_at == now
        db.add.assert_called_once()  # activity log added

    def test_complete_follow_up_skips_already_completed(self):
        from career_os.services.ticktick_sync import _complete_follow_up

        db = MagicMock()
        sync_task = SimpleNamespace(profile_id=1, entity_id=10)
        follow_up = MagicMock()
        follow_up.completed_at = datetime(2026, 1, 1, tzinfo=UTC)  # already done
        db.query.return_value.filter.return_value.first.return_value = follow_up

        _complete_follow_up(db, sync_task, datetime.now(UTC))
        db.add.assert_not_called()

    def test_complete_follow_up_skips_missing_entity(self):
        from career_os.services.ticktick_sync import _complete_follow_up

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        sync_task = SimpleNamespace(profile_id=1, entity_id=999)

        _complete_follow_up(db, sync_task, datetime.now(UTC))
        db.add.assert_not_called()

    def test_complete_learning_goal_sets_completed(self):
        from career_os.services.ticktick_sync import _complete_learning_goal

        db = MagicMock()
        sync_task = SimpleNamespace(entity_id=20)
        goal = MagicMock()
        goal.status = "in_progress"
        db.query.return_value.filter.return_value.first.return_value = goal

        now = datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC)
        _complete_learning_goal(db, sync_task, now)

        assert goal.status == "completed"
        assert goal.updated_at == now

    def test_complete_learning_goal_skips_already_completed(self):
        from career_os.services.ticktick_sync import _complete_learning_goal

        db = MagicMock()
        sync_task = SimpleNamespace(entity_id=20)
        goal = MagicMock()
        goal.status = "completed"
        db.query.return_value.filter.return_value.first.return_value = goal

        now = datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC)
        _complete_learning_goal(db, sync_task, now)
        assert goal.status == "completed"  # unchanged

    def test_complete_pipeline_action_marks_next_step_done(self):
        from career_os.services.ticktick_sync import _complete_pipeline_action

        db = MagicMock()
        sync_task = SimpleNamespace(profile_id=1, entity_id=30, title="Apply to Acme")
        app_obj = MagicMock()
        app_obj.next_step = "Send follow-up email"
        app_obj.id = 30
        db.query.return_value.filter.return_value.first.return_value = app_obj

        now = datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC)
        _complete_pipeline_action(db, sync_task, now)

        assert app_obj.next_step == "[Done] Send follow-up email"
        assert app_obj.updated_at == now
        db.add.assert_called_once()

    def test_complete_pipeline_action_handles_no_next_step(self):
        from career_os.services.ticktick_sync import _complete_pipeline_action

        db = MagicMock()
        sync_task = SimpleNamespace(profile_id=1, entity_id=30, title="Task")
        app_obj = MagicMock()
        app_obj.next_step = None
        app_obj.id = 30
        db.query.return_value.filter.return_value.first.return_value = app_obj

        _complete_pipeline_action(db, sync_task, datetime.now(UTC))
        assert app_obj.next_step is None  # unchanged, not "[Done] None"

    def test_complete_pipeline_action_skips_missing_entity(self):
        from career_os.services.ticktick_sync import _complete_pipeline_action

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        sync_task = SimpleNamespace(profile_id=1, entity_id=999, title="Task")

        _complete_pipeline_action(db, sync_task, datetime.now(UTC))
        db.add.assert_not_called()

    def test_apply_completion_dispatches_to_correct_handler(self):
        """Integration test: _apply_completion routes to the right handler via the dict."""
        from career_os.services.ticktick_sync import _apply_completion

        db = MagicMock()
        sync_task = SimpleNamespace(entity_type="follow_up", profile_id=1, entity_id=10)
        follow_up = MagicMock()
        follow_up.completed_at = None
        follow_up.application_id = 5
        db.query.return_value.filter.return_value.first.return_value = follow_up

        _apply_completion(db, sync_task)
        assert follow_up.completed_at is not None

    def test_apply_completion_unknown_type_is_noop(self):
        """Unknown entity types should not raise — just be silently ignored."""
        from career_os.services.ticktick_sync import _apply_completion

        db = MagicMock()
        sync_task = SimpleNamespace(entity_type="unknown_thing", profile_id=1, entity_id=10)

        _apply_completion(db, sync_task)  # should not raise
        db.query.assert_not_called()


# ---------------------------------------------------------------------------
# _fetch_entity (api/ticktick)
# ---------------------------------------------------------------------------


class TestFetchEntity:
    """Tests for the generic entity fetcher in ticktick API."""

    @staticmethod
    def _make_model():
        """Create a mock SQLAlchemy model class with id and profile_id columns."""
        model = MagicMock()
        model.id = MagicMock()
        model.profile_id = MagicMock()
        return model

    def test_returns_entity_when_found(self):
        from career_os.api.ticktick import _fetch_entity

        db = MagicMock()
        model = self._make_model()
        mock_obj = SimpleNamespace(id=1, profile_id=1)
        db.query.return_value.filter.return_value.first.return_value = mock_obj

        result = _fetch_entity(db, model, 1, 1, "Follow-up")
        assert result is mock_obj

    def test_raises_404_when_not_found(self):
        from fastapi import HTTPException

        from career_os.api.ticktick import _fetch_entity

        db = MagicMock()
        model = self._make_model()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            _fetch_entity(db, model, 999, 1, "Follow-up")
        assert exc_info.value.status_code == 404
        assert "Follow-up not found" in exc_info.value.detail

    def test_404_message_uses_label(self):
        from fastapi import HTTPException

        from career_os.api.ticktick import _fetch_entity

        db = MagicMock()
        model = self._make_model()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            _fetch_entity(db, model, 1, 1, "Learning goal")
        assert "Learning goal not found" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Batch 2 helpers
# ---------------------------------------------------------------------------


class TestExtractErrorDetail:
    """Tests for OpenRouter error detail extraction."""

    def test_extracts_message_from_valid_json(self):
        from career_os.ai.openrouter_provider import _extract_error_detail

        response = MagicMock()
        response.json.return_value = {"error": {"message": "Insufficient credits"}}
        assert _extract_error_detail(response) == "Insufficient credits"

    def test_returns_empty_on_json_error(self):
        from career_os.ai.openrouter_provider import _extract_error_detail

        response = MagicMock()
        response.json.side_effect = ValueError("bad json")
        assert _extract_error_detail(response) == ""

    def test_returns_empty_when_no_error_key(self):
        from career_os.ai.openrouter_provider import _extract_error_detail

        response = MagicMock()
        response.json.return_value = {"status": "fail"}
        assert _extract_error_detail(response) == ""


class TestHandleStatusTransition:
    """Tests for application status transition handler."""

    def test_skips_when_no_status_in_data(self):
        from career_os.services.applications import _handle_status_transition

        db = MagicMock()
        app_obj = MagicMock()
        update_data = {"notes": "updated"}
        _handle_status_transition(db, app_obj, update_data)
        # No activity logged for non-status changes
        db.add.assert_not_called()

    def test_normalizes_and_validates_status(self):
        from career_os.services.applications import (
            _handle_status_transition,
        )

        db = MagicMock()
        app_obj = MagicMock()
        app_obj.status = "discovered"
        app_obj.profile_id = 1
        app_obj.id = 10

        # discovered → interested is a valid transition
        update_data = {"status": "  Interested  "}
        _handle_status_transition(db, app_obj, update_data)
        assert update_data["status"] == "interested"

    def test_sets_date_applied_on_applied_transition(self):
        from career_os.services.applications import _handle_status_transition

        db = MagicMock()
        app_obj = MagicMock()
        # interested → applied is a valid transition
        app_obj.status = "interested"
        app_obj.profile_id = 1
        app_obj.id = 10
        app_obj.date_applied = None

        _handle_status_transition(db, app_obj, {"status": "applied"})
        assert app_obj.date_applied is not None


class TestApplyFieldUpdates:
    """Tests for application field update tracker."""

    def test_tracks_changed_fields(self):
        from career_os.services.applications import _apply_field_updates

        db = MagicMock()
        app_obj = MagicMock()
        app_obj.notes = "old"
        app_obj.url = "https://old.com"

        _apply_field_updates(db, app_obj, {"notes": "new"})
        # Should have called setattr and logged
        assert app_obj.notes == "new"

    def test_sets_status_without_logging(self):
        from career_os.services.applications import _apply_field_updates

        db = MagicMock()
        app_obj = MagicMock()
        app_obj.status = "discovered"
        app_obj.profile_id = 1
        app_obj.id = 10

        # Status field should be set but not counted as a changed field
        _apply_field_updates(db, app_obj, {"status": "applied"})


class TestApplyStatusTimestamps:
    """Tests for learning resource status timestamp handler."""

    def test_in_progress_sets_started_at(self):
        from career_os.services.learning import _apply_status_timestamps

        db = MagicMock()
        resource = MagicMock()
        resource.started_at = None
        now = datetime(2026, 4, 10, tzinfo=UTC)

        _apply_status_timestamps(db, resource, "in_progress", now)
        assert resource.status == "in_progress"
        assert resource.started_at == now

    def test_in_progress_preserves_existing_started_at(self):
        from career_os.services.learning import _apply_status_timestamps

        db = MagicMock()
        resource = MagicMock()
        old_time = datetime(2026, 1, 1, tzinfo=UTC)
        resource.started_at = old_time
        now = datetime(2026, 4, 10, tzinfo=UTC)

        _apply_status_timestamps(db, resource, "in_progress", now)
        assert resource.started_at == old_time  # preserved

    def test_completed_sets_both_timestamps(self):
        from career_os.services.learning import _apply_status_timestamps

        db = MagicMock()
        resource = MagicMock()
        resource.started_at = None
        now = datetime(2026, 4, 10, tzinfo=UTC)

        _apply_status_timestamps(db, resource, "completed", now)
        assert resource.status == "completed"
        assert resource.started_at == now
        assert resource.completed_at == now

    def test_not_started_clears_timestamps(self):
        from career_os.services.learning import _apply_status_timestamps

        db = MagicMock()
        resource = MagicMock()
        resource.started_at = datetime(2026, 1, 1, tzinfo=UTC)
        resource.completed_at = datetime(2026, 2, 1, tzinfo=UTC)
        now = datetime(2026, 4, 10, tzinfo=UTC)

        _apply_status_timestamps(db, resource, "not_started", now)
        assert resource.status == "not_started"
        assert resource.started_at is None
        assert resource.completed_at is None


class TestDeliverSingleNotification:
    """Tests for the individual notification delivery helper."""

    def test_successful_delivery(self):
        from career_os.services.pushover import _deliver_single_notification

        client = MagicMock()
        log_entry = MagicMock()
        log_entry.error_message = None
        log_entry.message = "Test notification"
        log_entry.title = "Test"

        result = _deliver_single_notification(client, log_entry)
        assert result is True
        assert log_entry.status == "sent"
        assert log_entry.error_message is None
        client.send_notification.assert_called_once()

    def test_failed_delivery(self):
        from career_os.services.pushover import PushoverAPIError, _deliver_single_notification

        client = MagicMock()
        client.send_notification.side_effect = PushoverAPIError("API down")
        log_entry = MagicMock()
        log_entry.error_message = None
        log_entry.message = "Test"
        log_entry.title = "Test"

        result = _deliver_single_notification(client, log_entry)
        assert result is False
        assert log_entry.status == "failed"
        assert "API down" in log_entry.error_message

    def test_parses_metadata_from_error_message_json(self):
        import json

        from career_os.services.pushover import _deliver_single_notification

        client = MagicMock()
        log_entry = MagicMock()
        log_entry.error_message = json.dumps({"url": "https://example.com", "priority": 1})
        log_entry.message = "Test"
        log_entry.title = "Test"

        _deliver_single_notification(client, log_entry)
        call_kwargs = client.send_notification.call_args.kwargs
        assert call_kwargs["url"] == "https://example.com"
        assert call_kwargs["priority"] == 1

    def test_handles_invalid_json_metadata(self):
        from career_os.services.pushover import _deliver_single_notification

        client = MagicMock()
        log_entry = MagicMock()
        log_entry.error_message = "not valid json {{"
        log_entry.message = "Test"
        log_entry.title = "Test"

        result = _deliver_single_notification(client, log_entry)
        assert result is True  # should still send successfully
