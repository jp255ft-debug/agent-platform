#!/usr/bin/env python3
"""Generate a coverage badge SVG from pytest-cov JSON report."""

import json
import sys
from pathlib import Path

COVERAGE_JSON = Path("coverage/coverage.json")
BADGE_OUTPUT = Path("coverage/coverage-badge.svg")


def get_coverage_percent() -> float:
    """Parse coverage.json and return the overall coverage percentage."""
    if not COVERAGE_JSON.exists():
        print(f"ERROR: {COVERAGE_JSON} not found. Run pytest --cov first.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(COVERAGE_JSON.read_text())
    totals = data.get("totals", {})
    covered = totals.get("covered_lines", 0)
    missing = totals.get("missing_lines", 0)
    total = covered + missing
    if total == 0:
        return 0.0
    return round((covered / total) * 100, 1)


def color_for(pct: float) -> str:
    """Return badge color based on coverage percentage."""
    if pct >= 90:
        return "brightgreen"
    elif pct >= 80:
        return "green"
    elif pct >= 70:
        return "yellowgreen"
    elif pct >= 60:
        return "yellow"
    elif pct >= 50:
        return "orange"
    else:
        return "red"


def generate_svg(pct: float) -> str:
    """Generate a shields.io-style SVG badge."""
    color = color_for(pct)
    label = "coverage"
    value = f"{pct}%"

    # Simple SVG badge template
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="110" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a">
    <rect width="110" height="20" rx="3" fill="#fff"/>
  </mask>
  <g mask="url(#a)">
    <rect width="55" height="20" fill="#555"/>
    <rect x="55" width="55" height="20" fill="#{color}"/>
    <rect width="110" height="20" fill="url(#b)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="27.5" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="27.5" y="14">{label}</text>
    <text x="82.5" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="82.5" y="14">{value}</text>
  </g>
</svg>"""


def main() -> None:
    pct = get_coverage_percent()
    svg = generate_svg(pct)
    BADGE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    BADGE_OUTPUT.write_text(svg)
    print(f"Coverage badge generated: {pct}% → {BADGE_OUTPUT}")


if __name__ == "__main__":
    main()
