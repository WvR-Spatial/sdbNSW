"""Trace a disagreement between two pulls of 'wind at overpass', Jervis Bay.

Two pulls of the same quantity disagreed on speed (7 Sep 2018: 3.58 vs
0.86 m/s) while agreeing on direction. The first pull's parameters were not
recorded, so it cannot be reproduced. This prints every candidate source for
the hours around each overpass, so the difference can be pinned on one of:

  * the model   -- ERA5 (0.25 deg) vs ERA5-Land (0.1 deg, land cells) vs
                   ECMWF IFS (9 km) vs Open-Meteo's default "best_match"
  * the hour    -- a time-zone slip puts "00:00" at 00:00 AEST = 14:00 UTC
                   the previous day, ten hours before the overpass
  * volatility  -- wind changing fast around the overpass, which would make
                   any single-hour value fragile

Usage (Anaconda Prompt, sdbnsw env, from the repo root):
    python scripts\\check_wind_sources.py

Needs network access to archive-api.open-meteo.com. Writes nothing.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

import requests

URL = "https://archive-api.open-meteo.com/v1/archive"
LAT, LON = -35.06195, 150.7345          # centre of the Jervis Bay bbox in config/sites.yml
OVERPASSES = ["2018-09-07", "2018-09-12", "2018-09-17"]   # all ~00:02-00:06 UTC
MODELS = ["era5", "era5_land", "ecmwf_ifs", "best_match"]
FIRST_PULL = {"2018-09-07": "3.58/300", "2018-09-12": "3.76/29", "2018-09-17": "2.40/17"}


def pull(model: str):
    params = {
        "latitude": LAT, "longitude": LON,
        "start_date": "2018-09-06", "end_date": "2018-09-17",
        "hourly": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms", "timezone": "GMT", "models": model,
    }
    try:
        r = requests.get(URL, params=params, timeout=30)
    except requests.RequestException as exc:
        return None, f"request failed: {exc}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}: {r.text[:150]}"
    j = r.json()
    h = j["hourly"]
    unit = j.get("hourly_units", {}).get("wind_speed_10m")
    if unit != "m/s":
        return None, f"unexpected unit {unit!r}"
    series = {t: (s, d) for t, s, d in zip(h["time"], h["wind_speed_10m"], h["wind_direction_10m"])}
    return series, f"cell {j.get('latitude'):.3f}, {j.get('longitude'):.3f}"


def fmt(v) -> str:
    if v is None or v[0] is None or v[1] is None:
        return "--"
    return f"{v[0]:.2f}/{v[1]:.0f}"


def main() -> int:
    data, notes = {}, {}
    for m in MODELS:
        data[m], notes[m] = pull(m)
    print(f"Point {LAT}, {LON}   speed m/s / from deg   times UTC\n")
    for m in MODELS:
        print(f"  {m:<11} {notes[m]}")
    print()

    header = f"{'UTC':<18}{'':<14}" + "".join(f"{m:>12}" for m in MODELS)
    print(header)
    print("-" * len(header))
    for day in OVERPASSES:
        d0 = datetime.fromisoformat(day)
        rows = [(d0 - timedelta(hours=10), "00:00 AEST")]
        rows += [(d0 + timedelta(hours=k), "OVERPASS" if k == 0 else "") for k in (-2, -1, 0, 1, 2)]
        for t, tag in rows:
            key = t.strftime("%Y-%m-%dT%H:%M")
            cells = "".join(f"{fmt(data[m].get(key)) if data[m] else 'n/a':>12}" for m in MODELS)
            print(f"{t:%Y-%m-%d %H:%M}  {tag:<14}{cells}")
        print(f"{'':<18}{'first pull':<14}{FIRST_PULL[day]:>12}\n")

    print("Reading it: find where the first pull's numbers appear. Same row as the\n"
          "overpass but another column -> the model differs. The 00:00 AEST row ->\n"
          "a time-zone slip. Nowhere -> a different point or date; paste the\n"
          "original command if you still have it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
