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
        assert _match_strength_keyword("Intellectual curiosity is a driver") == "Experimental Mindset"

    def test_experiment_maps_to_experimental_mindset(self):
        assert _match_strength_keyword("Likes to experiment with new ideas") == "Experimental Mindset"

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
            package_dir="/home/user/packages/acme-corp/", cover_letter_path="/cl.pdf", cv_path="/cv.pdf"
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
