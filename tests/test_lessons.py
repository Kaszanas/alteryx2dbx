"""Tests for the lessons learning loop infrastructure."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from alteryx2dbx.lessons.models import Lesson
from alteryx2dbx.lessons.store import LessonStore
from alteryx2dbx.lessons.capture import auto_capture
from alteryx2dbx.cli import main


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_lesson(**overrides) -> Lesson:
    defaults = dict(
        id="abc12345",
        date="2026-04-07",
        workflow="test_wf",
        symptom="Something broke",
        root_cause="Bad config",
        fix="Fix the config",
        category="tool_mapping",
    )
    defaults.update(overrides)
    return Lesson(**defaults)


# ── Model tests ──────────────────────────────────────────────────────


class TestLessonModel:
    def test_to_dict_roundtrip(self):
        lesson = _make_lesson()
        d = lesson.to_dict()
        restored = Lesson.from_dict(d)
        assert restored == lesson

    def test_to_json_roundtrip(self):
        lesson = _make_lesson(promoted=True, auto_captured=True)
        json_str = lesson.to_json()
        restored = Lesson.from_json(json_str)
        assert restored == lesson

    def test_from_dict_ignores_extra_keys(self):
        d = _make_lesson().to_dict()
        d["extra_field"] = "should be ignored"
        lesson = Lesson.from_dict(d)
        assert lesson.id == "abc12345"

    def test_new_id_is_12_chars(self):
        id_ = Lesson.new_id()
        assert len(id_) == 12

    def test_new_id_is_unique(self):
        ids = {Lesson.new_id() for _ in range(50)}
        assert len(ids) == 50


# ── Store tests ──────────────────────────────────────────────────────


class TestLessonStore:
    def test_add_and_list(self, tmp_path):
        store = LessonStore(tmp_path)
        lesson = _make_lesson()
        store.add(lesson)
        items = store.list_all()
        assert len(items) == 1
        assert items[0].symptom == "Something broke"

    def test_list_empty(self, tmp_path):
        store = LessonStore(tmp_path)
        assert store.list_all() == []

    def test_category_filter(self, tmp_path):
        store = LessonStore(tmp_path)
        store.add(_make_lesson(id="a", category="tool_mapping"))
        store.add(_make_lesson(id="b", category="validation"))
        store.add(_make_lesson(id="c", category="tool_mapping"))
        assert len(store.list_all(category="tool_mapping")) == 2
        assert len(store.list_all(category="validation")) == 1
        assert len(store.list_all(category="data_loading")) == 0

    def test_unpromoted_only(self, tmp_path):
        store = LessonStore(tmp_path)
        store.add(_make_lesson(id="a", promoted=False))
        store.add(_make_lesson(id="b", promoted=True))
        store.add(_make_lesson(id="c", promoted=False))
        assert len(store.list_all(unpromoted_only=True)) == 2
        assert len(store.list_all(unpromoted_only=False)) == 3

    def test_promote(self, tmp_path):
        store = LessonStore(tmp_path)
        store.add(_make_lesson(id="target"))
        store.add(_make_lesson(id="other"))
        assert store.promote("target") is True
        items = store.list_all()
        target = [lesson for lesson in items if lesson.id == "target"][0]
        other = [lesson for lesson in items if lesson.id == "other"][0]
        assert target.promoted is True
        assert other.promoted is False

    def test_promote_not_found(self, tmp_path):
        store = LessonStore(tmp_path)
        store.add(_make_lesson(id="exists"))
        assert store.promote("nonexistent") is False

    def test_search(self, tmp_path):
        store = LessonStore(tmp_path)
        store.add(_make_lesson(id="a", symptom="Filter returned wrong rows"))
        store.add(_make_lesson(id="b", root_cause="Join key mismatch"))
        store.add(_make_lesson(id="c", fix="Use coalesce for null handling"))
        assert len(store.search("filter")) == 1
        assert len(store.search("mismatch")) == 1
        assert len(store.search("coalesce")) == 1
        assert len(store.search("nonexistent")) == 0

    def test_databricks_env_path(self, tmp_path):
        with patch.dict(os.environ, {"DATABRICKS_RUNTIME_VERSION": "14.3"}):
            store = LessonStore(tmp_path)
            assert store.path == Path(
                "/Workspace/Shared/alteryx2dbx/lessons.jsonl"
            )

    def test_local_env_path(self, tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            # Remove DATABRICKS_RUNTIME_VERSION if present
            os.environ.pop("DATABRICKS_RUNTIME_VERSION", None)
            store = LessonStore(tmp_path)
            assert store.path == tmp_path / "lessons.jsonl"

    def test_list_all_handles_truncated_jsonl(self, tmp_path):
        """Truncated/corrupt JSONL lines should be skipped, not crash list_all()."""
        store = LessonStore(tmp_path)
        store.add(_make_lesson(id="good1"))
        # Append a truncated line directly
        with open(store.path, "a", encoding="utf-8") as f:
            f.write(
                '{"id": "bad", "date": "2026-01-01", "workflow": "w", "symptom": "s"\n'
            )
            f.write("not json at all\n")
        store.add(_make_lesson(id="good2"))
        items = store.list_all()
        assert len(items) == 2
        assert {lesson.id for lesson in items} == {"good1", "good2"}

    def test_promote_atomic_temp_file(self, tmp_path):
        """promote() should use atomic temp file approach and handle corrupt lines."""
        store = LessonStore(tmp_path)
        store.add(_make_lesson(id="target"))
        # Append a corrupt line
        with open(store.path, "a", encoding="utf-8") as f:
            f.write("truncated garbage\n")
        store.add(_make_lesson(id="other"))
        assert store.promote("target") is True
        items = store.list_all()
        target = [lesson for lesson in items if lesson.id == "target"][0]
        assert target.promoted is True
        # Corrupt line should be preserved in file (not lost)
        raw = store.path.read_text(encoding="utf-8")
        assert "truncated garbage" in raw

    def test_serverless_env_path(self, tmp_path):
        """IS_SERVERLESS env var should trigger Databricks workspace path."""
        with patch.dict(os.environ, {"IS_SERVERLESS": "true"}, clear=True):
            store = LessonStore(tmp_path)
            assert store.path == Path(
                "/Workspace/Shared/alteryx2dbx/lessons.jsonl"
            )


# ── Auto-capture tests ───────────────────────────────────────────────


@dataclass
class _FakeStep:
    step_name: str = "FakeStep"
    confidence: float = 1.0
    notes: list[str] = field(default_factory=list)


class TestAutoCapture:
    def test_low_confidence_captured(self):
        steps = {1: _FakeStep(step_name="SelectTool", confidence=0.5)}
        lessons = auto_capture("wf1", steps, [1])
        assert len(lessons) == 1
        assert lessons[0].category == "tool_mapping"
        assert "low confidence" in lessons[0].symptom

    def test_ambiguous_note_captured(self):
        steps = {
            1: _FakeStep(notes=["AMBIGUOUS: multiple interpretations possible"])
        }
        lessons = auto_capture("wf1", steps, [1])
        assert len(lessons) == 1
        assert lessons[0].category == "behavioral_difference"

    def test_clean_step_no_lessons(self):
        steps = {1: _FakeStep(confidence=0.95, notes=["All good"])}
        lessons = auto_capture("wf1", steps, [1])
        assert len(lessons) == 0

    def test_missing_step_skipped(self):
        steps = {1: _FakeStep()}
        lessons = auto_capture("wf1", steps, [1, 99])
        assert len(lessons) == 0

    def test_multiple_issues(self):
        steps = {
            1: _FakeStep(confidence=0.3, notes=["AMBIGUOUS: unclear mapping"]),
            2: _FakeStep(confidence=0.9),
            3: _FakeStep(confidence=0.5),
        }
        lessons = auto_capture("wf1", steps, [1, 2, 3])
        # Tool 1: low confidence + ambiguous note = 2 lessons
        # Tool 2: clean = 0
        # Tool 3: low confidence = 1
        assert len(lessons) == 3


# ── CLI tests ────────────────────────────────────────────────────────


class TestLessonsCLI:
    def test_add_lesson(self, tmp_path):
        lessons_file = tmp_path / "lessons.jsonl"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "lessons",
                "--lessons-file",
                str(lessons_file),
                "add",
                "--workflow",
                "test_wf",
                "--symptom",
                "Filter dropped nulls",
                "--root-cause",
                "PySpark Filter treats null as false",
                "--fix",
                "Add explicit null check",
                "--category",
                "behavioral_difference",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "added" in result.output
        assert lessons_file.exists()

    def test_list_empty(self, tmp_path):
        lessons_file = tmp_path / "lessons.jsonl"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "lessons",
                "--lessons-file",
                str(lessons_file),
                "list",
            ],
        )
        assert result.exit_code == 0
        assert "No lessons found" in result.output

    def test_list_after_add(self, tmp_path):
        lessons_file = tmp_path / "lessons.jsonl"
        runner = CliRunner()
        # Add a lesson first
        runner.invoke(
            main,
            [
                "lessons",
                "--lessons-file",
                str(lessons_file),
                "add",
                "--workflow",
                "wf1",
                "--symptom",
                "Test symptom",
                "--root-cause",
                "Test cause",
                "--fix",
                "Test fix",
                "--category",
                "validation",
            ],
        )
        result = runner.invoke(
            main,
            [
                "lessons",
                "--lessons-file",
                str(lessons_file),
                "list",
            ],
        )
        assert result.exit_code == 0
        assert "Test symptom" in result.output
        assert "[validation]" in result.output

    def test_promote_lesson(self, tmp_path):
        lessons_file = tmp_path / "lessons.jsonl"
        store = LessonStore(tmp_path)
        lesson = _make_lesson(id="promo123")
        store.add(lesson)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "lessons",
                "--lessons-file",
                str(lessons_file),
                "promote",
                "promo123",
            ],
        )
        assert result.exit_code == 0
        assert "promoted" in result.output

    def test_promote_not_found(self, tmp_path):
        lessons_file = tmp_path / "lessons.jsonl"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "lessons",
                "--lessons-file",
                str(lessons_file),
                "promote",
                "nonexistent",
            ],
        )
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_list_with_category_filter(self, tmp_path):
        lessons_file = tmp_path / "lessons.jsonl"
        store = LessonStore(tmp_path)
        store.add(
            _make_lesson(
                id="a", category="tool_mapping", symptom="Mapping issue"
            )
        )
        store.add(
            _make_lesson(
                id="b", category="validation", symptom="Validation issue"
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "lessons",
                "--lessons-file",
                str(lessons_file),
                "list",
                "--category",
                "validation",
            ],
        )
        assert result.exit_code == 0
        assert "Validation issue" in result.output
        assert "Mapping issue" not in result.output

    def test_list_unpromoted_flag(self, tmp_path):
        lessons_file = tmp_path / "lessons.jsonl"
        store = LessonStore(tmp_path)
        store.add(_make_lesson(id="a", promoted=False, symptom="Active one"))
        store.add(_make_lesson(id="b", promoted=True, symptom="Promoted one"))

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "lessons",
                "--lessons-file",
                str(lessons_file),
                "list",
                "--unpromoted",
            ],
        )
        assert result.exit_code == 0
        assert "Active one" in result.output
        assert "Promoted one" not in result.output
