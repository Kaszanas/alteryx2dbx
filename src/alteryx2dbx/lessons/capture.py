from alteryx2dbx.lessons.models import Lesson
from datetime import date


def auto_capture(
    workflow_name: str, steps: dict, execution_order: list[int]
) -> list[Lesson]:
    """Scan conversion results and auto-generate lessons for noteworthy patterns."""
    lessons = []
    today = date.today().isoformat()

    for tid in execution_order:
        step = steps.get(tid)
        if not step:
            continue

        # Capture low-confidence tools
        if step.confidence < 0.7:
            lessons.append(
                Lesson(
                    id=Lesson.new_id(),
                    date=today,
                    workflow=workflow_name,
                    symptom=f"Tool {tid} ({step.step_name}) has low confidence ({step.confidence:.0%})",
                    root_cause="Handler could not fully translate this tool pattern",
                    fix="Manual review required -- check generated code against Alteryx logic",
                    category="tool_mapping",
                    auto_captured=True,
                )
            )

        # Capture notes that indicate fixes were applied
        for note in step.notes or []:
            if "AMBIGUOUS" in note:
                lessons.append(
                    Lesson(
                        id=Lesson.new_id(),
                        date=today,
                        workflow=workflow_name,
                        symptom=note,
                        root_cause="Ambiguous pattern detected during conversion",
                        fix="Review the specific pattern noted above",
                        category="behavioral_difference",
                        auto_captured=True,
                    )
                )

    return lessons
