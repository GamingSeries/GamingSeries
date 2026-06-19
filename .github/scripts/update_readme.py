#!/usr/bin/env python3
"""Rebuild the live sections of the GitHub profile README from public APIs.

Sections are delimited by HTML comment markers (e.g. <!-- PROJECTS:START --> ...
<!-- PROJECTS:END -->) and rewritten in place. All network calls degrade
gracefully so a single outage never breaks the README.
"""
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import iss_graphic

USER = "GamingSeries"
ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ASSET_DIR = ROOT / "assets"
LAND = pathlib.Path(__file__).resolve().parents[1] / "data" / "land.json"
GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
NASA_KEY = os.environ.get("NASA_API_KEY") or "DEMO_KEY"
UA = {"User-Agent": "profile-dashboard"}


def get_json(url, headers=None, timeout=25):
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def gh(path):
    headers = {"Accept": "application/vnd.github+json"}
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
    return get_json(f"https://api.github.com{path}", headers=headers)


def cell(text):
    return (str(text) if text is not None else "").replace("|", "/").replace("\n", " ").strip()


def replace_block(text, name, body):
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    return re.sub(
        re.escape(start) + r".*?" + re.escape(end),
        lambda _m: f"{start}\n{body}\n{end}",
        text,
        flags=re.S,
    )


def build_snapshot(user, repos, last_active):
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    since = (user.get("created_at") or "----")[:4]
    return (
        "| Public repos | Total stars | Followers | Following | Member since | Last active |\n"
        "| :--: | :--: | :--: | :--: | :--: | :--: |\n"
        f"| {user.get('public_repos', '-')} | {stars} | {user.get('followers', '-')} "
        f"| {user.get('following', '-')} | {since} | {last_active} |"
    )


def build_projects(repos):
    show = [r for r in repos if r["name"].lower() != USER.lower()]
    show.sort(key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")), reverse=True)
    rows = [
        "| Repository | Language | Stars | Updated | Description |",
        "| :-- | :-- | :--: | :--: | :-- |",
    ]
    for r in show[:6]:
        rows.append(
            f"| [{r['name']}]({r['html_url']}) | {r.get('language') or '-'} "
            f"| {r.get('stargazers_count', 0)} | {r['updated_at'][:10]} "
            f"| {cell(r.get('description')) or '-'} |"
        )
    if len(rows) == 2:
        rows.append("| No public repositories found | - | - | - | - |")
    return "\n".join(rows)


def build_activity(events):
    lines, i, n = [], 0, len(events)
    while i < n and len(lines) < 7:
        e = events[i]
        et = e.get("type")
        repo = e.get("repo", {}).get("name", "")
        link = f"[{repo}](https://github.com/{repo})" if repo else "GitHub"
        day = e.get("created_at", "")[:10]
        payload = e.get("payload", {})
        if et == "PushEvent":
            count = payload.get("size", 1) or 1
            j = i + 1
            while j < n and events[j].get("type") == "PushEvent" \
                    and events[j].get("repo", {}).get("name") == repo:
                count += events[j].get("payload", {}).get("size", 1) or 1
                j += 1
            i = j
            lines.append(f"- `{day}` Pushed {count} commit{'s' if count != 1 else ''} to {link}")
            continue
        if et == "PullRequestEvent":
            num = payload.get("number")
            title = cell((payload.get("pull_request") or {}).get("title", ""))
            lines.append(f"- `{day}` {payload.get('action', '').capitalize()} PR #{num} in {link}: {title}")
        elif et == "IssuesEvent":
            lines.append(
                f"- `{day}` {payload.get('action', '').capitalize()} issue "
                f"#{payload.get('issue', {}).get('number')} in {link}"
            )
        elif et == "ReleaseEvent":
            tag = payload.get("release", {}).get("tag_name", "")
            lines.append(f"- `{day}` Published release `{tag}` in {link}")
        elif et == "CreateEvent":
            rt = payload.get("ref_type", "")
            if rt == "repository":
                lines.append(f"- `{day}` Created repository {link}")
            else:
                lines.append(f"- `{day}` Created {rt} `{cell(payload.get('ref'))}` in {link}")
        elif et == "WatchEvent":
            lines.append(f"- `{day}` Starred {link}")
        elif et == "ForkEvent":
            lines.append(f"- `{day}` Forked {link}")
        else:
            i += 1
            continue
        i += 1
    return "\n".join(lines) if lines else "- No recent public activity."


def build_signals():
    rows = ["| Live signal | Reading |", "| :-- | :-- |"]
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    try:
        d = get_json(
            f"https://api.nasa.gov/neo/rest/v1/feed?start_date={today}&end_date={today}"
            f"&api_key={NASA_KEY}"
        )
        neos = d.get("near_earth_objects", {}).get(today, [])
        haz = sum(1 for o in neos if o.get("is_potentially_hazardous_asteroid"))
        rows.append(
            f"| Near-Earth objects today (NASA) | {d.get('element_count', len(neos))} tracked, "
            f"{haz} flagged potentially hazardous |"
        )
    except Exception:
        rows.append("| Near-Earth objects today (NASA) | Unavailable |")
    try:
        d = get_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson")
        feats = d.get("features") or []
        if feats:
            p = max(feats, key=lambda x: x["properties"]["time"])["properties"]
            when = datetime.datetime.fromtimestamp(p["time"] / 1000, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            rows.append(f"| Latest M4.5+ earthquake (USGS) | M{p['mag']} - {cell(p['place'])} ({when}) |")
        else:
            rows.append("| Latest M4.5+ earthquake (USGS) | None in the last 24h |")
    except Exception:
        rows.append("| Latest M4.5+ earthquake (USGS) | Unavailable |")
    return "\n".join(rows)


def update_iss_graphic():
    """Regenerate assets/iss.svg from live ISS telemetry. Leaves the previous
    file untouched on any failure so a transient outage never blanks it."""
    try:
        d = get_json("https://api.wheretheiss.at/v1/satellites/25544?units=kilometers")
    except Exception:
        return False
    track = []
    try:
        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        for base in range(2):  # two calls of 9 points = one ~90 min orbit
            ts = ",".join(str(now + (base * 9 + i) * 330) for i in range(9))
            arr = get_json(
                f"https://api.wheretheiss.at/v1/satellites/25544/positions"
                f"?timestamps={ts}&units=kilometers"
            )
            track += [[p["latitude"], p["longitude"]] for p in arr]
    except Exception:
        track = []
    try:
        polygons = json.loads(LAND.read_text(encoding="utf-8")).get("polygons", [])
    except Exception:
        polygons = []
    try:
        svg = iss_graphic.render_iss_svg(d, polygons, track)
        ASSET_DIR.mkdir(exist_ok=True)
        (ASSET_DIR / "iss.svg").write_text(svg, encoding="utf-8")
        return True
    except Exception:
        return False


def main():
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        user = gh(f"/users/{USER}")
    except Exception:
        user = {}
    try:
        repos = [r for r in gh(f"/users/{USER}/repos?per_page=100&sort=updated") if not r.get("fork")]
    except Exception:
        repos = []
    try:
        events = gh(f"/users/{USER}/events/public?per_page=40")
        events = events if isinstance(events, list) else []
    except Exception:
        events = []

    last_active = events[0]["created_at"][:10] if events else "n/a"

    print("ISS graphic refreshed:", update_iss_graphic())

    text = README.read_text(encoding="utf-8")
    text = replace_block(text, "SNAPSHOT", build_snapshot(user, repos, last_active))
    text = replace_block(text, "PROJECTS", build_projects(repos))
    text = replace_block(text, "ACTIVITY", build_activity(events))
    text = replace_block(text, "SIGNALS", build_signals())
    text = replace_block(
        text, "UPDATED",
        f'<p align="center"><sub>Auto-refreshed {now} via GitHub Actions</sub></p>',
    )
    README.write_text(text, encoding="utf-8")
    print("README updated at", now)


if __name__ == "__main__":
    main()
