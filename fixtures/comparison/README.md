# Core 1.0 comparison tasks

This directory evaluates authoring and review effectiveness; it is separate from machine performance fixtures. Each task has
equivalent baseline Markdown and Bitz conditions. Participants must not read `answer-key.json` before completing a task.

Use `protocol.json` as the normative procedure. Assign conditions in balanced AB/BA order, use a clean task copy, prohibit network
and external assistance, and record all four required metrics. A task is complete only when its completion criteria pass blind review.
The five task definitions, protocol, answer key, and result schema are versioned together; changing one requires a new protocol version.

Validate `tasks/*.json` with `task.schema.json`, `protocol.json` with `protocol.schema.json`, `answer-key.json` with
`answer-key.schema.json`, and observations with `result.schema.json`.
