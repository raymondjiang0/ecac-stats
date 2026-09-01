import os
from app.config import OUR_TEAM_NAME


def test_our_team_name_is_string():
    assert isinstance(OUR_TEAM_NAME, str)
    assert OUR_TEAM_NAME  # non-empty


def test_fixture_pdf_exists():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")
    assert os.path.exists(path)
    assert os.path.getsize(path) > 100_000  # sanity: real PDF, not empty
