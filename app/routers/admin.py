from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.admin_service import ADMIN_RESET_CONFIRMATION, build_admin_csv_export, build_admin_dashboard, reset_event_data
from app.config import get_settings
from app.dependencies import build_template_context, get_db, templates

router = APIRouter(prefix="/admin", tags=["admin"])
ADMIN_SESSION_KEY = "admin_authenticated"


def _build_redirect_response(destination: str, status_code: int = status.HTTP_303_SEE_OTHER) -> RedirectResponse:
    return RedirectResponse(url=destination, status_code=status_code)


def _is_admin_authenticated(request: Request) -> bool:
    return bool(request.session.get(ADMIN_SESSION_KEY))


def _require_admin(request: Request) -> RedirectResponse | None:
    if _is_admin_authenticated(request):
        return None
    return _build_redirect_response(str(request.url_for("admin_login")))


@router.get("/login", name="admin_login")
def admin_login(request: Request):
    if _is_admin_authenticated(request):
        return _build_redirect_response(str(request.url_for("admin_dashboard")))

    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context=build_template_context(request, page_title="Admin Login"),
    )


@router.post("/login", name="admin_login_submit")
def admin_login_submit(request: Request, password: str = Form(...)):
    if password == get_settings().admin_password:
        request.session[ADMIN_SESSION_KEY] = True
        return _build_redirect_response(str(request.url_for("admin_dashboard")))

    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context=build_template_context(
            request,
            page_title="Admin Login",
            error_message="Неверный пароль администратора.",
        ),
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@router.get("", name="admin_dashboard")
def admin_dashboard(request: Request, session: Session = Depends(get_db)):
    redirect_response = _require_admin(request)
    if redirect_response is not None:
        return redirect_response

    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context=build_template_context(
            request,
            page_title="Admin Dashboard",
            dashboard=build_admin_dashboard(session),
            notice_message=(
                "Данные мероприятия очищены."
                if request.query_params.get("reset") == "done"
                else None
            ),
        ),
    )


@router.get("/export.csv", name="admin_export_csv")
def admin_export_csv(request: Request, session: Session = Depends(get_db)):
    redirect_response = _require_admin(request)
    if redirect_response is not None:
        return redirect_response

    filename = f"landau-event-export-{date.today().isoformat()}.csv"
    return Response(
        content=build_admin_csv_export(session),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reset", name="admin_reset")
def admin_reset(request: Request, session: Session = Depends(get_db), confirmation: str = Form(default="")):
    redirect_response = _require_admin(request)
    if redirect_response is not None:
        return redirect_response

    if confirmation.strip().upper() != ADMIN_RESET_CONFIRMATION:
        return templates.TemplateResponse(
            request=request,
            name="admin_dashboard.html",
            context=build_template_context(
                request,
                page_title="Admin Dashboard",
                dashboard=build_admin_dashboard(session),
                error_message=f"Для сброса введите {ADMIN_RESET_CONFIRMATION}.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    reset_event_data(session)
    return _build_redirect_response(f"{request.url_for('admin_dashboard')}?reset=done")


@router.post("/logout", name="admin_logout")
def admin_logout(request: Request):
    request.session.pop(ADMIN_SESSION_KEY, None)
    return _build_redirect_response(str(request.url_for("admin_login")))
