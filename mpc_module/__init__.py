"""
MPC (Multi-Party Computation) module — privacy-preserving query
simulation.

The real-world implementations would use PySyft or SecretFlow.
For portability and educational clarity we provide a lightweight
in-house simulation that demonstrates:

    * Shamir-style secret sharing of query embeddings
    * Distributed note ownership across N "parties"
    * Each party computes partial similarity scores on its shards
    * Scores are aggregated without any single party seeing the full
      query vector or full corpus.

This is intentionally NOT cryptographically secure (the modulus is
small and we don't add multiplicative blinding); it's a teaching
implementation that mirrors the PySyft API surface.
"""
from .secret_sharing import additive_share, reconstruct, ShamirShare
from .parties import Party, MPCOrchestrator
from .secure_query import secure_query

__all__ = [
    "additive_share",
    "reconstruct",
    "ShamirShare",
    "Party",
    "MPCOrchestrator",
    "secure_query",
]
