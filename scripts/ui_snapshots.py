"""Capture UI snapshots and simple DOM metrics for every page of the app.

Dev-only tool. It is not imported by the app, and Playwright is not a runtime
dependency (it is not listed in requirements.txt). Install it locally with:

    pip install playwright
    python -m playwright install chromium   # only if Edge is not available

The script starts nothing itself. Run the app first, with the LLM disabled so
pages render deterministically:

    HF_TOKEN= python -m streamlit run streamlit_app.py --server.port 8599 --server.headless true

then, in another shell:

    python scripts/ui_snapshots.py --label baseline

For every page and the viewports 1440x900 and 390x844 it waits for network
idle plus a settle delay, saves a viewport screenshot and a "tall" screenshot
(viewport height set to the measured content height, capped at 16000 px) into
``--out`` (default ``.ui_snapshots/<label>/``), and prints JSON metrics per
page: counts of KPI cards, Plotly charts, dataframes, download buttons and
Streamlit exceptions, plus the sidebar width.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PAGES: list[tuple[str, str]] = [
    ("home", "/"),
    ("kalkyl", "/Kalkyl"),
    ("investering", "/Investering"),
    ("budget", "/Budget"),
    ("standardkost", "/Standardkostnadsanalys"),
    ("kunskapstest", "/Kunskapstest"),
]

VIEWPORTS: list[tuple[int, int]] = [(1440, 900), (390, 844)]

MAX_TALL_HEIGHT = 16000

METRICS_JS = """
() => {
  const count = (sel) => document.querySelectorAll(sel).length;
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  let sidebarWidth = 0;
  if (sidebar) {
    const r = sidebar.getBoundingClientRect();
    // A collapsed sidebar is translated off-screen; report visible width.
    sidebarWidth = Math.max(0, Math.min(r.right, window.innerWidth) - Math.max(r.left, 0));
  }
  return {
    kpi: count('.eks-kpi'),
    plotly: count('.js-plotly-plot'),
    dataframe: count('[data-testid="stDataFrame"]'),
    download: count('[data-testid="stDownloadButton"]'),
    exception: count('[data-testid="stException"]'),
    sidebar_width: Math.round(sidebarWidth),
  };
}
"""

# Streamlit scrolls inside its own containers rather than the document, so take
# the largest scrollHeight among the candidates.
HEIGHT_JS = """
() => {
  const sels = ['[data-testid="stMain"]', '[data-testid="stAppViewContainer"]',
                'section.main', '[data-testid="stMainBlockContainer"]'];
  let h = document.scrollingElement ? document.scrollingElement.scrollHeight : 0;
  for (const s of sels) {
    const el = document.querySelector(s);
    if (el) h = Math.max(h, el.scrollHeight);
  }
  return h;
}
"""


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    p.add_argument("--base", default="http://localhost:8599", help="App base URL")
    p.add_argument("--label", default="snapshot", help="Sub-folder name for this run")
    p.add_argument("--out", default=None, help="Output folder (default .ui_snapshots/<label>/)")
    p.add_argument(
        "--channel",
        default="msedge",
        help="Browser channel (default msedge); falls back to bundled chromium",
    )
    p.add_argument("--settle", type=float, default=4.0, help="Seconds to wait after network idle")
    p.add_argument(
        "--pages",
        default=None,
        help="Comma-separated subset of page labels (" + ", ".join(n for n, _ in PAGES) + ")",
    )
    return p.parse_args(argv)


def _launch(pw: Any, channel: str) -> Any:
    if channel and channel != "chromium":
        try:
            return pw.chromium.launch(channel=channel)
        except Exception as exc:  # any launch failure triggers the fallback
            print(f"[warn] channel {channel!r} failed ({exc.__class__.__name__}); "
                  "falling back to bundled chromium", file=sys.stderr)
    return pw.chromium.launch()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed: pip install playwright", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else Path(".ui_snapshots") / args.label
    out.mkdir(parents=True, exist_ok=True)
    base = args.base.rstrip("/")

    pages = PAGES
    if args.pages:
        wanted = {s.strip() for s in args.pages.split(",") if s.strip()}
        pages = [pg for pg in PAGES if pg[0] in wanted]

    results: list[dict[str, Any]] = []
    shots = 0
    with sync_playwright() as pw:
        browser = _launch(pw, args.channel)
        try:
            for width, height in VIEWPORTS:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                for name, path in pages:
                    url = base + path
                    page.set_viewport_size({"width": width, "height": height})
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    time.sleep(args.settle)
                    stem = f"{name}_{width}"
                    page.screenshot(path=str(out / f"{stem}.png"))
                    shots += 1

                    metrics = page.evaluate(METRICS_JS)

                    content_h = int(page.evaluate(HEIGHT_JS))
                    tall_h = max(height, min(content_h, MAX_TALL_HEIGHT))
                    page.set_viewport_size({"width": width, "height": tall_h})
                    time.sleep(1.0)
                    page.screenshot(path=str(out / f"{stem}_tall.png"))
                    shots += 1

                    row = {"page": name, "path": path, "viewport": f"{width}x{height}",
                           "content_height": content_h, **metrics}
                    results.append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
                context.close()
        finally:
            browser.close()

    total_exc = sum(r["exception"] for r in results)
    summary = {"screenshots": shots, "pages": len(results), "exceptions": total_exc,
               "out": str(out)}
    (out / "metrics.json").write_text(
        json.dumps({"summary": summary, "pages": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 1 if total_exc else 0


if __name__ == "__main__":
    raise SystemExit(main())
