import os
from app.ingest.orchestrator import parse_all, TEMPLATES

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


class TestTemplates:
    def test_has_all_seven_templates(self):
        expected = {
            "instat_team_stats", "instat_players_main", "instat_time_distribution",
            "instat_challenges", "instat_hit_matrix", "instat_pass_matrix",
            "instat_shots",
        }
        assert set(TEMPLATES.keys()) == expected


class TestParseAll:
    def test_returns_dict_with_all_templates(self):
        result = parse_all(FIXTURE, "HARVARD CRIMSON")
        assert "templates" in result
        assert set(result["templates"].keys()) == {
            "instat_team_stats", "instat_players_main", "instat_time_distribution",
            "instat_challenges", "instat_hit_matrix", "instat_pass_matrix",
            "instat_shots",
        }

    def test_returns_warnings_list(self):
        result = parse_all(FIXTURE, "HARVARD CRIMSON")
        assert "warnings" in result
        assert isinstance(result["warnings"], list)

    def test_team_stats_is_dict(self):
        result = parse_all(FIXTURE, "HARVARD CRIMSON")
        assert isinstance(result["templates"]["instat_team_stats"], dict)

    def test_players_main_is_list(self):
        result = parse_all(FIXTURE, "HARVARD CRIMSON")
        assert isinstance(result["templates"]["instat_players_main"], list)

    def test_unknown_team_returns_warning(self):
        result = parse_all(FIXTURE, "NONEXISTENT TEAM")
        # All parsers return empty; warnings note the team wasn't found
        assert len(result["warnings"]) >= 1
        assert "team" in result["warnings"][0].lower() or "NONEXISTENT" in " ".join(result["warnings"])
