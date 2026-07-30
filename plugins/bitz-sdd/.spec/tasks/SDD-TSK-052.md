---
implements: SDD-FR-163
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py, plugins/bitz-sdd/skills/sdd-core/SKILL.md, plugins/bitz-sdd/skills/sdd-core/references/gates.md, tests/test_spec_status.py
status: done
---

### done フェーズの不変条件を実装しフェーズと次アクションの整合を固定する

- **作業内容**:
  1. `determine_phase()` に `n_draft` を導入し、最終分岐の前に「`draft` 要件が残る限り
     `done` を返さない（`plan` を返す）」段を加える。既存の `phase_code` 語彙は変更しない。
  2. 回帰テスト5件を追加 — 完了済みベースラインへ `draft` を足した状態が `plan` になること、
     `draft` が無い完了状態が `done` を維持すること、`phase_code` と `next_actions` が
     同じ工程を案内すること、`done` 時に未処理を促す次アクションが出ないこと、
     status 進行でフェーズが後退しないこと。
  3. `sdd-core` SKILL.md のフェーズ・ルーティング節と `references/gates.md` の
     ゲート対応節へ、`done` の不変条件を明記する。
- **検証**:
  - `pytest` 全スイート PASS。`tests/test_spec_labels.py` と `release_check.py` の
    フェーズ語彙照合が PASS することで語彙が7語のままであることを確認。
  - 修正前スクリプト（`origin/main`）との比較で、`verified` 要件1件＋`draft` 要件1件＋
    `done` タスク1件の workspace が修正前 `Done（確定待ち: Promotion Gate）`、
    修正後 `Plan（要件定義）` になることを実測。
  - `phase_code` を条件分岐に使う箇所を棚卸しし、影響が無いことを確認した — 分岐は
    `spec_status.py` 自身の `next_actions`（`design` / `plan` / `verify` の3箇所）だけで、
    他スキルは表示用の `phase` を読むのみ。`plan` 分岐は `n_tasks == 0` を併せて要求するため
    完了済み系列（タスクあり）では発火しない。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
