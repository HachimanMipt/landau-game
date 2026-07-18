from app.models import GameRun, Participant, Response, ScreenState


def register_player(client, *, name: str = "Алина", team: str = "10Б"):
    client.get("/")
    for _ in range(4):
        client.post("/api/onboarding/next")
    return client.post(
        "/api/onboarding/register",
        json={"participant_name": name},
        follow_redirects=False,
    )


def advance_until_next_work_or_final(client) -> None:
    for _ in range(4):
        response = client.post("/play/next", follow_redirects=False)
        assert response.status_code == 303
        page = client.get("/play")
        if "Проверка студенческой работы" in page.text or "Итог прохождения" in page.text:
            return
    raise AssertionError("Dialogue did not reach the next work or final screen.")


def test_onboarding_registration_creates_participant_and_run_and_sets_cookie(client, db_session) -> None:
    response = register_player(client)

    assert response.status_code == 200
    assert response.json()["redirect_url"] == "http://testserver/play"
    assert "landau_run=" in response.headers["set-cookie"]

    participants = db_session.query(Participant).all()
    runs = db_session.query(GameRun).all()

    assert len(participants) == 1
    assert participants[0].name == "Алина"
    assert participants[0].team is None
    assert len(runs) == 1
    assert runs[0].current_position == 1
    assert runs[0].screen_state == ScreenState.QUESTION


def test_empty_name_is_rejected(client, db_session) -> None:
    response = client.post(
        "/api/onboarding/register",
        json={"participant_name": "   "},
    )

    assert response.status_code == 400
    assert "Имя или псевдоним" in response.json()["detail"]
    assert db_session.query(Participant).count() == 0


def test_onboarding_uses_landau_and_text_cards_before_name_entry(client) -> None:
    welcome = client.get("/")
    assert welcome.status_code == 200
    assert "Я Лев Ландау, теоретический физик" in welcome.text
    assert "/static/images/image.png" in welcome.text

    client.post("/api/onboarding/next")
    classification_note = client.get("/")
    assert "Сноска о классификации" in classification_note.text
    assert "физик первого класса" in classification_note.text
    assert "/static/images/image.png" not in classification_note.text

    client.post("/api/onboarding/next")
    theorminimum = client.get("/")
    assert "теоретический минимум" in theorminimum.text
    assert "девять экзаменов" in theorminimum.text

    client.post("/api/onboarding/next")
    assistant_request = client.get("/")
    assert "нужны помощники" in assistant_request.text
    assert "Как вас зовут?" in assistant_request.text
    assert "data-participant-name" not in assistant_request.text

    client.post("/api/onboarding/next")
    identity = client.get("/")
    assert "Представьтесь" in identity.text
    assert "data-participant-name" in identity.text


def test_register_route_redirects_to_card_onboarding(client) -> None:
    response = client.get("/register", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "http://testserver/"


def test_play_without_session_redirects_to_start(client) -> None:
    response = client.get("/play", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "http://testserver/"


def test_answer_flow_switches_to_result_and_advances(client, db_session) -> None:
    register_player(client)

    question_page = client.get("/play")
    assert question_page.status_code == 200
    assert "Архивное дело № 01" in question_page.text
    assert "Работа 1 из 6" not in question_page.text

    answer_response = client.post(
        "/play/answer",
        data={
            "selected_verdict": "correct",
            "input_method": "button",
        },
        follow_redirects=False,
    )
    assert answer_response.status_code == 303

    result_page = client.get("/play")
    assert result_page.status_code == 200
    assert "Не надо валить студента" in result_page.text

    saved_response = db_session.query(Response).one()
    assert saved_response.question_id == "landau-levels"
    assert saved_response.is_correct is True
    assert saved_response.input_method.value == "button"
    assert saved_response.response_time_ms >= 0

    advance_response = client.post("/play/next", follow_redirects=False)
    assert advance_response.status_code == 303

    history_page = client.get("/play")
    assert "уровней Ландау" in history_page.text

    advance_response = client.post("/play/next", follow_redirects=False)
    assert advance_response.status_code == 303

    next_question_page = client.get("/play")
    assert "Архивное дело № 02" in next_question_page.text
    assert "Работа 2 из 6" not in next_question_page.text


def test_refresh_on_result_keeps_result_state(client, db_session) -> None:
    register_player(client)
    client.get("/play")
    client.post(
        "/play/answer",
        data={"selected_verdict": "correct", "input_method": "button"},
        follow_redirects=False,
    )

    run = db_session.query(GameRun).one()
    assert run.screen_state == ScreenState.RESULT

    refreshed = client.get("/play")
    assert refreshed.status_code == 200
    assert "Не надо валить студента" in refreshed.text
    assert "/static/images/image.png" in refreshed.text
    assert "Карточка персонажа" not in refreshed.text
    assert "Архивный разбор" not in refreshed.text


def test_detected_inaccuracy_can_show_historical_explanation(client) -> None:
    register_player(client)
    client.get("/play")
    client.post(
        "/play/answer",
        data={"selected_verdict": "correct", "input_method": "button"},
        follow_redirects=False,
    )
    client.post("/play/next", follow_redirects=False)
    client.post("/play/next", follow_redirects=False)

    second_question = client.get("/play")
    assert "Архивное дело № 02" in second_question.text

    client.post(
        "/play/answer",
        data={"selected_verdict": "inaccuracy", "input_method": "button"},
        follow_redirects=False,
    )
    result_page = client.get("/play")
    assert "Отлично подмечено" in result_page.text
    assert "Подробнее" in result_page.text
    assert "Дальше" in result_page.text

    client.post("/play/next", data={"swipe_direction": "left"}, follow_redirects=False)
    detail_page = client.get("/play")
    assert "Магнитные свойства атомов не исчезают" in detail_page.text
    client.post("/play/next", follow_redirects=False)
    client.post("/play/next", follow_redirects=False)
    third_question = client.get("/play")
    assert "Архивное дело № 03" in third_question.text


def test_review_redirects_until_run_is_completed(client) -> None:
    register_player(client)

    response = client.get("/review", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "http://testserver/play"


def test_full_run_reaches_final_and_allows_review(client) -> None:
    register_player(client)

    verdicts = [
        "correct",
        "inaccuracy",
        "inaccuracy",
        "correct",
        "inaccuracy",
        "correct",
    ]

    for index, verdict in enumerate(verdicts, start=1):
        question_page = client.get("/play")
        assert question_page.status_code == 200
        assert "Проверка студенческой работы" in question_page.text
        assert f"Работа {index} из 6" not in question_page.text

        client.post(
            "/play/answer",
            data={"selected_verdict": verdict, "input_method": "button"},
            follow_redirects=False,
        )
        advance_until_next_work_or_final(client)

    final_page = client.get("/play")
    assert final_page.status_code == 200
    assert "Итог прохождения" in final_page.text
    assert "6 / 6" in final_page.text

    review_page = client.get("/review")
    assert review_page.status_code == 200
    assert "Разбор прохождения" in review_page.text
