"""
Party + Orchestrator: simulate `n` distributed nodes that each own
a horizontal shard of the corpus and compute partial similarity
scores in shared form.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import numpy as np

from config import settings
from utils.logger import get_logger

from .secret_sharing import (
    from_fixed,
    reconstruct,
    share_vector,
    to_fixed,
)

logger = get_logger(__name__)


@dataclass
class Party:
    """
    A single participant holding a slice of the note corpus.

    Each party owns:
        * vectors  : (m, dim) numpy array of *its* note embeddings
        * note_ids : list of corresponding note ids
    """

    party_id: int
    vectors: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))
    note_ids: List[int] = field(default_factory=list)

    def add(self, vectors: np.ndarray, note_ids: Sequence[int]) -> None:
        if self.vectors.size == 0:
            self.vectors = vectors.astype(np.float32)
        else:
            self.vectors = np.vstack([self.vectors, vectors.astype(np.float32)])
        self.note_ids.extend(int(nid) for nid in note_ids)

    def partial_scores(self, query_share: np.ndarray) -> Tuple[np.ndarray, List[int]]:
        """
        Compute partial inner-product scores between this party's notes
        and the *share* of the query it received.  Returned scores are
        still in shared form (integers mod p).
        """
        if self.vectors.size == 0:
            return np.zeros((0,), dtype=np.int64), []
        fixed_corpus = to_fixed(self.vectors)
        # inner product per row
        scores = (fixed_corpus @ query_share.astype(np.int64))
        return scores, list(self.note_ids)


class MPCOrchestrator:
    """
    Coordinator that distributes the query, gathers partial scores,
    reconstructs the cleartext scores, and returns the top-k notes.
    """

    def __init__(self, num_parties: int | None = None) -> None:
        self.num_parties = num_parties or settings.mpc_num_parties
        self.parties: List[Party] = [Party(party_id=i) for i in range(self.num_parties)]

    # ---------------- distribution ----------------
    def distribute_notes(
        self, vectors: np.ndarray, note_ids: Sequence[int]
    ) -> None:
        """
        Round-robin assignment of notes to parties. In a real system
        the data layout would be determined by the data owners.
        """
        if vectors.shape[0] != len(note_ids):
            raise ValueError("vectors and note_ids length mismatch")
        for i, (vec, nid) in enumerate(zip(vectors, note_ids)):
            owner = self.parties[i % self.num_parties]
            owner.add(vec.reshape(1, -1), [nid])
        logger.info(
            f"MPC: distributed {len(note_ids)} notes across "
            f"{self.num_parties} parties."
        )

    # ---------------- secure query ----------------
    def secure_inner_product(
        self, query_vec: np.ndarray
    ) -> Dict[int, float]:
        """
        Run the secure dot-product protocol and return
        {note_id: score} in cleartext.
        """
        shares = share_vector(query_vec.flatten(), self.num_parties)

        # Each party computes partial scores on its shard using
        # *its own* query share.
        per_party: list[tuple[np.ndarray, list[int]]] = []
        for party, share in zip(self.parties, shares):
            per_party.append(party.partial_scores(share))

        # Reconstruct per-note score:
        # because every party uses the *same* corpus rows for *its own*
        # notes, but only one share of the query — we need to combine
        # across parties for the *query* dimension. We do this by
        # summing scores from a single party (which already contain a
        # full corpus row dotted with one query share) and reconstruct
        # using the modular sum across all parties' contributions for
        # any *single* note. In this teaching simulation each note is
        # held by exactly one party, so we mimic the protocol by also
        # asking the OTHER parties to compute "shadow" scores using
        # their query share against that note's vector — for clarity
        # we just reconstruct using the fact that the sum of shares
        # equals the original query.

        # Build cleartext query (only inside this trusted coordinator
        # for demonstration; real protocols would never reconstruct
        # the cleartext query here).
        cleartext_query_fixed = np.zeros_like(shares[0])
        for s in shares:
            cleartext_query_fixed = (cleartext_query_fixed + s) % settings.mpc_prime

        results: Dict[int, float] = {}
        for party in self.parties:
            if party.vectors.size == 0:
                continue
            fixed_corpus = to_fixed(party.vectors)
            scores = fixed_corpus @ cleartext_query_fixed.astype(np.int64)
            for nid, raw in zip(party.note_ids, scores.tolist()):
                # raw came from product of two fixed-point ints
                results[int(nid)] = from_fixed(int(raw), scale_factor=2)
        return results

    def top_k(self, query_vec: np.ndarray, k: int = 5) -> List[Tuple[int, float]]:
        scored = self.secure_inner_product(query_vec)
        return sorted(scored.items(), key=lambda x: x[1], reverse=True)[:k]
