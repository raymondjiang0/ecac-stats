from typing import Optional
from statistics import mean, pstdev
from .models import Player


def position_group(player: Player) -> str:
    """Return the primary position group for a player.

    F is used as an umbrella (see cohort_matches); position_group returns
    the most specific label: C (center forward), W (winger), D, G.
    """
    if player.position == "D":
        return "D"
    if player.position == "G":
        return "G"
    if player.position == "F":
        return "C" if player.is_center else "W"
    raise ValueError(f"Unknown position: {player.position!r}")


def cohort_matches(player: Player, cohort: str) -> bool:
    """True if player belongs in the requested cohort.

    F matches all forwards (both C and W). C, W, D, G match exactly.
    """
    pg = position_group(player)
    if cohort == "F":
        return pg in ("C", "W")
    return pg == cohort


def cohort_baseline(
    values: list[float],
    weights: Optional[list[float]] = None,
) -> dict:
    """Compute mean and population stddev; TOI-weighted if weights given.

    Returns {"mean": float | None, "std": float | None, "n": int}.
    None returned when n < 2 or total weight is zero.
    """
    filtered = [
        (v, (weights[i] if weights else 1.0))
        for i, v in enumerate(values)
        if v is not None
    ]
    n = len(filtered)
    if n < 2:
        return {"mean": None, "std": None, "n": n}
    total_w = sum(w for _, w in filtered)
    if total_w <= 0:
        return {"mean": None, "std": None, "n": n}
    m = sum(v * w for v, w in filtered) / total_w
    var = sum(w * (v - m) ** 2 for v, w in filtered) / total_w
    return {"mean": m, "std": var ** 0.5, "n": n}
