---
id: SDD-FR-123
version: 1.0
status: verified
domain: verification
priority: medium
origin: SI-SDD-008
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-123 軽量レーンの検証証跡基準

- **対応設計**: SDD-DSN-001
- **説明**: 軽量レーンでは `.spec/specs/<feature>/test-spec.md` を verified 化の必須証跡とせず、
  version 管理される STATE.md の遷移記録を検証判定の正本とし、PR がある場合は本文に残した
  実出力を配布時の証跡として組み合わせる。
  通常フローでは従来どおり `.spec/specs/<feature>/` にテスト仕様を記録する。
  本基準は今後の遷移に適用し、既存の verified 要件へ遡及適用しない。
- **受入基準 (EARS)**:
  - WHEN 軽量レーンの要件を verified へ遷移する THEN エージェントは STATE.md の actor 記録に秘匿情報を除いた対象リビジョン・実行コマンド・収集した期待件数・成功失敗スキップ件数・終了コード・機械チェック結果・実行日を含めること SHALL
  - WHERE version 管理される検証証跡に token・credential・その他の秘密値が含まれ得る THE エージェントは秘密値をプレースホルダー化し、安全な CI run または保護ログへの参照だけを記録すること SHALL
  - IF 必須検証が失敗・中断・結果欠落・期待件数不一致のいずれかである THEN エージェントは要件を verified へ遷移しないこと SHALL
  - IF 検証にスキップが含まれる THEN エージェントは各スキップの理由と要件または検収規律が許容する根拠を STATE.md に記録すること SHALL
  - IF 許容根拠のないスキップが1件以上ある THEN エージェントは要件を verified へ遷移しないこと SHALL
  - WHEN 軽量レーンの変更を PR として提出する THEN 開発者は PR 本文に秘匿情報を除いた検証コマンドの実出力を含めること SHALL
  - IF PR が存在しない THEN エージェントは STATE.md の正本記録だけで検証結果を再判定できる情報を保持すること SHALL
  - IF STATE.md と PR 本文の検証結果が一致しない THEN エージェントは STATE.md を正として PR 本文を訂正するまで verified へ遷移しないこと SHALL
  - WHEN verified 後に PR を提出または更新する THEN PR reviewer は STATE.md との一致を再確認し、不一致が解消するまでマージを拒否すること SHALL
  - WHERE STATE.md の必須フィールドが揃い、全必須検証が green で、結果欠落と未許容スキップがなく、PR がある場合は本文と一致する THE sdd-test は `.spec/specs/<feature>/test-spec.md` を必須としないこと SHALL
  - WHEN 通常フローでテストを実装した THEN sdd-test はテスト仕様を `.spec/specs/<feature>/` に記録すること SHALL
  - WHERE 本基準の適用開始前に verified へ到達した要件 THE sdd-test は検証証跡の遡及追加を要求しないこと SHALL
  - WHEN 軽量レーンの変更を検収する THEN PR reviewer または PR がない場合の実行エージェントは必須証跡チェックリストを全項目確認すること SHALL
  - WHEN 本要件を実装した変更を検収する THEN 開発者は release_check と全ワークスペースの spec inspect が PASS することを確認 SHALL
- **検証手段**: lifecycle.md と sdd-test/SKILL.md に、STATE.md を正本とする必須フィールド、
  red・欠落・不一致時の verified 拒否、PR の有無による証跡、通常フローの記録継続、
  既存 verified 要件への非遡及が明記されていることを目視確認する。release_check と
  全ワークスペースの spec inspect を実行する（manual-check）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
  - 1.0 (2026-07-18) SI-SDD-008 の起票時前提を再検証。ルート軽量レーンに
    `.spec/specs/` は存在せず、通常フロー側には記録実績があるため前提と提案趣旨に乖離なし。
