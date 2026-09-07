# Step 0-P validation

- Date: 2026-09-07
- Result: `Passed`
- Command: `uv run fixtures/validate_step0p.py`
- Validation runtime: CPython 3.14.4, Linux; dependencies pinned in the script metadata.
- Scope: preparation of performance/comparison inputs; this is not a Core performance baseline or Gate A approval.

| Check | Result |
|---|---|
| Draft 2020-12 schema structure | 8 schemas passed, including both future result schemas |
| Dataset, environment, plan, task, protocol, answer-key inputs | 11 JSON inputs passed |
| Benchmark dataset/environment references and task inventory | Passed |
| Single dataset generation | 2 runs matched: 300 SPEC, 1,000 statements, 5,000 relations |
| Federation dataset generation | 2 runs matched: 20 workspaces, 1,000 SPEC, 1,000 statements, 20,000 relations |
| Shape expectations | Exact byte count, statements/SPEC and directed edge density matched |
| Corrupted shape expectations | Both datasets rejected |
| Context input closure | Generator confirmed 20 documents, 1/3 workspaces and input byte budget |

Expected tree digests remained unchanged:

- Single: `sha256:0693e6ec926d4a411766796831e87c011004342810a5e6f3393e7afcd52c546c`
- Federation: `sha256:ad519b9442984ab9bce488ba1aa05277e9077bad178f89378a90e5f458134c25`

The validation runtime is distinct from the CPython 3.11.x performance reference environment.
Core output size, performance baseline, and participant observations remain pending until the relevant Core implementation exists.
Step 0B still requires the conformance fixtures and its complete fresh-checkout validation command; Step 0-P completion does not open Gate A.
