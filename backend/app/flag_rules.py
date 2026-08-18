"""Default auto-flag rule set. See spec §5.3 and §9.7."""
from .flags import Rule


DEFAULT_FLAG_RULES: list[Rule] = [
    Rule(stat_key="cf60",           window=3, baseline=10, z_threshold=1.0, label="Corsi shift"),
    Rule(stat_key="on_ice_xgf_pct", window=3, baseline=10, z_threshold=1.0, label="xG% shift"),
    Rule(stat_key="xfsh_pct",       window=5, baseline=15, z_threshold=1.2, label="shot quality shift"),
]
