---
id: SI-CORE-018
raised_by: プロジェクト改修計画 追加要望（2026-07-12 ユーザー提案: フェーズ・ステータス表記の日本語化）
target: bitz-sdd / bitz-ddd のフェーズ・ステータス表記（表示層）
proposed_change_type: bump
status: accepted
---
- **目的**: bitz-sdd / bitz-ddd のフェーズとステータスを「採用・未採用・開発中・
  ○○待機中」のような日本語表記にし、人間が状態を直読できるようにする。
- **設計方針（推奨案）**: **frontmatter の機械値は英語のまま維持し、表示層だけを
  日本語化する**。理由: 既存の全ワークスペース約111ファイルと spec_inspect.py が
  英語機械値に依存しており、値そのものの日本語化は全ファイル移行 + 全ツール改修 +
  外部利用プロジェクトの後方互換を要する高リスク変更のため（値の日本語化を望む場合は
  本 ISSUE の裁定時に代替案として人間が選択する。その場合は正規化層 + 移行スクリプトを追加）。
- **提案する修正**:
  1. **対訳表の制定（SSOT）**: sdd-core references/lifecycle.md に対訳表を定義し、
     機械可読辞書（labels_ja）をスクリプト側に1箇所だけ持つ。対訳案:
     - 要件: draft=起草中（承認待機中）/ approved=承認済み（採用）/ implementing=開発中 /
       verified=検証済み / promoted=昇格済み / deprecated=廃止
     - spec-issue: open=裁定待機中 / accepted=採用 / rejected=未採用
     - タスク: pending=着手待機中 / implementing=開発中 / blocked=依存待機中 / done=完了
     - フェーズ: Map=把握 / Discuss=設計討議 / Plan=計画 / Execute=実装 / Verify=検証 /
       Promotion Gate=昇格ゲート（訳語の最終確定は人間裁定）
  2. **表示への適用**: spec_inspect.py のレポート、spec_status.py（SI-CORE-011）、
     sdd_report.py の status-report、各 SKILL.md / references の表を日本語表記
     （必要なら「日本語（機械値）」併記）に統一する
  3. **入力の受理**: spec_update.py（SI-CORE-012）が日本語表記の入力（例: 「採用」）を
     機械値（accepted）へ正規化して書き込めるようにする（テスト先行）
  4. **bitz-ddd**: ddd-evaluate の成熟度レベル・MMI 採点表の表示も同じ対訳方針で日本語化する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`（対訳表）、
  `spec_inspect.py` / `spec_status.py` / `sdd_report.py` / `spec_update.py`（表示・正規化）、
  bitz-sdd / bitz-ddd の SKILL.md・references の状態表、`tests/`（正規化と表示の回帰テスト先行）、
  両プラグインのマニフェスト bump。
- **確認観点**:
  - frontmatter の既存機械値に diff が出ないこと（表示層のみの変更であることがレビューの中心）
  - spec_inspect / release_check / `.venv/bin/pytest` が PASS
  - 日本語入力の正規化で未知語がエラーになること（曖昧な状態値の混入防止）
  - 対訳の定義箇所が lifecycle.md + 辞書1箇所に閉じていること（訳語変更が1 PR で済む）
- **影響推定・ロールバック**: 表示層のみなのでデータ移行なし。表示部の revert だけで戻る。
- **依存**: SI-CORE-011 / 012（表示・正規化の実装先スクリプト）。対訳表の制定（修正1）のみ先行可。
- **裁定（2026-07-13, 人間）**: **表示層のみ日本語化** を採用。frontmatter の機械値は英語のまま維持し、レポート・表示のみ対訳辞書で日本語化する（値の日本語化＝機械値移行は不採用）。
