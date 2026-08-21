from sqlalchemy import Column, Integer, Float, String, Boolean, Date, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    number = Column(String, nullable=True)
    position = Column(String, nullable=False)  # "F", "D", "G"
    is_center = Column(Boolean, default=False)
    active = Column(Boolean, default=True)

    game_stats = relationship("PlayerGameStats", back_populates="player", cascade="all, delete-orphan")


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    opponent = Column(String, nullable=False)
    is_home = Column(Boolean, nullable=False)
    season = Column(String, nullable=False, default="2025-26")
    data_source = Column(String, nullable=False, default="49ing")
    # values: "49ing" | "instat" | "both" (SQLite does not enforce enum; validated at API layer)
    notes = Column(Text, nullable=True)

    team_stats = relationship("TeamGameStats", back_populates="game", uselist=False, cascade="all, delete-orphan")
    player_stats = relationship("PlayerGameStats", back_populates="game", cascade="all, delete-orphan")


class TeamGameStats(Base):
    __tablename__ = "team_game_stats"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), unique=True, nullable=False)

    # 5v5 core
    cf_for_5v5 = Column(Float, nullable=True)
    cf_against_5v5 = Column(Float, nullable=True)
    ff_for_5v5 = Column(Float, nullable=True)
    ff_against_5v5 = Column(Float, nullable=True)
    xgf_5v5 = Column(Float, nullable=True)
    xga_5v5 = Column(Float, nullable=True)

    # TOI decomposition → estimated 5v5 TOI = total - pp - pk - other
    total_game_time = Column(Float, nullable=True, default=60)  # minutes (60 reg / 65 OT / …)
    toi_pp = Column(Float, nullable=True)   # 5v4 power-play TOI (Data Cockpit Team tab)
    toi_pk = Column(Float, nullable=True)   # 4v5 penalty-kill TOI
    other_toi = Column(Float, nullable=True, default=0)  # rare states (4v4, 6v5 empty-net, …)

    # 5v4 (power play)
    cf_for_5v4 = Column(Float, nullable=True)
    cf_against_5v4 = Column(Float, nullable=True)
    xgf_5v4 = Column(Float, nullable=True)
    xga_5v4 = Column(Float, nullable=True)

    # 4v5 (penalty kill)
    cf_for_4v5 = Column(Float, nullable=True)
    cf_against_4v5 = Column(Float, nullable=True)
    xgf_4v5 = Column(Float, nullable=True)
    xga_4v5 = Column(Float, nullable=True)

    # Attack scenario mix — xG totals from 49ing Attack Scenarios tab (5v5 filter).
    # Platform only exposes xG per scenario, not shot-attempt counts.
    # Mix = each scenario's xGF ÷ team's total scenario xGF (expected-goal share).
    rush_xgf = Column(Float, nullable=True)
    oz_fc_xgf = Column(Float, nullable=True)
    oz_fo_xgf = Column(Float, nullable=True)
    sust_pos_xgf = Column(Float, nullable=True)

    game = relationship("Game", back_populates="team_stats")



class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)

    __table_args__ = (UniqueConstraint("player_id", "game_id"),)

    # On-ice 5v5 — stored as per-60 rates (49ing only exposes scaled values, not raw counts)
    toi_5v5 = Column(Float, nullable=True)               # minutes
    cf60 = Column("cf_for", Float, nullable=True)        # Corsi For per 60
    ca60 = Column("cf_against", Float, nullable=True)    # Corsi Against per 60
    ff60 = Column("ff_for", Float, nullable=True)        # Fenwick For per 60
    fa60 = Column("ff_against", Float, nullable=True)    # Fenwick Against per 60
    sf60 = Column("sf_for", Float, nullable=True)        # SOG For per 60
    sa60 = Column("sf_against", Float, nullable=True)    # SOG Against per 60
    xgf60 = Column("xgf", Float, nullable=True)          # xGF per 60
    xga60 = Column("xga", Float, nullable=True)          # xGA per 60

    # Individual shooting — raw counts per game (not per-60)
    icf = Column(Float, nullable=True)           # individual shot attempts
    isf = Column(Float, nullable=True)           # individual shots on goal

    # Shift
    median_shift_seconds = Column(Float, nullable=True)

    # Faceoffs (primarily centers)
    personal_draws_taken = Column(Float, nullable=True)
    personal_draws_won = Column(Float, nullable=True)
    team_fo_wins_on_ice = Column(Float, nullable=True)
    team_fo_losses_on_ice = Column(Float, nullable=True)

    player = relationship("Player", back_populates="game_stats")
    game = relationship("Game", back_populates="player_stats")


class PlayerGameStatsInStat(Base):
    __tablename__ = "player_game_stats_instat"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)

    __table_args__ = (UniqueConstraint("player_id", "game_id"),)

    # Individual shooting (raw counts per game)
    shots = Column(Integer, nullable=True)
    shots_on_goal = Column(Integer, nullable=True)
    blocked_shots = Column(Integer, nullable=True)
    pp_shots = Column(Integer, nullable=True)
    pp_shots_on_goal = Column(Integer, nullable=True)

    # On-ice Corsi (raw counts)
    corsi_plus = Column(Integer, nullable=True)
    corsi_minus = Column(Integer, nullable=True)

    # Physical
    hits_delivered = Column(Integer, nullable=True)
    hits_received = Column(Integer, nullable=True)

    # Puck battles by zone
    pb_won_dz = Column(Integer, nullable=True)
    pb_total_dz = Column(Integer, nullable=True)
    pb_won_oz = Column(Integer, nullable=True)
    pb_total_oz = Column(Integer, nullable=True)
    pb_won_nz = Column(Integer, nullable=True)
    pb_total_nz = Column(Integer, nullable=True)

    # Turnovers / recoveries
    puck_losses = Column(Integer, nullable=True)
    puck_losses_dz = Column(Integer, nullable=True)
    puck_recoveries = Column(Integer, nullable=True)
    puck_recoveries_oz = Column(Integer, nullable=True)

    # Zone entries
    entries_pass = Column(Integer, nullable=True)
    entries_stick = Column(Integer, nullable=True)
    entries_dump = Column(Integer, nullable=True)

    player = relationship("Player")
    game = relationship("Game")


class TeamGameStatsInStat(Base):
    __tablename__ = "team_game_stats_instat"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), unique=True, nullable=False)

    # Special teams detail
    pp_shots = Column(Integer, nullable=True)
    pp_time_seconds_in_oz = Column(Integer, nullable=True)
    pp_time_seconds_total = Column(Integer, nullable=True)
    pk_opp_breakouts = Column(Integer, nullable=True)
    pp_opp_breakouts_allowed = Column(Integer, nullable=True)

    # Puck possession (5v5)
    puck_possession_seconds_total = Column(Integer, nullable=True)
    oz_possession_seconds = Column(Integer, nullable=True)
    oz_possession_pct = Column(Float, nullable=True)

    # Team-level shot quality
    scoring_chance_shots = Column(Integer, nullable=True)
    scoring_chance_shots_on_goal = Column(Integer, nullable=True)

    game = relationship("Game")
