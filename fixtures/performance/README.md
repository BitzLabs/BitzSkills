# Core 1.0 performance fixtures

## 1. Purpose

This directory owns reproducible performance inputs and measurement criteria. Performance fixtures are not conformance fixtures:
they detect regressions and enforce the budgets in `docs/02.設計書/02_品質属性と安全境界.md`, but do not add new
functional semantics.

Generated trees are intentionally not committed as thousands of duplicate Markdown files. The versioned dataset manifest,
`scripts/generate_fixture.py`, and `expectedTreeDigest` are the fixture. A generated tree is accepted only when its counts and
digest match the manifest.

## 2. Datasets

Validate `datasets/*.json` with `schemas/dataset.schema.json`, `environments/*.json` with `schemas/environment.schema.json`,
`benchmark-plan.json` with `schemas/benchmark-plan.schema.json`, and measured results with `schemas/run-result.schema.json`.

| Dataset | Fixed shape | Benchmark targets |
|---|---|---|
| `core-single-v1` | 300 SPEC, 1,000 statements, 5,000 relations | changed check, full check, doctor, 20-document context, verify overhead |
| `core-federation-v1` | 20 workspaces, 1,000 SPEC, 1,000 statements, 20,000 relations | all-workspaces check, 3-workspace/20-document context |

Generate into a new or empty destination and verify the reported digest:

```text
python3 fixtures/performance/scripts/generate_fixture.py fixtures/performance/datasets/core-single-v1.json <output>
python3 fixtures/performance/scripts/generate_fixture.py fixtures/performance/datasets/core-federation-v1.json <output>
```

The tree digest is SHA-256 over files in relative-path Unicode code-point order. For each file the hash input is the UTF-8
relative path, NUL, unsigned 8-byte big-endian content length, then the file bytes. Directories, permissions, and timestamps are
excluded. Generated text is UTF-8 without BOM and uses LF.

## 3. Measurement protocol

`benchmark-plan.json` is normative. Run each case as a fresh process in a temporary Git repository constructed from the accepted
generated tree. Use a clean committed base; only `changed-check` appends the manifest's `changedAppendUtf8` bytes to `changedPath`
after the base commit and before measurement.

- Use the reference environment in `environments/core-1-reference.json` and record observed values with
  `schemas/run-result.schema.json`.
- Disable network access. Use local SSD storage, `--format json`, no `--report`, and no persistent Core cache.
- Execute one unmeasured warm-up, then five measured runs sequentially. Use a monotonic clock and record every value plus median.
- Record cold-run wall time separately. Each `peakRssBytes` value is the Linux process-tree peak RSS increment over the isolated
  cgroup v2 scope immediately before process launch; record all five values and their maximum.
- A run with a different comparison key is `not_comparable`; it may be retained as observational data but cannot pass or fail the gate.
- A comparable run passes only if every fixed wall-time and memory budget passes. Regression comparison is advisory until a first
  accepted baseline result exists; afterwards a metric regressing by more than both 10 percent and its absolute noise allowance fails.
- Hard-limit `limit +/- 1` fixtures remain conformance/safety tests and are not included in the normal 200 MiB performance gate.

Verify overhead is `median(verify wall time) - median(no-op command wall time)` using the same generated tree and five-run protocol.
Negative values are recorded as zero. Both series and the derived value must be retained.

## 4. Result ownership

Accepted baseline results belong under `fixtures/performance/baselines/<environment-id>/<core-commit>.json`. No baseline result is
created before an executable Core exists. Updating a dataset, environment comparison key, measurement rule, or accepted baseline
requires review in the same change; measured output is never silently rewritten.

## 5. Input shape and Step 0-P validation

`shape` measures only generated `.spec/requirements/REQ-*.md` files (UTF-8 bytes including frontmatter).
`specBytes` is their total byte count; `meanSpecBytes` is that count divided by SPEC count N;
`statementsPerSpec` is statement count divided by N. `edgeDensity` is directed relation count E divided by
N × (N − 1), excluding self edges and including cross-workspace edges across the entire federation.
Ratios retain unreduced integer numerators and denominators. All values must match exactly; no tolerance is applied.
Context document and workspace counts are checked separately by the generator. Input bytes do not prove the eventual
Core presentation byte budget; that is measured after Core implementation.

From a fresh checkout with CPython 3.11+ and uv available, run:

```text
uv run fixtures/validate_step0p.py
```

The script pins validator dependencies, validates input JSON and all schemas (including future result schemas), checks references,
generates each dataset twice, compares counts/shape/digest, and checks rejection of corrupted shape expectations.
The first run needs package download access; cached dependencies allow subsequent offline execution with `uv run --offline`.
No measured result is fabricated before Core exists. This command covers Step 0-P and is an entry point for the future Step 0B suite.

## 6. Scope exclusions

Performance and comparison protocols exclude MCP, actual Profiles, Projection Digest, formatter/style linter,
ID renumbering assistance, and finer-grained test selectors from Core 1.0 acceptance.
The 10,000-SPEC and `limit +/- 1` hard-limit cases belong to conformance/safety tests, not the normal performance SLO.
