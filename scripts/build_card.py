"""Build the neofetch-style profile card: an ASCII portrait next to a terminal-style info panel
with live GitHub stats. Writes dark_mode.svg and light_mode.svg to the repository root.

Standard library only, so the daily GitHub Action needs no installs:

    GITHUB_TOKEN=... python scripts/build_card.py

Without a token, or if the API call fails, the existing cards are left untouched so a bad day
never replaces real numbers with blanks. (Run with --force to write "-" placeholders anyway.)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

USER = "PrakharBhushan"
ROOT = Path(__file__).resolve().parent.parent

# (key, value) rows of the info panel. None draws a blank line; a ("-", title) row draws a
# section rule. Edit freely; stats rows are filled in from the GitHub API.
INFO = [
    ("OS", "macOS, Apple M1"),
    ("Uptime", "{uptime}"),
    ("Host", "JobVisitors (Co-Founder & Product Lead)"),
    ("Kernel", "B.Tech CSE, PSIT Kanpur"),
    ("IDE", "Claude Code, VS Code"),
    None,
    ("Languages.Code", "TypeScript, JavaScript, Python"),
    ("Languages.Real", "English, Hindi"),
    None,
    ("Shipped", "Magician AI, MockPe, KanoonAI, LayerStream"),
    ("Hobbies", "Clicking photos, building stuff"),
    ("Instagram", "@programmingwale · @btechhub (205K+)"),
    ("-", "Contact"),
    ("Email", "prakharbhushan03@gmail.com"),
    ("LinkedIn", "prakharbhushan03"),
    ("Website", "jobvisitors.com"),
    ("-", "GitHub Stats"),
    ("Repos", "{repos}  |  Stars: {stars}"),
    ("Contributions", "{contributions} (last year)  |  Followers: {followers}"),
]
BUILDING_SINCE = date(2021, 1, 1)  # first channel launched

THEMES = {
    "dark": {"bg": "#161b22", "border": "#30363d", "text": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff",
             "dim": "#6e7681", "accent": "#7ee787"},
    "light": {"bg": "#f6f8fa", "border": "#d0d7de", "text": "#24292f", "key": "#953800", "value": "#0a3069",
              "dim": "#8c959f", "accent": "#116329"},
}  # fmt: skip

WIDTH, HEIGHT = 1000, 470
ASCII_X, ASCII_Y, ASCII_SIZE, ASCII_LINE = 18, 36, 10, 12.3
INFO_X, INFO_Y, INFO_SIZE, INFO_LINE, INFO_COLS = 472, 40, 14, 20.5, 58


def uptime() -> str:
    today = date.today()
    months = (today.year - BUILDING_SINCE.year) * 12 + today.month - BUILDING_SINCE.month
    return f"{months // 12} years, {months % 12} months (building since {BUILDING_SINCE.year})"


def github_stats() -> dict[str, str] | None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("no GITHUB_TOKEN; stats unavailable")
        return None
    query = """query($login: String!) { user(login: $login) {
        followers { totalCount }
        contributionsCollection { contributionCalendar { totalContributions } }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
          totalCount nodes { stargazerCount } } } }"""
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            user = json.load(response)["data"]["user"]
    except Exception as error:
        print(f"stats unavailable: {error}")
        return None
    repos = user["repositories"]
    return {
        "repos": str(repos["totalCount"]),
        "stars": str(sum(node["stargazerCount"] for node in repos["nodes"])),
        "contributions": f"{user['contributionsCollection']['contributionCalendar']['totalContributions']:,}",
        "followers": str(user["followers"]["totalCount"]),
    }


def info_lines(values: dict[str, str], theme: dict[str, str]) -> list[str]:
    """One <tspan>-styled line per row, with dot leaders so values line up like neofetch."""
    header = f"{USER.lower()}@github"
    lines = [f'<tspan fill="{theme["accent"]}">{escape(header)}</tspan> '
             f'<tspan fill="{theme["dim"]}">{"─" * (INFO_COLS - len(header) - 1)}</tspan>']  # fmt: skip
    for row in INFO:
        if row is None:
            lines.append("")
            continue
        key, value = row
        if key == "-":
            lines.append(f'<tspan fill="{theme["dim"]}">─ </tspan><tspan fill="{theme["accent"]}">{escape(value)}</tspan>'
                         f'<tspan fill="{theme["dim"]}"> {"─" * (INFO_COLS - len(value) - 3)}</tspan>')  # fmt: skip
            continue
        value = value.format(**values)
        dots = "." * max(2, INFO_COLS - len(key) - len(value) - 4)
        lines.append(f'<tspan fill="{theme["key"]}">{escape(key)}</tspan>: '
                     f'<tspan fill="{theme["dim"]}">{dots}</tspan> '
                     f'<tspan fill="{theme["value"]}">{escape(value)}</tspan>')  # fmt: skip
    return lines


def render(theme_name: str, values: dict[str, str]) -> str:
    theme = THEMES[theme_name]
    portrait = (ROOT / "assets" / f"portrait_{theme_name}.txt").read_text().rstrip("\n").split("\n")
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'font-family="ConsolasFallback, Consolas, Menlo, \'DejaVu Sans Mono\', monospace">',
        "<style>text { white-space: pre; }</style>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" rx="12" fill="{theme["bg"]}" stroke="{theme["border"]}"/>',
        f'<text x="{ASCII_X}" y="{ASCII_Y}" font-size="{ASCII_SIZE}" fill="{theme["text"]}" xml:space="preserve">',
    ]
    for i, line in enumerate(portrait):
        out.append(f'<tspan x="{ASCII_X}" y="{ASCII_Y + i * ASCII_LINE:.1f}">{escape(line)}</tspan>')
    out.append("</text>")
    out.append(f'<text x="{INFO_X}" y="{INFO_Y}" font-size="{INFO_SIZE}" fill="{theme["text"]}" xml:space="preserve">')
    for i, line in enumerate(info_lines(values, theme)):
        out.append(f'<tspan x="{INFO_X}" y="{INFO_Y + i * INFO_LINE}">{line}</tspan>')
    out.append("</text>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    stats = github_stats()
    if stats is None:
        if "--force" not in sys.argv and (ROOT / "dark_mode.svg").exists():
            print("keeping the existing cards")
            return
        stats = {"repos": "-", "stars": "-", "contributions": "-", "followers": "-"}
    values = {"uptime": uptime(), **stats}
    for name in THEMES:
        (ROOT / f"{name}_mode.svg").write_text(render(name, values))
    print("stats:", values)


if __name__ == "__main__":
    main()
