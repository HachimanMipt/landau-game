from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.cards import ONBOARDING_CARD_COUNT
from app.config import get_settings
from app.dependencies import build_template_context, get_db, templates
from app.game_logic import InputMethod, SelectedVerdict, SwipeDirection
from app.game_service import (
    GameplayStateError,
    advance_run,
    build_onboarding_page_state,
    build_review_entries,
    build_run_page_state,
    build_run_summary,
    get_run_by_public_id,
    submit_current_answer,
)

router = APIRouter(tags=["public"])


def _build_redirect_response(destination: str, status_code: int = status.HTTP_303_SEE_OTHER) -> RedirectResponse:
    return RedirectResponse(url=destination, status_code=status_code)


def _build_public_context(request: Request, page_title: str, *, body_class: str, **context: object) -> dict[str, object]:
    return build_template_context(
        request,
        page_title=page_title,
        show_site_header=False,
        body_class=body_class,
        **context,
    )


def _clear_run_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(get_settings().run_cookie_name)


def _get_onboarding_step(request: Request) -> int:
    stored_step = request.session.get("onboarding_step", 0)
    if not isinstance(stored_step, int):
        return 0
    return min(max(stored_step, 0), ONBOARDING_CARD_COUNT - 1)


def _get_current_run(request: Request, session: Session) -> tuple[object | None, RedirectResponse | None]:
    run_public_id = request.cookies.get(get_settings().run_cookie_name)
    if not run_public_id:
        response = _build_redirect_response(request.url_for("start"))
        return None, response

    run = get_run_by_public_id(session, run_public_id)
    if run is None:
        response = _build_redirect_response(request.url_for("start"))
        _clear_run_cookie(response)
        return None, response

    return run, None


@router.get("/", name="start")
def start(request: Request):
    if request.cookies.get(get_settings().run_cookie_name):
        return _build_redirect_response(str(request.url_for("play")))

    return templates.TemplateResponse(
        request=request,
        name="play.html",
        context=_build_public_context(
            request,
            page_title="Знакомство",
            body_class="screen-play",
            page_state=build_onboarding_page_state(_get_onboarding_step(request)),
        ),
    )


@router.get("/register", name="register")
def register(request: Request):
    return _build_redirect_response(str(request.url_for("start")))


@router.get("/new-game", name="new_game")
def new_game(request: Request):
    request.session.pop("onboarding_step", None)
    response = _build_redirect_response(str(request.url_for("start")))
    _clear_run_cookie(response)
    return response


@router.get("/play", name="play")
def play(request: Request, session: Session = Depends(get_db)):
    run, redirect_response = _get_current_run(request, session)
    if redirect_response is not None:
        return redirect_response

    try:
        page_state = build_run_page_state(session, run)
    except GameplayStateError:
        response = _build_redirect_response(str(request.url_for("start")))
        _clear_run_cookie(response)
        return response

    if page_state.kind == "final":
        return templates.TemplateResponse(
            request=request,
            name="final.html",
            context=_build_public_context(
                request,
                page_title="Итог",
                body_class="screen-summary",
                page_state=page_state,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="play.html",
        context=_build_public_context(
            request,
            page_title="Игровая карточка",
            body_class="screen-play",
            page_state=page_state,
        ),
    )


@router.post("/play/answer", name="play_answer")
def play_answer(
    request: Request,
    session: Session = Depends(get_db),
    selected_verdict: SelectedVerdict = Form(...),
    input_method: InputMethod = Form(default=InputMethod.BUTTON),
):
    run, redirect_response = _get_current_run(request, session)
    if redirect_response is not None:
        return redirect_response

    try:
        submit_current_answer(
            session,
            run,
            selected_verdict=selected_verdict,
            input_method=input_method,
        )
    except GameplayStateError:
        return _build_redirect_response(str(request.url_for("play")))

    return _build_redirect_response(str(request.url_for("play")))


@router.post("/play/next", name="play_next")
def play_next(
    request: Request,
    session: Session = Depends(get_db),
    swipe_direction: SwipeDirection = Form(default=SwipeDirection.RIGHT),
):
    run, redirect_response = _get_current_run(request, session)
    if redirect_response is not None:
        return redirect_response

    try:
        advance_run(session, run, swipe_direction=swipe_direction)
    except GameplayStateError:
        return _build_redirect_response(str(request.url_for("play")))

    return _build_redirect_response(str(request.url_for("play")))


@router.get("/review", name="review")
def review(request: Request, session: Session = Depends(get_db)):
    run, redirect_response = _get_current_run(request, session)
    if redirect_response is not None:
        return redirect_response
    if run.status.value != "completed":
        return _build_redirect_response(str(request.url_for("play")))

    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context=_build_public_context(
            request,
            page_title="Разбор",
            body_class="screen-summary",
            participant=run.participant,
            summary=build_run_summary(run),
            review_entries=build_review_entries(run),
        ),
    )
