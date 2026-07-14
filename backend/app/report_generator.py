import os
from datetime import date
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def _fmt_pct(val, decimals=1):
    if val is None:
        return "—"
    return f"{val * 100:.{decimals}f}%"


def _fmt_float(val, decimals=2):
    if val is None:
        return "—"
    return f"{val:.{decimals}f}"


def _fmt_shift(seconds):
    if seconds is None:
        return "—"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def _trend_direction(values):
    """Simple trend: compare last 3 vs previous 3 averages."""
    vals = [v for v in values if v is not None]
    if len(vals) < 3:
        return "insufficient data"
    recent = sum(vals[-3:]) / 3
    prior = sum(vals[:-3]) / max(len(vals) - 3, 1)
    diff = recent - prior
    if abs(diff) < 0.005:
        return "stable"
    return "trending up" if diff > 0 else "trending down"


def generate_player_report(player, agg_stats: dict, team_agg: dict) -> bytes:
    template = _env.get_template("player_report.html")

    trend = agg_stats.get("trend", [])
    games_played = agg_stats.get("games_played", 0)
    small_sample = agg_stats.get("small_sample", True)

    def spark(key):
        return [t.get(key) for t in trend]

    def vs_team(player_val, team_val, higher_better=True):
        if player_val is None or team_val is None:
            return None
        diff = player_val - team_val
        return {"diff": diff, "positive": diff > 0 if higher_better else diff < 0}

    ctx = {
        "player": player,
        "agg": agg_stats,
        "team": team_agg,
        "generated_date": date.today().strftime("%B %d, %Y"),
        "games_played": games_played,
        "small_sample": small_sample,
        "agg_icf": agg_stats.get("icf"),
        "agg_isf": agg_stats.get("isf"),
        "fmt_pct": _fmt_pct,
        "fmt_float": _fmt_float,
        "fmt_shift": _fmt_shift,
        "trend_dir": _trend_direction,
        "spark": spark,
        "vs_team": vs_team,
        "trend": trend,
    }

    html_str = template.render(**ctx)
    return HTML(string=html_str).write_pdf()


def generate_team_report(team_agg: dict) -> bytes:
    template = _env.get_template("team_report.html")

    ctx = {
        "agg": team_agg,
        "generated_date": date.today().strftime("%B %d, %Y"),
        "fmt_pct": _fmt_pct,
        "fmt_float": _fmt_float,
        "trend_dir": _trend_direction,
    }

    html_str = template.render(**ctx)
    return HTML(string=html_str).write_pdf()
