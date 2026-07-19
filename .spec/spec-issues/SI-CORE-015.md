---
id: SI-CORE-015
raised_by: プロジェクト改修計画（2026-07-12 ユーザー要望 5。docs/improvement_master_plan.md）
target: sdd-core の spec-issue 運用（ルート/サブ SPEC 間の委託フローが未規定）
proposed_change_type: bump
status: accepted
origin: root
delegated_to: bitz-sdd:SDD-FR-132
---
- **目的**: ルート SPEC とサブ（ワークスペース）SPEC 間の issue 委託を正式なフローにする。
  現状は SI-CORE-003 →SDD-FR-001 の引き継ぎのように本文の自由記述で行われており、
  機械検証も追跡もできない。
- **提案する修正**（**テスト先行**）:
  1. spec-issue frontmatter を拡張する: `origin:`（起票ワークスペース）と
     `delegated_to:`（委託先ワークスペース + 引き継ぎ先 ID）。既存 SI は変更不要（後方互換）
  2. 委託フローを lifecycle.md に規定する:
     - サブ→ルート: 共通規約・複数プラグインに跨る問題はルートへ**エスカレーション**
     - ルート→サブ: 単一プラグインに閉じる問題はサブへ**委任**（SI-CORE-003 の手作業を正式化）
     - サブ↔サブ: **ルート経由を原則**とする。例外として `metadata.dependencies`
       （SI-CORE-007）で依存宣言済みのペアに限り直接委託を許可（依存の向きに沿う方向のみ）
     - ルート SPEC 不在のリポジトリ: ルート `.spec/` を作成してから委託する
       （既存のルート作成フローどおり）
  3. spec_inspect.py に workspace 横断チェックを追加する:
     `delegated_to` の先に対応するファイルが存在するか、双方向リンクが取れているか
- **対象ファイル**: `tests/`（先行）、
  `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py`、
  `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`、bitz-sdd マニフェスト bump。
- **確認観点**:
  - 既存 SI ファイル（拡張フィールドなし）が FAIL しないこと（後方互換の回帰テスト）
  - 委託リンク切れが FAIL として検出されること
  - 本リポジトリの `--workspace . plugins/*` 一括検証が PASS
- **影響推定・ロールバック**: 検証の追加と規定の追記。spec_inspect の追加チェックを
  revert すれば戻る（frontmatter 拡張は additive なので残っても無害）。
- **依存**: SI-CORE-012（起票スクリプトに委託フィールドを組み込むため）、SI-CORE-007（サブ間直接委託の許可条件）。
- **着手時裁定（2026-07-19, 人間・チャット指示）**:
  - サブ↔サブ直接委託の例外条項（`metadata.dependencies` 宣言済みペアに限る許可）は
    **不採用**。「複数サブに影響する問題はルートで管理し各サブへ依頼を出す」構成に従い、
    委託方向をサブ→ルート（エスカレーション）/ ルート→サブ（委任）の2方向に単純化する
  - 機械検証は ID 実在 + 双方向言及のみ（`<ws>:` 修飾部は人間向け情報として検証しない）
  - 実装は bitz-sdd ワークスペースへ委任（SDD-FR-132。本 frontmatter の
    `delegated_to:` が委託フロー自体のドッグフーディング実例）
  - 起票後に SI-CORE-031/032 で提案書式がデファクト運用済みとなったため、
    本件は「新設」ではなくデファクト書式の追認 + lifecycle.md の穴埋め + 機械検証の追加
- **実施**: 2026-07-19 SDD-FR-132 / SDD-TSK-017 として実装完了・verified 到達。
  テスト先行（tests/test_spec_inspect.py 委託7ケース + tests/test_spec_scaffold.py 2ケース）→
  spec_inspect.py の横断検証（load_spec_issues / build_delegation_context / check_delegations）、
  spec_scaffold.py の `--origin` / `--delegated-to`、lifecycle.md「ワークスペース間の
  spec-issue 委託」節、sdd-issue SKILL.md 手順4更新、bitz-sdd 2.3.0 bump。
  既存 SI（031/032 実運用データ）の後方互換を `--workspace . plugins/*` 一括 PASS で確認。
