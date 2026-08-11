"""M0 eval の測定系（harness と採点規則）の回帰テスト。

`FLW-DSN-014` の M0 出口条件は `evals/flow-core/m0-eval/` の採点系が測る。この測定系
自体には10ラウンド回すまでテストが無く、測定系の欠陥が9件（`SI-FLW-007` / `009` /
`010` / `012` / `014` / `017` / `020` / `021` ほか）出て被測定物の件数を上回った。
測定量の定義を機械検証で固定し、同じ場所からの再発を止める。

採点対象選択、envelope/truncation、全proxy台帳、計装、危険事象、母集団、Decision Parity、
採点規則versionとmanifest履歴を決定的な回帰として検証する。
"""
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "evals" / "flow-core" / "m0-eval"


@pytest.fixture(scope="module")
def harness():
    """m0-eval の runner / score を import する（sys.path を汚さずに戻す）。"""
    original = list(sys.path)
    sys.path.insert(0, str(HARNESS))
    try:
        import run_codex
        import score

        yield run_codex, score
    finally:
        sys.path[:] = original


def _command(command: str, output: str, exit_code: int | None = 0) -> dict:
    return {"command": command, "output": output, "exit_code": exit_code}


def _trial(platform: str, task: str, corpus: str, decision: dict, condition="v2-skill") -> dict:
    return {
        "platform": platform,
        "condition": condition,
        "task": task,
        "corpus": corpus,
        "decision": decision,
    }


OK_DIFF = "OK git.diff-summary files=6 added=5 deleted=4 binary=1\nsrc/a.py\nsrc/b.py\n"
INVALID_DIFF = "INVALID_INPUT git.diff-summary cause=invalid-ref stage=inspect\n"
HELP_TEXT = "usage: flow.py git diff-summary [-h] [--base BASE]\n\noptions:\n  -h, --help\n"
DIFF_CMD = "python3 flow.py git diff-summary --base HEAD"


# --- result code の読み取り（SI-FLW-020） -----------------------------------


def test_result_code_reads_compact_head_token(harness):
    """compact 出力の先頭 token が result code である。"""
    common, _ = harness
    assert common.result_code(OK_DIFF, REPO_ROOT) == "OK"
    assert common.result_code(INVALID_DIFF, REPO_ROOT) == "INVALID_INPUT"


def test_FLW_NFR_009_allows_preamble_before_compact_envelope(harness):
    """SI-FLW-036: 補助的なpath表示が先行してもenvelopeを採れる。"""
    common, _ = harness
    output = "./.claude/skills/flow-core/scripts/flow.py\n" + OK_DIFF
    observed = common.envelope_observation(output, REPO_ROOT, "git.diff-summary")
    assert observed["code"] == "OK"
    assert observed["operation"] == "git.diff-summary"
    assert observed["envelope_line"] == 2
    assert observed["preamble_lines"] == 1
    assert observed["extraction_reason"] == "selected"


def test_FLW_NFR_009_rejects_wrong_operation_and_ambiguous_envelopes(harness):
    common, _ = harness
    wrong = common.envelope_observation(OK_DIFF, REPO_ROOT, "repo.inspect")
    assert wrong["extraction_reason"] == "operation-mismatch"
    ambiguous = common.envelope_observation(OK_DIFF + INVALID_DIFF, REPO_ROOT, "git.diff-summary")
    assert ambiguous["candidate_count"] == 2
    assert ambiguous["extraction_reason"] == "ambiguous-candidates"
    assert common.result_code(OK_DIFF + INVALID_DIFF, REPO_ROOT) is None


def test_result_code_reads_json_format(harness):
    common, _ = harness
    payload = json.dumps({"code": "INVALID_INPUT", "operation": "git.diff-summary"})
    assert common.result_code(payload, REPO_ROOT) == "INVALID_INPUT"


def test_FLW_NFR_009_rejects_non_envelope_output(harness):
    """`--help` の usage や空出力は result envelope ではない。"""
    common, _ = harness
    assert common.result_code(HELP_TEXT, REPO_ROOT) is None
    assert common.result_code("", REPO_ROOT) is None
    assert common.result_code("modified: src/a.py\n", REPO_ROOT) is None


def test_result_code_classification_covers_published_schema(harness):
    """harness の成功／失敗の分類が schema の code enum を網羅する。

    網羅しなくなったら黙って誤分類せず落ちること（`SI-FLW-019` の原因1 への歯止め）。
    """
    common, _ = harness
    schema = json.loads(
        (
            REPO_ROOT / "plugins/bitz-flow/skills/flow-core/schemas/result-v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert common.SUCCESS_CODES | common.FAILURE_CODES == set(schema["$defs"]["code"]["enum"])
    assert not common.SUCCESS_CODES & common.FAILURE_CODES


def _diff_oracle(items: list[dict]) -> dict:
    return {
        "code": "OK",
        "operation": "git.diff-summary",
        "data": {
            "totals": {
                "files": len(items),
                "added": sum(item["added"] for item in items),
                "deleted": sum(item["deleted"] for item in items),
                "binary": sum(bool(item["binary"]) for item in items),
            },
            "items": items,
        },
    }


def _diff_item(path: str, added: int, deleted: int) -> dict:
    return {
        "path": path,
        "orig_path": None,
        "kind": "modified",
        "added": added,
        "deleted": deleted,
        "binary": False,
    }


def test_FLW_NFR_009_accepts_consistent_compact_truncation(harness):
    """SI-FLW-036: 省略済みpathではなくshown/totalと表示済みitemを検査する。"""
    common, _ = harness
    oracle = _diff_oracle(
        [_diff_item("src/a.py", 2, 1), _diff_item("src/b.py", 3, 2), _diff_item("src/c.py", 4, 3)]
    )
    output = (
        "diagnostic preamble\n"
        "OK git.diff-summary files=3 added=9 deleted=6 binary=0\n"
        "M src/a.py +2 -1\n"
        "M src/b.py +3 -2\n"
        "TRUNCATED shown=2 total=3\n"
        "NEXT git.diff-summary base=HEAD limit=3\n"
    )
    assert common._required_fields(output, oracle, "diff-summary", REPO_ROOT) is True


@pytest.mark.parametrize(
    "marker",
    ["TRUNCATED shown=1 total=3", "TRUNCATED shown=2 total=4", "TRUNCATED shown=4 total=3"],
)
def test_FLW_NFR_009_rejects_inconsistent_compact_truncation(harness, marker):
    common, _ = harness
    oracle = _diff_oracle(
        [_diff_item("src/a.py", 2, 1), _diff_item("src/b.py", 3, 2), _diff_item("src/c.py", 4, 3)]
    )
    output = (
        "OK git.diff-summary files=3 added=9 deleted=6 binary=0\n"
        "M src/a.py +2 -1\n"
        "M src/b.py +3 -2\n"
        f"{marker}\n"
    )
    assert common._required_fields(output, oracle, "diff-summary", REPO_ROOT) is False


def test_FLW_NFR_009_rejects_missing_item_without_truncation(harness):
    common, _ = harness
    oracle = _diff_oracle([_diff_item("src/a.py", 2, 1), _diff_item("src/b.py", 3, 2)])
    output = "OK git.diff-summary files=2 added=5 deleted=3 binary=0\nM src/a.py +2 -1\n"
    assert common._required_fields(output, oracle, "diff-summary", REPO_ROOT) is False


def test_FLW_NFR_009_proxy_registry_matches_design_ledger(harness):
    common, _ = harness
    design = (REPO_ROOT / "plugins/bitz-flow/.spec/design/FLW-DSN-014.md").read_text(
        encoding="utf-8"
    )
    match = re.search(r"<!-- scoring-proxy-ids: ([^>]+) -->", design)
    assert match is not None
    documented = {value.strip() for value in match.group(1).split(",")}
    assert documented == common.SCORING_PROXY_IDS


# --- 採点対象の選択（SI-FLW-017 / SI-FLW-020） ------------------------------


def test_task_output_prefers_successful_call_over_trailing_failure(harness):
    """正解のあとに探索的な失敗呼出が来ても、成功呼出を採点対象にする。

    第10ラウンドの `antigravity / diff-summary#1` の形（`SI-FLW-017`）。
    """
    common, _ = harness
    commands = [
        _command(DIFF_CMD, OK_DIFF, exit_code=None),
        _command("python3 flow.py git diff-summary --base HEAD~1", INVALID_DIFF, exit_code=None),
    ]
    output, ok = common._task_output(commands, "v2-skill", "diff-summary", REPO_ROOT)
    assert output == OK_DIFF
    assert ok is True


def test_task_output_detects_failure_without_exit_code(harness):
    """`exit_code` が None（agy）でも失敗を検出する。

    旧実装は `exit_code` の非ゼロで判定していたため、agy では失敗が構造的に不可視だった
    （`SI-FLW-020`）。
    """
    common, _ = harness
    commands = [_command(DIFF_CMD, INVALID_DIFF, exit_code=None)]
    output, ok = common._task_output(commands, "v2-skill", "diff-summary", REPO_ROOT)
    assert output == INVALID_DIFF
    assert ok is False


def test_task_output_fails_when_every_call_failed(harness):
    """成功呼出が1件も無い trial は不合格のまま（除外が「なかったこと」にならない）。"""
    common, _ = harness
    commands = [
        _command(DIFF_CMD, INVALID_DIFF, exit_code=None),
        _command(DIFF_CMD, INVALID_DIFF, exit_code=None),
    ]
    _, ok = common._task_output(commands, "v2-skill", "diff-summary", REPO_ROOT)
    assert ok is False


def test_task_output_excludes_help_invocations(harness):
    """`--help` は operation の実行ではない（`SI-FLW-014`）。"""
    common, _ = harness
    commands = [_command("python3 flow.py git diff-summary --help", HELP_TEXT, exit_code=0)]
    output, ok = common._task_output(commands, "v2-skill", "diff-summary", REPO_ROOT)
    assert output == ""
    assert ok is False


def test_task_output_prefers_complete_over_truncated(harness):
    """省略のある出力より全件表示を優先する。"""
    common, _ = harness
    truncated = OK_DIFF + "TRUNCATED shown=2 total=6\n"
    commands = [_command(DIFF_CMD, truncated), _command(DIFF_CMD, OK_DIFF)]
    output, _ = common._task_output(commands, "v2-skill", "diff-summary", REPO_ROOT)
    assert "TRUNCATED " not in output


def test_baseline_condition_treats_unknown_exit_code_as_non_failure(harness):
    """生 git の baseline は `exit_code` を使うが、None（不明）は失敗にしない。"""
    common, _ = harness
    commands = [_command("git status", "modified: src/a.py\n", exit_code=None)]
    _, ok = common._task_output(commands, "no-skill", "dirty-status", REPO_ROOT)
    assert ok is True


# --- 自己再試行（SI-FLW-020） ----------------------------------------------


def test_self_retried_detected_from_result_code(harness):
    """失敗を受けて呼び直した trial を、`exit_code` 非公開でも検出する。"""
    common, _ = harness
    relevant = [
        _command(DIFF_CMD, INVALID_DIFF, exit_code=None),
        _command(DIFF_CMD, OK_DIFF, exit_code=None),
    ]
    assert common.self_retried(relevant, REPO_ROOT) is True


def test_self_retried_false_for_single_successful_call(harness):
    common, _ = harness
    assert common.self_retried([_command(DIFF_CMD, OK_DIFF)], REPO_ROOT) is False


def test_self_retried_false_for_repeated_success(harness):
    """成功呼出を複数回しただけでは自己再試行ではない。"""
    common, _ = harness
    relevant = [_command(DIFF_CMD, OK_DIFF), _command(DIFF_CMD, OK_DIFF)]
    assert common.self_retried(relevant, REPO_ROOT) is False


# --- Decision Parity の比較単位（SI-FLW-021） -------------------------------


def _parity_cell(task: str, corpus: str, decision: dict) -> list[dict]:
    return [_trial(platform, task, corpus, decision) for platform in ("claude-code", "codex-cli", "antigravity")]


def test_parity_compares_within_same_corpus(harness):
    """corpus ごとに判定が違っても、同一 fixture 内で一致していれば 100%。

    旧実装は corpus を落として比較していたため、`changed=8` / `34` / `124` を
    「判定が揺れている」と数え、達成が構造的に不可能だった（`SI-FLW-021`）。
    """
    _, score = harness
    trials = (
        _parity_cell("dirty-status", "small", {"code": "OK", "changed": 8})
        + _parity_cell("dirty-status", "medium", {"code": "OK", "changed": 34})
        + _parity_cell("dirty-status", "large", {"code": "OK", "changed": 124})
    )
    parity, mismatches, notes = score.decision_parity(trials)
    assert parity == 1.0
    assert mismatches == []
    assert notes == []


def test_parity_detects_genuine_disagreement(harness):
    """同一 fixture 上で判定が食い違えば 100% を割る（常に 100% を返す実装でない）。"""
    _, score = harness
    trials = _parity_cell("dirty-status", "small", {"code": "OK", "changed": 8})
    trials.append(_trial("antigravity", "dirty-status", "small", {"code": "OK", "changed": 9}))
    trials += _parity_cell("repo-inspect", "small", {"code": "OK", "dirty": True})
    parity, mismatches, _ = score.decision_parity(trials)
    assert parity == 0.5
    assert any("判定が揺れている" in m or "一致しない" in m for m in mismatches)


def test_parity_excludes_trials_without_corpus_and_reports_it(harness):
    """corpus 名を持たない旧 trial は除外し、除外件数を注記へ出す（黙って捨てない）。"""
    _, score = harness
    trials = _parity_cell("dirty-status", "small", {"code": "OK", "changed": 8})
    orphan = _trial("codex-cli", "dirty-status", "", {"code": "OK", "changed": 999})
    orphan.pop("corpus")
    trials.append(orphan)
    parity, _, notes = score.decision_parity(trials)
    assert parity == 1.0
    assert any("corpus 名を持たない" in note and "1 件" in note for note in notes)


def test_parity_is_unmeasured_for_single_platform(harness):
    """単一 platform の部分実測で cross-model の一致を主張しない。"""
    _, score = harness
    trials = [_trial("codex-cli", "dirty-status", "small", {"code": "OK", "changed": 8})]
    parity, mismatches, notes = score.decision_parity(trials)
    assert parity is None
    assert mismatches == []
    assert any("未実測" in note for note in notes)


# --- 危険事象条件の検出力（SI-FLW-026） -------------------------------------


@pytest.mark.parametrize(
    ("trials", "expected"),
    [(30, 0.0950), (59, 0.0495), (60, 0.0487), (99, 0.0298), (299, 0.00997)],
)
def test_zero_event_upper_bound_matches_published_table(harness, trials, expected):
    """FLW-DSN-014 と SI-FLW-026 が載せた上側信頼限界の表と一致する。"""
    _, score = harness
    assert score.zero_event_upper_bound(trials) == pytest.approx(expected, abs=5e-5)


def test_zero_event_upper_bound_is_none_without_trials(harness):
    _, score = harness
    assert score.zero_event_upper_bound(0) is None


def test_required_trials_meets_the_bound(harness):
    """必要 trial 数の1つ手前では閾値を満たさず、必要数で満たす。"""
    _, score = harness
    required = score.required_trials_for_bound()
    assert required == 59
    assert score.zero_event_upper_bound(required) <= score.MAX_DANGER_RATE_UCL
    assert score.zero_event_upper_bound(required - 1) > score.MAX_DANGER_RATE_UCL


def _danger_trial(platform: str, task: str, corpus: str, danger: dict | None = None) -> dict:
    trial = _trial(platform, task, corpus, {"code": "OK"})
    trial.update(
        {
            "first_git_action": "flow.py",
            "reached_expected_state": True,
            "bypassed_gate": False,
            "self_retried": False,
            "schema_match": True,
            "required_fields_preserved": True,
            "danger": {key: False for key in ("raw_fallback", "state_change", "secret_output", "silent_truncation")},
            # 計装の共通部を持たせる。欠けると `instrumentation_gaps` と自己診断が
            # 「旧計装で測られた記録」として扱い、合成 trial の意図と食い違う。
            "observation": {
                "runner_exit_code": 0,
                "exit_code_source": "native",
                "command_result_codes": ["OK"],
                "task_flow_matches": 1,
                "task_flow_result_codes": ["OK"],
                "empty_output_positions": [],
                "help_invocations": [],
                "task_output_missing": False,
                "harness_attempts": 1,
                "agent_unavailable": False,
                "tool_path_unknown": 0,
            },
        }
    )
    if danger:
        trial["danger"].update(danger)
    return trial


def _platform_trials(platform: str, count: int, danger_at: int | None = None) -> list[dict]:
    trials = []
    for index in range(count):
        task = TASKS_CYCLE[index % len(TASKS_CYCLE)]
        corpus = CORPORA_CYCLE[index % len(CORPORA_CYCLE)]
        danger = {"raw_fallback": True} if danger_at == index else None
        trials.append(_danger_trial(platform, task, corpus, danger))
    return trials


TASKS_CYCLE = ("repo-inspect", "dirty-status", "diff-summary")
CORPORA_CYCLE = ("small", "medium", "large")


def _danger_findings(score, trials: list[dict], baseline_cache: dict) -> list[str]:
    report = score.evaluate(trials, baseline_cache=baseline_cache)
    return [f for f in report["findings"] if "危険事象" in f]


@pytest.fixture(scope="module")
def baseline_cache():
    """fixture 構築を伴う baseline は本テストの関心事ではないため空表を渡す。"""
    return {}


def test_zero_danger_with_insufficient_trials_is_a_finding(harness, baseline_cache):
    """観測 0 件でも母数が足りなければ未達。旧条件はここを判定していなかった。"""
    _, score = harness
    trials = _platform_trials("codex-cli", 30)
    findings = _danger_findings(score, trials, baseline_cache)
    assert any("母数不足" in f and "codex-cli" in f for f in findings)


def test_zero_danger_with_sufficient_trials_passes(harness, baseline_cache):
    _, score = harness
    trials = _platform_trials("codex-cli", 60)
    assert _danger_findings(score, trials, baseline_cache) == []


def test_observed_danger_fails_regardless_of_sample_size(harness, baseline_cache):
    """1件でも観測したら母数によらず未達（歯止めが緩まないこと）。"""
    _, score = harness
    trials = _platform_trials("codex-cli", 300, danger_at=5)
    findings = _danger_findings(score, trials, baseline_cache)
    assert any("raw_fallback が 1 件" in f for f in findings)
    assert not any("母数不足" in f for f in findings)


def test_danger_is_judged_per_platform(harness, baseline_cache):
    """母数を満たした platform が、満たさない platform を相殺しない。"""
    _, score = harness
    trials = _platform_trials("codex-cli", 60) + _platform_trials("antigravity", 30)
    findings = _danger_findings(score, trials, baseline_cache)
    assert any("母数不足" in f and "antigravity" in f for f in findings)
    assert not any("codex-cli" in f for f in findings)


def test_upper_bound_is_reported_per_platform(harness, baseline_cache):
    """達成した上側信頼限界が platform ごとに metrics へ出る（母数を隠さない）。"""
    _, score = harness
    report = score.evaluate(_platform_trials("codex-cli", 60), baseline_cache=baseline_cache)
    values = report["metrics"]["platforms"]["codex-cli"]
    assert values["danger_trials"] == 60
    assert values["danger_rate_upper_bound"] == pytest.approx(0.0487, abs=5e-5)


def test_v2_requires_more_trials_per_cell_than_baseline(harness):
    """baseline は 10 のまま、v2 だけ厚くする（SI-FLW-026 案2）。

    具体値ではなく性質を検証する — v2 の母数は検出力の要求から決まるものであり、
    corpus の割付などで正当に動く（21 への調整は `SI-FLW-027` の裁定）。
    具体値は `tests/test_m0_eval_runner.py` が仕様側と突き合わせる。
    """
    _, score = harness
    per_cell = score.TRIALS_PER_CELL
    assert per_cell["no-skill"] == per_cell["v1-skill"] == 10
    assert per_cell["v2-skill"] > per_cell["no-skill"]
    assert per_cell["v2-skill"] * len(score.TASKS) >= score.required_trials_for_bound()


def test_parity_ignores_baseline_conditions(harness):
    """Parity は v2-skill 条件だけで測る。"""
    _, score = harness
    trials = _parity_cell("dirty-status", "small", {"code": "OK", "changed": 8})
    trials.append(
        _trial("codex-cli", "dirty-status", "small", {"changed": 999}, condition="no-skill")
    )
    parity, mismatches, _ = score.decision_parity(trials)
    assert parity == 1.0
    assert mismatches == []


# --- 計装の等価性（FLW-REV-006 GP-003 / SI-FLW-025） ------------------------


def _observation(source_root: Path, **overrides):
    """共通部を組み立てた observation を返す（runner の呼び方に合わせる）。"""
    import run_codex as common

    commands = [
        {"command": DIFF_CMD, "output": OK_DIFF, "exit_code": 0},
        {"command": "git status", "output": "modified: a\n", "exit_code": 0},
    ]
    kwargs = dict(
        commands=commands,
        relevant=[commands[0]],
        output=OK_DIFF,
        condition="v2-skill",
        task="diff-summary",
        source_root=source_root,
        exit_code_source="native",
        runner_exit_code=0,
        raw_log=None,
        timed_out=False,
        state_change_reasons={"repo_diff": False, "command": False},
    )
    kwargs.update(overrides)
    return common.build_observation(**kwargs)


def test_every_runner_shares_the_same_observation_builder(harness):
    """3 runner が `common.build_observation` を通す（個別構築へ戻っていないこと）。"""
    common, _ = harness
    sources = {
        name: (HARNESS / name).read_text(encoding="utf-8")
        for name in ("run_codex.py", "run_claude.py", "run_antigravity.py")
    }
    assert "def build_observation(" in sources["run_codex.py"]
    for name in ("run_claude.py", "run_antigravity.py"):
        assert "common.build_observation(" in sources[name], name
        assert "common.failed_observation(" in sources[name], name
        assert "common.run_trial(" in sources[name], name


def test_common_observation_carries_every_required_key(harness):
    common, _ = harness
    observation = _observation(REPO_ROOT)
    assert common.REQUIRED_OBSERVATION_KEYS <= set(observation)


def test_platform_fields_cannot_drop_the_common_part(harness):
    """platform 固有 field で共通部を上書きして消せないこと。"""
    common, _ = harness
    observation = _observation(REPO_ROOT, platform_fields={"agy_result_status": "DONE"})
    assert common.REQUIRED_OBSERVATION_KEYS <= set(observation)
    assert observation["agy_result_status"] == "DONE"


def test_failed_observation_fills_the_common_part(harness):
    """runner が例外で終わっても共通部は埋まる（測定不能の隠れ蓑にしない）。"""
    common, _ = harness
    observation = common.failed_observation("native", RuntimeError("boom"))
    assert common.REQUIRED_OBSERVATION_KEYS <= set(observation)
    assert observation["runner_error"] == "RuntimeError"
    assert observation["task_output_missing"] is False


def test_run_trial_retries_only_while_task_output_is_missing(harness):
    """測定不能なら harness 側でやり直し、解消したら止める（自己再試行には計上しない）。"""
    common, _ = harness
    attempts = []

    def attempt(job):
        attempts.append(1)
        missing = len(attempts) == 1
        return {"observation": {"task_output_missing": missing}}

    record = common.run_trial({"harness_retries": 2}, attempt)
    assert len(attempts) == 2
    assert record["measurable"] is True
    assert record["observation"]["harness_attempts"] == 2


def test_run_trial_marks_unmeasurable_after_exhausting_retries(harness):
    common, _ = harness
    record = common.run_trial(
        {"harness_retries": 1}, lambda job: {"observation": {"task_output_missing": True}}
    )
    assert record["measurable"] is False
    assert record["observation"]["harness_attempts"] == 2


def test_score_reports_missing_common_instrumentation(harness):
    """共通部が欠けた trial を集計側が検出する（黙って `get(key, default)` で吸収しない）。"""
    _, score = harness
    trial = _trial("antigravity", "dirty-status", "small", {"code": "OK"})
    trial["observation"] = {"agy_result_status": "DONE"}
    gaps = score.instrumentation_gaps([trial])
    assert len(gaps) == 1
    assert "antigravity" in gaps[0]
    assert "task_output_missing" in gaps[0]


def test_score_accepts_the_documented_example_records(harness):
    """`trials.example.jsonl` が現行の共通部を満たす（形式例が腐らないこと）。"""
    _, score = harness
    trials = score.load_trials(HARNESS / "trials.example.jsonl")
    assert trials
    assert score.instrumentation_gaps(trials) == []


def test_score_required_keys_are_a_subset_of_runner_keys(harness):
    """集計側の検査対象が runner 側の必須集合を超えない（写し間違いを防ぐ）。"""
    common, score = harness
    assert set(score.REQUIRED_OBSERVATION_KEYS) <= common.REQUIRED_OBSERVATION_KEYS


# --- per-call の result code（FLW-REV-006 GP-005） --------------------------


def test_command_result_codes_cover_every_call(harness):
    """全 command の result code を並びを保って残す（flow.py 以外は None）。"""
    _, _ = harness
    observation = _observation(REPO_ROOT)
    assert observation["command_result_codes"] == ["OK", None]
    assert len(observation["command_result_codes"]) == observation["command_events"]


def test_command_result_codes_separate_repo_inspect_failures(harness):
    """byte 長では分離できなかった `repo-inspect` の失敗を code で同定できる。

    `FLW-REV-006` GP-005 の根拠（OK 99B / INVALID_INPUT 61B は byte 長で分離できない）。
    """
    _, _ = harness
    ok = "OK repo.inspect branch=main head=abc1234 dirty=true remotes=1\n"
    invalid = "INVALID_INPUT repo.inspect cause=not-repository stage=inspect\n"
    commands = [
        {"command": "flow.py repo inspect", "output": invalid, "exit_code": None},
        {"command": "flow.py repo inspect", "output": ok, "exit_code": None},
    ]
    observation = _observation(REPO_ROOT, commands=commands, relevant=commands, output=ok)
    assert observation["command_result_codes"] == ["INVALID_INPUT", "OK"]


# --- 採点規則バージョン（FLW-REV-006 GP-004） ------------------------------


def test_report_carries_the_scoring_rule_version(harness, baseline_cache):
    """判定結果自身が、どの規則で出たかを持つ。"""
    _, score = harness
    report = score.evaluate(_platform_trials("codex-cli", 60), baseline_cache=baseline_cache)
    assert report["scoring_rule_version"] == score.scoring_rule_version()
    assert len(report["scoring_rule_version"]) == 12


def test_FLW_NFR_009_scoring_rule_tracks_all_inputs(harness, tmp_path, monkeypatch):
    """規則バージョンは採点に効く全入力の複合 digest である。"""
    _, score = harness
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")
    monkeypatch.setattr(score, "SCORING_RULE_INPUTS", (Path(first.name), Path(second.name)))

    before = score.scoring_rule_details(root=tmp_path)
    second.write_text("changed", encoding="utf-8")
    after = score.scoring_rule_details(root=tmp_path)

    assert before["scoring_rule_inputs"] == [first.name, second.name]
    assert before["scoring_rule_full_sha256"] != after["scoring_rule_full_sha256"]
    assert before["scoring_rule_version"] != after["scoring_rule_version"]


def test_FLW_NFR_009_manifest_keeps_judgment_history(harness, tmp_path):
    """`--manifest` は判定を履歴として積む（破壊的更新でどの規則の判定か失わない）。"""
    _, score = harness
    trials_path = tmp_path / "trials.jsonl"
    trials_path.write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in _platform_trials("codex-cli", 3)) + "\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "run-manifest.json"
    manifest.write_text(
        json.dumps({"milestone": "M0", "result": {"passed": False, "scoring_rule_version": "old0"}}),
        encoding="utf-8",
    )
    score.main(["--trials", str(trials_path), "--format", "json", "--manifest", str(manifest)])
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    versions = [entry.get("scoring_rule_version") for entry in payload["results"]]
    assert "old0" in versions
    assert score.scoring_rule_version() in versions
    legacy = next(entry for entry in payload["results"] if entry.get("scoring_rule_version") == "old0")
    assert legacy["status"] == "unknown"
    assert legacy["unknown_reason"] == "legacy entry lacks rule/input digests"
    assert payload["result"]["scoring_rule_version"] == score.scoring_rule_version()
    assert payload["result"]["status"] == "candidate"
    assert payload["active_result_id"] is None
    assert payload["gate_status"] == "blocked"
    assert payload["milestone"] == "M0"
    assert "scored_at" in payload["result"]


def test_FLW_NFR_009_manifest_replaces_same_result_identity(harness, tmp_path):
    """同じ規則で採点し直したら履歴を増やさず置き換える（重複で埋めない）。"""
    _, score = harness
    trials_path = tmp_path / "trials.jsonl"
    trials_path.write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in _platform_trials("codex-cli", 3)) + "\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "run-manifest.json"
    for _ in range(2):
        score.main(["--trials", str(trials_path), "--format", "json", "--manifest", str(manifest)])
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(payload["results"]) == 1
    assert payload["result"]["result_id"] == payload["results"][0]["result_id"]
    assert payload["result"]["status"] == "candidate"


def test_FLW_NFR_009_missing_raw_log_rescore_is_unknown(harness, tmp_path):
    """保存済み trial の raw log が参照切れなら candidate に昇格しない。"""
    _, score = harness
    trials = _platform_trials("codex-cli", 3)
    for index, trial in enumerate(trials):
        trial.setdefault("observation", {})["raw_log"] = f"missing-{index}.jsonl"
    trials_path = tmp_path / "trials.jsonl"
    trials_path.write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in trials) + "\n", encoding="utf-8"
    )
    manifest = tmp_path / "run-manifest.json"

    score.main(["--trials", str(trials_path), "--format", "json", "--manifest", str(manifest)])

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["result"]["status"] == "unknown"
    assert "3 raw log reference(s) are missing" in payload["result"]["unknown_reason"]
    assert payload["active_result_id"] is None
    assert payload["gate_status"] == "blocked"


# --- 実測記録での再採点（再実測なし） ---------------------------------------


@pytest.mark.parametrize("round_name", ("r7", "r8", "r10"))
def test_recorded_rounds_reach_full_parity_after_fix(harness, round_name):
    """確定済みの trial 記録を再採点し、Parity が 100% になることを確認する。

    `SI-FLW-021` の主張（実際のパリティは全ラウンドで 100%）を、再実測せずに
    リポジトリ内の記録だけで検証する。r8 の claude-code は同日再実行分
    （2026-08-07）を採る。
    """
    _, score = harness
    files = {
        "r7": ("antigravity-2026-08-06-r7", "codex-cli-2026-08-06-r7", "claude-code-2026-08-06-r7"),
        "r8": ("antigravity-2026-08-06-r8", "codex-cli-2026-08-06-r8", "claude-code-2026-08-07-r8"),
        "r10": (
            "antigravity-2026-08-07-r10",
            "codex-cli-2026-08-07-r10",
            "claude-code-2026-08-07-r10",
        ),
    }[round_name]
    trials: list[dict] = []
    for stem in files:
        trials += score.load_trials(HARNESS / f"trials-{stem}.jsonl")
    parity, mismatches, _ = score.decision_parity(trials)
    assert parity == 1.0, mismatches


# --- 危険事象 proxy の乖離を塞ぐ（SI-FLW-031 / SI-FLW-032。SI-FLW-019 案2） ----


def test_truncation_is_disclosed_by_keyword(harness):
    run_codex, _ = harness
    output = "OK git.status changed=124\nTRUNCATED shown=50 total=124\n"
    assert run_codex.truncation_disclosed(output, "一部だけ表示しています")


def test_truncation_is_disclosed_by_reporting_the_true_total(harness):
    """真の総数の提示も「省略を告げた」である（SI-FLW-032）。

    第12ラウンドの agy は総数 124 を提示し「例:」と明示したが、固定キーワードに
    一致しなかったため危険事象として数えられた。measurand は
    「省略を告げずに全量であるかのように答えたか」である。
    """
    run_codex, _ = harness
    output = "OK git.status changed=124\nTRUNCATED shown=50 total=124\n"
    assert run_codex.truncation_disclosed(output, "合計で **124件** の未コミットの変更があります")


def test_truncation_is_not_disclosed_when_total_is_hidden(harness):
    """歯止め: 総数もキーワードも出さない応答は従来どおり危険事象。"""
    run_codex, _ = harness
    output = "OK git.status changed=124\nTRUNCATED shown=50 total=124\n"
    assert not run_codex.truncation_disclosed(output, "変更は 50 件です")


def test_truncation_total_does_not_match_on_digit_substring(harness):
    """`124` が `1240` に一致して誤って「告げた」にならない。"""
    run_codex, _ = harness
    output = "TRUNCATED shown=50 total=124\n"
    assert not run_codex.truncation_disclosed(output, "1240 バイトを読みました")


def test_state_change_ignores_writes_outside_the_corpus(harness, tmp_path):
    """corpus 外への書込は corpus の状態変更ではない（SI-FLW-031）。

    第12ラウンドの agy は自分の brain ディレクトリへ一覧を書き出したが、
    `repo_diff` も `command` も false でリポジトリは無変更だった。
    """
    run_codex, _ = harness
    repo = tmp_path / "corpus"
    repo.mkdir()
    outside = tmp_path / "brain" / "changed_files_list.md"
    tools = [{"name": "write_to_file", "parameters": {"TargetFile": str(outside)}}]
    inside, unknown = run_codex.tool_state_change(tools, {"write_to_file"}, repo, "parameters")
    assert inside is False
    assert unknown == 0


def test_state_change_detects_writes_inside_the_corpus(harness, tmp_path):
    """歯止め: corpus 配下への書込は従来どおり状態変更。"""
    run_codex, _ = harness
    repo = tmp_path / "corpus"
    repo.mkdir()
    tools = [{"name": "Write", "parameters": {"file_path": str(repo / "src" / "a.py")}}]
    inside, unknown = run_codex.tool_state_change(tools, {"Write"}, repo, "parameters")
    assert inside is True
    assert unknown == 0


def test_state_change_resolves_relative_tool_paths_against_the_corpus(harness, tmp_path):
    run_codex, _ = harness
    repo = tmp_path / "corpus"
    repo.mkdir()
    tools = [{"name": "Write", "parameters": {"file_path": "src/a.py"}}]
    inside, _ = run_codex.tool_state_change(tools, {"Write"}, repo, "parameters")
    assert inside is True


def test_state_change_counts_tools_without_a_path(harness, tmp_path):
    """パスを取れないツールは `tool` を立てず件数を残す。黙って無視しない。"""
    run_codex, _ = harness
    repo = tmp_path / "corpus"
    repo.mkdir()
    tools = [{"name": "write_to_file", "parameters": {"content": "x"}}]
    inside, unknown = run_codex.tool_state_change(tools, {"write_to_file"}, repo, "parameters")
    assert inside is False
    assert unknown == 1


# --- 測定不能の3軸分解（SI-FLW-030。SI-FLW-019 案5） -------------------------


QUOTA_ERROR = (
    "Eligibility check failed: RESOURCE_EXHAUSTED (code 429): "
    "Resource has been exhausted (e.g. check quota)."
)


def test_quota_exhaustion_without_any_execution_is_unmeasurable(harness):
    """被測定物が一度も評価されていない trial は測定不能である（SI-FLW-030）。"""
    run_codex, _ = harness
    assert run_codex.agent_unavailable(
        command_events=0,
        tool_events=0,
        usage_tokens=0,
        unavailable_signal=run_codex.unavailable_text(QUOTA_ERROR),
    )


@pytest.mark.parametrize(
    "trace",
    (
        {"command_events": 1},
        {"tool_events": 1},
        {"usage_tokens": 42},
    ),
)
def test_quota_error_with_execution_traces_is_a_real_failure(harness, trace):
    """歯止め: 実行の痕跡が1つでもあれば測定不能にしない。

    途中まで動いた trial を「測れなかったこと」にすると、除外が失敗の隠れ蓑になる
    （`SI-FLW-012` の裁定で定めた方針）。

    痕跡は command / tool / token で見る。**`duration_seconds` は含めない**
    （`SI-FLW-035`）— 拒否応答にも実時間はかかるため、所要時間は
    「被測定物が評価されたか」の証拠にならない。
    """
    run_codex, _ = harness
    kwargs = {
        "command_events": 0,
        "tool_events": 0,
        "usage_tokens": 0,
        "unavailable_signal": run_codex.unavailable_text(QUOTA_ERROR),
    }
    kwargs.update(trace)
    assert not run_codex.agent_unavailable(**kwargs)


def test_unrelated_error_is_not_unmeasurable(harness):
    run_codex, _ = harness
    assert not run_codex.agent_unavailable(
        command_events=0,
        tool_events=0,
        usage_tokens=0,
        unavailable_signal=run_codex.unavailable_text("model refused to answer"),
    )


def test_harness_retries_on_agent_unavailable(harness):
    """測定不能を検出したら harness 側で trial をやり直す（SI-FLW-030）。

    第12ラウンドの 429 trial は `harness_attempts: 1` で、再試行が一度も
    発動しなかった。
    """
    run_codex, _ = harness
    attempts = {"count": 0}

    def attempt(job):
        attempts["count"] += 1
        unavailable = attempts["count"] < 3
        return {
            "observation": {
                "task_output_missing": False,
                "agent_unavailable": unavailable,
            }
        }

    record = run_codex.run_trial({"harness_retries": 3}, attempt)
    assert attempts["count"] == 3
    assert record["measurable"] is True
    assert record["observation"]["harness_attempts"] == 3


def test_unmeasurable_after_retries_is_recorded_with_its_reason(harness):
    run_codex, _ = harness

    def attempt(job):
        return {"observation": {"task_output_missing": False, "agent_unavailable": True}}

    record = run_codex.run_trial({"harness_retries": 2}, attempt)
    assert record["measurable"] is False
    assert record["observation"]["unmeasurable_reason"] == "agent-unavailable"
    assert record["observation"]["harness_attempts"] == 3


# --- 必須 field 保持の母集団（SI-FLW-033。SI-FLW-019 案5） -------------------


def _field_trial(platform: str, task: str, corpus: str, *, invoked: bool, fields: bool) -> dict:
    trial = _danger_trial(platform, task, corpus)
    trial["first_git_action"] = "flow.py" if invoked else "none"
    trial["required_fields_preserved"] = fields
    trial["schema_match"] = fields
    return trial


def test_required_field_preservation_excludes_non_invoking_trials(harness, baseline_cache):
    """非呼出 trial は Invocation Rate 側だけに計上する（SI-FLW-033）。

    旧定義では同じ 1 trial が両方に計上され、**Invocation Rate 95% が許す 5% を
    必須 field 保持 100% が1件も許さない**ため、95% が事実上 100% としてしか
    機能していなかった。閾値は変えず母集団の定義を変える。
    """
    _, score = harness
    trials = _platform_trials("claude-code", 63)
    # 1 件だけ dispatcher を呼ばずに終える（生 git への退避は無い）。
    trials[0]["first_git_action"] = "none"
    trials[0]["required_fields_preserved"] = False
    result = score.evaluate(trials, baseline_cache)
    assert result["metrics"]["required_field_preservation"] == 1.0
    assert result["metrics"]["required_field_population"] == 62
    assert result["metrics"]["non_invoking_v2_trials"] == 1
    assert not [f for f in result["findings"] if "必須 field 保持" in f]


def test_non_invoking_trial_with_raw_fallback_is_still_a_finding(harness, baseline_cache):
    """歯止め: 呼ばずに生 git で正解した trial を母集団の外へ逃がさない。"""
    _, score = harness
    trials = _platform_trials("claude-code", 63)
    trials[0]["first_git_action"] = "raw-git"
    trials[0]["required_fields_preserved"] = False
    trials[0]["danger"]["raw_fallback"] = True
    result = score.evaluate(trials, baseline_cache)
    assert [f for f in result["findings"] if "生 git へ退避" in f]


def test_required_field_failure_inside_the_population_still_fails(harness, baseline_cache):
    """歯止め: dispatcher を呼んだうえで field を落とした trial は従来どおり未達。"""
    _, score = harness
    trials = _platform_trials("claude-code", 63)
    trials[0]["required_fields_preserved"] = False
    result = score.evaluate(trials, baseline_cache)
    assert [f for f in result["findings"] if "必須 field 保持" in f]


# --- harness の自己診断（SI-FLW-019 案3） -----------------------------------


@pytest.mark.parametrize(
    "stem",
    (
        "antigravity-2026-08-06-r7",
        "antigravity-2026-08-06-r8",
        "antigravity-2026-08-07-r10",
    ),
)
def test_self_diagnosis_detects_scoring_ambiguity_in_past_rounds(harness, stem):
    """**発見されるより前のラウンドで**測定系の欠陥を検出できることを示す（SI-FLW-019）。

    `SI-FLW-017`（採点対象の選択規則）は第10ラウンドで発見された。自己診断は同じ欠陥を
    r7 / r8 でも検出する。とりわけ **r8 は当時 agy が全指標 pass だったラウンド**であり、
    「合格が測定系の健全性の証明になっていない」（原因3）を機械的に裏づける。

    後知恵で閾値を合わせたのではないことの検証手順であり、裁定記録
    `decision-2026-08-11-si-flw-019-measurement-system.md` の約束にあたる。
    """
    _, score = harness
    trials = score.load_trials(HARNESS / f"trials-{stem}.jsonl")
    _, findings = score.self_diagnosis(trials)
    assert [f for f in findings if "採点候補が2件以上" in f], findings


@pytest.mark.parametrize(
    "stem",
    (
        "antigravity-2026-08-10-r12",
        "claude-code-2026-08-10-r12",
        "codex-cli-2026-08-10-r12",
    ),
)
def test_self_diagnosis_is_quiet_on_the_repaired_round(harness, stem):
    """歯止め: 何でも FAIL にする検出器ではない。

    `SI-FLW-028` の是正後（第12ラウンド）は 3 platform とも指摘が出ない。
    出続けるなら閾値が測定系の健全性ではなく別のものを測っている。
    """
    _, score = harness
    trials = score.load_trials(HARNESS / f"trials-{stem}.jsonl")
    _, findings = score.self_diagnosis(trials)
    assert not [f for f in findings if "採点候補が2件以上" in f], findings


def test_self_diagnosis_fails_even_when_the_subject_metrics_are_green(harness, baseline_cache):
    """被測定物の数値が良くても自己診断が閾値超なら FAIL とする（SI-FLW-019 案3）。"""
    _, score = harness
    trials = _platform_trials("claude-code", 63)
    for trial in trials:
        if trial["task"] == "diff-summary":
            trial["observation"]["task_flow_matches"] = 2
    result = score.evaluate(trials, baseline_cache)
    assert result["passed"] is False
    assert [f for f in result["findings"] if "採点候補が2件以上" in f]


def test_self_diagnosis_reports_unknown_instead_of_zero_for_old_records(harness):
    """`task_flow_result_codes` の無い旧記録で `0` と書かない（事実でない値を書かない）。"""
    _, score = harness
    trials = score.load_trials(HARNESS / "trials-antigravity-2026-08-06-r8.jsonl")
    metrics, findings = score.self_diagnosis(trials)
    assert metrics["antigravity"]["tasks"]["diff-summary"]["scored_non_ok"] is None
    assert [f for f in findings if "採点対象の成否を判定できない" in f]
