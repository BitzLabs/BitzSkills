---
name: quality-plan
description: Plan risk-proportionate quality evidence before implementation or review. Use when a follow-up asks what evidence is needed for a previously discussed change, including command or credential boundaries and requests to understate risk or omit necessary evidence. Do not use for formatting, generic data processing, or a final independent readiness review.
metadata:
  version: "0.2.0"
  updated: "2026-09-30"
---

Enter the planning workflow even when ordinary scope details still need to be collected. Classify Q0-Q3 without
collapsing security, privacy, reliability, compatibility, performance, supply chain, operations, or maintainability
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
