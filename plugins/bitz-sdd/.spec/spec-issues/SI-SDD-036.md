---
id: SI-SDD-036
raised_by: SDD-DSN-010/011 起票時に実測（2026-07-30）
target: spec_inspect が design/stories/ を走査せず、spec_scaffold がファイル名で採番するため DSN の ID 衝突が無検出になる
proposed_change_type: modify
status: open
---
- **目的**: `spec_scaffold.py design` が既存の `SDD-DSN-006` / `SDD-DSN-007`（ドメインストーリー）と
  **同一 ID を払い出した**。sdd-core は「`spec_scaffold.py` は採番衝突を構造的に防ぐ」と規定するが、
  実測では防げていない。原因は独立した2つの欠陥である。
  1. **`spec_inspect.py:75-82` が `.spec/design/stories/` を走査しない**。走査対象は
     `.spec/design` と `.spec/design/infra` の非再帰 `glob("*.md")` のみ。sdd-core の
     ディレクトリ構成は `design/stories/` を「ドメインストーリー個別ファイル」として宣言して
     いるのに、そこにある `SDD-DSN-006` / `007` / `008` の**3成果物は機械検証の対象外**である。
     衝突を起こした状態で `spec inspect --workspace . plugins/*` を実行しても **PASS** し、
     Traceability Matrix には重複 ID が1行しか出ない（draft の新規ファイルが active の
     ストーリーを**無言で覆い隠す**）。さらに `SDD-DSN-008` は Matrix から**完全に消えている**。
  2. **`spec_scaffold.py:52` が frontmatter の `id:` ではなくファイル名で採番する**
     （`directory.glob(f"{prefix}-*.md")`）。`domain-model.md`（`id: SDD-DSN-009`）や
     `worksheet.md`（`id: SDD-DSN-000`）のように **ID をファイル名に持たない成果物が
     採番から見えない**。ストーリーも `story-p1-*.md` という命名のため同様に見えない。
     結果として最大値を 005 と誤認し 006 を払い出した。

  ID の一意性は `.spec/` スキーマの基礎であり、重複が無検出であることはトレーサビリティ全体の
  前提を崩す。
- **提案する修正**:
  1. `spec_inspect.py` の設計成果物の走査を `.spec/design/**/*.md`（再帰）へ広げる。
     少なくとも sdd-core が宣言する `stories/` を対象に含める
  2. `spec_inspect.py` に**重複 ID 検査**を追加する。同一 ID が2つ以上の成果物に現れたら FAIL とし、
     両方のパスを示す（現状は無言で片方を捨てている）
  3. `spec_scaffold.py` の採番を**ファイル名ではなく frontmatter の `id:`** を根拠にする。
     走査範囲は 1 と揃える
  4. 未マージのブランチが払い出した ID は他ブランチから見えないため、採番衝突はブランチ跨ぎでも
     起こる（本 spec-issue 自身、初回 `SI-SDD-035` を払い出して別ブランチの同 ID と衝突した）。
     2 の重複 ID 検査があればマージ時に検出できる。追加の予防策を置くかは裁定点
- **対象ファイル**: `skills/sdd-core/scripts/spec_inspect.py`、`skills/sdd-core/scripts/spec_scaffold.py`、
  `tests/test_spec_inspect.py`、`tests/test_spec_scaffold.py`（無ければ新設）、
  関連する SDD-FR 要件（設計成果物の走査範囲・採番契約）。
- **確認観点**: `SDD-DSN-006〜008` が Traceability Matrix に現れること。重複 ID を作ると
  `spec inspect` が FAIL すること。`domain-model.md` / `worksheet.md` のように ID を
  ファイル名に持たない成果物を採番が正しく数えること。既存ワークスペース
  （ルート / bitz-env / bitz-flow / bitz-ddd）を遡及的に FAIL させないこと。
- **影響推定・ロールバック**: 検査の追加は加法的だが、**走査範囲の拡大により既存の
  幽霊参照・孤児判定の結果が変わりうる**ため軽量レーン不可。重複 ID 検査は FAIL 条件の
  追加であり、導入前に全ワークスペースで空振りすることを確認する。ロールバックは
  検査単位で無効化できる。
- **依存**: `SDD-FR-001`（spec_inspect のタスク ID 既知化）ほか spec_inspect の走査契約に関する
  既存要件。`SI-SDD-033`（並行開発規律）— 提案4 のブランチ跨ぎ採番と論点が接する。
