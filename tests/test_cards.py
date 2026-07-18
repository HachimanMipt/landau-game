from app.cards import MAX_LANDAU_CARD_CHARACTERS, build_landau_card
from app.content import get_scene_by_id


def test_long_landau_history_is_split_into_readable_cards() -> None:
    scene = get_scene_by_id("landau-levels")

    card = build_landau_card(scene, is_correct=True)
    dialogue_lines = card.meta["dialogue_lines"]

    assert card.meta["history_start"] == 1
    assert len(dialogue_lines) > 2
    assert dialogue_lines[0].startswith("Все верно")
    assert all(len(line) <= MAX_LANDAU_CARD_CHARACTERS for line in dialogue_lines[1:])
