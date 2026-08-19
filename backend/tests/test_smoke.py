def test_db_session_is_writable(db_session):
    from app.models import Player
    p = Player(name="Test", number="1", position="F", is_center=False, active=True)
    db_session.add(p)
    db_session.commit()
    assert db_session.query(Player).count() == 1


def test_seed_roster_creates_six(db_session, seed_roster):
    from app.models import Player
    all_players = db_session.query(Player).order_by(Player.name).all()
    assert len(all_players) == 6
    positions = sorted([p.position for p in all_players])
    assert positions == ["D", "D", "F", "F", "F", "G"]


def test_seed_games_default_is_ten(db_session, seed_games):
    from app.models import Game
    games = seed_games()
    assert len(games) == 10
    assert db_session.query(Game).count() == 10
