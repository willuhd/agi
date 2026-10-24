"""Command line:

    python -m schoolmap 215 B208            # time + itinerary
    python -m schoolmap 215 B208 --json     # machine-readable
    python -m schoolmap --rooms [FLOOR]     # list rooms
    python -m schoolmap --viewer            # open the 3-D viewer in the browser
"""
import argparse
import json
import sys
import webbrowser

import schoolmap


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m schoolmap", description="Walking time between rooms of the school.")
    ap.add_argument("origin", nargs="?")
    ap.add_argument("destination", nargs="?")
    ap.add_argument("--speed", type=float, help="walking speed m/s (default 1.2)")
    ap.add_argument("--lifts", action="store_true", help="allow lifts")
    ap.add_argument("--closed", nargs="*", default=(), help="connector ids to close, e.g. S5")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rooms", nargs="?", const="ALL", help="list rooms (optionally of one floor)")
    ap.add_argument("--viewer", action="store_true", help="open the interactive 3-D viewer")
    a = ap.parse_args(argv)
    if a.viewer:
        webbrowser.open(schoolmap.viewer_path().resolve().as_uri())
        return 0
    if a.rooms:
        for r in schoolmap.rooms(None if a.rooms == "ALL" else a.rooms.upper()):
            print(f"{r['id']:>9}  {r['floor']:>2}  {r['kind']:<9} {r['name']}")
        return 0
    if not (a.origin and a.destination):
        ap.print_help()
        return 1
    r = schoolmap.route(a.origin, a.destination, walk_speed=a.speed, elevator=a.lifts or None,
                        disabled_connectors=tuple(s.upper() for s in a.closed))
    if a.json:
        d = r.to_dict()
        for leg in d["legs"]:
            leg.pop("path")
        print(json.dumps(d, indent=2))
    else:
        print(r.summary())
        print(f"  walking {r.walk_m:.0f} m = {r.walk_s:.0f} s, stairs {r.vertical_s:.0f} s, "
              f"floors up {r.floors_up} / down {r.floors_down}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
