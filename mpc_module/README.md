# MPC Module — Privacy-Preserving Query Simulation

This package demonstrates how a Retrieval-Augmented Generation system
*could* operate when no single participant is trusted with the full
corpus or the full query.

## Concept

```
┌──────────────────────────────────────────────────────────────────┐
│                       Coordinator (no data)                      │
│      build query shares q_1, q_2, …, q_n  s.t.  Σ q_i = q        │
└──────────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Party 1    │ │   Party 2    │ │     ...      │ │   Party n    │
│ owns shard 1 │ │ owns shard 2 │ │              │ │ owns shard n │
│ computes     │ │ computes     │ │              │ │ computes     │
│ partial s_1  │ │ partial s_2  │ │              │ │ partial s_n  │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                              │
                              ▼
              cleartext top-k note IDs only
```

## Limitations

* The orchestrator briefly reconstructs the query inside this
  educational implementation — a real protocol (e.g. SPDZ) would
  keep it secret-shared end-to-end.
* The modulus is small (`MPC_PRIME = 2^31 - 1`) and there is no
  authentication or maliciously-secure check.
* No fixed-point overflow handling for very long vectors.

## When to plug in real frameworks

`PySyft`, `SecretFlow`, `tf-encrypted`, or `MP-SPDZ` can be dropped
into `parties.py` and `secret_sharing.py` without changing the public
`secure_query()` API used by the Flask blueprint.
