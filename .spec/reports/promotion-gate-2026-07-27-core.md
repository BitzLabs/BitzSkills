# Promotion Gate 裁定記録 — ルートワークスペース CORE 要件 25 件

- **日付**: 2026-07-27
- **対象ワークスペース**: `/`（ルート = マーケットプレイス `bitzskills`）
- **裁定者（人間）**: hide
- **裁定の形式**: セッション内の対話裁定。「SDD の未 Promoted を Promote できますか」の問いに対し、
  対象範囲「ルート CORE 25 件のみ」・実行経路「代行可視化経路（エージェントが実行）」を選択
- **代行実行者（エージェント）**: claude-code
- **遷移**: `verified → promoted`

## 対象要件（25 件）

CORE-CON-001 / CORE-CON-002 / CORE-CON-003 / CORE-CON-004 / CORE-CON-005 /
CORE-CON-006 / CORE-CON-007 / CORE-CON-008 / CORE-CON-009 / CORE-CON-010 /
CORE-FR-001 / CORE-FR-002 / CORE-FR-003 / CORE-FR-006 / CORE-FR-007 /
CORE-FR-008 / CORE-FR-009 / CORE-FR-010 / CORE-FR-012 / CORE-FR-013 /
CORE-FR-014 / CORE-FR-015 / CORE-FR-016 / CORE-FR-017 / CORE-NFR-001

対象外: CORE-FR-004 / CORE-FR-005（deprecated）、CORE-FR-011（2026-07-27 に promoted 済み）。

## チェックリスト（gates.md「3. Promotion Gate」）

1. **docs/ 更新ドラフトの承認** — 追加ドラフトなし。`docs/` は日本語必須 6 章がすべて
   `status: active` で整備済み（コミット `8731ce7`）。`spec inspect` の「docs 乖離（派生元 docs が
   派生後に変更された要件 — stale 候補）」は **なし ✅**
2. **LESSONS_LEARNED 候補の取捨選択** — 新規採用なし。`docs/05_リリース・運用/教訓.md` に
   LL-0001〜LL-0003 を収録済みで、本昇格に伴って新たに恒久化すべき知見は生じていない
3. **tombstone テストの削除可否判定** — 該当なし（リポジトリに tombstone テストは存在しない）
4. **stale マークゼロの確認** — **0 件 ✅**（`spec inspect --workspace . plugins/*` が全ワークスペース PASS。
   幽霊参照 0 / 実装待ち要件 0 / 孤児要件 0 / 未参照要件 0 / docs 乖離 0）
5. **代行遷移（agent-proxy-unverified）の decision-ref 確認** — 昇格前時点で本ワークスペースの
   代行経路遷移は **0 件**（`spec status` の経路別集計: 対話確認 2 / 代行 0）。
   対話確認 2 件は CORE-FR-004 / CORE-FR-005 の deprecated 化。
   本記録による昇格自体が代行経路 25 件となるため、次回ゲートでの確認対象は本ファイルとなる
6. **（任意）sdd-review の実行** — 省略。docs/ 更新ドラフトが無く、直近の統合レビュー
   `CORE-REV-002` は PASS 判定済み
7. **specs/&lt;feature&gt;/ のアーカイブ** — 該当なし（ルートに `.spec/specs/` は存在せず、直近 feature の
   test-spec は `.spec/archive/2026-07-27-spec-wrapper-codex-resolution/` へアーカイブ済み）

## 検証証跡（昇格実行前に取得）

| 検査 | 結果 |
|---|---|
| `python3 scripts/release_check.py` | **PASS（全チェック合格）** |
| `.venv/bin/pytest -q` | **361 passed in 7.90s** |
| `spec inspect --workspace . plugins/*` | **PASS ✅** |
| `spec status .` | 要件 28（verified 25 / promoted 1 / deprecated 2）、タスク 28 全件 done、spec-issue 35（open 0） |

## 残余リスク（lifecycle.md の規定どおり）

代行可視化経路が保証するのは「裁定の所在が正直に記録されること」までで、`--on-behalf-of` /
`--actor` / `--decision-ref` のいずれも本人認証や裁定の真正性証明ではない。参照先の裁定が当該遷移を
本当に許可したかの確認は、次回 Promotion Gate の人間確認とレビューに残る。

## 既知の環境課題（本昇格の合否には影響しない）

`scripts/spec` ラッパーが固定版競合で停止する状態にある（`claude=3.1.0, codex=3.0.1`）。
Claude 側キャッシュのみ bitz-sdd 3.1.0 に更新され、Codex 側が 3.0.1 のまま残っているため、
SI-CORE-034 の設計どおり安全側で停止している。本作業では
`BITZSKILLS_PLUGINS_DIR=~/.claude/plugins` を明示して迂回した。恒久対処は Codex プラグインの更新（人間側操作）。
