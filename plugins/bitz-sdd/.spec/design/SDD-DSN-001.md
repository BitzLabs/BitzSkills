---
id: SDD-DSN-001
title: "検証証跡と unit-test 語彙の後方互換拡張"
status: active
version: 1.0
updated: 2026-07-18
owner: hide
implements: SDD-FR-123, SDD-FR-124
origin: SI-SDD-008, SI-SDD-009
---

# SDD-DSN-001 検証証跡と unit-test 語彙の後方互換拡張

- **背景 / 課題**:
  - 軽量レーンと通常フローで `.spec/specs/` の要求水準が明文化されておらず、verified の
    証跡判断がワークスペースごとに分かれている。
  - 自動ユニット／回帰テストを表す統制語彙がなく、`example-test` が代用されている。
- **設計判断**:
  1. 軽量レーンは `.spec/specs/` を必須にせず、version 管理される STATE.md の遷移記録を
     検証判定の正本とする。記録には対象リビジョン（コミット SHA、未コミットなら base HEAD と
     working tree の明記）、コマンド、収集した期待件数、成功失敗スキップ件数、終了コード、
     機械チェック結果、実行日を含め、実績合計と期待件数を照合する。スキップは理由と
     要件または検収規律が許容する根拠を記録し、未許容スキップ、失敗・中断・結果欠落・
     期待件数不一致では verified を拒否する。PR がある場合は
     STATE.md を含む version 管理証跡では token・credential・その他の秘密値をプレースホルダー化し、
     完全ログが必要なら安全な CI run または保護ログへの参照だけを記録する。PR 本文へも
     秘匿情報を除いた実出力を転載し、不一致時は
     STATE.md を正として PR を訂正する。verified 後の PR 提出・更新でも再照合し、
     不一致が残る間はマージを拒否する。PR がない場合も
     STATE.md の情報だけで判定を再現できるようにする。通常フローは従来の
     `.spec/specs/<feature>/` 記録を維持する。
  2. `verification_method` に `unit-test` を後方互換な列挙値として追加する。
     定義元は spec_inspect.py の `VMETHODS` のままとし、scaffold は import により共有する。
  3. 既存の verified 要件と `example-test` 宣言には遡及変更を要求しない。
  4. `unit-test` は bitz-sdd 1.11.4 以降で利用可能とする。プロジェクトが固定する実行版が
     それより古い場合は使用せず、先にプラグインを更新する。旧版 inspect が語彙外として
     拒否する挙動は、安全側停止として維持する。
  5. 証跡の必須項目は lifecycle.md と sdd-test のチェックリストで監査する。今回の変更では
     STATE.md の自由記述契約を構造化し直す自動検査までは導入せず、欠落時は verified を拒否する。
     自動検査が必要になった場合は別の spec-issue として契約変更を裁定する。
  6. SI-SDD-008 案Aは PR ベースの開発を前提としていたが、BitzSDD の公開規律は PR を使わない
     ワークスペースでも適用されるため、PR 不在時は STATE.md 単独で再判定可能にする補正を加える。
     PR がある場合の STATE.md + PR 本文という案Aの要求水準は維持する。
- **契約境界**:
  - 変更する契約: verified 証跡のレーン別規律、requirement frontmatter の許容列挙値。
  - 維持する契約: 既存の verification_method 値、spec_scaffold/spec_inspect の CLI、
    通常フローのテスト仕様記録先、3マニフェストの同値性。
- **代替案と却下理由**:
  - 全レーンで `.spec/specs/` を必須化する案は、軽量レーンの目的に対して証跡作成コストが大きく、
    過去の verified 要件を不適合にし得るため採用しない。
  - `example-test` の定義だけを拡張する案は、自動テストと有限入出力例の区別が集計上残らないため採用しない。
- **影響範囲・ロールバック**: sdd-core の lifecycle/verification、spec_inspect の語彙、
  sdd-test の記録規律、回帰テスト、プラグイン version に限定し、すべてを bitz-sdd 1.11.4 の
  同一リリースへ含める。撤回時は maintainer が
  `rg -n '^verification_method: unit-test$' --glob '**/.spec/requirements/*.md' . plugins`
  で全ワークスペースの使用箇所を列挙し、まず非推奨化を告知する。各要件を `example-test` へ
  移行して一括 spec inspect が PASS した次のリリースでのみ語彙を削除する。
- **実装順序**: 両要件は lifecycle / sdd-test / plugin version の変更境界が重複するため、
  1タスク・1リリースで原子的に実装する。完了条件は対象回帰テスト、全 pytest、release_check、
  全ワークスペース spec inspect の全 green とする。
- **Design Gate 入力**: 2026-07-18、SI-SDD-008/009 を accepted としたうえで「SDD で進める」
  というユーザー指示を受領。裁定案は **SI-SDD-008 は案A、SI-SDD-009 は案A** とする。
  SI-SDD-008 には上記の PR 不在時補正を含める。設計はレビュー統合判定が PASS した後に
  active 化し、要件を approved へ遷移する。
- **Design Gate 裁定**: 2026-07-18、SDD-REV-001 の PASS（4.50 / 5.00、critical/major 0）を
  証跡として、上記ユーザー指示に基づき active 化。
