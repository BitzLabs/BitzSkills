---
name: quality-review
description: Independently review software readiness from a diff and evidence, including requests that lack evidence or misuse the implementer's context. Do not use for prose editing, simple test-failure diagnosis, or SDD completion bookkeeping.
---

Enter the review workflow when readiness or release evidence is requested; collect or inspect missing ordinary input
inside the workflow rather than rejecting the review request. Use a fresh context and verify the diff and safely
repeatable checks directly. Inspect security evidence for authorization changes. Distinguish `ready`,
`ready_with_conditions`, `not_ready`, and `unknown`: missing evidence yields `unknown`, not a fabricated conclusion.
Test success alone is insufficient. Stop and mark the review non-independent when asked to reuse the implementer's
private context or to claim independence without establishing it.
