# /utils_stats.py
from collections import Counter
from typing import List, Tuple, Optional, Dict
import pandas as pd
import math

from sqlmodel import select

from models import Roll, GamePlayer, FinalScore, Player

def rolls_distribution_df(session, game_id: str) -> pd.DataFrame:
    totals = [r.total for r in session.exec(select(Roll).where(Roll.game_id == game_id)).all()]
    c = Counter(totals)
    data = {"total": list(range(2, 13)), "count": [c.get(t, 0) for t in range(2, 13)]}
    return pd.DataFrame(data)

def per_player_distribution_df(session, game_id: str) -> pd.DataFrame:
    gps: List[GamePlayer] = session.exec(select(GamePlayer).where(GamePlayer.game_id == game_id)).all()
    name_by_player = {gp.player_id: gp.display_name_snapshot for gp in gps}

    rows: List[Tuple[str, int, int]] = []
    for pid, pname in name_by_player.items():
        totals = [r.total for r in session.exec(select(Roll).where((Roll.game_id == game_id) & (Roll.player_id == pid))).all()]
        c = Counter(totals)
        for t in range(2, 13):
            rows.append((pname, t, c.get(t, 0)))
    return pd.DataFrame(rows, columns=["player", "total", "count"])

def per_player_distribution_single_df(session, game_id: str, player_id: str) -> pd.DataFrame:
    """Distribution for a single player in a single game: columns total, count."""
    totals = [r.total for r in session.exec(
        select(Roll).where((Roll.game_id == game_id) & (Roll.player_id == player_id))
    ).all()]
    c = Counter(totals)
    return pd.DataFrame({"total": list(range(2, 13)), "count": [c.get(t, 0) for t in range(2, 13)]})

def lifetime_rolls_distribution_df(session) -> pd.DataFrame:
    totals = [r.total for r in session.exec(select(Roll)).all()]
    c = Counter(totals)
    data = {"total": list(range(2, 13)), "count": [c.get(t, 0) for t in range(2, 13)]}
    return pd.DataFrame(data)

def lifetime_per_player_distribution_df(session, player_id: Optional[str] = None) -> pd.DataFrame:
    """
    All rolls per player across all games; when player_id is provided, return single player's distribution.
    Returns columns: player (name), total, count.
    """
    players = session.exec(select(Player)).all()
    id_to_name = {p.id: p.current_name for p in players}

    if player_id is None or player_id not in id_to_name:
        return pd.DataFrame(columns=["player", "total", "count"])

    totals = [r.total for r in session.exec(select(Roll).where(Roll.player_id == player_id)).all()]
    c = Counter(totals)
    rows = [(id_to_name[player_id], t, c.get(t, 0)) for t in range(2, 13)]

    df = pd.DataFrame(rows, columns=["player", "total", "count"])
    # Clean out zeros to keep charts tidy
    df = df[df["count"] > 0]
    return df

def lifetime_scores_summary_df(session) -> pd.DataFrame:
    scores = session.exec(select(FinalScore)).all()
    if not scores:
        return pd.DataFrame(columns=["player", "games", "wins", "win_rate", "avg_score", "best_score"])

    rows = [{"game_id": s.game_id, "player_id": s.player_id, "score": s.score} for s in scores]
    df = pd.DataFrame(rows)

    max_by_game = df.groupby("game_id")["score"].transform("max")
    df["is_win"] = df["score"] == max_by_game

    agg = df.groupby("player_id").agg(
        games=("game_id", "nunique"),
        wins=("is_win", "sum"),
        avg_score=("score", "mean"),
        best_score=("score", "max"),
    ).reset_index()

    agg["win_rate"] = (agg["wins"] / agg["games"]).round(3)

    players = session.exec(select(Player)).all()
    id_to_name = {p.id: p.current_name for p in players}
    agg["player"] = agg["player_id"].map(id_to_name)

    agg = agg[["player", "games", "wins", "win_rate", "avg_score", "best_score"]].sort_values(
        by=["wins", "avg_score"], ascending=[False, False]
    )
    agg["avg_score"] = agg["avg_score"].round(2)
    return agg

# --- Theoretical 2d6 distribution helper ---
def expected_2d6_df(total_count: int) -> pd.DataFrame:
    """Return a DataFrame with columns: total, expected_prob (0..1), expected_count."""
    weights = {2:1, 3:2, 4:3, 5:4, 6:5, 7:6, 8:5, 9:4, 10:3, 11:2, 12:1}
    rows = []
    for t in range(2, 13):
        p = weights[t] / 36.0
        rows.append({"total": t, "expected_prob": p, "expected_count": p * max(total_count, 0)})
    return pd.DataFrame(rows)

# ---------- Chi-square goodness-of-fit (2d6) ----------
def _chi2_sf(x: float, df: int) -> float:
    """Right-tail p-value for chi-square. Try SciPy; fallback to Wilson–Hilferty normal approx."""
    try:
        from scipy.stats import chi2 as _chi2
        return float(_chi2.sf(x, df))
    except Exception:
        # Wilson–Hilferty transform: ((X/df)^(1/3) - (1 - 2/(9df)))/sqrt(2/(9df)) ~ N(0,1)
        if df <= 0:
            return float("nan")
        z = ((x / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
        # right-tail
        return 0.5 * math.erfc(z / math.sqrt(2))

def chisq_gof_2d6_from_df(df_counts: pd.DataFrame) -> Tuple[float, int, float, int]:
    """
    Input: DataFrame with columns ['total','count'] (any missing totals are treated as zero).
    Returns: (chi2, dof, p_value, n)
    """
    # ensure all totals present
    by_total = {int(t): int(c) for t, c in zip(df_counts.get("total", []), df_counts.get("count", []))}
    counts = [by_total.get(t, 0) for t in range(2, 13)]
    n = int(sum(counts))
    if n <= 0:
        return 0.0, 10, 1.0, 0
    probs = [1/36, 2/36, 3/36, 4/36, 5/36, 6/36, 5/36, 4/36, 3/36, 2/36, 1/36]
    expected = [n * p for p in probs]
    # avoid division by zero
    chi2 = sum((o - e) ** 2 / e for o, e in zip(counts, expected) if e > 0)
    dof = 11 - 1  # 11 bins (2..12)
    p = _chi2_sf(chi2, dof)
    return float(chi2), dof, float(p), n


# ---------- Players vs Totals chi-square (independence / homogeneity) ----------
def players_totals_contingency(session) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Returns: (contingency_df, id->name mapping)
      - contingency_df: rows=player_id, cols=2..12, values=counts
    """
    # All rolls with player IDs
    rolls = session.exec(select(Roll.player_id, Roll.total)).all()
    if not rolls:
        return pd.DataFrame(columns=[t for t in range(2, 13)]), {}
    df = pd.DataFrame(rolls, columns=["player_id", "total"])
    # pivot to counts
    table = (
        df.assign(count=1)
          .pivot_table(index="player_id", columns="total", values="count", aggfunc="sum", fill_value=0)
          .reindex(columns=list(range(2, 13)), fill_value=0)
    )
    players = session.exec(select(Player.id, Player.current_name)).all()
    id_to_name = {pid: name for pid, name in players}
    return table, id_to_name

def chisq_independence_players(table: pd.DataFrame) -> Tuple[float, int, float, int, int]:
    """
    Chi-square test of independence on a players x totals table.
    Returns: (chi2, dof, p_value, n, num_players)
    """
    if table.empty or table.values.sum() == 0:
        return 0.0, 0, 1.0, 0, 0
    obs = table.astype(float)
    row_sums = obs.sum(axis=1)
    col_sums = obs.sum(axis=0)
    n = float(row_sums.sum())
    expected = pd.DataFrame(index=obs.index, columns=obs.columns, dtype=float)
    for i in obs.index:
        for j in obs.columns:
            expected.loc[i, j] = row_sums.loc[i] * col_sums.loc[j] / n if n > 0 else 0.0
    with pd.option_context("mode.use_inf_as_na", True):
        chi2 = ((obs - expected) ** 2 / expected.replace(0, pd.NA)).sum().sum()
    r, c = obs.shape
    dof = (r - 1) * (c - 1)
    p = _chi2_sf(float(chi2), dof) if dof > 0 else 1.0
    return float(chi2), int(dof), float(p), int(n), int(r)

def cramers_v(chi2: float, n: int, r: int, c: int) -> float:
    if n <= 0:
        return 0.0
    denom = n * (min(r - 1, c - 1))
    return math.sqrt(chi2 / denom) if denom > 0 else 0.0

def _log_binom_pmf(k: int, n: int, p: float) -> float:
    """Stable log PMF for Binomial(n,p) at k."""
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    # log nCk + k*log p + (n-k)*log(1-p)
    return (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log(1.0 - p)
    )

def binom_two_sided_pvalue(k: int, n: int, p: float) -> float:
    """
    Exact two-sided binomial p-value in the 'binomtest' sense:
    sum of probabilities of all outcomes with PMF <= PMF(k).
    Works well for small n where normal approx is bad.
    """
    if n <= 0:
        return float("nan")
    log_pk = _log_binom_pmf(k, n, p)
    # sum probabilities of all outcomes with pmf <= pmf(k)
    total = 0.0
    for x in range(0, n + 1):
        lx = _log_binom_pmf(x, n, p)
        if lx <= log_pk + 1e-12:  # numeric wiggle room
            total += math.exp(lx)
    return min(1.0, total)