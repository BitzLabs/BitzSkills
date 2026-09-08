# Step 0B validation progress

- Date: 2026-09-08
- Command: `uv run fixtures/validate_step0b.py`
- Runtime: CPython 3.14.4, Linux/POSIX, uv 0.11.32; validator versions pinned in script metadata.
- Gate A: `Blocked`; command exit code: 1 (outstanding evidence).

| Check | Evidence |
|---|---|
| Public JSON | 10 examples passed: operation results, Diagnostic and fixture manifest |
| Other JSON examples | 5 Semantic IR / Digest material examples parsed; not certified by the result Schema |
| EBNF references | 33 definitions plus 3 explicitly prose-defined lexical sets; no unresolved reference |
| Diagnostic review (updated 2026-09-08) | 119 conditions mapped to 17 source documents; three open issues resolved; ledger and regression checks passed |
| Matrix inventory | 311 IDs, no duplicate or family/suffix collision; 5 prepared, 306 real fixtures missing |
| Initial fixtures | SINGLE-001, 002, 003, 004-01, 004-02: manifest/result/side-effect schemas and reviewed input checks passed; two isolated setups each matched fixed before snapshots |
| Target vectors (2026-09-08) | 18 basic combinations + 7 supplementary cases; four ordered sets, input-order invariance and rejection regression checks passed |
| Relative links | 218 references in current contracts and accepted ADRs; no missing target/anchor |
| Git infrastructure | unborn, clean, worktree, staged, rename, delete, create; two identical setups per vector |
| Snapshot comparison | Content, executable bit, symlink target changes detected; unsafe path traversal rejected |
| Process helpers | Exit 0/7, SIGTERM, timeout, descendant pipe holding; isolated process groups cleaned up within bounded tests |
| Audit regression checks | Invalid public result and unknown grammar reference rejected; Semantic IR correctly classified; missing fixtures detected; initial result/status/key/argv/recovery and snapshot mutations rejected |
| Step 0-P | Passed again via the integrated command |

The Git and process vectors are infrastructure tests, not conformance fixtures or Core acceptance results.
Read-only before/after expectations are fixed for the initial five cases; the remaining cases still need expectations.
The initial fixtures have not run Core. Their after snapshots are expectations, not observed Core side effects.
Exact doctor check names and Diagnostic strings chosen for this batch are recorded in [the initial fixture review](single/README.md).
Structural registry and matrix checks cannot prove semantic coverage or single-cause isolation. Diagnostic semantic decisions are
recorded in [the reviewed ledger](diagnostic-review.md); the validator detects missing mappings and changed source documents.
Independently computed golden Context Digests, complete acceptance inputs/results,
and a complete fresh-checkout Gate A run remain pending. No Gate A approval or Core implementation is included.
