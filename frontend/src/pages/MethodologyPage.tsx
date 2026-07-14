interface StatEntry {
  name: string
  question: string
  formula: string
  whyNotGoals: string
  caveat?: string
  notTracked?: string
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
    name: 'True Individual Value (Rel. xGF%)',
    question: 'How much better or worse does the team perform with her on vs. off the ice?',
    formula: 'Rel. xGF% = On-Ice xGF% (while on) − Off-Ice xGF% (while off)',
    whyNotGoals: 'On-ice stats alone are confounded by linemate quality. Relative metrics subtract the team\'s baseline rate when the player is off the ice — if the team has a 55% xGF% with her on and 48% with her off, her Rel. xGF% is +7%, isolating her contribution from teammates.',
    notTracked: "Not currently captured. 49ing's Data Cockpit only exposes on-ice stats per player — it does not provide off-ice xGF/xGA (what the team does while a specific player is not on the ice). Computing Rel. xGF% requires play-by-play player tracking data that is not available through the platform.",
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
]

function StatBlock({ stat, index }: { stat: StatEntry; index: number }) {
  return (
    <div style={{
      borderLeft: `3px solid ${stat.notTracked ? 'var(--border)' : 'var(--crimson)'}`,
      paddingLeft: 20,
      marginBottom: 28,
      opacity: stat.notTracked ? 0.7 : 1,
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: stat.notTracked ? 'var(--text-secondary)' : 'var(--crimson)', minWidth: 18 }}>
          {String(index).padStart(2, '0')}
        </span>
        <h3 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 18, fontWeight: 700, color: 'var(--text)', lineHeight: 1.2 }}>
          {stat.name}
        </h3>
        {stat.notTracked && (
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
          <span style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Why not raw goals/shots? </span>
          {stat.whyNotGoals}
        </p>

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

export default function MethodologyPage() {
  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Methodology</div>
          <div className="page-subtitle">Why these 12 stats, what they mean, and where they fall short</div>
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
            "For FO%: 49ing's definition is ambiguous between personal draw win rate and on-ice team faceoff rate. Both are captured and displayed separately until confirmed with 49ing's team.",
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
        Team Stats (5 tracked · 1 not tracked)
      </div>
      {TEAM_STATS.map((s, i) => <StatBlock key={s.name} stat={s} index={i + 1} />)}

      {/* Individual stats */}
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 20, marginTop: 8, paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>
        Individual Stats (4 tracked · 2 not tracked)
      </div>
      {PLAYER_STATS.map((s, i) => <StatBlock key={s.name} stat={s} index={i + 7} />)}

      {/* Data source note */}
      <div style={{ marginTop: 20, padding: '14px 18px', background: 'var(--surface)', borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        All raw inputs are derived from 49ing's Data Cockpit platform, which auto-tags video and generates advanced hockey stats.
        Stat definitions and formulas used here follow 49ing's own glossary (support.49ing.ch/glossary) — not generic hockey-analytics conventions,
        as some definitions differ. Where ambiguity exists (notably FO%), both interpretations are captured.
      </div>
    </>
  )
}
