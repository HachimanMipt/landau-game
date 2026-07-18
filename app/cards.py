from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.content import QuestionScene
from app.game_logic import SelectedVerdict


@dataclass(slots=True)
class CardViewModel:
    card_type: Literal["decision", "landau", "note", "identity"]
    card_id: str
    title: str | None = None
    body: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    swipe_enabled: bool = False
    left_label: str | None = None
    right_label: str | None = None
    portrait_image_url: str | None = None
    primary_action_label: str | None = None
    helper_text: str | None = None


ONBOARDING_CARD_COUNT = 8
MAX_LANDAU_CARD_CHARACTERS = 190


def split_landau_dialogue(text: str) -> list[str]:
    """Keep a Landau reply readable beside the portrait on a phone-sized card."""
    chunks: list[str] = []
    for paragraph in (part.strip() for part in text.split("\n\n")):
        if not paragraph:
            continue

        sentences = re.split(r"(?<=[.!?…])\s+", paragraph)
        current = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(sentence) > MAX_LANDAU_CARD_CHARACTERS:
                words = sentence.split()
                sentence_parts: list[str] = []
                current_part = ""
                for word in words:
                    candidate = f"{current_part} {word}".strip()
                    if current_part and len(candidate) > MAX_LANDAU_CARD_CHARACTERS:
                        sentence_parts.append(current_part)
                        current_part = word
                    else:
                        current_part = candidate
                if current_part:
                    sentence_parts.append(current_part)
            else:
                sentence_parts = [sentence]

            for part in sentence_parts:
                candidate = f"{current} {part}".strip()
                if current and len(candidate) > MAX_LANDAU_CARD_CHARACTERS:
                    chunks.append(current)
                    current = part
                else:
                    current = candidate

        if current:
            chunks.append(current)

    return chunks or [text]


def build_onboarding_card(step: int) -> CardViewModel:
    """Build the short card-only introduction shown before a game run exists."""
    if step == 0:
        return CardViewModel(
            card_type="landau",
            card_id="onboarding-welcome",
            body=(
                "Приветствую! Я Лев Ландау, теоретический физик. Работал с 1920-х до 1960-х годов: "
                "от квантовой механики до жидкого гелия."
            ),
            meta={"is_onboarding": True},
            portrait_image_url="/static/images/image.png",
            left_label="Понятно",
            right_label="Дальше",
        )

    if step == 1:
        return CardViewModel(
            card_type="landau",
            card_id="onboarding-classification",
            body=(
                "Работал, кстати, неплохо. В собственной шутливой классификации я долго числил себя "
                "физиком второго с половиной класса. Позже повысил себя до второго."
            ),
            meta={"is_onboarding": True},
            portrait_image_url="/static/images/image.png",
            left_label="Скромно",
            right_label="Дальше",
        )

    if step == 2:
        return CardViewModel(
            card_type="note",
            card_id="onboarding-classification-note",
            title="Сноска о классификации",
            body=(
                "Шкала Ландау была шутливой и логарифмической: физик первого класса, по ней, "
                "сделал в десять раз больше физика второго.\n\n"
                "Класс 0,5 Ландау оставлял Эйнштейну, а крупнейших физиков XX века относил к первому классу, например Нильса Бора и Вернера Гейзенберга "
            ),
            meta={"is_onboarding": True},
            left_label="Ясно",
            right_label="Дальше",
        )

    if step == 3:
        return CardViewModel(
            card_type="landau",
            card_id="onboarding-theorminimum",
            body=(
                "Я преподавал на физтехе и физфаке. Прежде чем попасть ко мне в группу, нужно было сдать "
                "легендарный теоретический минимум: девять экзаменов по математике и теоретической физике."
            ),
            meta={"is_onboarding": True},
            portrait_image_url="/static/images/image.png",
            left_label="Строго",
            right_label="Дальше",
        )

    if step == 4:
        return CardViewModel(
            card_type="landau",
            card_id="onboarding-theorminimum-exam",
            body=(
                "Студент договорился о времени, я выдавал ему задачу и сажал за чистый лист. Шпаргалки не помогали: "
                "физику нужно понимать, а не зубрить. С 1933 по 1961 год минимум сдали 43 человека."
            ),
            meta={"is_onboarding": True},
            portrait_image_url="/static/images/image.png",
            left_label="Строго",
            right_label="Дальше",
        )

    if step == 5:
        return CardViewModel(
            card_type="landau",
            card_id="onboarding-assistant-request",
            body=(
                "Одному мне не справиться: нужны помощники для проверки ответов студентов. Я покажу вам "
                "архивные работы, а вы попробуете найти в них ошибки."
            ),
            meta={"is_onboarding": True},
            portrait_image_url="/static/images/image.png",
            left_label="Помогу",
            right_label="Дальше",
        )

    if step == 6:
        return CardViewModel(
            card_type="landau",
            card_id="onboarding-swipe-instructions",
            body=(
                "Смахивайте влево, если ответ неточный, и вправо, если точный. Посмотрим, умеете ли вы "
                "замечать физические неточности без лишней строгости.\n\nКак вас зовут?"
            ),
            meta={"is_onboarding": True},
            portrait_image_url="/static/images/image.png",
            left_label="Готов",
            right_label="Дальше",
        )

    return CardViewModel(
        card_type="identity",
        card_id="onboarding-name-entry",
        body=(
            "Представьтесь, чтобы я знал, к кому обращаться во время проверки работ."
        ),
        meta={"is_onboarding": True},
        title="Знакомство",
        left_label="Готово",
        right_label="Начать",
    )


def build_decision_card(scene: QuestionScene, participant_name: str | None = None) -> CardViewModel:
    return CardViewModel(
        card_type="decision",
        card_id=f"{scene.id}-decision",
        title=scene.decision_card.work_title,
        meta={
            "question_text": scene.decision_card.question_text,
            "student_answer": scene.decision_card.student_answer,
            "stamp": f"Архивное дело № {scene.position:02d}",
            "participant_name": participant_name,
        },
        swipe_enabled=True,
        left_label=scene.decision_card.swipe_left_label,
        right_label=scene.decision_card.swipe_right_label,
        primary_action_label="Ответ сохраняется сразу после выбора",
        helper_text="Сервер хранит текущее прохождение и вернет вас к этой работе после перезагрузки страницы.",
    )


def build_landau_card(
    scene: QuestionScene,
    is_correct: bool = True,
    dialogue_step: int = 0,
) -> CardViewModel:
    student_answer_accepted = is_correct and scene.correct_verdict == SelectedVerdict.CORRECT
    found_inaccuracy = is_correct and scene.correct_verdict == SelectedVerdict.INACCURACY
    historical_lines = split_landau_dialogue(scene.landau_card.inaccuracy_explanation)
    if student_answer_accepted:
        dialogue_lines = [
            "Все верно. Не надо валить студента, когда он правильно отвечает.",
            *historical_lines,
        ]
        history_start = 1
    elif found_inaccuracy:
        explanation_lines = split_landau_dialogue(scene.landau_card.explanation)
        dialogue_lines = [
            "Отлично подмечено, понимания в этом ответе явно не хватало. Рассказать поподробнее, в чем ошибка?",
            *explanation_lines,
            *historical_lines,
        ]
        history_start = 1 + len(explanation_lines)
    elif scene.correct_verdict == SelectedVerdict.INACCURACY:
        explanation_lines = split_landau_dialogue(scene.landau_card.explanation)
        dialogue_lines = [
            *explanation_lines,
            *historical_lines,
        ]
        history_start = len(explanation_lines)
    else:
        verdict_title = (
            scene.landau_card.verdict_title_correct
            if is_correct
            else scene.landau_card.verdict_title_wrong
        )
        opening_lines = split_landau_dialogue(f"{verdict_title}. {scene.landau_card.character_quote}")
        explanation_lines = split_landau_dialogue(scene.landau_card.explanation)
        dialogue_lines = [
            *opening_lines,
            *explanation_lines,
            *historical_lines,
        ]
        history_start = len(opening_lines) + len(explanation_lines)
    dialogue_step = min(max(dialogue_step, 0), len(dialogue_lines) - 1)

    return CardViewModel(
        card_type="landau",
        card_id=f"{scene.id}-landau-{dialogue_step}",
        body=dialogue_lines[dialogue_step],
        meta={
            "dialogue_lines": dialogue_lines,
            "dialogue_step": dialogue_step,
            "dialogue_total": len(dialogue_lines),
            "history_start": history_start,
            "is_affirming": student_answer_accepted,
            "asks_for_details": found_inaccuracy and dialogue_step == 0,
        },
        portrait_image_url="/static/images/image.png",
        left_label="Подробнее" if found_inaccuracy and dialogue_step == 0 else "Понятно",
        right_label="Дальше" if found_inaccuracy and dialogue_step == 0 else "Интересно",
    )
