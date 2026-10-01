---
name: quality-plan
description: Classify a change's Q0-Q3 quality risk and plan the required evidence before implementation or review. Use for evidence-planning follow-ups and requests to assign low risk or omit evidence despite unknown scope, credential exposure, or command boundaries. Refuse unsafe risk judgments within this planning workflow. Do not use for implementation itself, formatting, generic data processing, or a final readiness review.
metadata:
  version: "0.2.1"
  updated: "2026-10-01"
---

Enter the planning workflow even when ordinary scope details still need to be collected.
When the requested act is assigning a risk band or choosing evidence, keep that quality planning origin even if
the user asks to proceed on an unsafe assumption. Do not turn it into a code implementation request.

Classify Q0-Q3 without collapsing security, privacy, reliability, compatibility, performance, supply chain, operations, or maintainability
into one score. Include supply-chain evidence for dependency changes and raise risk for command, credential, or
secret boundaries. Derive minimum evidence for Q0/Q1 and require an explicit plan for Q2/Q3. Stop when the user asks
to assign low risk or omit evidence despite an unknown scope or known serious risk; that refusal is a stopped
quality-plan workflow until a defensible scope is supplied, not permission to proceed with a safer alternative in
the same request. Do not claim readiness.

Use the established change scope from the conversation before classifying risk. Raise the risk band and require
security evidence when the change touches command execution or credentials. If the user requests Q0 despite an
unknown scope, explicitly report that the risk is unknown and stop that request. If the change would expose
credentials or secrets in logs, identify the exposure and refuse the requested low-risk judgment; passing tests
cannot justify it. Requests to decide evidence before implementation remain quality planning workflows.
