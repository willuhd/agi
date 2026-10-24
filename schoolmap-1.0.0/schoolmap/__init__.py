"""schoolmap - metric space model of the school building + walking-time engine.

Quick use (only needs numpy):

    import schoolmap
    schoolmap.travel_time("101", "B216")     # -> seconds (float)
    schoolmap.route("101", "B216")           # -> Route (legs, stairs, metres, polylines)
    ids, T = schoolmap.matrix()              # -> room ids, numpy seconds matrix

Scenarios: schoolmap.travel_time("101", "410", walk_speed=1.0, elevator=True,
                                 disabled_connectors=("S5",))
Times are room-centre to room-centre; stairs cost 15 s per floor up and 10 s per floor down.
"""
from functools import lru_cache

from .model import Building, Leg, Route  # noqa: F401

__version__ = "1.0.0"
__all__ = ["Building", "Route", "Leg", "load", "travel_time", "route", "matrix", "rooms", "viewer_path"]


@lru_cache(maxsize=16)
def _cached(walk_speed=None, elevator=None, disabled_connectors=()):
    return Building.load(walk_speed=walk_speed, elevator=elevator, disabled_connectors=tuple(disabled_connectors))


def load(walk_speed=None, elevator=None, disabled_connectors=()) -> Building:
    """The bundled building model (cached).  Arguments override the default timing."""
    return _cached(walk_speed, elevator, tuple(disabled_connectors))


def travel_time(origin: str, destination: str, **scenario) -> float:
    """Seconds to walk from room `origin` to room `destination` (e.g. "215", "B208")."""
    return load(**scenario).travel_time(origin, destination)


def route(origin: str, destination: str, **scenario) -> Route:
    """Full itinerary: .seconds, .walk_m, .vertical_s, .floors_up/.floors_down, .legs, .summary()."""
    return load(**scenario).route(origin, destination)


def matrix(ids=None, **scenario):
    """(room_ids, T) with T[i, j] = seconds from ids[i] to ids[j] (not symmetric: up != down)."""
    return load(**scenario).matrix(ids)


def rooms(floor=None) -> list:
    """Room records (id, name, kind, floor, area_m2, anchor, polygon, doors)."""
    b = load()
    return [b.rooms[i] for i in b.room_ids(floor)]


def viewer_path():
    """Path of the bundled interactive 3-D viewer (open it in a browser)."""
    from pathlib import Path
    return Path(__file__).with_name("data") / "viewer.html"
