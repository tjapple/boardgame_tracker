# /games/catan_app.py
import streamlit as st
import pandas as pd
import altair as alt
import math

from sqlmodel import select
from db import get_session
from models import Player, PlayerAlias, DiceSet, Game, GamePlayer, Roll, FinalScore
from utils_stats import (
    rolls_distribution_df,
    per_player_distribution_df,
    per_player_distribution_single_df,
    lifetime_rolls_distribution_df,
    lifetime_per_player_distribution_df,
    lifetime_scores_summary_df,
    expected_2d6_df,
    chisq_gof_2d6_from_df,
    players_totals_contingency,
    chisq_independence_players,
    cramers_v,
    binom_two_sided_pvalue,
)

# ---- Session keys (namespaced) ----
if "catan_active_game_id" not in st.session_state:
    st.session_state.catan_active_game_id = None
if "catan_turn_idx" not in st.session_state:
    st.session_state.catan_turn_idx = 0
if "catan_roll_counter" not in st.session_state:
    st.session_state.catan_roll_counter = 0
if "catan_nav" not in st.session_state:
    st.session_state.catan_nav = "Players"  # default landing page

def _success(msg: str):
    st.toast(msg)

def _load_game_players(session, game_id: str):
    return session.exec(
        select(GamePlayer).where(GamePlayer.game_id == game_id).order_by(GamePlayer.turn_order)
    ).all()

def _inject_big_button_css():
    st.markdown(
        """
        <style>
        .dice-grid [data-testid="stButton"] > button {
            width: 100% !important;
            min-width: 400px !important;
            height: 320px !important;           
            font-size: 100px !important;         
            font-weight: 900 !important;
            border-radius: 20px !important;
            background: linear-gradient(180deg,#34d399 0%,#059669 100%) !important;
            color: #ffffff !important;
            border: none !important;
            box-shadow: 0 10px 28px rgba(0,0,0,0.40);
        }
        .dice-grid [data-testid="stButton"] > button:hover {
            filter: brightness(1.10); transform: translateY(-2px);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def _pretty_bar(chart):
    return (
        chart.properties(height=260)
        .configure(background="transparent")
        .configure_axis(labelColor="#e6f4ea", titleColor="#e6f4ea", labelFontSize=12, titleFontSize=14)
        .configure_legend(labelColor="#e6f4ea", titleColor="#e6f4ea")
        .configure_header(title=None, labelFontSize=12, labelColor="#e6f4ea")
        .configure_view(strokeWidth=0)
        .configure_bar(size=30)
    )

def _bar_vs_expected(df, title_x="Roll Total"):
    total_count = int(df["count"].sum()) if not df.empty else 0
    exp = expected_2d6_df(total_count)
    merged = pd.merge(exp, df, on="total", how="left").fillna({"count": 0})
    denom = merged["count"].sum()
    merged["pct"] = (merged["count"] / denom) if denom > 0 else 0.0
    merged["delta"] = merged["pct"] - merged["expected_prob"]
    merged["mu"] = merged["expected_prob"] * total_count
    merged["sigma"] = (merged["expected_prob"] * (1 - merged["expected_prob"]) * total_count) ** 0.5
    merged["z"] = 0.0
    nz = merged["sigma"] > 0
    merged.loc[nz, "z"] = (merged.loc[nz, "count"] - merged.loc[nz, "mu"]) / merged.loc[nz, "sigma"]
    merged["p_value"] = merged["z"].abs().apply(lambda z: math.erfc(abs(z) / math.sqrt(2)))

    bars = (
        alt.Chart(merged)
        .mark_bar()
        .encode(
            x=alt.X("total:O", title=title_x),
            y=alt.Y("count:Q", title="Count"),
            tooltip=[
                alt.Tooltip("total:O", title="Total"),
                alt.Tooltip("count:Q", title="Count"),
                alt.Tooltip("expected_count:Q", title="Expected", format=".1f"),  # <-- add this line here
                alt.Tooltip("pct:Q", title="Actual %", format=".1%"),
                alt.Tooltip("expected_prob:Q", title="Expected %", format=".1%"),
                alt.Tooltip("delta:Q", title="Δ (A−E)", format="+.1%"),
                alt.Tooltip("z:Q", title="z", format=".2f"),
                alt.Tooltip("p_value:Q", title="p-value", format=".3f"),
            ],
        )
    )

    line = (
        alt.Chart(merged)
        .mark_line(point=True, interpolate="monotone", strokeDash=[4, 2], size=2)
        .encode(
            x=alt.X("total:O", title=title_x),
            y=alt.Y("expected_count:Q", title="Count"),
            tooltip=[
                alt.Tooltip("total:O", title="Total"),
                alt.Tooltip("expected_prob:Q", title="Expected %", format=".1%"),
                alt.Tooltip("expected_count:Q", title="Expected count", format=".1f"),
            ],
        )
    )
    return _pretty_bar(bars + line)

def _show_gof_line(df_counts: pd.DataFrame, label: str):
    chi2, dof, p, n = chisq_gof_2d6_from_df(df_counts)
    note = _low_power_note(n)
    qual = _qualify_p(p)
    st.caption(f"χ² GOF — {label}: χ²={chi2:.2f}, df={dof}, p={p:.3f}{qual}, n={n}{note}")


def _qualify_p(p: float) -> str:
    if not isinstance(p, float) or math.isnan(p):
        return ""
    if p < 0.001: return " (highly unlikely)"
    if p < 0.01:  return " (unlikely)"
    if p < 0.05:  return " (slightly unlikely)"
    if p <= 0.95: return " (neutral)"
    if p <= 0.99: return " (slightly likely)"
    if p <= 0.999:return " (likely)"
    return " (highly likely)"

def _low_power_note(n: int) -> str:
    # For 2d6, min expected = n/36; rule-of-thumb needs >=5
    return " — low sample; χ² may be unreliable" if n < 180 else ""


def render():
    st.title("Catan Tracker")
    st.sidebar.subheader("Catan Navigation")
    st.sidebar.radio("Go to", ["Players", "New Game", "Active Game", "Historical Data"], key="catan_nav")
    page = st.session_state.catan_nav

    if page == "Players":
        st.header("Players")
        with get_session() as session:
            st.subheader("Add Player")
            with st.form("add_player_form", clear_on_submit=True):
                name = st.text_input("Player name", placeholder="e.g., Alice")
                submitted = st.form_submit_button("Add to Library")
                if submitted and name.strip():
                    p = Player(current_name=name.strip())
                    session.add(p)
                    session.add(PlayerAlias(player_id=p.id, name=name.strip()))
                    session.commit()
                    _success(f"Added player: {name}")

            st.subheader("Player Library")
            players = session.exec(select(Player).order_by(Player.created_at.desc())).all()
            for p in players:
                with st.expander(f"{p.current_name}"):
                    new_name = st.text_input(f"Rename {p.current_name}", value=p.current_name, key=f"rename_{p.id}")
                    if st.button("Save name", key=f"save_{p.id}"):
                        new_name_clean = new_name.strip()
                        if new_name_clean and new_name_clean != p.current_name:
                            p.current_name = new_name_clean
                            session.add(PlayerAlias(player_id=p.id, name=new_name_clean))
                            session.add(p)
                            session.commit()
                            _success("Name updated (stats preserved via stable player id)")

                    aliases = session.exec(select(PlayerAlias).where(PlayerAlias.player_id == p.id)).all()
                    st.caption("Name history:")
                    st.write(", ".join(a.name for a in aliases))

    elif page == "New Game":
        st.header("Start a New Catan Game")
        with get_session() as session:
            st.subheader("Dice Set")
            dice_sets = session.exec(select(DiceSet).order_by(DiceSet.created_at.desc())).all()
            id_to_label = {ds.id: ds.label for ds in dice_sets}
            choice_id = st.selectbox(
                "Choose existing dice set",
                options=[None] + list(id_to_label.keys()),
                format_func=lambda k: "<Create new>" if k is None else id_to_label[k],
            )
            new_label = st.text_input("Or create new dice set label", placeholder="e.g., Red/White set")
            dice_set_id = None
            if choice_id is not None:
                dice_set_id = choice_id
            elif new_label.strip():
                ds = DiceSet(label=new_label.strip())
                session.add(ds)
                session.commit()
                dice_set_id = ds.id
                _success(f"Created dice set: {ds.label}")

            st.subheader("Players & Turn Order")
            all_players = session.exec(select(Player).order_by(Player.current_name.asc())).all()
            name_by_id = {p.id: p.current_name for p in all_players}
            selected_ids = st.multiselect(
                "Add players (from library)",
                options=[p.id for p in all_players],
                format_func=lambda pid: name_by_id[pid],
            )
            orders = {}
            if selected_ids:
                st.write("Assign turn order (1 = first)")
                cols = st.columns(min(4, len(selected_ids)))
                for i, pid in enumerate(selected_ids):
                    with cols[i % len(cols)]:
                        orders[pid] = st.number_input(
                            f"{name_by_id[pid]}", min_value=1, max_value=len(selected_ids), value=i + 1, step=1
                        )
                if len(set(orders.values())) != len(selected_ids):
                    st.warning("Turn orders must be unique.")
            notes = st.text_area("Notes (optional)")
            if st.button("Start Game", type="primary", disabled=not (dice_set_id and selected_ids)):
                g = Game(dice_set_id=dice_set_id, notes=notes)
                session.add(g)
                session.commit()
                ordered = sorted([(pid, int(orders[pid])) for pid in selected_ids], key=lambda x: x[1])
                for pid, order in ordered:
                    gp = GamePlayer(
                        game_id=g.id,
                        player_id=pid,
                        turn_order=order,
                        display_name_snapshot=name_by_id[pid],
                    )
                    session.add(gp)
                session.commit()
                st.session_state.catan_active_game_id = g.id
                st.session_state.catan_turn_idx = 0
                st.session_state.catan_roll_counter = 0
                _success("Game started. Switch to 'Active Game'.")

    elif page == "Active Game":
        st.header("Active Game")
        _inject_big_button_css()
        game_id = st.session_state.catan_active_game_id
        if not game_id:
            st.info("No active game. Start one from 'New Game'.")
        else:
            with get_session() as session:
                gps = _load_game_players(session, game_id)
                if not gps:
                    st.error("No players found for this game.")
                else:
                    order_names = [f"{gp.turn_order}. {gp.display_name_snapshot}" for gp in gps]
                    st.write("**Turn order:** " + "  ·  ".join(order_names))
                    current_gp = gps[st.session_state.catan_turn_idx % len(gps)]
                    st.subheader(f"Current player: {current_gp.display_name_snapshot}")

                    st.write("Click the roll result:")
                    with st.container():
                        st.markdown('<div class="dice-grid">', unsafe_allow_html=True)
                        btn_cols = st.columns(6, gap="large")  # 6 columns, original style
                        totals = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]  # ascending 2..12
                        pressed_total = None
                        for i, t in enumerate(totals):
                            with btn_cols[i % 6]:
                                if st.button(str(t), key=f"catan_roll_{t}"):
                                    pressed_total = t
                        st.markdown("</div>", unsafe_allow_html=True)

                    if pressed_total is not None:
                        r = Roll(
                            game_id=game_id,
                            player_id=current_gp.player_id,
                            total=pressed_total,
                            idx_in_game=st.session_state.catan_roll_counter,
                        )
                        session.add(r)
                        st.session_state.catan_roll_counter += 1
                        st.session_state.catan_turn_idx = (st.session_state.catan_turn_idx + 1) % len(gps)
                        session.commit()
                        _success(f"Recorded roll: {current_gp.display_name_snapshot} → {pressed_total}")

                    st.subheader("Live Roll Distribution (This Game)")
                    dist_df = rolls_distribution_df(session, game_id)
                    _show_gof_line(dist_df, "this game")
                    st.altair_chart(_bar_vs_expected(dist_df), use_container_width=True)

                    st.subheader("Per-Player Distribution")
                    pid_to_name = {gp.player_id: gp.display_name_snapshot for gp in gps}
                    default_pid = gps[0].player_id
                    selected_pid = st.selectbox(
                        "Player",
                        options=list(pid_to_name.keys()),
                        index=list(pid_to_name.keys()).index(default_pid),
                        format_func=lambda pid: pid_to_name[pid],
                        key="catan_active_player_select",
                    )
                    pp_one_df = per_player_distribution_single_df(session, game_id, selected_pid)
                    _show_gof_line(pp_one_df, f"{pid_to_name[selected_pid]} (this game)")
                    st.altair_chart(_bar_vs_expected(pp_one_df), use_container_width=True)

                    st.divider()
                    st.subheader("End Game & Scores")
                    with st.form("catan_end_game_form"):
                        scores = {}
                        cols = st.columns(min(4, len(gps)))
                        for i, gp in enumerate(gps):
                            with cols[i % len(cols)]:
                                scores[gp.player_id] = st.number_input(
                                    f"{gp.display_name_snapshot}", min_value=0, max_value=100, value=0, step=1
                                )
                        end_now = st.form_submit_button("Save Scores & End Game", type="primary")
                    if end_now:
                        for gp in gps:
                            fs = FinalScore(game_id=game_id, player_id=gp.player_id, score=int(scores[gp.player_id]))
                            session.add(fs)
                        g = session.get(Game, game_id)
                        g.ended_at = pd.Timestamp.utcnow().to_pydatetime()
                        session.add(g)
                        session.commit()
                        st.session_state.catan_active_game_id = None
                        st.session_state.catan_turn_idx = 0
                        st.session_state.catan_roll_counter = 0
                        _success("Game ended and scores saved.")

    elif page == "Historical Data":
        st.header("Catan — Historical Data")
        with get_session() as session:
            # Lifetime overall
            st.subheader("Lifetime Roll Distribution (All Games)")
            lifetime_df = lifetime_rolls_distribution_df(session)
            if lifetime_df["count"].sum() == 0:
                st.info("No rolls recorded yet.")
            else:
                _show_gof_line(lifetime_df, "lifetime (all games)")
                st.altair_chart(_bar_vs_expected(lifetime_df, title_x="Roll Total (2–12)"), use_container_width=True)

            # Lifetime per-player (single select)
            st.subheader("Lifetime Per-Player Distribution")
            players = session.exec(select(Player).order_by(Player.current_name.asc())).all()
            pid_to_name = {p.id: p.current_name for p in players}
            if pid_to_name:
                default_pid = next(iter(pid_to_name.keys()))
                selected_pid = st.selectbox(
                    "Player",
                    options=list(pid_to_name.keys()),
                    index=list(pid_to_name.keys()).index(default_pid),
                    format_func=lambda pid: pid_to_name[pid],
                    key="catan_lifetime_player_select",
                )
                pp_life_df = lifetime_per_player_distribution_df(session, player_id=selected_pid)
                if pp_life_df.empty or pp_life_df["count"].sum() == 0:
                    st.caption("No per-player roll data.")
                else:
                    # Convert to the same shape ['total','count'] for GOF line
                    tmp = pp_life_df.rename(columns={"player": "_"}).drop(columns=["_"])
                    _show_gof_line(tmp, f"{pid_to_name[selected_pid]} (lifetime)")
                    st.altair_chart(_bar_vs_expected(tmp), use_container_width=True)
            else:
                st.caption("No players yet.")

            st.subheader("Lifetime Scores & Wins")
            summary_df = lifetime_scores_summary_df(session)
            if summary_df.empty:
                st.caption("No completed games with scores yet.")
            else:
                st.dataframe(summary_df, use_container_width=True)

            # Independence across players (optional but useful)
            st.subheader("Players vs Totals — Distribution Differences")
            table, id_to_name = players_totals_contingency(session)
            if table.empty or table.values.sum() == 0 or table.shape[0] < 2:
                st.caption("Not enough data to compare players yet.")
            else:
                chi2, dof, p, n, r = chisq_independence_players(table)
                V = cramers_v(chi2, n, r, table.shape[1])
                st.caption(f"χ² independence: χ²={chi2:.2f}, df={dof}, p={p:.3f}, n={n}, Cramér’s V={V:.2f}")

            st.divider()
            with st.expander("Individual Games"):
                games = session.exec(select(Game).order_by(Game.started_at.desc())).all()
                if not games:
                    st.caption("No games recorded yet.")
                else:
                    for g in games:
                        date_str = pd.to_datetime(g.started_at).strftime("%m/%d/%Y")
                        with st.expander(f"{date_str}"):
                            gps = session.exec(
                                select(GamePlayer).where(GamePlayer.game_id == g.id).order_by(GamePlayer.turn_order)
                            ).all()
                            st.write("**Players:** " + ", ".join(f"{gp.turn_order}. {gp.display_name_snapshot}" for gp in gps))
                            dist_df = rolls_distribution_df(session, g.id)
                            _show_gof_line(dist_df, f"game {date_str}")
                            st.altair_chart(_bar_vs_expected(dist_df), use_container_width=True)

                            scores = session.exec(select(FinalScore).where(FinalScore.game_id == g.id)).all()
                            if scores:
                                by_pid = {s.player_id: s.score for s in scores}
                                rows = [{"player": gp.display_name_snapshot, "score": by_pid.get(gp.player_id, None)} for gp in gps]
                                df = pd.DataFrame(rows)
                                st.table(df)
                                if df["score"].notna().any():
                                    max_score = df["score"].max()
                                    winners = df[df["score"] == max_score]["player"].tolist()
                                    st.success(f"Winner: {', '.join(winners)} (score {max_score})")
                            else:
                                st.caption("No final scores recorded for this game.")
    else:
        st.error("Unknown page")
