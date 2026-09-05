interface StatEntry {
  name: string
  question: string
  formula: string
  whyNotGoals: string
  caveat?: string
  notTracked?: string
  status?: 'planned'
  sourceNote?: string
  limitations?: string[]
}

const TEAM_STATS: StatEntry[] = [
  {
    name: 'Possession Share (CF%)',
    question: 'Who controlled the puck?',
    formula: 'CF% = CF For ÷ (CF For + CF Against)',
    whyNotGoals: 'Corsi counts every shot attempt — goals, on-goal, missed, iron, and blocked — so it uses far more data per game than on-goal shots alone. More data means less game-to-game randomness and more reliable signal about which team was actually in control.',
  },
  {
    name: 'Quality Shot Share (xGF%)',
    question: 'Who got the better chances?',
    formula: 'xGF% = xGF ÷ (xGF + xGA)',
    whyNotGoals: 'xG models the goal probability of each unblocked shot using location and shot type. Summing these probabilities gives a volume-adjusted picture of shot quality that\'s more stable game-to-game than counting actual goals, which are highly influenced by save quality and randomness.',
  },
  {
    name: 'Offense Created / Defense Exposed (xGF60 / xGA60)',
    question: 'How often were we generating or surrendering quality chances, normalized to a full game?',
    formula: 'xGF60 = (xGF ÷ TOI) × 60 · xGA60 = (xGA ÷ TOI) × 60',
    whyNotGoals: 'Rate stats remove the effect of TOI differences between games and let you compare pace of play fairly across a season. Using xG rather than goals makes the rate more stable.',
  },
  {
    name: 'Special Teams Splits (5v4 / 4v5)',
    question: 'How effective are we on the power play and penalty kill?',
    formula: '5v4 CF% = CF For (5v4) ÷ (CF For + CF Against at 5v4) · same pattern for xGF%',
    whyNotGoals: 'Special teams sample sizes are too small for goal-based measures to stabilize. Corsi and xG use more events and give a clearer read on PP/PK structure earlier in the season.',
  },
  {
    name: 'Attack Scenario Mix',
    question: 'How are we generating our chances — off rushes, forechecks, faceoffs, or sustained pressure?',
    formula: 'Share of shot attempts in each bucket: Rush / OZ FC / OZ FO / Sust. Pos.',
    whyNotGoals: 'Attack scenario tagging from 49ing tells you the structure behind the shots — not just that you got 20 shot attempts, but whether they came from speed (rush), work (forecheck), structure (sustained possession), or set plays (faceoff). This shapes practice emphasis. Note: every shot attempt is bucketed into exactly one scenario; rebounds are credited to the originating scenario.',
  },
  {
    name: 'Special Teams (Advanced)',
    question: 'How is our special teams unit actually functioning beyond just Corsi?',
    formula: 'PP Shots/min = PP shots ÷ PP minutes · PP OZ Ratio = PP time in OZ ÷ total PP time · PK Opp-Breakout Rate = opp breakouts allowed ÷ number of PKs',
    whyNotGoals: 'Existing CF%/xGF% only says whether we had the puck. These three stats add: efficiency (are we generating shots per minute of PP time?), setup quality (how much PP time is actually in the offensive zone vs. getting cleared?), and PK forecheck effectiveness (how often does the opposing PP break out of their zone against our forecheck?). Together they tell a story about whether the units are structurally working, not just whether they controlled the puck.',
    sourceNote: 'Requires InStat data (PP time-in-zone tracking is not exposed by 49ing).',
    limitations: [
      'All three require InStat weeks to compute — not available on 49ing-only games.',
      'PP OZ Ratio does not distinguish possession vs. controlled zone time — includes any time the puck is in the OZ.',
    ],
  },
  {
    name: 'Win Probability Trend',
    question: 'Who was really winning moment to moment, independent of the scoreboard?',
    formula: 'Cumulative xGF% at each period = cumulative xGF ÷ (cumulative xGF + cumulative xGA)',
    whyNotGoals: 'Score effects distort play: teams that go up 2–0 often concede possession intentionally. Win probability from xGF% tracks the underlying flow of the game rather than the artifact of whoever scored first.',
    notTracked: "Not currently captured. 49ing's xG chart plots each individual shot's goal probability as a point — it does not expose cumulative per-period xGF/xGA as a readable number. Eyeballing the chart endpoint is not accurate enough to enter reliably, and filtering by period still requires visual estimation. If 49ing adds a period-breakdown table in a future update, this stat can be added without any structural changes to the tool.",
  },
]

const PLAYER_STATS: StatEntry[] = [
  {
    name: "Player's Territorial Impact (On-Ice CF% / xGF%)",
    question: "Does this player help the team control play and generate quality chances?",
    formula: 'On-Ice CF% = CF For (on ice) ÷ (CF For + CF Against while on ice) · same for xGF%',
    whyNotGoals: 'A player can drive shots and suppress danger without scoring — raw goals don\'t capture this. On-ice Corsi/xGF% measures the team\'s collective performance while she\'s on the ice, which reflects her true territorial impact.',
  },
  {
    name: 'Offensive Drive / Defensive Hold (CF60 / CA60 / FF60 / FA60 / SF60 / SA60)',
    question: 'How fast does she drive shot volume for and against?',
    formula: 'CF60, FF60, SF60 = on-ice team shot attempts / unblocked / on-goal per 60 min TOI (reported directly by 49ing, already scaled) · CA60, FA60, SA60 = same for opponent output',
    whyNotGoals: 'Per-60 rates normalize for ice time, making it fair to compare a player with 8 min TOI per game to one with 20 min. 49ing reports these values pre-scaled to 60-min equivalents — we enter them directly. Unblocked (Fenwick) removes the blocker\'s role; on-goal (Shots) is the strictest threshold.',
  },
  {
    name: 'Shot Quality For & Against (xFSh% / xFSv%)',
    question: 'How dangerous are the team\'s shots with her on ice — and how well does she suppress danger?',
    formula: 'xFSh% = xGF60 ÷ FF60 (avg danger per unblocked shot for — 60s cancel, equals xGF ÷ FF) · xFSv% = 1 − (xGA60 ÷ FA60) (danger suppressed)',
    whyNotGoals: 'Volume of unblocked shots (FF, FA) tells you one thing; quality tells you another. A player can be on the ice for lots of low-danger shots — xFSh%/xFSv% reveal whether the shots she\'s involved in are high- or low-quality, independent of volume.',
  },
  {
    name: 'How She\'s Deployed (Shift Length / TOI)',
    question: 'What\'s her usage context — how long does she play per shift, and how much total ice time?',
    formula: 'Shift.Length = median shift length (not mean) · TOI = total 5v5 ice time (minutes)',
    whyNotGoals: 'Median shift length is used deliberately (not mean) because it\'s robust to outlier long shifts that would inflate the average. TOI contextualizes all rate stats — a player with 8 min 5v5 TOI and a player with 20 min are generating stats over very different samples.',
    notTracked: "Zone Start Ratio (ZSR = OZS ÷ (OZS + DZS)) is not tracked — 49ing does not expose zone start counts per player. ZSR would require offensive/defensive zone faceoff data split by player, which is not available through the Data Cockpit.",
  },
  {
    name: 'Faceoff Battle (FO% — Forwards)',
    question: 'How well does she win draws?',
    formula: 'Personal Draw Win% = Personal Draws Won ÷ Personal Draws Taken · On-Ice Team FO% = Team FO Wins (on ice) ÷ (Wins + Losses while on ice)',
    whyNotGoals: '49ing\'s "FO%" label is ambiguous between two distinct measures: (a) the player\'s own draw win rate, and (b) the team\'s overall faceoff win rate while that player is on ice (which includes teammates\' draws). These can differ substantially if teammates take most draws. Both are shown here — which one 49ing labels as "FO%" has not yet been confirmed with their team.',
  },
  {
    name: 'Impact Score',
    question: "One number: how much is this player helping the team win, controlling for her position?",
    formula: 'Impact_game = mean( z_position(on-ice xGF60 − xGA60), z_position(on-ice CF%), z_position(puck battle W%*), z_position(controlled entry %*) ) · Impact_season = TOI-weighted mean of per-game values, clamped to [−3, +3] · *InStat-only components dropped when absent',
    whyNotGoals: 'Standard plus/minus counts goals during 5v5 — a tiny event count in a 28-game season, heavily distorted by save quality and randomness. Impact Score uses shot-based signals (xG, Corsi, puck battle W%) that have 10–50× the event volume per game and stabilize far faster. Each component is z-normalized within the player\'s position group so forwards are compared to forwards, defenders to defenders. Hover on the score in the report to see the component breakdown.',
    sourceNote: 'Both sources supported. Component availability depends on source: puck battle W% and controlled entry % require InStat.',
    limitations: [
      'Not adjusted for teammate quality — no WOWY (with-or-without-you) data available from either platform.',
      'Not adjusted for opponent quality — no opponent-strength adjustment.',
      'Not adjusted for zone starts (unavailable in either source).',
      'Games with <5 min TOI are excluded from the calculation.',
      'First 8–10 games of a season: interpret with caution regardless of what the number says.',
      'Component set varies by data source. InStat weeks include battle W% and entry quality; 49ing-only weeks include just the xG and Corsi components.',
    ],
  },
  {
    name: 'Contested Puck Win % (Overall / DZ / OZ / NZ)',
    question: "How often does she come out with the puck when it's up for grabs?",
    formula: 'PB Win % = Σ pb_won ÷ Σ pb_total across all zones · Zone splits: PB DZ % / PB OZ % / PB NZ % follow same pattern within each zone',
    whyNotGoals: 'Puck battles are the closest measurable proxy for "grinder" performance — winning duels for loose pucks. Overall PB% is role-dependent (defenders spend more time in the DZ; their DZ% matters most). Showing zone splits lets the coach separate a slot-clearing D from a puck-hog forward.',
    sourceNote: 'InStat only — 49ing does not expose puck battles.',
    limitations: [
      'Does not measure difficulty of the battle — a puck battle in the slot is not equivalent to one at the blue line, but they count equally here.',
      'InStat\'s "puck battle" definition combines open-ice duels and board battles; no split available.',
      'N/A on 49ing weeks — will show as "not available for this window" in aggregate views.',
    ],
  },
  {
    name: 'Zone Entry Composition (Pass / Stick / Dump %)',
    question: 'How does this player get into the offensive zone — carrying, passing, or dumping?',
    formula: 'Entry Pass % = entries via pass ÷ total entries · Entry Stick % = entries via stickhandling ÷ total entries · Entry Dump % = entries via dump-in ÷ total entries',
    whyNotGoals: 'Historical (NHL) research shows carry-in entries produce ~2× the shots per entry that dump-ins do. Entry composition reveals role and skill — a high-Stick% forward is carrying the puck, a high-Pass% forward is setting up entries for teammates, a high-Dump% forward is playing conservatively or being overmatched.',
    sourceNote: 'InStat only.',
    limitations: [
      'Does not measure what happened after the entry — a failed carry and a successful dump are weighted equally.',
      'Sample sizes per player per game are small (2–10 entries); trends stabilize only over multiple games.',
    ],
  },
  {
    name: 'Turnover Location Ratio (DZ Loss Share / OZ Recovery Share)',
    question: "Where does she lose the puck — where it's cheap, or where it hurts?",
    formula: 'DZ Loss Share = puck losses in DZ ÷ total puck losses · OZ Recovery Share = puck recoveries in OZ ÷ total puck recoveries',
    whyNotGoals: 'Raw turnover count is misleading. OZ losses are largely acceptable — aggressive plays fail. DZ losses become chances against and shift momentum. A player with 6 total losses but 5 in the DZ is a bigger concern than one with 12 losses but 1 in the DZ. Same asymmetry for recoveries: OZ recoveries create chances; DZ recoveries just prevent them.',
    sourceNote: 'InStat only.',
    limitations: [
      'Does not weight losses by resulting danger — a DZ loss at the point is not the same as one below the goal line.',
      'Does not distinguish forced turnovers (opponent takeaway) from unforced errors.',
    ],
  },
  {
    name: 'Danger-Zone Shot Share',
    question: "Of the team's high-danger shots, how many is this player taking?",
    formula: 'Danger Share % = player\'s shots from scoring-chance area ÷ team\'s shots from scoring-chance area · Danger Shots/60 = player\'s SCA shots × 60 ÷ TOI',
    whyNotGoals: 'A player with 8 shots all from the point contributes less to expected goals than a player with 3 shots all from the slot. Danger Share identifies who\'s actually shooting from where goals get scored, independent of total shot volume. Complements Individual Shot Attempts (ICF) with a quality dimension.',
    sourceNote: 'InStat uses "shots from scoring chance area." 49ing fallback: slot-zone shot count.',
    limitations: [
      'Does not sub-differentiate within the scoring-chance zone — a shot from the crease and a shot from the top of the slot count equally.',
      'Team-relative denominator means the number shifts based on teammates\' shot selection, not just this player\'s.',
      'A player who missed games where the team recorded high-danger shots will have their share understated — the denominator includes all team games in the window, not just games this player appeared in.',
    ],
  },
  {
    name: 'Defensive Disruption Index (DDI/60)',
    question: "How active is she off-puck defensively — how often is she taking pucks away and getting in shooting lanes?",
    formula: 'DDI/60 = (takeaways + shots blocked + DZ puck battles won) × 60 ÷ TOI · Season aggregate: TOI-weighted mean of per-game DDI/60',
    whyNotGoals: 'No single tracked stat measures "stick work" or "off-puck disruption" directly. DDI is a composite proxy combining three related activities — takeaways (winning the puck without contact), blocks (getting in shooting lanes), and defensive-zone puck battles won (successful contested-puck plays in your own end). Explicitly a proxy, not a measurement.',
    status: 'planned',
    sourceNote: 'Blocks and takeaways from either source; DZ puck battles from InStat only (component drops to 0 on 49ing weeks, indicated in the UI).',
    limitations: [
      'A composite of three loosely related activities — a high DDI does not mean elite defender in the abstract.',
      'Does not measure positioning or gap control (both invisible in the underlying data).',
      'Rewards volume, which penalizes minimal-mistake defenders who quietly prevent situations from developing.',
      'On 49ing-only weeks, the DZ puck battles component drops to zero, so the score is systematically lower and not comparable across source splits.',
    ],
  },
  {
    name: 'Shot Threat by Scenario, All Players',
    question: 'Where and how is each player generating shots — off the rush, from the slot, on the power play?',
    formula: 'Filter chips: location (slot / center / flank / blue line), context (positional / counter-attack / "off the rush"), strength (5v5 / PP / SH) · Per filter combo: Shots/60 = filtered shots × 60 ÷ TOI at that strength · SH% = goals ÷ shots on goal',
    whyNotGoals: 'Aggregate shot totals hide structure. A forward with 30 shots in 10 games might have 25 of them from the point (low value) or 20 of them off the rush (high value); the totals look identical. Shot-threat filtering lets the coach see where and how a player generates offense.',
    status: 'planned',
    sourceNote: 'InStat only — 49ing does not expose per-player attack scenario or shot location.',
    limitations: [
      'SH% (shooting percentage) needs 200+ shots to stabilize; most players won\'t reach that in a 28-game season.',
      '"Off the rush" is proxied by InStat\'s "counter-attack" classification, which is close but not identical.',
      'N/A on 49ing weeks.',
    ],
  },
  {
    name: 'Goalie Stats (SV% / GA/60 / HD SV%)',
    question: 'How is she playing — and what should we not read too much into?',
    formula: 'SV% = 1 − (goals against ÷ shots on goal against) · GA/60 = goals against × 60 ÷ TOI · HD SV% = 1 − (goals from HD area ÷ HD shots faced)',
    whyNotGoals: 'Traditional goalie stats (wins, GAA) confound goalie play with team play. SV% is closer, but even SV% is very noisy over small samples — a single softie can move it by ~1%. HD SV% narrows the sample to high-danger shots only, which is more predictive of true goalie skill. Per-goalie splits require multiple goalies to have logged games; team-level splits pool across both goalies but lose individual attribution.',
    status: 'planned',
    sourceNote: 'SV% and GA/60 from either source. HD SV% requires InStat (scoring-chance shot classification).',
    limitations: [
      'SV% is noisy below ~300 shots-against — early-season swings of ±3% are normal.',
      'HD SV% depends on InStat\'s shot-area classification, which is not video-reviewed by 49ing/InStat.',
      'No opponent-strength adjustment — team\'s schedule quality drastically shifts shot quality faced.',
      'No rebound tracking — rebound saves and initial saves are indistinguishable.',
      'No goals-saved-above-expected (GSAx) — would require per-shot xG on the shots faced, which InStat exposes only in aggregate.',
      'Screen/deflection context missing.',
    ],
  },
  {
    name: 'True Individual Value (Rel. xGF%)',
    question: 'How much better or worse does the team perform with her on vs. off the ice?',
    formula: 'Rel. xGF% = On-Ice xGF% (while on) − Off-Ice xGF% (while off)',
    whyNotGoals: 'On-ice stats alone are confounded by linemate quality. Relative metrics subtract the team\'s baseline rate when the player is off the ice — if the team has a 55% xGF% with her on and 48% with her off, her Rel. xGF% is +7%, isolating her contribution from teammates.',
    notTracked: "Not currently captured. 49ing's Data Cockpit only exposes on-ice stats per player — it does not provide off-ice xGF/xGA (what the team does while a specific player is not on the ice). Computing Rel. xGF% requires play-by-play player tracking data that is not available through either 49ing or InStat.",
  },
]

const ANALYTICAL_LAYERS: StatEntry[] = [
  {
    name: 'Position-Aware Comparison',
    question: "Is she above or below average — for her role specifically, not just team-wide?",
    formula: 'Team Baseline = mean of stat across all players in the window (TOI-weighted for per-60 stats) · Position Baseline = same, filtered to player\'s position group (F / C / W / D / G)',
    whyNotGoals: 'A team-wide baseline flatters defenders on offensive stats and forwards on defensive stats, because the roles produce systematically different numbers. Position-aware comparison shows two deltas — vs. team, and vs. position — and a colored indicator (green if better than both, yellow if better than one, red if below both). Faceoff stats compare to centers only; general stats compare to the appropriate positional group.',
    sourceNote: 'Works on any stat, either source.',
    limitations: [
      'Small position cohorts (e.g., 6 defenders) produce noisier baselines than the full team cohort.',
      'Cohort sizes on early-season data may be too small for reliable comparison — same 8–10 game caveat applies.',
    ],
  },
  {
    name: 'TOI Trend Flag',
    question: "Is she getting more or less ice time lately? Was tonight's TOI unusual?",
    formula: 'Rolling trend: (toi_L3 − toi_L10) ÷ toi_L10 → ±10% triggers ⬆/⬇ trend badge · Single-game outlier: game_toi ÷ toi_L10 < 0.50 → "reduced role" badge · > 1.50 → "expanded role" badge',
    whyNotGoals: 'Ice-time shifts are the most direct signal of coach decisions — benching, injury, promotion up the lines. Two independent triggers: a rolling window (are the last 3 games trending different from her usual?) and a single-game outlier (was tonight abnormal?). Rolling trend catches slow drifts; single-game outlier catches sharp one-offs.',
    sourceNote: 'Uses TOI, which either source provides.',
    limitations: [
      'Requires at least 10 games of history before the trend flag can fire.',
      'Thresholds (10% / 50% / 150%) are defaults — expect to tune with real usage.',
      'Does not distinguish reasons — a "reduced role" flag could be injury, benching, matchup, or blowout garbage-time.',
    ],
  },
  {
    name: 'Auto-Flag Engine',
    question: 'What has meaningfully shifted for this player lately that I should look at?',
    formula: 'For each configured rule (stat, window, baseline, z_threshold): baseline_mean, baseline_std = TOI-weighted stats over last {baseline} games · window_mean = TOI-weighted mean over last {window} games · z = (window_mean − baseline_mean) ÷ baseline_std · flag if |z| > z_threshold',
    whyNotGoals: 'Numbers on a page are passive — the coach has to hunt for what changed. The auto-flag engine inverts that: it scans configured stats (xGF%, CF60, xFSh%, etc.) against each player\'s own recent baseline, and surfaces anything more than ~1 standard deviation off. Player report shows 0–3 badges at the top ("xG% shift", "Corsi shift") that jump to the relevant stat block on click.',
    sourceNote: 'Works on any stat with sufficient history, either source.',
    limitations: [
      'Requires ≥ {baseline} games of history — no flags in the first ~10 games of a season.',
      'Rules with different windows may produce conflicting flags (e.g., L3 trending up while L5 trending down). This is by design; different windows tell different stories.',
      'Thresholds (z = 1.0 default) are heuristics — expect to tune per stat.',
    ],
  },
]

function StatBlock({ stat, index }: { stat: StatEntry; index: number }) {
  const isPlanned = stat.status === 'planned'
  const isNotTracked = !!stat.notTracked && !isPlanned
  const borderColor = isPlanned
    ? 'var(--gold)'
    : isNotTracked
      ? 'var(--border)'
      : 'var(--crimson)'
  const numberColor = isPlanned
    ? 'var(--gold)'
    : isNotTracked
      ? 'var(--text-secondary)'
      : 'var(--crimson)'
  const whyLabel = isPlanned ? 'Why this metric' : 'Why not raw goals/shots?'

  return (
    <div style={{
      borderLeft: `3px solid ${borderColor}`,
      paddingLeft: 20,
      marginBottom: 28,
      opacity: isNotTracked ? 0.7 : 1,
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: numberColor, minWidth: 18 }}>
          {String(index).padStart(2, '0')}
        </span>
        <h3 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 18, fontWeight: 700, color: 'var(--text)', lineHeight: 1.2 }}>
          {stat.name}
        </h3>
        {isPlanned && (
          <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--gold)', background: 'rgba(200, 168, 75, 0.1)', border: '1px solid rgba(200, 168, 75, 0.4)', borderRadius: 4, padding: '2px 7px' }}>
            🚧 Coming Soon
          </span>
        )}
        {isNotTracked && (
          <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 7px' }}>
            Not Tracked
          </span>
        )}
      </div>

      <div style={{ marginLeft: 30 }}>
        <div style={{ fontSize: 13, fontStyle: 'italic', color: 'var(--text-secondary)', marginBottom: 10 }}>
          "{stat.question}"
        </div>

        <div style={{ background: 'var(--card)', borderRadius: 6, padding: '8px 12px', marginBottom: 12, fontFamily: 'monospace', fontSize: 11.5, color: 'var(--ice)', border: '1px solid var(--border)' }}>
          {stat.formula}
        </div>

        <p style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.65, marginBottom: 10 }}>
          <span style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{whyLabel} </span>
          {stat.whyNotGoals}
        </p>

        {stat.sourceNote && (
          <div style={{ background: 'rgba(120, 160, 200, 0.08)', border: '1px solid rgba(120, 160, 200, 0.25)', borderRadius: 6, padding: '8px 12px', marginBottom: 10, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            <strong style={{ color: 'var(--ice)' }}>Data source:</strong> {stat.sourceNote}
          </div>
        )}

        {stat.limitations && stat.limitations.length > 0 && (
          <div style={{ background: 'rgba(200, 168, 75, 0.06)', border: '1px solid rgba(200, 168, 75, 0.25)', borderRadius: 6, padding: '10px 14px', marginBottom: 10 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 6 }}>
              Limitations
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {stat.limitations.map((lim, i) => (
                <li key={i} style={{ marginBottom: 3 }}>{lim}</li>
              ))}
            </ul>
          </div>
        )}

        {stat.notTracked && (
          <div style={{ background: 'rgba(150,150,150,0.07)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 14px', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            <strong>Why not tracked:</strong> {stat.notTracked}
          </div>
        )}

        {stat.caveat && (
          <div style={{ background: 'rgba(200, 168, 75, 0.08)', border: '1px solid rgba(200, 168, 75, 0.3)', borderRadius: 6, padding: '10px 14px', fontSize: 12, color: 'var(--gold)', lineHeight: 1.5 }}>
            ⚠ {stat.caveat}
          </div>
        )}
      </div>
    </div>
  )
}

function countStatuses(stats: StatEntry[]) {
  let tracked = 0
  let planned = 0
  let notTracked = 0
  for (const s of stats) {
    if (s.status === 'planned') planned++
    else if (s.notTracked) notTracked++
    else tracked++
  }
  return { tracked, planned, notTracked }
}

function formatCounts({ tracked, planned, notTracked }: { tracked: number; planned: number; notTracked: number }) {
  const parts: string[] = []
  if (tracked > 0) parts.push(`${tracked} tracked`)
  if (planned > 0) parts.push(`${planned} planned`)
  if (notTracked > 0) parts.push(`${notTracked} not tracked`)
  return parts.join(' · ')
}

export default function MethodologyPage() {
  const teamCounts = countStatuses(TEAM_STATS)
  const playerCounts = countStatuses(PLAYER_STATS)
  const layerCounts = countStatuses(ANALYTICAL_LAYERS)
  const totalItems = TEAM_STATS.length + PLAYER_STATS.length + ANALYTICAL_LAYERS.length
  const totalTracked = teamCounts.tracked + playerCounts.tracked + layerCounts.tracked
  const totalPlanned = teamCounts.planned + playerCounts.planned + layerCounts.planned

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Methodology</div>
          <div className="page-subtitle">
            {totalItems} stats and layers — {totalTracked} shipped, {totalPlanned} planned. Formulas, reasoning, and honest limitations.
          </div>
        </div>
      </div>

      {/* Global caveats */}
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '20px 24px', marginBottom: 32 }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--crimson)', marginBottom: 14 }}>
          Global Caveats — Read Before Interpreting Any Stat
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            "Most research validating Corsi, Fenwick, and xG model behavior comes from men's professional hockey (primarily the NHL). These methods have not been specifically validated for women's college hockey. They are the best available analytical tools, not proven-optimal ones for this context.",
            "ECAC's ~28-game regular season is shorter than the professional-hockey samples on which these stats were developed. Stats require a certain volume of events to stabilize (reduce randomness enough to reflect true performance). Early-season numbers — especially through the first 8–10 games — deserve substantially more caution than late-season totals.",
            "All stats default to 5v5 strength state unless explicitly labeled otherwise. Power play and penalty kill stats are tracked separately.",
            "The tool ingests data from two platforms (49ing and InStat). Some stats are only available on games entered from one source or the other — this is called out per-stat and shown in the player report as availability badges.",
            "For FO%: 49ing's definition is ambiguous between personal draw win rate and on-ice team faceoff rate. Both are captured and displayed separately until confirmed with 49ing's team.",
            "Stats marked 🚧 Coming Soon are documented here but not yet computing values in the tool. Formulas are the design intent — refinements may occur during implementation.",
          ].map((text, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, fontSize: 13, color: 'var(--text)', lineHeight: 1.6 }}>
              <span style={{ color: 'var(--crimson)', fontWeight: 700, flexShrink: 0 }}>—</span>
              <span>{text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Team stats */}
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 20, paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>
        Team Stats ({formatCounts(teamCounts)})
      </div>
      {TEAM_STATS.map((s, i) => <StatBlock key={s.name} stat={s} index={i + 1} />)}

      {/* Player stats */}
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 20, marginTop: 8, paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>
        Individual Stats ({formatCounts(playerCounts)})
      </div>
      {PLAYER_STATS.map((s, i) => <StatBlock key={s.name} stat={s} index={i + 1 + TEAM_STATS.length} />)}

      {/* Analytical layers */}
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 20, marginTop: 8, paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>
        Analytical Layers ({formatCounts(layerCounts)})
      </div>
      {ANALYTICAL_LAYERS.map((s, i) => <StatBlock key={s.name} stat={s} index={i + 1 + TEAM_STATS.length + PLAYER_STATS.length} />)}

      {/* Data source note */}
      <div style={{ marginTop: 20, padding: '14px 18px', background: 'var(--surface)', borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        Raw inputs come from two platforms: <strong>49ing's Data Cockpit</strong> (per-60 rates, xG by attack scenario) and <strong>InStat</strong> (raw per-game counts, puck battles by zone, hit and pass matrices, per-player zone entries). Each game is entered from whichever source the analyst pulls that week; some stats are only available on games entered from a specific source, which is noted per-stat. Stat definitions follow the source's own glossary where it differs from generic hockey-analytics conventions.
      </div>
    </>
  )
}
