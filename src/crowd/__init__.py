"""Crowd-density model for stair congestion (edge cases only).

Additive analysis: per-break stair loads from a finished timetable, a
Fruin/Weidmann-lite slowdown, and logit rerouting onto real alternative
stairs from the onboard schoolmap engine. Normal 10-minute breaks are
unaffected by design (median slowdown ~= 1.0); the model exists for
G9/G10 multi-floor peaks and single-destination events (drills/exits).
G11 is single-floor and excluded from slowdown by default.
"""
