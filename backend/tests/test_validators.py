import pytest
from app.models import Player
from app.ingest.validators import validate_jersey


class TestValidateJersey:
    def test_matches_existing_player(self, db_session, seed_roster):
        # seed_roster fixture (from conftest.py) creates 6 players with numbers 10,7,9,2,4,30
        roster = {p.number: p for p in db_session.query(Player).all()}
        player, warnings = validate_jersey("10", roster)
        assert player is not None
        assert player.number == "10"
        assert warnings == []

    def test_returns_none_and_warning_for_unknown_jersey(self, db_session, seed_roster):
        roster = {p.number: p for p in db_session.query(Player).all()}
        player, warnings = validate_jersey("99", roster)
        assert player is None
        assert len(warnings) == 1
        assert "99" in warnings[0]
