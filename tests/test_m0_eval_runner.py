"""M0 eval runner の CLI・job 構築・run manifest の契約テスト。

`FLW-REV-006` GP-003 は「歯止めが codex-cli でしか効いていない」ことを blocking として
挙げた。`observation` の共通化（`SI-FLW-025`）でその一部は塞いだが、**runner の CLI と
job 構築は検査対象になっておらず**、`--harness-retries` が codex-cli にしか無い
（＝共通化した再試行機構へ claude-code / antigravity から到達できない）ことも、
run manifest の `budget` ブロックが定数のまま10ラウンド更新されなかったことも、
機械検査では捕まらなかった。

3 runner の**構成の対称性**そのものをテストで固定する。platform 固有であってよい差
（`--codex-version` 等の version フラグ、timeout の既定値）は明示的に除外する。
"""
import argparse
import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "evals" / "flow-core" / "m0-eval"
RUNNERS = ("run_codex.py", "run_claude.py", "run_antigravity.py")

# platform 固有であってよい CLI フラグ。ここに無い差分はテストが落とす。
PLATFORM_SPECIFIC_FLAGS = {"--codex-version", "--claude-version", "--agy-version"}


@pytest.fixture(scope="module")
def harness():
    original = list(sys.path)
    sys.path.insert(0, str(HARNESS))
    try:
        import run_antigravity
        import run_claude
        import run_codex
        import score

        yield {
            "run_codex.py": run_codex,
            "run_claude.py": run_claude,
            "run_antigravity.py": run_antigravity,
            "score": score,
        }
    finally:
        sys.path[:] = original


def _cli_flags(name: str) -> dict[str, object]:
    tree = ast.parse((HARNESS / name).read_text(encoding="utf-8"))
    flags: dict[str, object] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument"):
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant)):
            continue
        default = None
        for keyword in node.keywords:
            if keyword.arg == "default":
                try:
                    default = ast.literal_eval(keyword.value)
                except ValueError:
                    default = "<expr>"
        flags[node.args[0].value] = default
    return flags


# --- CLI の対称性 -----------------------------------------------------------


def test_every_runner_exposes_the_same_cli_surface():
    """platform 固有フラグを除き、3 runner の CLI が一致する。

    `--harness-retries` が codex-cli にしか無く、共通化した再試行機構へ
    他 2 runner から到達できなかった事象の回帰テスト。
    """
    flags = {name: set(_cli_flags(name)) - PLATFORM_SPECIFIC_FLAGS for name in RUNNERS}
    base = flags["run_codex.py"]
    for name in RUNNERS:
        assert flags[name] == base, f"{name}: +{sorted(flags[name] - base)} -{sorted(base - flags[name])}"


def test_every_runner_accepts_harness_retries():
    for name in RUNNERS:
        assert "--harness-retries" in _cli_flags(name), name


def test_harness_retries_default_is_positive_everywhere():
    """再試行が既定 0（＝実質無効）の runner が無いこと。"""
    for name in RUNNERS:
        default = _cli_flags(name)["--harness-retries"]
        assert isinstance(default, int) and default >= 1, (name, default)


def test_trials_has_no_hardcoded_default():
    """`--trials` の既定は所要数の解決に委ねる（10 の直書きへ戻っていないこと）。"""
    for name in RUNNERS:
        assert _cli_flags(name)["--trials"] is None, name


# --- 所要 trial 数を仕様から読む（SI-FLW-026） ------------------------------


def test_runners_read_required_trials_from_the_scorer(harness):
    """runner と採点側が同一の `TRIALS_PER_CELL` を見る（写しを持たない）。"""
    score = harness["score"]
    assert harness["run_codex.py"].TRIALS_PER_CELL is score.TRIALS_PER_CELL


def test_v2_trials_satisfy_the_required_sample_size(harness):
    """v2 の所要数が危険事象条件の必要母数を満たす（SI-FLW-026）。"""
    score = harness["score"]
    per_platform = score.TRIALS_PER_CELL["v2-skill"] * len(score.TASKS)
    assert per_platform >= score.required_trials_for_bound()
    assert score.zero_event_upper_bound(per_platform) <= score.MAX_DANGER_RATE_UCL


def test_baseline_trials_are_unchanged(harness):
    """baseline は Invocation 比較にしか使わないため 10 のまま。"""
    score = harness["score"]
    assert score.TRIALS_PER_CELL["no-skill"] == 10
    assert score.TRIALS_PER_CELL["v1-skill"] == 10


def test_v2_trials_split_corpora_evenly(harness):
    """v2 の所要数で corpus が均等に割れる（small / medium / large が同数）。"""
    import collections

    common = harness["run_codex.py"]
    score = harness["score"]
    counts = collections.Counter(
        common.CORPORA[(trial - 1) % len(common.CORPORA)]
        for trial in range(1, score.TRIALS_PER_CELL["v2-skill"] + 1)
    )
    assert len(set(counts.values())) == 1, counts


# --- job 構築 ---------------------------------------------------------------


def _plan(module, argv: list[str]) -> dict:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        assert module.main(argv) == 0
    return json.loads(buffer.getvalue())


BASE_ARGV = ["--plan", "--output", "/dev/null", "--manifest", "/dev/null", "--corpus-root", "/tmp/unused"]


@pytest.mark.parametrize("name", RUNNERS)
def test_plan_uses_required_trials_per_condition(harness, name):
    plan = _plan(harness[name], BASE_ARGV)
    assert plan["trials_per_condition"] == harness["score"].TRIALS_PER_CELL


@pytest.mark.parametrize("name", RUNNERS)
def test_trials_override_applies_to_every_condition(harness, name):
    """smoke run 用の一律指定は全 condition へ効く。"""
    plan = _plan(harness[name], BASE_ARGV + ["--trials", "2"])
    assert set(plan["trials_per_condition"].values()) == {2}


@pytest.mark.parametrize("name", RUNNERS)
def test_plan_job_count_matches_per_condition_trials(harness, name):
    plan = _plan(harness[name], BASE_ARGV)
    expected = sum(len(plan["tasks"]) * n for n in plan["trials_per_condition"].values())
    assert plan["jobs"] == expected


@pytest.mark.parametrize("name", RUNNERS)
def test_condition_filter_limits_the_plan(harness, name):
    plan = _plan(harness[name], BASE_ARGV + ["--condition", "v2-skill"])
    assert list(plan["trials_per_condition"]) == ["v2-skill"]


# --- run manifest の証跡 ----------------------------------------------------


def _fake_args(module) -> argparse.Namespace:
    return argparse.Namespace(
        model="m",
        model_version="v",
        reasoning_effort="low",
        codex_version="c",
        claude_version="c",
        agy_version="c",
        harness_retries=3,
        actual_prs=None,
        actual_sessions=None,
        review_fix_rounds=None,
    )


def _write(module, tmp_path: Path, trials_per_condition: dict[str, int]) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / f"{module.PLATFORM}.json"
    corpus = {"v2-skill": {"small": {"raw_baseline_bytes": {"dirty-status": 1}}}}
    module._write_manifest(path, _fake_args(module), corpus, 0, trials_per_condition)
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", RUNNERS)
def test_manifest_records_the_sample_size(harness, tmp_path, name):
    """どの母数で測った記録かを manifest から確かめられる。"""
    payload = _write(harness[name], tmp_path / name, {"v2-skill": 21})
    assert payload["trials_per_condition"] == {"v2-skill": 21}
    assert payload["harness_retries"] == 3


@pytest.mark.parametrize("name", RUNNERS)
def test_manifest_carries_the_recalibrated_budget(harness, tmp_path, name):
    """予算が GP-001 の再校正値であり、裁定記録を参照している。

    旧実装は `max_prs: 1 / max_sessions: 5` の定数で、全10ラウンド更新されなかった。
    """
    payload = _write(harness[name], tmp_path / name, {"v2-skill": 21})
    budget = payload["budget"]
    assert budget["max_prs"] == 4
    assert budget["max_sessions"] == 14
    assert budget["consumed_prs_before_recalibration"] == 17
    # 予算を再確認した裁定が古い順に積まれ、最後が現行の根拠になる。
    assert budget["budget_reconfirmation_refs"][0].endswith(
        "decision-2026-08-08-gp-001-m0-budget-exit-criteria.md"
    )
    assert budget["budget_reconfirmation_refs"][-1].endswith(
        "decision-2026-08-08-m0-budget-overrun.md"
    )


@pytest.mark.parametrize("name", RUNNERS)
def test_manifest_records_unknown_actuals_as_null(harness, tmp_path, name):
    """実績は runner が知り得ないため未指定なら null。`0` のような事実でない値を書かない。"""
    payload = _write(harness[name], tmp_path / name, {"v2-skill": 21})
    budget = payload["budget"]
    assert budget["actual_prs"] is None
    assert budget["actual_sessions"] is None
    assert budget["review_fix_rounds"] is None


@pytest.mark.parametrize("name", RUNNERS)
def test_budget_reconfirmation_refs_point_at_existing_files(harness, tmp_path, name):
    """予算の根拠が実在する裁定記録を指す（追随漏れをテストで落とす）。"""
    payload = _write(harness[name], tmp_path / name, {"v2-skill": 21})
    refs = payload["budget"]["budget_reconfirmation_refs"]
    assert refs
    for ref in refs:
        assert (REPO_ROOT / ref).exists(), ref
