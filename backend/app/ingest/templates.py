"""Central registry mapping template name → parser function.

Adding a new template: import the parser, add the entry, and add the target
table's commit logic to app.ingest.commit.
"""
from .parsers.team_stats import parse_team_stats
from .parsers.players_main import parse_players_main
from .parsers.time_distribution import parse_time_distribution
from .parsers.challenges import parse_challenges
from .parsers.hit_matrix import parse_hit_matrix
from .parsers.pass_matrix import parse_pass_matrix
from .parsers.shots import parse_shots


TEMPLATES = {
    "instat_team_stats": parse_team_stats,
    "instat_players_main": parse_players_main,
    "instat_time_distribution": parse_time_distribution,
    "instat_challenges": parse_challenges,
    "instat_hit_matrix": parse_hit_matrix,
    "instat_pass_matrix": parse_pass_matrix,
    "instat_shots": parse_shots,
}
