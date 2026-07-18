#!/usr/bin/env python3
"""旧英語8章の docs/ を日本語6章へ安全に移行する。

既定はdry-run。`--apply` は全件preflight後にhash付きmanifestを残して移動し、
`--rollback` は移行後hashを全件照合してから逆順に戻す。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


MANIFEST_NAME = ".sdd-docs-migration.json"
MASTER_BACKUP_NAME = ".sdd-docs-migration-master.backup"
MANDATORY_FOLDERS = (
    "00_はじめに",
    "01_システム仕様",
    "02_ユースケース",
    "03_設計仕様",
    "04_テスト仕様",
    "05_リリース・運用",
)
LEGACY_FOLDERS = (
    "01-context",
    "02-design",
    "03-implementation",
    "04-quality",
    "05-operations",
    "06-reference",
    "07-governance",
    "08-knowledge",
)

EXACT_PATHS = {
    "01-context/constraints.md": "00_はじめに/制約.md",
    "01-context/glossary.md": "00_はじめに/用語集.md",
    "01-context/mission-vision.md": "00_はじめに/ミッション・ビジョン.md",
    "01-context/non-goals.md": "00_はじめに/対象外.md",
    "01-context/personas-journeys.md": "00_はじめに/ペルソナ・ジャーニー.md",
    "01-context/positioning.md": "00_はじめに/ポジショニング.md",
    "01-context/stakeholders.md": "00_はじめに/ステークホルダー.md",
    "01-context/success-metrics.md": "00_はじめに/成功指標.md",
    "02-design/ARCHITECTURE.md": "03_設計仕様/アーキテクチャ.md",
    "02-design/data-model.md": "03_設計仕様/データモデル.md",
    "02-design/domain-model.md": "03_設計仕様/ドメインモデル.md",
    "02-design/public-api.md": "03_設計仕様/公開API.md",
    "02-design/security-model.md": "03_設計仕様/セキュリティモデル.md",
    "02-design/decisions/ADR-template.md": "03_設計仕様/意思決定/ADR-template.md",
    "03-implementation/PATTERNS.md": "03_設計仕様/実装パターン.md",
    "04-quality/TESTING.md": "04_テスト仕様/テスト戦略.md",
    "05-operations/OPERATIONS.md": "05_リリース・運用/運用・リリース.md",
    "06-reference/EXTERNAL-APIS.md": "06_リファレンス/外部API.md",
    "07-governance/GOVERNANCE.md": "00_はじめに/ガバナンス.md",
    "08-knowledge/LESSONS_LEARNED.md": "05_リリース・運用/教訓.md",
    "08-knowledge/postmortems/POSTMORTEM-template.md": "05_リリース・運用/ポストモーテム/POSTMORTEM-template.md",
}
PREFIX_PATHS = (
    ("02-design/decisions/", "03_設計仕様/意思決定/"),
    ("08-knowledge/postmortems/", "05_リリース・運用/ポストモーテム/"),
    ("01-context/", "00_はじめに/"),
    ("02-design/", "03_設計仕様/"),
    ("03-implementation/", "03_設計仕様/"),
    ("04-quality/", "04_テスト仕様/"),
    ("05-operations/", "05_リリース・運用/"),
    ("06-reference/", "06_リファレンス/"),
    ("07-governance/", "00_はじめに/"),
    ("08-knowledge/", "05_リリース・運用/"),
)

SYSTEM_DOC = """---
id: DOC-system-overview
title: システム仕様
status: active
version: 0.1.0
changeImpact: high
project_type: both
updated: 2026-07-18
owner: human
---

# システム仕様

機能・非機能・制約の人間向け索引です。検証可能な契約の正本は `.spec/requirements/` に置きます。
"""
USECASE_DOC = """---
id: DOC-usecase-index
title: ユースケース一覧
status: proposed
version: 0.1.0
changeImpact: medium
project_type: both
updated: 2026-07-18
owner: human
---

# ユースケース一覧

利用者とシステムの対話への索引です。
"""
REGISTRY_ROWS = (
    "| DOC-system-overview | [システム仕様](01_システム仕様/システム仕様.md) | system | active | 0.1.0 | 機能・非機能・制約の索引 |",
    "| DOC-usecase-index | [ユースケース一覧](02_ユースケース/ユースケース一覧.md) | usecase | proposed | 0.1.0 | 利用シナリオの索引 |",
)


class MigrationError(Exception):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def target_for(rel: str) -> str:
    if rel in EXACT_PATHS:
        return EXACT_PATHS[rel]
    for old, new in PREFIX_PATHS:
        if rel.startswith(old):
            return new + rel[len(old):]
    raise MigrationError(f"CONFLICT: 移動先を決定できない: {rel}")


def set_frontmatter_value(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise MigrationError("CONFLICT: MASTER.md にfrontmatterがない")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise MigrationError("CONFLICT: MASTER.md のfrontmatterが閉じていない")
    prefix = key + ":"
    for i in range(1, end):
        if lines[i].startswith(prefix):
            lines[i] = f"{key}: {value}"
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    lines.insert(end, f"{key}: {value}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def transform_master(text: str, include_reference: bool) -> str:
    replacements = list(EXACT_PATHS.items()) + list(PREFIX_PATHS)
    for old, new in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(old, new)
    if include_reference:
        text = set_frontmatter_value(text, "optional_chapters", "reference")
    missing_rows = [row for row in REGISTRY_ROWS if row.split("|", 2)[1].strip() not in text]
    if missing_rows:
        block = "\n".join(missing_rows) + "\n"
        marker = "<!-- DOCUMENT_REGISTRY_END -->"
        if marker in text:
            text = text.replace(marker, block + marker, 1)
        else:
            text += "\n" + block
    return text


def build_plan(root: Path):
    docs = root / "docs"
    master = docs / "MASTER.md"
    if not docs.is_dir() or not master.is_file():
        raise MigrationError("CONFLICT: docs/MASTER.md が存在しない")

    legacy_files = []
    for folder in LEGACY_FOLDERS:
        base = docs / folder
        if base.is_dir():
            legacy_files.extend(path for path in base.rglob("*") if path.is_file())
    legacy_files = sorted(set(legacy_files))
    if not legacy_files:
        return docs, master, [], None, False

    existing_new = [folder for folder in MANDATORY_FOLDERS + ("06_リファレンス",) if (docs / folder).exists()]
    if existing_new:
        raise MigrationError(f"CONFLICT: 旧章と新章が混在している: {', '.join(existing_new)}")

    moves = []
    targets = {}
    for src in legacy_files:
        rel = src.relative_to(docs).as_posix()
        dst_rel = target_for(rel)
        if dst_rel in targets:
            raise MigrationError(f"CONFLICT: 複数ファイルが同じ移行先を要求: {targets[dst_rel]} / {rel} -> {dst_rel}")
        dst = docs / dst_rel
        if dst.exists():
            raise MigrationError(f"CONFLICT: 移行先が既に存在する: {dst_rel}")
        targets[dst_rel] = rel
        moves.append({"src": rel, "dst": dst_rel, "sha256": sha256(src), "completed": False})

    include_reference = any(item["src"].startswith("06-reference/") for item in moves)
    master_before = master.read_text(encoding="utf-8")
    master_after = transform_master(master_before, include_reference)
    return docs, master, moves, master_after, include_reference


def print_plan(moves, include_reference):
    print("DRY-RUN: 変更は行いません")
    for item in moves:
        print(f"MOVE: {item['src']} -> {item['dst']}")
    print("CREATE: 01_システム仕様/システム仕様.md")
    print("CREATE: 02_ユースケース/ユースケース一覧.md")
    print("UPDATE: MASTER.md の既知リンク")
    if include_reference:
        print("DECLARE: optional_chapters: reference")


def remove_empty_dirs(docs: Path, folders) -> None:
    candidates = []
    for folder in folders:
        base = docs / folder
        if base.is_dir():
            candidates.extend(path for path in base.rglob("*") if path.is_dir())
            candidates.append(base)
    for path in sorted(set(candidates), key=lambda p: len(p.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def apply_migration(root: Path) -> int:
    docs = root / "docs"
    manifest_path = docs / MANIFEST_NAME
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("state") == "applied":
            print("ALREADY-APPLIED: 既に日本語6章へ移行済みです")
            return 0
        if existing.get("state") == "applying":
            raise MigrationError("CONFLICT: 途中の移行manifestがある。先に --rollback を実行する")

    docs, master, moves, master_after, include_reference = build_plan(root)
    if not moves:
        print("ALREADY-APPLIED: 移行対象の旧英語章はありません")
        return 0

    created_dirs = list(MANDATORY_FOLDERS) + (["06_リファレンス"] if include_reference else [])
    created_files = [
        {"path": "01_システム仕様/システム仕様.md", "content": SYSTEM_DOC},
        {"path": "02_ユースケース/ユースケース一覧.md", "content": USECASE_DOC},
    ]
    for item in created_files:
        path = docs / item["path"]
        if path.exists():
            raise MigrationError(f"CONFLICT: 生成先が既に存在する: {item['path']}")
        item["sha256"] = hashlib.sha256(item["content"].encode("utf-8")).hexdigest()
        item["completed"] = False

    backup_path = docs / MASTER_BACKUP_NAME
    if backup_path.exists():
        raise MigrationError(f"CONFLICT: 既存のbackupがある: {MASTER_BACKUP_NAME}")
    manifest = {
        "schema_version": 1,
        "state": "applying",
        "moves": moves,
        "created_dirs": created_dirs,
        "created_files": created_files,
        "master": {
            "before_sha256": sha256(master),
            "after_sha256": hashlib.sha256(master_after.encode("utf-8")).hexdigest(),
            "updated": False,
            "backup": MASTER_BACKUP_NAME,
        },
    }
    atomic_json(manifest_path, manifest)
    backup_path.write_bytes(master.read_bytes())

    try:
        for folder in created_dirs:
            (docs / folder).mkdir(parents=True, exist_ok=True)
        for item in manifest["moves"]:
            src = docs / item["src"]
            dst = docs / item["dst"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            item["completed"] = True
            atomic_json(manifest_path, manifest)
        for item in manifest["created_files"]:
            path = docs / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item.pop("content"), encoding="utf-8")
            item["completed"] = True
            atomic_json(manifest_path, manifest)
        master.write_text(master_after, encoding="utf-8")
        manifest["master"]["updated"] = True
        manifest["state"] = "applied"
        atomic_json(manifest_path, manifest)
        remove_empty_dirs(docs, LEGACY_FOLDERS)
    except Exception as exc:
        atomic_json(manifest_path, manifest)
        raise MigrationError(f"移行途中で停止した。manifestから --rollback 可能: {exc}") from exc

    print(f"APPLIED: {len(moves)}ファイルを日本語6章へ移行しました")
    print("NEXT: docs_inspect.py --strict と git diff を確認してください")
    return 0


def rollback(root: Path) -> int:
    docs = root / "docs"
    manifest_path = docs / MANIFEST_NAME
    if not manifest_path.is_file():
        raise MigrationError("CONFLICT: rollback用manifestがない")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("state") == "rolled_back":
        print("ALREADY-ROLLED-BACK: 既に旧章へ戻っています")
        return 0
    if manifest.get("state") not in {"applying", "applied"}:
        raise MigrationError(f"CONFLICT: rollback不能なstate: {manifest.get('state')}")

    master = docs / "MASTER.md"
    backup = docs / manifest["master"]["backup"]
    if not backup.is_file():
        raise MigrationError("CONFLICT: MASTER backupがない")
    if manifest["master"].get("updated") and sha256(master) != manifest["master"]["after_sha256"]:
        raise MigrationError("CONFLICT: 移行後にMASTER.mdが変更されている")
    for item in manifest["moves"]:
        if not item.get("completed"):
            continue
        src, dst = docs / item["src"], docs / item["dst"]
        if src.exists() or not dst.is_file() or sha256(dst) != item["sha256"]:
            raise MigrationError(f"CONFLICT: rollback前hash/配置不一致: {item['dst']}")
    for item in manifest["created_files"]:
        if not item.get("completed"):
            continue
        path = docs / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise MigrationError(f"CONFLICT: 生成文書が変更されている: {item['path']}")

    if manifest["master"].get("updated"):
        master.write_bytes(backup.read_bytes())
    for item in reversed(manifest["created_files"]):
        if item.get("completed"):
            (docs / item["path"]).unlink()
    for item in reversed(manifest["moves"]):
        if not item.get("completed"):
            continue
        src, dst = docs / item["src"], docs / item["dst"]
        src.parent.mkdir(parents=True, exist_ok=True)
        dst.rename(src)
    remove_empty_dirs(docs, manifest.get("created_dirs", []))
    manifest["state"] = "rolled_back"
    atomic_json(manifest_path, manifest)
    print("ROLLED-BACK: 旧英語章へ復元しました")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BitzSDD docs: 旧英語8章から日本語6章への移行")
    parser.add_argument("--root", default=".", help="リポジトリルート")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="preflight成功後に移行を適用")
    mode.add_argument("--rollback", action="store_true", help="manifestを使って旧章へ復元")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.rollback:
            return rollback(root)
        if args.apply:
            return apply_migration(root)
        docs, _master, moves, _master_after, include_reference = build_plan(root)
        manifest = docs / MANIFEST_NAME
        if not moves and manifest.is_file():
            state = json.loads(manifest.read_text(encoding="utf-8")).get("state")
            if state == "applied":
                print("ALREADY-APPLIED: 既に日本語6章へ移行済みです")
                return 0
        if not moves:
            print("DRY-RUN: 移行対象の旧英語章はありません")
            return 0
        print_plan(moves, include_reference)
        return 0
    except (MigrationError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
