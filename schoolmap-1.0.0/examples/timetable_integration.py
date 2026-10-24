"""How a timetable optimiser can use the engine.

Score a student's day by the walking time between consecutive lessons and check which
changeovers do not fit in the break.  Swap in your own timetable structure.
"""
import schoolmap

BREAK_S = 5 * 60          # passing time between lessons

# one student's day: list of rooms in lesson order
day = ["215", "B208", "410", "109", "B217", "305"]

total = 0.0
for a, b in zip(day, day[1:]):
    t = schoolmap.travel_time(a, b)
    total += t
    flag = "  <-- longer than the break" if t > BREAK_S else ""
    print(f"{a:>5} -> {b:<5} {t:6.1f} s{flag}")
print(f"total walking time: {total:.0f} s")

# for an optimiser it is usually faster to grab the matrix once and index it
ids, T = schoolmap.matrix()
idx = {r: i for i, r in enumerate(ids)}


def movement_cost(rooms_in_order):
    return sum(T[idx[a], idx[b]] for a, b in zip(rooms_in_order, rooms_in_order[1:]))


print("cost via matrix:", round(movement_cost(day), 1), "s")
