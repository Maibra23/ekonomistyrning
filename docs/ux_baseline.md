# UX modernization baseline

Start point for branch `ux/modernization` (tag `ux-baseline`, commit `606cfb7` plus the plan document).

## Environment

- Python 3.12.10, streamlit 1.67.0, plotly 6.6.0, playwright 1.64.0 (dev-only)

## Checks

| Check | Result |
|---|---|
| `pytest tests/ -q` | 2282 passed, 4 skipped |
| `ruff check utils/ pages/ tests/ streamlit_app.py scripts/` | 1 error at baseline (unused import `link_records` in `pages/3_Budget.py`, F401); removed in T00, now clean |
| `mypy` (CI config: `files = ["utils"]`) | no issues in 25 source files |

## Visual baseline

Captured with `python scripts/ui_snapshots.py --label baseline` against the app at
`http://localhost:8599` started with `HF_TOKEN=` (LLM disabled). The output is in
`.ui_snapshots/baseline/` (git-ignored): 24 PNGs (6 pages x 2 viewports x viewport and tall)
plus `metrics.json`.

| Page | KPI | Charts | Dataframes | Downloads | Exceptions | Content height 1440 / 390 |
|---|---|---|---|---|---|---|
| `/` | 0 | 0 | 0 | 0 | 0 | 1703 / 2951 |
| `/Kalkyl` | 13 | 5 | 6 | 3 | 0 | 2197 / 3168 |
| `/Investering` | 9 | 6 | 4 | 2 | 0 | 2164 / 3659 |
| `/Budget` | 18 | 4 | 5 | 1 | 0 | 4976 / 8942 |
| `/Standardkostnadsanalys` | 10 | 4 | 3 | 3 | 0 | 2614 / 3263 |
| `/Kunskapstest` | 0 | 0 | 0 | 0 | 0 | 966 / 1299 |

Sidebar width: 260 px at 1440, 300 px at 390. At 390 px the sidebar opens expanded and
covers the content (`initial_sidebar_state="expanded"`, see D8).
