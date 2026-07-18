from app.config import get_settings
from app.models import GameRun, Participant, Response


def register_player(client, *, name: str = "Алина", team: str = "10Б"):
    client.get("/")
    for _ in range(4):
        client.post("/api/onboarding/next")
    return client.post(
        "/api/onboarding/register",
        json={"participant_name": name},
        follow_redirects=False,
    )


def login_admin(client, *, password: str | None = None):
    return client.post(
        "/admin/login",
        data={"password": password or get_settings().admin_password},
        follow_redirects=False,
    )


def advance_until_next_work_or_final(client) -> None:
    for _ in range(4):
        client.post("/play/next", follow_redirects=False)
        page = client.get("/play")
        if "Проверка студенческой работы" in page.text or "Итог прохождения" in page.text:
            return
    raise AssertionError("Dialogue did not reach the next work or final screen.")


def complete_run(client) -> None:
    register_player(client)
    verdicts = [
        "correct",
        "inaccuracy",
        "inaccuracy",
        "correct",
        "inaccuracy",
        "correct",
    ]

    for verdict in verdicts:
        client.get("/play")
        client.post(
            "/play/answer",
            data={"selected_verdict": verdict, "input_method": "button"},
            follow_redirects=False,
        )
        advance_until_next_work_or_final(client)


def test_dashboard_requires_login(client) -> None:
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "http://testserver/admin/login"


def test_correct_password_allows_dashboard(client) -> None:
    response = login_admin(client)

    assert response.status_code == 303
    assert response.headers["location"] == "http://testserver/admin"

    dashboard = client.get("/admin")
    assert dashboard.status_code == 200
    assert "Панель организатора" in dashboard.text


def test_wrong_password_does_not_authenticate(client) -> None:
    response = login_admin(client, password="not-the-password")

    assert response.status_code == 401
    assert "Неверный пароль администратора" in response.text

    dashboard = client.get("/admin", follow_redirects=False)
    assert dashboard.status_code == 303
    assert dashboard.headers["location"] == "http://testserver/admin/login"


def test_csv_export_contains_saved_results(client) -> None:
    complete_run(client)
    login_admin(client)

    response = client.get("/admin/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "participant_name" in response.text
    assert "Алина" in response.text
    assert "landau-levels" in response.text


def test_reset_requires_confirmation(client, db_session) -> None:
    register_player(client)
    login_admin(client)

    response = client.post("/admin/reset", data={"confirmation": "WRONG"})

    assert response.status_code == 400
    assert "Для сброса введите RESET" in response.text
    assert db_session.query(Participant).count() == 1
    assert db_session.query(GameRun).count() == 1


def test_reset_clears_event_data_after_confirmation(client, db_session) -> None:
    complete_run(client)
    login_admin(client)

    response = client.post("/admin/reset", data={"confirmation": "RESET"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "http://testserver/admin?reset=done"
    assert db_session.query(Participant).count() == 0
    assert db_session.query(GameRun).count() == 0
    assert db_session.query(Response).count() == 0
