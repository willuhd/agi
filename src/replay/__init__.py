"""Break-time dot replay on the existing floor-plan art.

Additive frontend only: renders base floor panels with the same tt.viz.plan
renderer that produced docs/img/floorplans.svg, then animates student (blue)
and teacher (red) dots per break from a finished timetable. Motion is
schematic straight lines (not corridor routing); cross-floor movers fade out
at origin and fade in at destination. If output/elevator_sim.json exists its
peak-break waits are shown alongside.
"""
