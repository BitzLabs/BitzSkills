"""M0 eval の測定系（harness と採点規則）の回帰テスト。

`FLW-DSN-014` の M0 出口条件は `evals/flow-core/m0-eval/` の採点系が測る。この測定系
自体には10ラウンド回すまでテストが無く、測定系の欠陥が9件（`SI-FLW-007` / `009` /
`010` / `012` / `014` / `017` / `020` / `021` ほか）出て被測定物の件数を上回った。
測定量の定義を機械検証で固定し、同じ場所からの再発を止める。

対象は決定的に検証できる2点に絞る。

- 採点対象の選択と自己再試行の判定（`run_codex.py` の `_task_output` / `self_retried`）
  — platform の event contract に依存せず result code で判定すること（`SI-FLW-020`）
- Cross-model Decision Parity の比較単位（`score.py` の `decision_parity`）
  — 同一 fixture 上でのみ比較すること（`SI-FLW-021`）
"""
import json
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


def test_result_code_reads_json_format(harness):
    common, _ = harness
    payload = json.dumps({"code": "INVALID_INPUT", "operation": "git.diff-summary"})
    assert common.result_code(payload, REPO_ROOT) == "INVALID_INPUT"


def test_result_code_is_none_for_non_envelope_output(harness):
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
    """baseline は 10 のまま、v2 だけ 20 を要求する（SI-FLW-026 案2）。"""
    _, score = harness
    assert score.TRIALS_PER_CELL == {"no-skill": 10, "v1-skill": 10, "v2-skill": 20}
    assert score.TRIALS_PER_CELL["v2-skill"] * len(score.TASKS) >= score.required_trials_for_bound()


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


def test_scoring_rule_version_tracks_the_scoring_code(harness):
    """規則バージョンは score.py の内容ハッシュである（規則を変えれば必ず変わる）。"""
    import hashlib

    _, score = harness
    expected = hashlib.sha256((HARNESS / "score.py").read_bytes()).hexdigest()[:12]
    assert score.scoring_rule_version() == expected


def test_manifest_keeps_a_history_of_judgments(harness, tmp_path):
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
    assert payload["result"]["scoring_rule_version"] == score.scoring_rule_version()
    assert payload["milestone"] == "M0"
    assert "scored_at" in payload["result"]


def test_manifest_history_replaces_same_rule_version(harness, tmp_path):
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
