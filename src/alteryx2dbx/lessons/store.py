import json
import os
from pathlib import Path
from alteryx2dbx.lessons.models import Lesson


class LessonStore:
    def __init__(self, project_dir: Path | None = None):
        if os.environ.get("DATABRICKS_RUNTIME_VERSION") or os.environ.get(
            "IS_SERVERLESS"
        ):
            self.path = Path("/Workspace/Shared/alteryx2dbx/lessons.jsonl")
        else:
            self.path = (project_dir or Path.cwd()) / "lessons.jsonl"

    def _ensure_dir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, lesson: Lesson) -> None:
        self._ensure_dir()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(lesson.to_json() + "\n")

    def list_all(
        self, *, category: str | None = None, unpromoted_only: bool = False
    ) -> list[Lesson]:
        if not self.path.exists():
            return []
        lessons = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lesson = Lesson.from_json(line)
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue  # skip corrupt/truncated lines
                if category and lesson.category != category:
                    continue
                if unpromoted_only and lesson.promoted:
                    continue
                lessons.append(lesson)
        return lessons

    def promote(self, lesson_id: str) -> bool:
        if not self.path.exists():
            return False

        found = False
        temp_path = self.path.with_suffix(".tmp")

        with (
            open(self.path, encoding="utf-8") as f_in,
            open(temp_path, "w", encoding="utf-8") as f_out,
        ):
            for line in f_in:
                line = line.strip()
                if not line:
                    continue
                try:
                    lesson = Lesson.from_json(line)
                    if lesson.id == lesson_id:
                        lesson.promoted = True
                        found = True
                    f_out.write(lesson.to_json() + "\n")
                except (json.JSONDecodeError, KeyError, TypeError):
                    f_out.write(line + "\n")  # preserve corrupt lines

        if found:
            temp_path.replace(self.path)  # atomic on POSIX
        else:
            temp_path.unlink(missing_ok=True)

        return found

    def search(self, keyword: str) -> list[Lesson]:
        keyword_lower = keyword.lower()
        return [
            lesson
            for lesson in self.list_all()
            if keyword_lower in lesson.symptom.lower()
            or keyword_lower in lesson.root_cause.lower()
            or keyword_lower in lesson.fix.lower()
        ]
