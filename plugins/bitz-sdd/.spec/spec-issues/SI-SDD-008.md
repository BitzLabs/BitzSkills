---
id: SI-SDD-008
raised_by: 開発フロー振り返り（2026-07-18 セッション、SI-CORE-007 実装サイクルの実地観察）
target: plugins/bitz-sdd/skills/sdd-core references/lifecycle.md・sdd-test（軽量レーンの検証記録基準が未規定）
proposed_change_type: modify
status: open
---
- **目的**: 検証証跡の置き場がワークスペース間で非対称になっている。bitz-sdd ワークスペースは
  `.spec/specs/<feature>/test-spec.md` に検証記録を残すが、ルートワークスペースの
  軽量レーン実装（例: CORE-FR-012 / CORE-FR-013）は STATE.md の遷移記録 + PR 本文の実出力のみで
  verified 化している。どちらが規律上の要求水準なのかが未規定のため、ワークスペースごとに
  エージェントの判断がぶれる。
- **提案する修正**: 次のいずれかを人間が裁定し、lifecycle.md（と sdd-test）に明文化する:
  - **案A（推奨）**: 軽量レーンでは `.spec/specs/` の検証記録を必須とせず、
    「STATE.md の verified 遷移記録（実行したテスト・件数・機械チェック結果を actor 欄に記載）
    + PR 本文の実出力」で足りると規定する。通常フロー（Design Gate を通る変更）は従来どおり
    `.spec/specs/<feature>/` に記録する
  - **案B**: レーンに関わらず verified 化には `.spec/specs/<feature>/test-spec.md` を必須とする
    （ルートワークスペースにも specs/ を新設。過去分の遡及は不要と明記）
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`、
  `plugins/bitz-sdd/skills/sdd-test/SKILL.md`、bitz-sdd マニフェスト bump。
- **確認観点**: 既存の verified 済み要件が遡及で不適合にならないこと（後方互換の明記）。
  release_check / spec_inspect PASS。
- **影響推定・ロールバック**: ドキュメント追記のみ。該当節の revert で戻る。
- **依存**: なし。
