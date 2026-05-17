"""
Simple additive secret-sharing helpers.

A secret `x` is split into `n` shares `(s_1, …, s_n)` such that
`sum(s_i) mod p = x`. Each share alone reveals nothing about `x`
when the modulus `p` is large.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import List, Sequence

import numpy as np

from config import settings


@dataclass(frozen=True)
class ShamirShare:
    """
    Stand-in for a proper Shamir share. In this simulation it carries
    an additive share plus a party id.
    """

    party_id: int
    value: int


def additive_share(value: int, n: int, prime: int | None = None) -> List[int]:
    """Split `value` into `n` additive shares modulo `prime`."""
    p = prime or settings.mpc_prime
    shares: list[int] = []
    acc = 0
    for _ in range(n - 1):
        s = secrets.randbelow(p)
        shares.append(s)
        acc = (acc + s) % p
    shares.append((value - acc) % p)
    return shares


def reconstruct(shares: Sequence[int], prime: int | None = None) -> int:
    """Reconstruct the original secret from its additive shares."""
    p = prime or settings.mpc_prime
    return sum(shares) % p


# ---- Float ↔ fixed-point helpers (so we can share embedding vectors) ----
_FIXED_SCALE = 1_000_000  # 6 decimal digits of precision


def to_fixed(arr: np.ndarray) -> np.ndarray:
    """Convert a float array to int64 fixed-point representation."""
    return (arr * _FIXED_SCALE).astype(np.int64)


def from_fixed(x: int | float, scale_factor: int = 1) -> float:
    """
    Convert a (possibly multiplied) fixed-point integer back to float.
    `scale_factor` is the number of times two fixed-point values have
    been multiplied together (each multiplication squares the scale).
    """
    return float(x) / (_FIXED_SCALE ** scale_factor)


def share_vector(vec: np.ndarray, n: int, prime: int | None = None) -> List[np.ndarray]:
    """Element-wise additive share of a float vector."""
    fixed = to_fixed(vec.flatten())
    p = prime or settings.mpc_prime
    parts = [np.zeros_like(fixed) for _ in range(n)]
    acc = np.zeros_like(fixed)
    for i in range(n - 1):
        rnd = np.array(
            [secrets.randbelow(p) for _ in range(fixed.size)], dtype=np.int64
        )
        parts[i] = rnd
        acc = (acc + rnd) % p
    parts[-1] = (fixed - acc) % p
    return parts


def reconstruct_vector(shares: Sequence[np.ndarray], prime: int | None = None) -> np.ndarray:
    """Recombine additively-shared vector."""
    p = prime or settings.mpc_prime
    summed = np.zeros_like(shares[0])
    for s in shares:
        summed = (summed + s) % p
    # Re-centre values that crossed the modulus boundary
    half = p // 2
    summed = np.where(summed > half, summed - p, summed)
    return summed.astype(np.float64) / _FIXED_SCALE
