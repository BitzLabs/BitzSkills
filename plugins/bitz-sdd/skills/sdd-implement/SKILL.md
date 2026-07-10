---
name: sdd-implement
description: BitzSDD の実装工程を行うスキル。承認済み（approved）要件を .spec/tasks/ のタスクへ分解（1タスク1ファイル、implements / depends_on / boundary 宣言）し、要件 ID に紐づけた実装を規律（契約保護・境界厳守・タスク単位コミット）に従って進める。ユーザーが「実装して」「タスクに分解して」「タスク分解」「並列で実装」「implements」と言及したとき、または Design Gate 通過後に実装フェーズへ移行するときに使用する。テスト仕様の導出と検証は sdd-test が担当する。
metadata:
  version: "0.1.1"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-11"
---

# SDD Implement — タスク分解と実装の規律

Design Gate を通過した承認済み要件を、並列実行に耐えるタスク群へ分解し、
要件 ID へのトレーサビリティを保ったまま実装します。

## 前提

*   対象要件が `approved` であること（draft のまま実装を始めない。ゲートは `sdd-core` の references/gates.md が正）。
*   タスクの frontmatter 書式は `sdd-core` の assets/artifact-frontmatter.md（公開契約）の ID 規律に従う（`TSK` プレフィックス）。

## 実行手順

1.  **タスク分解**: `references/task-decomposition.md` に従い、`.spec/tasks/` に1タスク1ファイルで作成する。
    各タスクに `implements`（要件 ID）/ `depends_on` / `boundary` を必ず宣言する。
    契約固定 → ドメイン → インフラ → 結線の4フェーズパターンで依存グラフを構築する。
2.  **並列投入の判定**: `depends_on` が解決済みかつ `boundary` が互いに素なタスク群のみ並列投入する。
    並列時のブランチ運用・権限マトリクスは `sdd-core` の references/parallel-git.md に従う。
3.  **実装の規律**: `references/implementation-discipline.md` に従う。
    boundary 外への書き込み禁止・契約（API シグネチャ / スキーマ / 公開インターフェース）の独断変更禁止。
    契約変更が必要になったら実装を中断し `.spec/spec-issues/` へ起票して人間の裁定を待つ。
4.  **コミット**: 1タスク = 1論理コミット。メッセージにタスク ID と要件 ID を含める
    （例: `feat(domain): [TSK-042] ... (implements FR-012)`）。

## 後続工程

*   実装が揃ったら `sdd-test` でテスト仕様の導出・検証に進む。
*   要件カバレッジと境界厳守の機械検証は `sdd-core` 同梱の `spec_inspect.py`（implements マップ突合）が行う。
