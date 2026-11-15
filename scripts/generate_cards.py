#!/usr/bin/env python3
"""Generate GitHub stats and top-languages SVG cards for the profile README.

Runs in GitHub Actions with the built-in GITHUB_TOKEN, so it never depends on
a shared public service. Uses only the Python standard library.

Usage:
    GITHUB_TOKEN=... python scripts/generate_cards.py <username> <output_dir>
"""

import json
import os
import sys
import urllib.request
from html import escape

API = "https://api.github.com/graphql"

# Tokyo Night palette (matches the rest of the README)
BG = "#1a1b27"
TITLE = "#70a5fd"
TEXT = "#38bdae"
ICON = "#bf91f3"
MUTED = "#a9b1d6"

CARD_WIDTH = 467
LANGS_COUNT = 8

# Languages that are mostly generated/markup and would swamp the chart
EXCLUDED_LANGS = {"Jupyter Notebook", "HTML", "CSS", "SCSS"}

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    name
    login
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) { totalCount }
    repositories(
      first: 100
      after: $cursor
      ownerAffiliations: OWNER
      isFork: false
    ) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def graphql(token, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-cards-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]["user"]


def fetch(username, token):
    user, repos, cursor = None, [], None
    while True:
        page = graphql(token, {"login": username, "cursor": cursor})
        if page is None:
            raise RuntimeError(f"User {username!r} not found")
        user = user or page
        repos.extend(page["repositories"]["nodes"])
        info = page["repositories"]["pageInfo"]
        if not info["hasNextPage"]:
            break
        cursor = info["endCursor"]

    cc = user["contributionsCollection"]
    stats = {
        "name": user["name"] or user["login"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
    }

    langs = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in EXCLUDED_LANGS:
                continue
            entry = langs.setdefault(name, {"size": 0, "color": edge["node"]["color"] or "#858585"})
            entry["size"] += edge["size"]
    return stats, langs


def card(height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{height}" viewBox="0 0 {CARD_WIDTH} {height}" role="img" aria-label="{escape(title)}">
  <style>
    .title {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: {TITLE}; }}
    .label {{ font: 600 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: {TEXT}; }}
    .value {{ font: 700 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: {TEXT}; }}
    .lang  {{ font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: {MUTED}; }}
  </style>
  <rect width="100%" height="100%" rx="4.5" fill="{BG}"/>
  <text x="25" y="35" class="title">{escape(title)}</text>
{body}
</svg>
"""


# 16x16 Octicons paths
ICONS = {
    "stars": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z",
    "commits": "M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z",
    "prs": "M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354Z",
    "issues": "M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z",
    "contributed": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z",
}


def render_stats(s):
    rows = [
        ("stars", "Total Stars Earned", s["stars"]),
        ("commits", "Commits (this year)", s["commits"]),
        ("prs", "Total PRs", s["prs"]),
        ("issues", "Total Issues", s["issues"]),
        ("contributed", "Contributed to (last year)", s["contributed"]),
    ]
    body = []
    for i, (key, label, value) in enumerate(rows):
        y = 70 + i * 25
        body.append(
            f'  <g transform="translate(25,{y})">'
            f'<svg viewBox="0 0 16 16" width="16" height="16" y="-12"><path fill="{ICON}" d="{ICONS[key]}"/></svg>'
            f'<text x="25" class="label">{label}:</text>'
            f'<text x="{CARD_WIDTH - 50}" text-anchor="end" class="value">{value:,}</text></g>'
        )
    title = f"{s['name']}'s GitHub Stats"
    return card(195, title, "\n".join(body))


def render_langs(langs):
    top = sorted(langs.items(), key=lambda kv: kv[1]["size"], reverse=True)[:LANGS_COUNT]
    total = sum(v["size"] for _, v in top) or 1
    bar_w = CARD_WIDTH - 50
    body = [f'  <clipPath id="bar"><rect x="25" y="55" width="{bar_w}" height="8" rx="5"/></clipPath>',
            '  <g clip-path="url(#bar)">']
    x = 25.0
    for name, v in top:
        w = bar_w * v["size"] / total
        body.append(f'    <rect x="{x:.2f}" y="55" width="{w + 0.5:.2f}" height="8" fill="{v["color"]}"/>')
        x += w
    body.append("  </g>")

    col_w = bar_w / 2
    for i, (name, v) in enumerate(top):
        cx = 25 + (i % 2) * col_w
        cy = 90 + (i // 2) * 25
        pct = 100 * v["size"] / total
        body.append(
            f'  <circle cx="{cx + 5:.1f}" cy="{cy - 4}" r="5" fill="{v["color"]}"/>'
            f'<text x="{cx + 15:.1f}" y="{cy}" class="lang">{escape(name)} {pct:.2f}%</text>'
        )
    rows = (len(top) + 1) // 2
    height = max(90 + max(rows - 1, 0) * 25 + 25, 195)  # match stats card
    return card(height, "Most Used Languages", "\n".join(body))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    username, out_dir = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")

    stats, langs = fetch(username, token)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "stats.svg"), "w") as f:
        f.write(render_stats(stats))
    with open(os.path.join(out_dir, "top-langs.svg"), "w") as f:
        f.write(render_langs(langs))
    print(f"Wrote cards for {username}: {stats}")


if __name__ == "__main__":
    main()
