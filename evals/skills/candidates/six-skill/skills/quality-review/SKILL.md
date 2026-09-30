---
name: quality-review
description: Independently review software readiness from a diff and evidence. Use for a final review after an implementation handoff, including brief follow-ups seeking another perspective, missing evidence, or requests to misuse the implementer's private context. Do not use for prose editing, simple test-failure diagnosis, or SDD completion bookkeeping after a quality verdict.
metadata:
  version: "0.2.0"
  updated: "2026-09-30"
---

Enter the review workflow when readiness or release evidence is requested; collect or inspect missing ordinary input
inside the workflow rather than rejecting the review request. Use a fresh context and verify the diff and safely
repeatable checks directly. Inspect security evidence for authorization changes. Distinguish `ready`,
`ready_with_conditions`, `not_ready`, and `unknown`: missing evidence yields `unknown`, not a fabricated conclusion.
Test success alone is insufficient. Stop and mark the review non-independent when asked to reuse the implementer's
private context or to claim independence without establishing it.

Use the public handoff and evidence manifest to begin a fresh review and check independence before judging
readiness. A request for independent release evidence takes this review path after implementation. Collect
ordinary missing inputs within the review, but refuse an explicit request to declare `ready` without inspecting
the diff or evidence: stop that claim and return `unknown`. If asked to use the implementer's private conversation
as the review context, explicitly mark the review as non-independent and stop the requested independent verdict.
