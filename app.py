# /app.py
import streamlit as st
from db import create_db_and_tables

st.set_page_config(page_title="Board Game Hub", page_icon="🎲", layout="wide")
create_db_and_tables()

# ---- Dark-green site theme ----
def _inject_site_theme():
    st.markdown(
        """
        <style>
        :root{
          --bg:#0b3d2e; --panel:#0e4b38; --sidebar:#0a2f24;
          --accent:#2ecc71; --accent2:#27ae60; --text:#e6f4ea;
        }
        .stApp { background: var(--bg); color: var(--text); }

        /* Sidebar + header */
        [data-testid="stSidebar"] { background: var(--sidebar); color: var(--text); }
        header[data-testid="stHeader"] {
          background: var(--bg);
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        /* More space between header and page title */
        .block-container { padding-top: 2.4rem; }

        /* Headings spacing */
        h1, .stMarkdown h1 { margin-top: 0.25rem; margin-bottom: 1.0rem; }

        /* Buttons default */
        div[data-testid="stButton"] > button {
          background: linear-gradient(180deg, var(--accent) 0%, var(--accent2) 100%);
          color: white; border: 0; border-radius: 12px;
          padding: 14px 22px; font-size: 18px; font-weight: 700;
          box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        }
        div[data-testid="stButton"] > button:hover {
          filter: brightness(1.08); transform: translateY(-1px);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

_inject_site_theme()

# App routing state
if "current_app" not in st.session_state:
    st.session_state.current_app = "Library"

st.sidebar.title("Board Game Hub")

if st.session_state.current_app != "Library":
    if st.sidebar.button("← Back to Library", use_container_width=True):
        st.session_state.current_app = "Library"
        st.rerun()

def render_library():
    st.title("Your Game Library")
    st.caption("Click a game to open its tracker. Start with Catan; add more later.")

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown("### 🟠 Catan")
            st.write("Track dice rolls, turn order, and final scores. Live histograms included.")
            if st.button("Open Catan", key="open_catan", use_container_width=True):
                st.session_state.current_app = "Catan"
                st.rerun()
    with col2:
        with st.container(border=True):
            st.markdown("### ♟️ Chess")
            st.write("(Coming soon) Record results, openings, time controls.")
            st.button("Not available", key="notavail_chess", disabled=True, use_container_width=True)
    with col3:
        with st.container(border=True):
            st.markdown("### 🎲 Other Games")
            st.write("(Coming soon) Add any tabletop game with custom events.")
            st.button("Not available", key="notavail_other", disabled=True, use_container_width=True)

if st.session_state.current_app == "Library":
    render_library()
elif st.session_state.current_app == "Catan":
    from games.catan_app import render as render_catan
    render_catan()
else:
    st.error(f"Unknown app: {st.session_state.current_app}")
