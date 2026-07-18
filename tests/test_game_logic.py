from app.game_logic import (
    EvaluatedResponse,
    SelectedVerdict,
    SwipeDirection,
    calculate_score,
    final_status_for_score,
    is_response_correct,
    summarize_run,
    swipe_for_verdict,
    verdict_for_swipe,
)


def test_swipe_and_verdict_mapping_is_fixed() -> None:
    assert verdict_for_swipe(SwipeDirection.LEFT) == SelectedVerdict.INACCURACY
    assert verdict_for_swipe(SwipeDirection.RIGHT) == SelectedVerdict.CORRECT
    assert swipe_for_verdict(SelectedVerdict.INACCURACY) == SwipeDirection.LEFT
    assert swipe_for_verdict(SelectedVerdict.CORRECT) == SwipeDirection.RIGHT


def test_response_correctness_is_computed_from_verdicts() -> None:
    assert is_response_correct(SelectedVerdict.CORRECT, SelectedVerdict.CORRECT) is True
    assert is_response_correct(SelectedVerdict.CORRECT, SelectedVerdict.INACCURACY) is False
    assert is_response_correct(SelectedVerdict.INACCURACY, SelectedVerdict.CORRECT) is False


def test_score_and_final_status_rules_match_spec() -> None:
    assert calculate_score([True, False, True, True]) == 3
    assert final_status_for_score(10) == "Старший ассистент Ландау"
    assert final_status_for_score(8) == "Допущен к проверке теорминимума"
    assert final_status_for_score(6) == "Внимательный рецензент"
    assert final_status_for_score(4) == "Требуется повторная проверка"
    assert final_status_for_score(2) == "Студенты подали апелляцию"
    assert final_status_for_score(6, total_questions=6) == "Старший ассистент Ландау"
    assert final_status_for_score(5, total_questions=6) == "Допущен к проверке теорминимума"
    assert final_status_for_score(4, total_questions=6) == "Внимательный рецензент"
    assert final_status_for_score(3, total_questions=6) == "Требуется повторная проверка"
    assert final_status_for_score(2, total_questions=6) == "Студенты подали апелляцию"


def test_run_summary_counts_key_outcomes() -> None:
    summary = summarize_run(
        [
            EvaluatedResponse(
                selected_verdict=SelectedVerdict.INACCURACY,
                correct_verdict=SelectedVerdict.INACCURACY,
                response_time_ms=1100,
            ),
            EvaluatedResponse(
                selected_verdict=SelectedVerdict.CORRECT,
                correct_verdict=SelectedVerdict.INACCURACY,
                response_time_ms=1500,
            ),
            EvaluatedResponse(
                selected_verdict=SelectedVerdict.INACCURACY,
                correct_verdict=SelectedVerdict.CORRECT,
                response_time_ms=900,
            ),
            EvaluatedResponse(
                selected_verdict=SelectedVerdict.CORRECT,
                correct_verdict=SelectedVerdict.CORRECT,
                response_time_ms=1300,
            ),
        ]
    )

    assert summary.checked_works == 4
    assert summary.score == 2
    assert summary.inaccuracies_found == 1
    assert summary.missed_inaccuracies == 1
    assert summary.correct_answers_rejected == 1
    assert summary.average_response_time_ms == 1200
    assert summary.final_status == "Студенты подали апелляцию"
