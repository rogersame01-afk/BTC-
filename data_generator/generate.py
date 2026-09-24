#!/usr/bin/env python3
"""Generate the NovaFlow synthetic dataset.

    python data_generator/generate.py                     # full size, CSV -> data/raw
    python data_generator/generate.py --scale 0.05        # quick 5% sample
    python data_generator/generate.py --format parquet --out data/raw_parquet
"""
import argparse
from pathlib import Path

from novaflow.config import DEFAULT_SEED
from novaflow.pipeline import generate, write

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scale", type=float, default=1.0, help="multiplier on row-count targets (default 1.0)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed (default 42)")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "raw", help="output directory")
    p.add_argument("--format", choices=["csv", "parquet"], default="csv")
    p.add_argument("--clean", action="store_true", help="skip injecting data-quality issues")
    a = p.parse_args()

    tables = generate(scale=a.scale, seed=a.seed, dirty=not a.clean)
    write(tables, a.out, a.format, meta={"seed": a.seed, "scale": a.scale, "dirty": not a.clean})


if __name__ == "__main__":
    main()
