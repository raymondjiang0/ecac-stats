"""Field-level validation for parsed InStat data.

Each validator returns a value (possibly None if invalid) and a list of
warning strings. Warnings are surfaced in the review UI but do not block
commit — the coach can accept them or fix them inline.
"""
from typing import Optional
from ..models import Player


def validate_jersey(
    jersey: str, roster: dict[str, Player]
) -> tuple[Optional[Player], list[str]]:
    """Look up a player by jersey number against the current roster.

    roster: {jersey_number_str: Player}
    Returns (Player or None, warnings).
    """
    player = roster.get(str(jersey).strip())
    if player is None:
        return None, [f"Jersey {jersey!r} not found in roster"]
    return player, []
