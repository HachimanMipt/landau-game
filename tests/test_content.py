import json

import pytest

from app.content import EXPECTED_ACTIVE_SCENE_COUNT, load_question_scenes


def test_demo_question_scenes_match_phase_two_requirements() -> None:
    scenes = load_question_scenes()

    assert len(scenes) == EXPECTED_ACTIVE_SCENE_COUNT
    assert len({scene.id for scene in scenes}) == EXPECTED_ACTIVE_SCENE_COUNT
    assert len({scene.position for scene in scenes}) == EXPECTED_ACTIVE_SCENE_COUNT
    assert {scene.position for scene in scenes} == set(range(1, EXPECTED_ACTIVE_SCENE_COUNT + 1))
    assert [scene.id for scene in scenes] == [
        "landau-levels",
        "order-parameter",
        "superfluid-helium",
        "ginzburg-landau-superconductivity",
        "landau-damping",
        "fermi-liquid",
    ]

    for scene in scenes:
        assert scene.decision_card.question_text
        assert scene.decision_card.student_answer
        assert scene.landau_card.explanation
        assert scene.landau_card.inaccuracy_explanation
        assert scene.landau_card.character_quote
        assert scene.sources

    history_years = ["1930", "1937", "1941", "1950", "1946", "1956"]
    for scene, year in zip(scenes, history_years, strict=True):
        assert year in scene.landau_card.inaccuracy_explanation


def test_duplicate_scene_id_is_rejected(tmp_path) -> None:
    source = [
        {
            "id": "duplicate",
            "position": index + 1,
            "decision_card": {
                "work_title": f"Работа {index + 1} из 10",
                "question_text": "Вопрос",
                "student_answer": "Ответ",
                "swipe_left_label": "Есть неточность",
                "swipe_right_label": "Ответ верный",
            },
            "correct_verdict": "correct",
            "landau_card": {
                "verdict_title_correct": "Верно",
                "verdict_title_wrong": "Неверно",
                "explanation": "Объяснение",
                "inaccuracy_explanation": "Неточности нет",
                "character_quote": "Реплика",
                "fact_title": "Факт",
                "fact_text": "Текст",
                "place": None,
                "period": None,
                "people": None,
                "importance": None,
            },
            "sources": [],
            "difficulty": 1,
            "fact_check_status": "needs_review",
            "enabled": True,
        }
        for index in range(EXPECTED_ACTIVE_SCENE_COUNT)
    ]
    temp_path = tmp_path / "questions.json"
    temp_path.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        load_question_scenes(path=temp_path)
