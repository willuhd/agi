"""Minimal use of the walking-time engine (only numpy needed)."""
import schoolmap

# 1. one number: seconds from room 215 to room B208
print(schoolmap.travel_time("215", "B208"))

# 2. the full itinerary
r = schoolmap.route("215", "B208")
print(r.summary())
for leg in r.legs:
    print(f"  {leg.kind:<6} {leg.floor:<8} {leg.seconds:5.1f} s  {leg.via}")

# 3. scenarios: slower crowd during class change, lifts allowed, a stairwell closed
print(schoolmap.travel_time("215", "B208", walk_speed=1.0))
print(schoolmap.travel_time("215", "B208", elevator=True))
print(schoolmap.travel_time("215", "B208", disabled_connectors=("S1",)))

# 4. the whole matrix for an optimiser
ids, T = schoolmap.matrix()
print(len(ids), "rooms; 101 -> 410:", T[ids.index("101"), ids.index("410")], "s")
