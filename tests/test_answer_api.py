from app.models import Response


def register_player(client):
    client.get("/")
    for _ in range(4):
        client.post("/api/onboarding/next")
    return client.post(
        "/api/onboarding/register",
        json={"participant_name": "Алина"},
        follow_redirects=False,
    )


def test_answer_api_requires_active_run(client) -> None:
    response = client.post(
        "/api/answers/current",
        json={
            "selected_verdict": "correct",
            "input_method": "swipe",
        },
    )

    assert response.status_code == 401
    assert response.json()["ok"] is False


def test_answer_api_saves_only_one_response_for_duplicate_submission(client, db_session) -> None:
    register_player(client)
    client.get("/play")

    first = client.post(
        "/api/answers/current",
        json={
            "selected_verdict": "inaccuracy",
            "input_method": "swipe",
        },
    )
    second = client.post(
        "/api/answers/current",
        json={
            "selected_verdict": "inaccuracy",
            "input_method": "swipe",
        },
    )

    assert first.status_code == 200
    assert first.json()["ok"] is True
    assert first.json()["duplicate"] is False

    assert second.status_code == 200
    assert second.json()["ok"] is True
    assert second.json()["duplicate"] is True

    responses = db_session.query(Response).all()
    assert len(responses) == 1
    assert responses[0].input_method.value == "swipe"


def test_api_cannot_answer_without_current_question_state(client) -> None:
    register_player(client)
    client.get("/play")
    client.post(
        "/api/answers/current",
        json={
            "selected_verdict": "inaccuracy",
            "input_method": "swipe",
        },
    )

    response = client.post(
        "/api/answers/current",
        json={
            "selected_verdict": "inaccuracy",
            "input_method": "swipe",
        },
    )

    assert response.status_code == 200
    assert response.json()["duplicate"] is True


def test_next_api_advances_after_result_card(client) -> None:
    register_player(client)
    client.get("/play")
    client.post(
        "/api/answers/current",
        json={
            "selected_verdict": "correct",
            "input_method": "swipe",
        },
    )
    client.post("/api/play/next")
    client.post("/api/play/next")
    client.get("/play")
    client.post(
        "/api/answers/current",
        json={
            "selected_verdict": "inaccuracy",
            "input_method": "swipe",
        },
    )

    response = client.post("/api/play/next", json={"swipe_direction": "left"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["redirect_url"] == "http://testserver/play"

    second_line = client.get("/play")
    assert "Магнитные свойства атомов не исчезают" in second_line.text
    assert "/static/images/image.png" in second_line.text

    client.post("/api/play/next")
    history_line = client.get("/play")
    assert "В 1937 году" in history_line.text
    client.post("/api/play/next")
    next_question_page = client.get("/play")
    assert "Архивное дело № 03" in next_question_page.text


def test_next_api_skips_error_explanation_but_keeps_history_when_swiped_right(client) -> None:
    register_player(client)
    client.get("/play")
    client.post(
        "/api/answers/current",
        json={"selected_verdict": "correct", "input_method": "swipe"},
    )
    client.post("/api/play/next")
    client.post("/api/play/next")
    client.get("/play")
    client.post(
        "/api/answers/current",
        json={"selected_verdict": "inaccuracy", "input_method": "swipe"},
    )

    response = client.post("/api/play/next", json={"swipe_direction": "right"})

    assert response.status_code == 200
    history_line = client.get("/play")
    assert "В 1937 году" in history_line.text
    assert "Магнитные свойства атомов не исчезают" not in history_line.text

    client.post("/api/play/next")
    next_question_page = client.get("/play")
    assert "Архивное дело № 03" in next_question_page.text
