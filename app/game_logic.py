from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Iterable, Sequence


class SelectedVerdict(str, Enum):
    CORRECT = "correct"
    INACCURACY = "inaccuracy"


class SwipeDirection(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class InputMethod(str, Enum):
    SWIPE = "swipe"
    BUTTON = "button"
    KEYBOARD = "keyboard"


@dataclass(frozen=True, slots=True)
class EvaluatedResponse:
    selected_verdict: SelectedVerdict
    correct_verdict: SelectedVerdict
    response_time_ms: int | None = None

    def __post_init__(self) -> None:
        if self.response_time_ms is not None and self.response_time_ms < 0:
            raise ValueError("response_time_ms must be non-negative")


@dataclass(frozen=True, slots=True)
class RunSummary:
    checked_works: int
    score: int
    inaccuracies_found: int
    missed_inaccuracies: int
    correct_answers_rejected: int
    average_response_time_ms: int | None
    final_status: str


def verdict_for_swipe(direction: SwipeDirection) -> SelectedVerdict:
    if direction == SwipeDirection.LEFT:
        return SelectedVerdict.INACCURACY
    return SelectedVerdict.CORRECT


def swipe_for_verdict(verdict: SelectedVerdict) -> SwipeDirection:
    if verdict == SelectedVerdict.INACCURACY:
        return SwipeDirection.LEFT
    return SwipeDirection.RIGHT


def is_response_correct(
    selected_verdict: SelectedVerdict,
    correct_verdict: SelectedVerdict,
) -> bool:
    return selected_verdict == correct_verdict


def calculate_score(correctness_values: Iterable[bool]) -> int:
    return sum(1 for is_correct in correctness_values if is_correct)


def final_status_for_score(score: int, total_questions: int = 10) -> str:
    if total_questions <= 0:
        raise ValueError("total_questions must be positive")
    if score < 0 or score > total_questions:
        raise ValueError("score must be between 0 and total_questions inclusive")

    score_ratio = score / total_questions
    if score == total_questions:
        return "Старший ассистент Ландау"
    if score_ratio >= 0.8:
        return "Допущен к проверке теорминимума"
    if score_ratio >= 0.6:
        return "Внимательный рецензент"
    if score_ratio >= 0.4:
        return "Требуется повторная проверка"
    return "Студенты подали апелляцию"


def summarize_run(responses: Sequence[EvaluatedResponse], total_questions: int = 10) -> RunSummary:
    correctness = [
        is_response_correct(response.selected_verdict, response.correct_verdict)
        for response in responses
    ]
    score = calculate_score(correctness)

    inaccuracies_found = sum(
        1
        for response in responses
        if response.correct_verdict == SelectedVerdict.INACCURACY
        and response.selected_verdict == SelectedVerdict.INACCURACY
    )
    missed_inaccuracies = sum(
        1
        for response in responses
        if response.correct_verdict == SelectedVerdict.INACCURACY
        and response.selected_verdict == SelectedVerdict.CORRECT
    )
    correct_answers_rejected = sum(
        1
        for response in responses
        if response.correct_verdict == SelectedVerdict.CORRECT
        and response.selected_verdict == SelectedVerdict.INACCURACY
    )

    times = [response.response_time_ms for response in responses if response.response_time_ms is not None]
    average_response_time_ms = round(mean(times)) if times else None

    return RunSummary(
        checked_works=len(responses),
        score=score,
        inaccuracies_found=inaccuracies_found,
        missed_inaccuracies=missed_inaccuracies,
        correct_answers_rejected=correct_answers_rejected,
        average_response_time_ms=average_response_time_ms,
        final_status=final_status_for_score(score, total_questions),
    )
