from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, RootModel, ValidationError, field_validator, model_validator

from app.config import BASE_DIR
from app.game_logic import SelectedVerdict

QUESTIONS_PATH = BASE_DIR / "data" / "questions.json"
EXPECTED_ACTIVE_SCENE_COUNT = 6
FactCheckLiteral = Literal["verified", "needs_review"]


def _strip_required_text(value: str) -> str:
    if not isinstance(value, str):
        return value
    return value.strip()


def _strip_optional_text(value: str | None) -> str | None:
    if value is None or not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped or None


class DecisionCardContent(BaseModel):
    work_title: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    student_answer: str = Field(min_length=1)
    swipe_left_label: str = Field(min_length=1)
    swipe_right_label: str = Field(min_length=1)

    _strip_fields = field_validator(
        "work_title",
        "question_text",
        "student_answer",
        "swipe_left_label",
        "swipe_right_label",
        mode="before",
    )(_strip_required_text)


class LandauCardContent(BaseModel):
    verdict_title_correct: str = Field(min_length=1)
    verdict_title_wrong: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    inaccuracy_explanation: str = Field(min_length=1)
    character_quote: str = Field(min_length=1)
    fact_title: str = Field(min_length=1)
    fact_text: str = Field(min_length=1)
    place: str | None = None
    period: str | None = None
    people: str | None = None
    importance: str | None = None

    _strip_required_fields = field_validator(
        "verdict_title_correct",
        "verdict_title_wrong",
        "explanation",
        "inaccuracy_explanation",
        "character_quote",
        "fact_title",
        "fact_text",
        mode="before",
    )(_strip_required_text)

    _strip_optional_fields = field_validator(
        "place",
        "period",
        "people",
        "importance",
        mode="before",
    )(_strip_optional_text)


class QuestionScene(BaseModel):
    id: str = Field(min_length=1)
    position: int = Field(ge=1)
    decision_card: DecisionCardContent
    correct_verdict: SelectedVerdict
    landau_card: LandauCardContent
    sources: list[str] = Field(default_factory=list)
    difficulty: int = Field(default=1, ge=1, le=3)
    fact_check_status: FactCheckLiteral = "needs_review"
    enabled: bool = True

    _strip_id = field_validator("id", mode="before")(_strip_required_text)

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        if value is None:
            return []
        return value

    @field_validator("sources")
    @classmethod
    def strip_source_strings(cls, value: list[str]) -> list[str]:
        normalized = []
        for item in value:
            stripped = _strip_required_text(item)
            if not stripped:
                raise ValueError("Source entries must not be empty strings")
            normalized.append(stripped)
        return normalized


class SceneCollection(RootModel[list[QuestionScene]]):
    @model_validator(mode="after")
    def validate_scene_collection(self) -> "SceneCollection":
        scenes = self.root
        ids = [scene.id for scene in scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("Question scene ids must be unique")

        enabled_scenes = [scene for scene in scenes if scene.enabled]
        if len(enabled_scenes) != EXPECTED_ACTIVE_SCENE_COUNT:
            raise ValueError(
                f"Expected exactly {EXPECTED_ACTIVE_SCENE_COUNT} enabled scenes, found {len(enabled_scenes)}"
            )

        positions = [scene.position for scene in enabled_scenes]
        if len(positions) != len(set(positions)):
            raise ValueError("Enabled question scene positions must be unique")

        return self


def load_question_scenes(path: Path | None = None) -> list[QuestionScene]:
    source_path = path or QUESTIONS_PATH
    raw_data = json.loads(source_path.read_text(encoding="utf-8"))
    try:
        scenes = SceneCollection.model_validate(raw_data).root
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return sorted((scene for scene in scenes if scene.enabled), key=lambda scene: scene.position)


def load_preview_scene(path: Path | None = None) -> QuestionScene:
    scenes = load_question_scenes(path=path)
    if not scenes:
        raise ValueError("No enabled scenes found in data/questions.json")
    return scenes[0]


def get_scene_by_position(position: int, path: Path | None = None) -> QuestionScene:
    scenes = load_question_scenes(path=path)
    for scene in scenes:
        if scene.position == position:
            return scene
    raise ValueError(f"Scene with position {position} was not found")


def get_scene_by_id(scene_id: str, path: Path | None = None) -> QuestionScene:
    scenes = load_question_scenes(path=path)
    for scene in scenes:
        if scene.id == scene_id:
            return scene
    raise ValueError(f"Scene with id {scene_id} was not found")


def get_enabled_scene_count(path: Path | None = None) -> int:
    return len(load_question_scenes(path=path))
