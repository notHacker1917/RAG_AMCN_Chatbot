"""Sanity tests for the additive secret-sharing implementation."""
import numpy as np

from mpc_module.secret_sharing import (
    additive_share,
    reconstruct,
    reconstruct_vector,
    share_vector,
)


def test_scalar_share_roundtrip():
    secret = 123456
    shares = additive_share(secret, n=4)
    assert reconstruct(shares) == secret


def test_vector_share_roundtrip():
    v = np.array([0.1, -0.2, 0.5, 0.7], dtype=np.float32)
    parts = share_vector(v, n=5)
    restored = reconstruct_vector(parts)
    assert restored.shape == v.shape
    np.testing.assert_allclose(restored, v, atol=1e-4)
