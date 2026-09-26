"""適合fixtureの選択と決定的な分割。分割は合否条件を変更しない。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def step_ids(step):
    steps = json.loads((ROOT / "steps.json").read_text())["steps"]
    if type(step) is not int or step not in {entry["step"] for entry in steps}:
        raise ValueError("steps.jsonに存在するStepを指定してください")
    return list(dict.fromkeys(identifier for entry in steps if entry["step"] <= step
                              for identifier in entry["fixtures"]))


def is_scale(identifier):
    return identifier.startswith(("MULTI-020-", "MULTI-021-"))


def estimated_cost(identifier):
    # 初期の配分用相対重み。合否や実測の性能SLOには使わない。
    # relation/traceのlimitケースはローカルで約41秒。その他は保守的な推定。
    if is_scale(identifier):
        path = ROOT / "multi" / identifier / "dataset.json"
        if not path.is_file():
            return 0.3
        dataset = json.loads(path.read_text())
        return {"relationEdgeCount": 42, "traceEntryCount": 42, "inputBytes": 10,
                "specFileCount": 12, "statementCount": 12, "commandDefinitionCount": 12,
                "verifyBindingCount": 20, "memberCount": 2}[dataset["dimension"]]
    return 0.3


def partition(identifiers, shards):
    if type(shards) is not int or not 1 <= shards <= len(identifiers):
        raise ValueError("分割数は1以上、fixture件数以下にしてください")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("fixture IDが重複しています")
    groups = [[] for _ in range(shards)]
    costs = [0.0] * shards
    weights = {identifier: estimated_cost(identifier) for identifier in identifiers}
    for identifier in sorted(identifiers, key=lambda value: (-weights[value], value)):
        index = min(range(shards), key=lambda n: (costs[n], n))
        groups[index].append(identifier)
        costs[index] += weights[identifier]
    order = {identifier: index for index, identifier in enumerate(identifiers)}
    return [sorted(group, key=order.__getitem__) for group in groups]


def selected_ids(identifiers, suite="full", shard=1, shards=1):
    if suite not in ("full", "standard", "scale"):
        raise ValueError("suiteが不正です")
    chosen = [identifier for identifier in identifiers
              if suite == "full" or is_scale(identifier) == (suite == "scale")]
    if type(shard) is not int or not 1 <= shard <= shards:
        raise ValueError("shardは1以上、shards以下にしてください")
    return partition(chosen, shards)[shard - 1]
