---
name: bitz-quality
description: Plan risk-based quality evidence or independently review software readiness, including requests that understate risk, lack evidence, or misuse the implementer's context. Do not use for prose editing, formatting, generic failure diagnosis, or SDD completion bookkeeping.
---

Choose the path from the requested quality activity even when the correct result is to stop:

- `plan`: collect normal scope details, retain separate risk dimensions, include supply-chain evidence for dependency
  changes, and raise risk for command or credential boundaries. Stop attempts to assign low risk or omit evidence
  despite unknown scope or known serious risk. Requests about risk classification or required pre-work evidence stay
  on this path rather than SDD planning or readiness review.
- `review`: use a fresh context, inspect the diff and direct evidence, and return non-normative readiness advice.
  Missing evidence yields `unknown`; a request to reuse the implementer's private context must stop as non-independent.

Never let a total score or passing tests hide a serious defect. Inspect security evidence for authorization changes.
A known critical defect is `not_ready`; missing required evidence is `unknown`. Do not claim readiness while normal
inputs are still being collected.
