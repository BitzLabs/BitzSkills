---
id: SI-SDD-036
raised_by: SDD-DSN-010/011 起票時に実測（2026-07-30）
target: spec_inspect が design/stories/ を走査せず、spec_scaffold がファイル名で採番するため DSN の ID 衝突が無検出になる
proposed_change_type: modify
status: accepted
github_issue: https://github.com/BitzLabs/BitzSkills/issues/134
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
     なお `spec_inspect.py:97` に**重複 ID 検査は存在する**。走査対象外のファイルが
     見えないため発火しなかっただけであり、欠けているのは検査ではなく**走査範囲**である。
  2. **`spec_scaffold.py:52` が frontmatter の `id:` ではなくファイル名で採番する**
     （`directory.glob(f"{prefix}-*.md")`）。`domain-model.md`（`id: SDD-DSN-009`）や
     `worksheet.md`（`id: SDD-DSN-000`）のように **ID をファイル名に持たない成果物が
     採番から見えない**。ストーリーも `story-p1-*.md` という命名のため同様に見えない。
     結果として最大値を 005 と誤認し 006 を払い出した。

  **これは SI-SDD-006（2026-07-18）の再発である**。同 spec-issue は同種の採番衝突を扱い、
  提案1（正規表現をサフィックス付きファイル名へ緩和）で実装したが、**提案2「ファイル名でなく
  frontmatter の `id:` を正として走査する方式」は「実装時に判断してよい」として見送られた**。
  今回はまさにその見送った側の経路（ID をファイル名に持たない成果物・サブディレクトリ）で再発した。

  ID の一意性は `.spec/` スキーマの基礎であり、重複が無検出であることはトレーサビリティ全体の
  前提を崩す。
- **提案する修正**:
  1. `spec_inspect.py` の設計成果物の走査を `.spec/design/**/*.md`（再帰）へ広げる。
     少なくとも sdd-core が宣言する `stories/` を対象に含める。**既存の重複 ID 検査
     （`spec_inspect.py:97`）はこれだけで発火するようになる**
  2. 重複 ID を検出したとき、**両方のパスを示す**（現在は ID だけを報告し、どのファイルが
     衝突したか分からない）
  3. `spec_scaffold.py` の採番を**ファイル名ではなく frontmatter の `id:`** を根拠にする
     （＝ SI-SDD-006 提案2 の再提案）。走査範囲は 1 と揃える
  4. 未マージのブランチが払い出した ID は他ブランチから見えないため、採番衝突はブランチ跨ぎでも
     起こる（本 spec-issue 自身、初回 `SI-SDD-035` を払い出して別ブランチの同 ID と衝突した）。
     1 により重複はマージ後に検出できるようになるが、事前に防ぐ手を置くかは裁定点
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
- **依存**: `SI-SDD-006`（同種の採番衝突。提案2 が見送られた結果として本件が再発した）、
  `SDD-FR-001`（spec_inspect のタスク ID 既知化）ほか spec_inspect の走査契約に関する既存要件。
  `SI-SDD-033`（並行開発規律）— 提案4 のブランチ跨ぎ採番と論点が接する。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。sdd-core が宣言する `design/stories/` を走査対象へ入れ、既存の重複 ID 検査を宣言どおり発火させる |
| ガードレール抵触 | なし。読み取り専用の検査範囲拡大と採番根拠の変更 |
| 影響範囲 | sdd-core の `spec_inspect.py` / `spec_scaffold.py`、関連テスト、走査契約に関する SDD-FR 要件 |
| 軽量レーン適否 | 不適。走査範囲の拡大により幽霊参照・孤児判定の結果が変わりうる |

**推薦: accept（提案1〜3）**。ID の一意性は `.spec/` スキーマの基礎であり、重複が無検出である
ことはトレーサビリティ全体の前提を崩す。`SI-SDD-006` 提案2 を見送った経路での再発であり、
同じ判断を三度繰り返さない。**提案4（ブランチ跨ぎの事前防止）は見送りを推薦する** —
提案1 により重複はマージ後に必ず FAIL として検出でき、他ブランチの ref を読む機構は
`SI-SDD-033` の機械強制と所有者が重なるため、bitz-flow への移管方針が決まるまで実装しない。

## 実施

2026-07-30 に **accept（提案1〜3）**。裁定記録は
`.spec/reports/decision-2026-07-30-order8-design-foundation.md`（裁定H）。
ROADMAP 順序8 の最優先項目として、他3件（`SI-SDD-032` / `033` / `034`）より先に実装・land する。

- **提案1**（`design/**/*.md` の再帰走査）— 実装対象。裁定時の実測で、再帰化により新たに
  レジストリへ入るのは bitz-sdd の `design/stories/` の3件（`SDD-DSN-006` / `007` / `008`）だけ
  であり、`design/infra` はどのワークスペースにも存在しない。全7ワークスペースの重複 ID は
  現時点で 0 件のため、遡及 FAIL は生じない。
- **提案2**（重複時に両方のパスを示す）— 実装対象。
- **提案3**（frontmatter の `id:` を根拠にした採番）— 実装対象。`SI-SDD-006` 提案2 の再提案を
  今回は見送らない。
- **提案4**（ブランチ跨ぎ採番の事前防止）— **見送り**。提案1 により重複はマージ後に必ず
  FAIL として検出でき、他ブランチの ref を読む機構は `SI-SDD-033` の機械強制（同じく見送り）と
  所有者が重なる。bitz-flow への Git 運用移管が裁定されるまで実装しない。
  残余リスク（DSN 払い出し集中期の改番手戻り）は裁定記録に記載。
