import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Player, Game


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seed_roster(db_session):
    players = [
        Player(name="Center One",  number="10", position="F", is_center=True,  active=True),
        Player(name="Winger One",  number="7",  position="F", is_center=False, active=True),
        Player(name="Winger Two",  number="9",  position="F", is_center=False, active=True),
        Player(name="Defender One", number="2", position="D", is_center=False, active=True),
        Player(name="Defender Two", number="4", position="D", is_center=False, active=True),
        Player(name="Goalie One",   number="30", position="G", is_center=False, active=True),
    ]
    for p in players:
        db_session.add(p)
    db_session.commit()
    return players


@pytest.fixture
def seed_games(db_session):
    def _seed(n=10):
        base = date(2025, 10, 1)
        games = []
        for i in range(n):
            g = Game(
                date=base + timedelta(days=i * 4),
                opponent=f"Opp{i}",
                is_home=(i % 2 == 0),
                season="2025-26",
            )
            db_session.add(g)
            games.append(g)
        db_session.commit()
        return games
    return _seed
