#!/usr/bin/env python3
"""Refresh the Live World Feed block in README.md with public, key-free data."""
import datetime
import json
import pathlib
import re
import urllib.request

README = pathlib.Path(__file__).resolve().parents[2] / "README.md"
START = "<!-- WORLD-FEED:START -->"
END = "<!-- WORLD-FEED:END -->"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-world-feed"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.load(resp)


def cell(value):
    return str(value).replace("|", "/").strip()


def iss_position():
    try:
        d = fetch("https://api.wheretheiss.at/v1/satellites/25544")
        return f"{d['latitude']:.2f} deg, {d['longitude']:.2f} deg"
    except Exception:
        return "Unavailable"


def latest_quake():
    try:
        d = fetch(
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
        )
        feats = d.get("features") or []
        if not feats:
            return "No M4.5+ events in the last 24h"
        f = max(feats, key=lambda x: x["properties"]["time"])
        p = f["properties"]
        when = datetime.datetime.utcfromtimestamp(p["time"] / 1000).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        return f"M{p['mag']} - {p['place']} ({when})"
    except Exception:
        return "Unavailable"


def main():
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    table = (
        "| Signal | Reading |\n"
        "| --- | --- |\n"
        f"| ISS ground position | {cell(iss_position())} |\n"
        f"| Latest M4.5+ earthquake | {cell(latest_quake())} |\n"
        f"| Last updated | {cell(now)} |\n"
    )
    block = f"{START}\n{table}{END}"
    text = README.read_text(encoding="utf-8")
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        block.replace("\\", "\\\\"),
        text,
        flags=re.S,
    )
    README.write_text(new, encoding="utf-8")
    print(new)


if __name__ == "__main__":
    main()
