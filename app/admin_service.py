from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from io import StringIO
from statistics import mean

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.game_logic import final_status_for_score
from app.game_service import build_run_summary, get_total_questions, parse_question_order
from app.models import GameRun, Participant, Response, RunStatus

ADMIN_RESET_CONFIRMATION = "RESET"


@dataclass(frozen=True, slots=True)
class DashboardMetric:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class DashboardBreakdownItem:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class DashboardRunRow:
    participant_name: str
    team: str | None
    status_label: str
    progress_text: str
    score_text: str
    started_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class AdminDashboardData:
    summary: list[DashboardMetric]
    final_status_breakdown: list[DashboardBreakdownItem]
    recent_runs: list[DashboardRunRow]
    reset_confirmation_value: str


def _load_runs(session: Session) -> list[GameRun]:
    statement = (
        select(GameRun)
        .options(joinedload(GameRun.participant), selectinload(GameRun.responses))
        .order_by(GameRun.started_at.desc())
    )
    return list(session.scalars(statement))


def _format_datetime(value) -> str:
    if value is None:
        return "—"
    return value.astimezone().strftime("%d.%m.%Y %H:%M")


def _format_average_score(scores: list[int], total_questions: int) -> str:
    if not scores:
        return f"— / {total_questions}"
    raw_average = mean(scores)
    formatted = f"{raw_average:.1f}".rstrip("0").rstrip(".")
    return f"{formatted} / {total_questions}"


def _format_average_response_time(values: list[int]) -> str:
    if not values:
        return "—"
    return f"{round(mean(values))} мс"


def _build_final_status_breakdown(completed_runs: list[GameRun]) -> list[DashboardBreakdownItem]:
    labels = [
        final_status_for_score(10),
        final_status_for_score(8),
        final_status_for_score(6),
        final_status_for_score(4),
        final_status_for_score(0),
    ]
    counts = Counter(build_run_summary(run).final_status for run in completed_runs)
    return [DashboardBreakdownItem(label=label, value=str(counts.get(label, 0))) for label in labels]


def build_admin_dashboard(session: Session) -> AdminDashboardData:
    runs = _load_runs(session)
    total_questions = get_total_questions()
    participant_count = session.query(Participant).count()
    completed_runs = [run for run in runs if run.status == RunStatus.COMPLETED]
    all_response_times = [response.response_time_ms for run in runs for response in run.responses]
    all_responses = [response for run in runs for response in run.responses]

    summary = [
        DashboardMetric(label="Участники", value=str(participant_count)),
        DashboardMetric(label="Запущено прохождений", value=str(len(runs))),
        DashboardMetric(label="Завершено прохождений", value=str(len(completed_runs))),
        DashboardMetric(
            label="Средний балл",
            value=_format_average_score([run.score for run in completed_runs], total_questions),
        ),
        DashboardMetric(label="Сохранено ответов", value=str(len(all_responses))),
        DashboardMetric(
            label="Среднее время ответа",
            value=_format_average_response_time(all_response_times),
        ),
    ]

    recent_runs = [
        DashboardRunRow(
            participant_name=run.participant.name,
            team=run.participant.team,
            status_label="Завершено" if run.status == RunStatus.COMPLETED else "В процессе",
            progress_text=f"{len(run.responses)} / {total_questions}",
            score_text=f"{run.score} / {total_questions}",
            started_at=_format_datetime(run.started_at),
            updated_at=_format_datetime(run.completed_at or run.updated_at),
        )
        for run in runs[:8]
    ]

    return AdminDashboardData(
        summary=summary,
        final_status_breakdown=_build_final_status_breakdown(completed_runs),
        recent_runs=recent_runs,
        reset_confirmation_value=ADMIN_RESET_CONFIRMATION,
    )


def build_admin_csv_export(session: Session) -> str:
    runs = _load_runs(session)
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "participant_public_id",
            "participant_name",
            "team",
            "run_public_id",
            "run_status",
            "run_score",
            "run_started_at",
            "run_completed_at",
            "question_position",
            "question_id",
            "selected_verdict",
            "is_correct",
            "swipe_direction",
            "input_method",
            "response_time_ms",
            "shown_at",
            "answered_at",
        ],
    )
    writer.writeheader()

    for run in reversed(runs):
        order_index = {question_id: index for index, question_id in enumerate(parse_question_order(run), start=1)}
        sorted_responses = sorted(run.responses, key=lambda response: order_index.get(response.question_id, 9999))

        if not sorted_responses:
            writer.writerow(
                {
                    "participant_public_id": run.participant.public_id,
                    "participant_name": run.participant.name,
                    "team": run.participant.team or "",
                    "run_public_id": run.public_id,
                    "run_status": run.status.value,
                    "run_score": run.score,
                    "run_started_at": run.started_at.isoformat(),
                    "run_completed_at": run.completed_at.isoformat() if run.completed_at else "",
                    "question_position": "",
                    "question_id": "",
                    "selected_verdict": "",
                    "is_correct": "",
                    "swipe_direction": "",
                    "input_method": "",
                    "response_time_ms": "",
                    "shown_at": "",
                    "answered_at": "",
                }
            )
            continue

        for response in sorted_responses:
            writer.writerow(
                {
                    "participant_public_id": run.participant.public_id,
                    "participant_name": run.participant.name,
                    "team": run.participant.team or "",
                    "run_public_id": run.public_id,
                    "run_status": run.status.value,
                    "run_score": run.score,
                    "run_started_at": run.started_at.isoformat(),
                    "run_completed_at": run.completed_at.isoformat() if run.completed_at else "",
                    "question_position": order_index.get(response.question_id, ""),
                    "question_id": response.question_id,
                    "selected_verdict": response.selected_verdict.value,
                    "is_correct": str(response.is_correct).lower(),
                    "swipe_direction": response.swipe_direction.value,
                    "input_method": response.input_method.value,
                    "response_time_ms": response.response_time_ms,
                    "shown_at": response.shown_at.isoformat(),
                    "answered_at": response.answered_at.isoformat(),
                }
            )

    return "\ufeff" + output.getvalue()


def reset_event_data(session: Session) -> None:
    session.execute(delete(Response))
    session.execute(delete(GameRun))
    session.execute(delete(Participant))
    session.commit()
