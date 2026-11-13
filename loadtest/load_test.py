"""Load test for the MaintainOps API against real PostgreSQL.

Start the stack (docker compose up), then:
    python loadtest/load_test.py --base http://localhost:8000

Three checks:
  reads        50 clients hit the list and dashboard endpoints for 30 s.
  restocks     200 restocks of one part at a time, 50 and then 100 at once;
               stock must rise by exactly the number of 201 responses.
  maintenance  200 maintenance logs at 100 at once, each using the same two
               parts; stock must fall by exactly the number of 201 responses.

Note: this writes to the database it points at. Use a throwaway database.
"""
import argparse
import asyncio
import json
import random
import time

import httpx

READS = ["/equipment", "/parts", "/dashboard/summary", "/alerts/low-stock", "/activity"]


def pct(sorted_ms, q):
    return round(sorted_ms[max(0, int(len(sorted_ms) * q) - 1)], 1)


async def reads(base, conc=50, seconds=30):
    lat, codes = [], {}
    stop = time.perf_counter() + seconds
    async with httpx.AsyncClient(base_url=base, timeout=30, limits=httpx.Limits(max_connections=conc)) as c:
        async def worker():
            while time.perf_counter() < stop:
                t = time.perf_counter()
                try:
                    k = (await c.get(random.choice(READS))).status_code
                except Exception as e:
                    k = type(e).__name__
                lat.append((time.perf_counter() - t) * 1000)
                codes[k] = codes.get(k, 0) + 1
        t0 = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(conc)])
        el = time.perf_counter() - t0
    lat.sort()
    return dict(check="reads", clients=conc, requests=len(lat), rps=round(len(lat) / el, 1),
                p50_ms=pct(lat, .5), p95_ms=pct(lat, .95), codes=codes)


async def burst(base, conc, n, make_request, stock_part, sign):
    sem = asyncio.Semaphore(conc)
    lat, codes = [], {}
    async with httpx.AsyncClient(base_url=base, timeout=90, limits=httpx.Limits(max_connections=conc)) as c:
        before = (await c.get(f"/parts/{stock_part}")).json()["quantity_on_hand"]

        async def one(i):
            async with sem:
                t = time.perf_counter()
                try:
                    k = (await make_request(c, i)).status_code
                except Exception as e:
                    k = type(e).__name__
                lat.append((time.perf_counter() - t) * 1000)
                codes[k] = codes.get(k, 0) + 1

        t0 = time.perf_counter()
        await asyncio.gather(*[one(i) for i in range(n)])
        el = time.perf_counter() - t0
        after = (await c.get(f"/parts/{stock_part}")).json()["quantity_on_hand"]
    lat.sort()
    ok = codes.get(201, 0)
    changed = (after - before) * sign
    return dict(clients=conc, requests=n, seconds=round(el, 1), codes=codes, p95_ms=pct(lat, .95),
                stock_changed=changed, matches_201s=changed == ok)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    base = ap.parse_args().base
    await reads(base, 10, 3)  # warm-up
    print(json.dumps(await reads(base)))

    def restock(c, i):
        return c.post("/parts/1/restock", json={"quantity": 1, "unit_cost": "4.50", "supplier": "loadtest"})
    for conc in (50, 100):
        print(json.dumps(dict(check="restocks", **await burst(base, conc, 200, restock, 1, +1))))

    async with httpx.AsyncClient(base_url=base) as c:
        equipment = [e["id"] for e in (await c.get("/equipment")).json()]
        for pid in (1, 2):
            await c.post(f"/parts/{pid}/restock", json={"quantity": 1000, "unit_cost": "1.00", "supplier": "loadtest"})

    def maintenance(c, i):
        return c.post("/maintenance-logs", json={
            "equipment_id": equipment[i % len(equipment)], "description": "load test",
            "parts_used": [{"part_id": 2, "quantity": 1}, {"part_id": 1, "quantity": 1}]})
    print(json.dumps(dict(check="maintenance", **await burst(base, 100, 200, maintenance, 2, -1))))


if __name__ == "__main__":
    asyncio.run(main())
