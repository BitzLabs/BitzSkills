# Step 0B validation progress

- Date: 2026-09-07
- Command: `uv run fixtures/validate_step0b.py`
- Runtime: CPython 3.14.4, Linux/POSIX, uv 0.11.32; validator versions pinned in script metadata.
- Gate A: `Blocked`; command exit code: 1 (outstanding evidence).

| Check | Evidence |
|---|---|
| Public JSON | 10 examples passed: operation results, Diagnostic and fixture manifest |
| Other JSON examples | 5 Semantic IR / Digest material examples parsed; not certified by the result Schema |
| EBNF references | 33 definitions plus 3 explicitly prose-defined lexical sets; no unresolved reference |
| Registry structure | 115 unique conditions; severity/status vocabulary checked; semantic coverage pending |
| Matrix inventory | 311 IDs, no duplicate or family/suffix collision; all 311 real fixtures missing |
| Relative links | 218 references in current contracts and accepted ADRs; no missing target/anchor |
| Git infrastructure | unborn, clean, worktree, staged, rename, delete, create; two identical setups per vector |
| Snapshot comparison | Content, executable bit, symlink target changes detected; unsafe path traversal rejected |
| Process helpers | Exit 0/7, SIGTERM, timeout, descendant pipe holding; isolated process groups cleaned up within bounded tests |
| Audit regression checks | Invalid public result and unknown grammar reference rejected; Semantic IR correctly classified; missing fixtures detected |
| Step 0-P | Passed again via the integrated command |

The Git and process vectors are infrastructure tests, not conformance fixtures or Core acceptance results.
The side-effect comparator is tested, but read-only/report/cache before/after expectations must still be fixed for each acceptance case.
Structural registry and matrix checks cannot prove semantic coverage or single-cause isolation.
Target-expansion vectors, independently computed golden Context Digests, complete acceptance inputs/results,
and a complete fresh-checkout Gate A run remain pending. No Gate A approval or Core implementation is included.
