"""適合fixtureの選択と決定的な分割。分割は合否条件を変更しない。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# GitHub Actions run 36248419060（commit 9ade7d0f、CPython 3.12、ubuntu-24.04）の
# 独立2組の中央値。分割と所要時間の予測だけに使い、合否条件には使わない。
MODEL_SOURCE = {
    "runUrl": "https://github.com/BitzLabs/BitzSkills/actions/runs/36248419060",
    "commit": "9ade7d0f74fdec6878b5fddf15ea76fac23e1f68",
    "replicas": 2,
}
DEFAULT_SECONDS = 0.13
WORKER_OVERHEAD_SECONDS = 12.0
SCALE_SECONDS = {
    (False, "relationEdgeCount"): 104.70,
    (False, "traceEntryCount"): 102.20,
    (False, "specFileCount"): 53.50,
    (False, "verifyBindingCount"): 34.90,
    (False, "inputBytes"): 19.30,
    (False, "statementCount"): 7.84,
    (False, "commandDefinitionCount"): 2.75,
    (False, "memberCount"): 2.68,
    (True, "relationEdgeCount"): 31.85,
    (True, "traceEntryCount"): 34.73,
    (True, "specFileCount"): 9.40,
    (True, "verifyBindingCount"): 14.43,
    (True, "inputBytes"): 6.08,
    (True, "statementCount"): 0.78,
    (True, "commandDefinitionCount"): 2.64,
    (True, "memberCount"): 0.70,
}
STANDARD_SECONDS = {
    "SINGLE-126-12": 6.12,
    "SINGLE-126-13": 3.13,
    "SINGLE-059": 3.13,
    "SINGLE-126-15": 1.34,
    "SINGLE-126-08": 0.90,
    "SINGLE-001": 0.69,
    "SINGLE-003": 0.68,
    "SINGLE-073-02": 0.65,
    "SINGLE-002": 0.64,
    "SINGLE-035-02": 0.33,
    "SINGLE-064": 0.33,
}


def step_ids(step):
    steps = json.loads((ROOT / "steps.json").read_text())["steps"]
    if type(step) is not int or step not in {entry["step"] for entry in steps}:
        raise ValueError("steps.jsonに存在するStepを指定してください")
    return list(dict.fromkeys(identifier for entry in steps if entry["step"] <= step
                              for identifier in entry["fixtures"]))


def is_scale(identifier):
    return identifier.startswith(("MULTI-020-", "MULTI-021-"))


def estimated_seconds(identifier):
    """直近のCI実測からfixtureの所要時間を予測する。性能SLOや合否には使わない。"""
    if is_scale(identifier):
        path = ROOT / "multi" / identifier / "dataset.json"
        if not path.is_file():
            return DEFAULT_SECONDS
        dataset = json.loads(path.read_text())
        return SCALE_SECONDS[(dataset["crosses"], dataset["dimension"])]
    return STANDARD_SECONDS.get(identifier, DEFAULT_SECONDS)


def predicted_seconds(identifiers, worker_overhead=False):
    seconds = sum(estimated_seconds(identifier) for identifier in identifiers)
    return seconds + (WORKER_OVERHEAD_SECONDS if worker_overhead else 0.0)


def partition(identifiers, shards):
    if type(shards) is not int or not 1 <= shards <= len(identifiers):
        raise ValueError("分割数は1以上、fixture件数以下にしてください")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("fixture IDが重複しています")
    groups = [[] for _ in range(shards)]
    costs = [0.0] * shards
    weights = {identifier: estimated_seconds(identifier) for identifier in identifiers}
    for identifier in sorted(identifiers, key=lambda value: (-weights[value], value)):
        index = min(range(shards), key=lambda n: (costs[n], n))
        groups[index].append(identifier)
        costs[index] += weights[identifier]
    order = {identifier: index for index, identifier in enumerate(identifiers)}
    return [sorted(group, key=order.__getitem__) for group in groups]


def partition_plan(identifiers, shards):
    """分割内容と、jobの固定時間を含む予測秒数を返す。"""
    return [{"shard": index, "fixtureCount": len(group),
             "predictedSeconds": round(predicted_seconds(group, worker_overhead=True), 1),
             "fixtures": group}
            for index, group in enumerate(partition(identifiers, shards), 1)]


def selected_ids(identifiers, suite="full", shard=1, shards=1):
    if suite not in ("full", "standard", "scale"):
        raise ValueError("suiteが不正です")
    chosen = [identifier for identifier in identifiers
              if suite == "full" or is_scale(identifier) == (suite == "scale")]
    if type(shard) is not int or not 1 <= shard <= shards:
        raise ValueError("shardは1以上、shards以下にしてください")
    return partition(chosen, shards)[shard - 1]
