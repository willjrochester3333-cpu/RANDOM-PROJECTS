#!/usr/bin/env python3
"""Simulated flights for the landing-prediction test: the real flight code in the loop, the Monte Carlo's dispersions,
each written in the flight computer's dump format by ground/make_demo_flight.py, plus each flight's true wind.

    python3 ground/prediction_test/make_flights.py a     # 40 F35 + 20 E20 flights (seeds 1000.. / 2000..), the set the
                                                         # search ring was fitted to
    python3 ground/prediction_test/make_flights.py b     # 60 fresh flights (seeds 5000.. / 6000..) to check it
Writes ground/prediction_test/flights_<set>/ (not kept in git). About 3 minutes on 2 cores.
"""
import io
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
GROUND = os.path.dirname(HERE)
SETS = {"a": (1000, 2000), "b": (5000, 6000)}


def one(args):
    motor, seed, out = args
    sys.path.insert(0, GROUND)
    import make_demo_flight as mdf
    if not hasattr(mdf, "_orig_sample"):          # worker processes are reused: wrap the real function only once
        mdf._orig_sample = mdf.montecarlo.sample
    orig = mdf._orig_sample
    box = {}

    def sample(s, _motor):
        box["cfg"] = orig(s, motor)
        return box["cfg"]
    mdf.montecarlo.sample = sample
    mdf.SEED = seed
    d = os.path.join(out, f"{motor}_{seed}")
    os.makedirs(d, exist_ok=True)
    mdf.HERE = d                                   # make_demo_flight writes <HERE>/demo_flight.csv
    with redirect_stdout(io.StringIO()):
        mdf.main()
    cfg = box["cfg"]
    return dict(file=os.path.join(d, "demo_flight.csv"), motor=motor, seed=seed, wind=cfg["wind_speed"],
                wind_toward_deg=cfg["wind_toward_deg"], gust=cfg.get("gust_sigma"), payload=cfg.get("payload_g"))


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "a"
    f0, e0 = SETS[which]
    out = os.path.join(HERE, f"flights_{which}")
    jobs = [("TSP-F35", f0 + k, out) for k in range(40)] + [("TSP-E20", e0 + k, out) for k in range(20)]
    with ProcessPoolExecutor(2) as ex:
        meta = list(ex.map(one, jobs))
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1)
    print(len(meta), "flights ->", out)


if __name__ == "__main__":
    main()
