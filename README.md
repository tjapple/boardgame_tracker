# Board Game Hub (Catan-first)

Ever wonder if your dice are loaded??

This is a Python + Streamlit app to track board game stats (starting with **Catan**): player library, turn order, live dice roll capture, lifetime analytics, and fairness tests (χ² GOF, per-bin exact binomial p-values). Designed so other games can be added later.



## Features

- Game Library → Catan sub-app

- Players: add/rename (aliases keep stats intact)

- New Game: choose dice set, select players, set order

- Active Game: \*\*giant dice buttons\*\*, auto-advance turns, \*\*live charts\*\*

- Historical Data: lifetime distributions + \*\*expected vs actual\*\* overlay, \*\*χ²\*\* summaries, \*\*Players vs Totals\*\* independence (Cramér’s V)



## Tech

- **Python 3.11**, Streamlit, SQLModel/SQLAlchemy (SQLite), Altair, Pandas

- Optional: SciPy for exact χ² p-values (fallback approximation included)



## Quickstart (Windows / PowerShell)

```powershell

# Clone

git clone https://github.com/tjapple/boardgame_tracker.git

cd boardgame_tracker


# Create environment (conda) or use venv if you prefer

conda create -n bg-hub python=3.11 -y

conda activate bg-hub



# Install deps

pip install -r requirements.txt



# Run

streamlit run app.py
```



