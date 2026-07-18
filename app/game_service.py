from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.cards import (
    ONBOARDING_CARD_COUNT,
    CardViewModel,
    build_decision_card,
    build_landau_card,
    build_onboarding_card,
)
from app.content import QuestionScene, get_enabled_scene_count, get_scene_by_id, load_question_scenes
from app.game_logic import (
    EvaluatedResponse,
    InputMethod,
    RunSummary,
    SelectedVerdict,
    SwipeDirection,
    is_response_correct,
    summarize_run,
    swipe_for_verdict,
)
from app.models import GameRun, Participant, Response, RunStatus, ScreenState, utc_now


class RegistrationValidationError(ValueError):
    pass


class GameplayStateError(ValueError):
    pass


@dataclass(slots=True)
class RunPageState:
    kind: Literal["question", "result", "final"]
    participant_name: str
    team: str | None
    position: int
    total_questions: int
    card_view: CardViewModel | None = None
    summary: RunSummary | None = None
    latest_response: Response | None = None


@dataclass(slots=True)
class OnboardingPageState:
    kind: Literal["onboarding"]
    step: int
    total_steps: int
    card_view: CardViewModel


@dataclass(frozen=True, slots=True)
class ReviewEntry:
    position: int
    scene: QuestionScene
    response: Response


def ensure_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_registration_field(value: str | None, *, required: bool, max_length: int) -> str | None:
    if value is None:
        value = ""
    normalized = value.strip()
    if required and not normalized:
        raise RegistrationValidationError("Имя или псевдоним должно содержать от 1 до 40 символов.")
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise RegistrationValidationError(f"Поле должно содержать не более {max_length} символов.")
    return normalized


def build_question_order() -> list[str]:
    return [scene.id for scene in load_question_scenes()]


def serialize_question_order(order: list[str]) -> str:
    return json.dumps(order, ensure_ascii=False)


def parse_question_order(run: GameRun) -> list[str]:
    order = json.loads(run.question_order_json)
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise GameplayStateError("Stored question order is invalid.")
    return order


def get_total_questions() -> int:
    return get_enabled_scene_count()


def build_onboarding_page_state(step: int) -> OnboardingPageState:
    """Return the current pre-registration card without creating database records."""
    card_view = build_onboarding_card(step)
    return OnboardingPageState(
        kind="onboarding",
        step=step,
        total_steps=ONBOARDING_CARD_COUNT,
        card_view=card_view,
    )


def get_scene_for_run_position(run: GameRun, position: int | None = None) -> QuestionScene:
    order = parse_question_order(run)
    resolved_position = position or run.current_position
    if resolved_position < 1 or resolved_position > len(order):
        raise GameplayStateError("Current run position is outside the available question range.")
    return get_scene_by_id(order[resolved_position - 1])


def create_participant_and_run(session: Session, name: str, team: str | None) -> GameRun:
    participant = Participant(
        public_id=str(uuid4()),
        name=name,
        team=team,
    )
    run = GameRun(
        public_id=str(uuid4()),
        participant=participant,
        question_order_json=serialize_question_order(build_question_order()),
    )
    session.add_all([participant, run])
    session.commit()
    session.refresh(run)
    return run


def get_run_by_public_id(session: Session, public_id: str) -> GameRun | None:
    statement = (
        select(GameRun)
        .options(joinedload(GameRun.participant), selectinload(GameRun.responses))
        .where(GameRun.public_id == public_id)
    )
    return session.scalar(statement)


def ensure_question_is_shown(session: Session, run: GameRun) -> None:
    if run.status != RunStatus.IN_PROGRESS or run.screen_state != ScreenState.QUESTION:
        return
    if run.current_question_shown_at is None:
        run.current_question_shown_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)


def get_response_for_question(run: GameRun, question_id: str) -> Response | None:
    for response in run.responses:
        if response.question_id == question_id:
            return response
    return None


def build_run_page_state(session: Session, run: GameRun) -> RunPageState:
    total_questions = get_total_questions()
    participant_name = run.participant.name
    team = run.participant.team

    if run.status == RunStatus.COMPLETED or run.screen_state == ScreenState.FINAL:
        return RunPageState(
            kind="final",
            participant_name=participant_name,
            team=team,
            position=min(run.current_position, total_questions),
            total_questions=total_questions,
            summary=build_run_summary(run),
        )

    if run.screen_state == ScreenState.QUESTION:
        ensure_question_is_shown(session, run)
        scene = get_scene_for_run_position(run)
        return RunPageState(
            kind="question",
            participant_name=participant_name,
            team=team,
            position=run.current_position,
            total_questions=total_questions,
            card_view=build_decision_card(scene, participant_name=participant_name),
        )

    if run.screen_state == ScreenState.RESULT:
        scene = get_scene_for_run_position(run)
        response = get_response_for_question(run, scene.id)
        if response is None:
            raise GameplayStateError("Result state is missing its saved response.")
        return RunPageState(
            kind="result",
            participant_name=participant_name,
            team=team,
            position=run.current_position,
            total_questions=total_questions,
            card_view=build_landau_card(
                scene,
                is_correct=response.is_correct,
                dialogue_step=run.result_step,
            ),
            latest_response=response,
        )

    raise GameplayStateError("Unsupported run screen state.")


def submit_current_answer(
    session: Session,
    run: GameRun,
    *,
    selected_verdict: SelectedVerdict,
    input_method: InputMethod,
) -> tuple[Response, bool]:
    if run.status == RunStatus.COMPLETED or run.screen_state == ScreenState.FINAL:
        raise GameplayStateError("This run is already completed.")

    scene = get_scene_for_run_position(run)
    existing_response = get_response_for_question(run, scene.id)
    if existing_response is not None:
        return existing_response, True

    if run.screen_state != ScreenState.QUESTION:
        raise GameplayStateError("Current work cannot accept another answer right now.")

    shown_at = ensure_utc_datetime(run.current_question_shown_at or utc_now())
    answered_at = utc_now()
    response_time_ms = max(0, int((answered_at - shown_at).total_seconds() * 1000))
    is_correct = is_response_correct(selected_verdict, scene.correct_verdict)

    response = Response(
        game_run_id=run.id,
        question_id=scene.id,
        selected_verdict=selected_verdict,
        is_correct=is_correct,
        swipe_direction=swipe_for_verdict(selected_verdict),
        input_method=input_method,
        shown_at=shown_at,
        answered_at=answered_at,
        response_time_ms=response_time_ms,
    )
    session.add(response)

    run.score = run.score + (1 if is_correct else 0)
    run.screen_state = ScreenState.RESULT
    run.result_step = 0
    run.last_answered_question_id = scene.id
    run.current_question_shown_at = None
    session.add(run)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        refreshed_run = get_run_by_public_id(session, run.public_id)
        if refreshed_run is None:
            raise GameplayStateError("Run disappeared during answer submission.")
        duplicate_response = get_response_for_question(refreshed_run, scene.id)
        if duplicate_response is None:
            raise
        return duplicate_response, True

    session.refresh(run)
    session.refresh(response)
    return response, False


def advance_run(
    session: Session,
    run: GameRun,
    *,
    swipe_direction: SwipeDirection = SwipeDirection.RIGHT,
) -> None:
    if run.status == RunStatus.COMPLETED or run.screen_state == ScreenState.FINAL:
        return
    if run.screen_state != ScreenState.RESULT:
        raise GameplayStateError("Cannot advance before the current answer is saved.")

    scene = get_scene_for_run_position(run)
    response = get_response_for_question(run, scene.id)
    if response is None:
        raise GameplayStateError("Result state is missing its saved response.")
    result_card = build_landau_card(
        scene,
        is_correct=response.is_correct,
        dialogue_step=run.result_step,
    )
    dialogue_total = result_card.meta["dialogue_total"]
    asks_for_details = result_card.meta["asks_for_details"]
    if asks_for_details and swipe_direction == SwipeDirection.RIGHT:
        # "Дальше" skips the technical breakdown but preserves the historical closing note.
        run.result_step = dialogue_total - 1
        session.add(run)
        session.commit()
        session.refresh(run)
        return

    if run.result_step + 1 < dialogue_total:
        run.result_step += 1
        session.add(run)
        session.commit()
        session.refresh(run)
        return

    total_questions = get_total_questions()
    if run.current_position >= total_questions:
        run.status = RunStatus.COMPLETED
        run.screen_state = ScreenState.FINAL
        run.result_step = 0
        run.completed_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)
        return

    run.current_position += 1
    run.screen_state = ScreenState.QUESTION
    run.result_step = 0
    run.current_question_shown_at = utc_now()
    session.add(run)
    session.commit()
    session.refresh(run)


def build_run_summary(run: GameRun) -> RunSummary:
    ordered_responses = sorted(
        run.responses,
        key=lambda response: parse_question_order(run).index(response.question_id),
    )
    evaluated = [
        EvaluatedResponse(
            selected_verdict=response.selected_verdict,
            correct_verdict=get_scene_by_id(response.question_id).correct_verdict,
            response_time_ms=response.response_time_ms,
        )
        for response in ordered_responses
    ]
    return summarize_run(evaluated, total_questions=get_total_questions())


def build_review_entries(run: GameRun) -> list[ReviewEntry]:
    order_index = {scene_id: index for index, scene_id in enumerate(parse_question_order(run), start=1)}
    sorted_responses = sorted(run.responses, key=lambda response: order_index[response.question_id])
    entries = []
    for response in sorted_responses:
        entries.append(
            ReviewEntry(
                position=order_index[response.question_id],
                scene=get_scene_by_id(response.question_id),
                response=response,
            )
        )
    return entries
