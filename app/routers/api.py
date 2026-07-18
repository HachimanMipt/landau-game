from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.cards import ONBOARDING_CARD_COUNT
from app.config import get_settings
from app.dependencies import get_db
from app.game_logic import InputMethod, SelectedVerdict, SwipeDirection
from app.game_service import (
    GameplayStateError,
    RegistrationValidationError,
    advance_run,
    create_participant_and_run,
    get_run_by_public_id,
    normalize_registration_field,
    submit_current_answer,
)

router = APIRouter(prefix="/api", tags=["api"])


class CurrentAnswerPayload(BaseModel):
    selected_verdict: SelectedVerdict
    input_method: InputMethod


class ResultAdvancePayload(BaseModel):
    swipe_direction: SwipeDirection = SwipeDirection.RIGHT


class OnboardingRegistrationPayload(BaseModel):
    participant_name: str


def _redirect_payload(url: str, *, ok: bool, detail: str, duplicate: bool = False) -> JSONResponse:
    status_code = status.HTTP_200_OK if ok else status.HTTP_409_CONFLICT
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": ok,
            "duplicate": duplicate,
            "detail": detail,
            "redirect_url": url,
        },
    )


@router.get("/healthz", name="healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _get_onboarding_step(request: Request) -> int:
    stored_step = request.session.get("onboarding_step", 0)
    if not isinstance(stored_step, int):
        return 0
    return min(max(stored_step, 0), ONBOARDING_CARD_COUNT - 1)


@router.post("/onboarding/next", name="onboarding_next_api")
def onboarding_next_api(request: Request) -> JSONResponse:
    next_step = min(_get_onboarding_step(request) + 1, ONBOARDING_CARD_COUNT - 1)
    request.session["onboarding_step"] = next_step
    return _redirect_payload(
        str(request.url_for("start")),
        ok=True,
        detail="Advanced to the next introduction card.",
    )


@router.post("/onboarding/register", name="onboarding_register_api")
def onboarding_register_api(
    request: Request,
    payload: OnboardingRegistrationPayload,
    session: Session = Depends(get_db),
) -> JSONResponse:
    try:
        participant_name = normalize_registration_field(payload.participant_name, required=True, max_length=40)
    except RegistrationValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "ok": False,
                "detail": str(exc),
                "redirect_url": str(request.url_for("start")),
            },
        )

    run = create_participant_and_run(session, name=participant_name or "", team=None)
    request.session.pop("onboarding_step", None)
    response = _redirect_payload(
        str(request.url_for("play")),
        ok=True,
        detail="Participant registered.",
    )
    response.set_cookie(
        key=get_settings().run_cookie_name,
        value=run.public_id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 8,
    )
    return response


@router.post("/answers/current", name="current_answer")
def current_answer(
    request: Request,
    payload: CurrentAnswerPayload,
    session: Session = Depends(get_db),
) -> JSONResponse:
    run_public_id = request.cookies.get(get_settings().run_cookie_name)
    if not run_public_id:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "ok": False,
                "detail": "No active game run was found.",
                "redirect_url": str(request.url_for("start")),
            },
        )

    run = get_run_by_public_id(session, run_public_id)
    if run is None:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "ok": False,
                "detail": "The active run cookie is stale.",
                "redirect_url": str(request.url_for("start")),
            },
        )

    try:
        _, duplicate = submit_current_answer(
            session,
            run,
            selected_verdict=payload.selected_verdict,
            input_method=payload.input_method,
        )
    except GameplayStateError as exc:
        return _redirect_payload(
            str(request.url_for("play")),
            ok=False,
            detail=str(exc),
        )

    return _redirect_payload(
        str(request.url_for("play")),
        ok=True,
        detail="Answer saved.",
        duplicate=duplicate,
    )


@router.post("/play/next", name="play_next_api")
def play_next_api(
    request: Request,
    payload: ResultAdvancePayload | None = None,
    session: Session = Depends(get_db),
) -> JSONResponse:
    run_public_id = request.cookies.get(get_settings().run_cookie_name)
    if not run_public_id:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "ok": False,
                "detail": "No active game run was found.",
                "redirect_url": str(request.url_for("start")),
            },
        )

    run = get_run_by_public_id(session, run_public_id)
    if run is None:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "ok": False,
                "detail": "The active run cookie is stale.",
                "redirect_url": str(request.url_for("start")),
            },
        )

    try:
        advance_run(
            session,
            run,
            swipe_direction=payload.swipe_direction if payload else SwipeDirection.RIGHT,
        )
    except GameplayStateError as exc:
        return _redirect_payload(
            str(request.url_for("play")),
            ok=False,
            detail=str(exc),
        )

    return _redirect_payload(
        str(request.url_for("play")),
        ok=True,
        detail="Advanced to the next card.",
    )
