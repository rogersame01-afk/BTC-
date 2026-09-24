"""Date helpers and sampling utilities shared by all generators.

Dates inside the simulation are Python ordinals (ints, days since 0001-01-01)
because they are cheap to do arithmetic on in tight loops; they are converted
to numpy datetime64 when the DataFrames are assembled.
"""
from calendar import monthrange
from datetime import date

import numpy as np
import pandas as pd

from .config import END_DATE, START_DATE

START_ORD = START_DATE.toordinal()
END_ORD = END_DATE.toordinal()
EPOCH_ORD = date(1970, 1, 1).toordinal()
DAY_SECONDS = 86_400


def add_months(ordinal: int, months: int) -> int:
    d = date.fromordinal(ordinal)
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, monthrange(y, m)[1])).toordinal()


def quarter_end(ordinal: int) -> int:
    d = date.fromordinal(ordinal)
    q_month = ((d.month - 1) // 3 + 1) * 3
    return date(d.year, q_month, monthrange(d.year, q_month)[1]).toordinal()


def ord_to_date(ords) -> np.ndarray:
    """Ordinals (-1 = missing) -> datetime64[D] array with NaT for missing."""
    a = np.asarray(ords, dtype=np.int64)
    out = (a - EPOCH_ORD).astype("datetime64[D]")
    out[a < 0] = np.datetime64("NaT")
    return out


def ord_to_ts(ords, seconds) -> np.ndarray:
    """Ordinals + seconds-of-day -> datetime64[s] (NaT where ordinal is -1)."""
    a = np.asarray(ords, dtype=np.int64)
    s = np.asarray(seconds, dtype=np.int64)
    out = ((a - EPOCH_ORD) * DAY_SECONDS + s).astype("datetime64[s]")
    out[a < 0] = np.datetime64("NaT")
    return out


def business_seconds(rng: np.random.Generator, n: int) -> np.ndarray:
    """Time-of-day in seconds, concentrated in business hours."""
    in_hours = rng.random(n) < 0.82
    h = np.where(in_hours, np.clip(rng.normal(12.5, 2.4, n), 7.0, 19.5), rng.uniform(0, 24, n))
    return np.minimum((h * 3600).astype(np.int64), DAY_SECONDS - 1)


def growth_day_ordinals(rng, n, start=START_ORD, end=END_ORD, growth=1.0,
                        weekend_factor=0.3, quarter_end_boost=0.0) -> np.ndarray:
    """Sample n day ordinals between start and end with an exponential growth
    trend, weekday seasonality and an optional end-of-quarter bump."""
    days = np.arange(start, end + 1)
    t = (days - start) / max(end - start, 1)
    w = np.exp(growth * t)
    dow = (days + 6) % 7  # ordinal 1 (0001-01-01) is a Monday -> dow 0
    w = w * np.where(dow >= 5, weekend_factor, 1.0)
    if quarter_end_boost:
        dates = pd.to_datetime(ord_to_date(days))
        dte = ((dates + pd.offsets.QuarterEnd(0)) - dates).days.values
        w = w * (1 + quarter_end_boost * (dte < 14))
    return rng.choice(days, size=n, p=w / w.sum())


def weekday_shift(ords: np.ndarray, rng, keep_weekend=0.15) -> np.ndarray:
    """Move most weekend dates back to the preceding Friday (sales behaviour)."""
    ords = np.asarray(ords).copy()
    dow = (ords + 6) % 7
    move = (dow >= 5) & (rng.random(len(ords)) > keep_weekend)
    ords[move] -= dow[move] - 4
    return ords


def weighted_choice(rng, mapping: dict, n: int):
    keys = list(mapping)
    p = np.array([mapping[k] for k in keys], dtype=float)
    return rng.choice(np.array(keys, dtype=object), size=n, p=p / p.sum())


def make_ids(prefix: str, n: int, start: int = 1, width: int = 7) -> np.ndarray:
    return np.char.add(f"{prefix}-", np.char.zfill(np.arange(start, start + n).astype(str), width)).astype(object)


def fmt_id(prefix: str, i: int, width: int = 7) -> str:
    return f"{prefix}-{i:0{width}d}"
