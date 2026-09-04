"""Write parsed InStat data to target tables.

One transaction per commit call. Upserts by (game_id, player_id) or
(game_id, from_player_id, to_player_id) for matrix rows — so re-ingest
of the same game replaces prior values.
"""
from ..models import (
    Player, TeamGameStatsInStat, PlayerGameStatsInStat,
    PlayerGameStats, PlayerHitMatrix, PlayerPassMatrix,
)


def commit_parsed(parsed: dict, game_id: int, db_session) -> dict:
    """Write all templates' data to DB atomically.

    Returns {"wrote": {template_name: row_count}, "skipped": [warnings]}.
    Rolls back on any exception.
    """
    templates = parsed["templates"]
    wrote = {name: 0 for name in templates}
    skipped: list[str] = []

    # Single-team assumption: current app tracks one team (OUR_TEAM_NAME).
    # Multi-team support would require scoping this query by a team_id FK
    # on Player, which the schema doesn't currently have.
    roster = {p.number: p for p in db_session.query(Player).all()}

    try:
        # instat_team_stats: single upsert on game_id
        team = templates.get("instat_team_stats") or {}
        # Skip when all team fields are None — likely means the parser
        # couldn't extract this section, not "explicitly clear this data".
        # A re-ingest with all-None values will NOT clear previously-written
        # team-stats values.
        if any(v is not None for v in team.values()):
            existing = db_session.query(TeamGameStatsInStat).filter_by(
                game_id=game_id
            ).one_or_none()
            if existing is None:
                existing = TeamGameStatsInStat(game_id=game_id)
                db_session.add(existing)
            for k, v in team.items():
                setattr(existing, k, v)
            wrote["instat_team_stats"] = 1

        # instat_players_main: upsert per player row
        for row in templates.get("instat_players_main") or []:
            player = roster.get(str(row.get("jersey_number", "")).strip())
            if player is None:
                skipped.append(
                    f"players_main: jersey {row.get('jersey_number')!r} not in roster"
                )
                continue
            existing = db_session.query(PlayerGameStatsInStat).filter_by(
                game_id=game_id, player_id=player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerGameStatsInStat(game_id=game_id, player_id=player.id)
                db_session.add(existing)
            for k in ("shots", "shots_on_goal", "blocked_shots",
                      "pp_shots", "pp_shots_on_goal",
                      "corsi_plus", "corsi_minus",
                      "hits_delivered", "hits_received",
                      "puck_losses", "puck_losses_dz",
                      "puck_recoveries", "puck_recoveries_oz",
                      "entries_pass", "entries_stick", "entries_dump"):
                if k in row:
                    setattr(existing, k, row[k])
            wrote["instat_players_main"] += 1

        # instat_challenges: upsert per player row into pb_* fields
        for row in templates.get("instat_challenges") or []:
            player = roster.get(str(row.get("jersey_number", "")).strip())
            if player is None:
                skipped.append(
                    f"challenges: jersey {row.get('jersey_number')!r} not in roster"
                )
                continue
            existing = db_session.query(PlayerGameStatsInStat).filter_by(
                game_id=game_id, player_id=player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerGameStatsInStat(game_id=game_id, player_id=player.id)
                db_session.add(existing)
            for k in ("pb_won_dz", "pb_total_dz",
                      "pb_won_oz", "pb_total_oz",
                      "pb_won_nz", "pb_total_nz"):
                if k in row:
                    setattr(existing, k, row[k])
            wrote["instat_challenges"] += 1

        # instat_time_distribution: upsert PlayerGameStats toi/pp/sh
        # (Only for InStat-sourced games; if PlayerGameStats already
        # populated by 49ing, this overwrites — fine per data_source == "both"
        # 49ing-precedence rule NOT applying to raw TOI which is identical
        # across sources.)
        for row in templates.get("instat_time_distribution") or []:
            player = roster.get(str(row.get("jersey_number", "")).strip())
            if player is None:
                skipped.append(
                    f"time_distribution: jersey {row.get('jersey_number')!r} not in roster"
                )
                continue
            existing = db_session.query(PlayerGameStats).filter_by(
                game_id=game_id, player_id=player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerGameStats(game_id=game_id, player_id=player.id)
                db_session.add(existing)
            # Convert seconds → minutes for the model's Float TOI fields
            if row.get("toi_5v5_seconds") is not None:
                existing.toi_5v5 = row["toi_5v5_seconds"] / 60.0
            if row.get("toi_pp_seconds") is not None:
                existing.toi_pp = row["toi_pp_seconds"] / 60.0
            if row.get("toi_sh_seconds") is not None:
                existing.toi_sh = row["toi_sh_seconds"] / 60.0
            wrote["instat_time_distribution"] += 1

        # instat_hit_matrix: upsert per from→to pair
        for row in templates.get("instat_hit_matrix") or []:
            f_player = roster.get(str(row.get("from_jersey", "")).strip())
            t_player = roster.get(str(row.get("to_jersey", "")).strip())
            if f_player is None or t_player is None:
                skipped.append(
                    f"hit_matrix: pair {row.get('from_jersey')}→{row.get('to_jersey')} not in roster"
                )
                continue
            existing = db_session.query(PlayerHitMatrix).filter_by(
                game_id=game_id, from_player_id=f_player.id, to_player_id=t_player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerHitMatrix(
                    game_id=game_id, from_player_id=f_player.id, to_player_id=t_player.id
                )
                db_session.add(existing)
            existing.delivered = row.get("delivered", 0)
            existing.received = row.get("received", 0)
            wrote["instat_hit_matrix"] += 1

        # instat_pass_matrix: upsert per from→to pair
        for row in templates.get("instat_pass_matrix") or []:
            f_player = roster.get(str(row.get("from_jersey", "")).strip())
            t_player = roster.get(str(row.get("to_jersey", "")).strip())
            if f_player is None or t_player is None:
                skipped.append(
                    f"pass_matrix: pair {row.get('from_jersey')}→{row.get('to_jersey')} not in roster"
                )
                continue
            existing = db_session.query(PlayerPassMatrix).filter_by(
                game_id=game_id, from_player_id=f_player.id, to_player_id=t_player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerPassMatrix(
                    game_id=game_id, from_player_id=f_player.id, to_player_id=t_player.id
                )
                db_session.add(existing)
            existing.count = row.get("count", 0)
            wrote["instat_pass_matrix"] += 1

        db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    return {"wrote": wrote, "skipped": skipped}
