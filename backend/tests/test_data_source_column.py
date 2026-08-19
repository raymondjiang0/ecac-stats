import pytest
from datetime import date
from app.models import Game, Player


class TestGameDataSource:
    def test_default_is_49ing(self, db_session):
        g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26")
        db_session.add(g)
        db_session.commit()
        db_session.refresh(g)
        assert g.data_source == "49ing"

    def test_can_set_instat(self, db_session):
        g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26",
                 data_source="instat")
        db_session.add(g)
        db_session.commit()
        db_session.refresh(g)
        assert g.data_source == "instat"

    def test_can_set_both(self, db_session):
        g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26",
                 data_source="both")
        db_session.add(g)
        db_session.commit()
        assert g.data_source == "both"
