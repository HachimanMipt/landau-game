from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.game_logic import InputMethod, SelectedVerdict, SwipeDirection


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ScreenState(str, Enum):
    QUESTION = "question"
    RESULT = "result"
    FINAL = "final"


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(40))
    team: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    game_runs: Mapped[list["GameRun"]] = relationship(back_populates="participant")


class GameRun(Base):
    __tablename__ = "game_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    status: Mapped[RunStatus] = mapped_column(
        SqlEnum(RunStatus, native_enum=False),
        default=RunStatus.IN_PROGRESS,
    )
    screen_state: Mapped[ScreenState] = mapped_column(
        SqlEnum(ScreenState, native_enum=False),
        default=ScreenState.QUESTION,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_position: Mapped[int] = mapped_column(Integer, default=1)
    result_step: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    question_order_json: Mapped[str] = mapped_column(Text, default="[]")
    current_question_shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_answered_question_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    participant: Mapped[Participant] = relationship(back_populates="game_runs")
    responses: Mapped[list["Response"]] = relationship(back_populates="game_run")


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("game_run_id", "question_id", name="uq_game_run_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(100), index=True)
    selected_verdict: Mapped[SelectedVerdict] = mapped_column(SqlEnum(SelectedVerdict, native_enum=False))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    swipe_direction: Mapped[SwipeDirection] = mapped_column(SqlEnum(SwipeDirection, native_enum=False))
    input_method: Mapped[InputMethod] = mapped_column(SqlEnum(InputMethod, native_enum=False))
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    response_time_ms: Mapped[int] = mapped_column(Integer)

    game_run: Mapped[GameRun] = relationship(back_populates="responses")
