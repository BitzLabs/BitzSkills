"""Schema fileの場所を解決する。

公開結果とFrontmatterのSchemaは契約の正本であり、docs/03.詳細設計/schemas/に置く（ADR-050）。
fixture自身の形式を定めるmanifestと副作用のSchemaは、fixtureのroot directoryに置く。
"""
from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[2] / "docs/03.詳細設計/schemas"
CONTRACT_NAMES = frozenset({"result", "frontmatter"})


def schema_path(root, name):
    if name in CONTRACT_NAMES:
        return CONTRACT / f"{name}.schema.json"
    return Path(root) / f"{name}.schema.json"
