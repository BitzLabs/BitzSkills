---
id: SI-SDD-018
raised_by: SI-CORE-031/032 実装キャンペーン（PR #70〜#75）の振り返り（2026-07-19）
target: spec_inspect にレポートを書き込まない読み取り専用モードが無く並列 PR 運用と干渉する
proposed_change_type: modify
status: accepted
origin: root（SI-CORE-031/032 の実装振り返り）
github_issue: https://github.com/BitzLabs/BitzSkills/issues/82
---
- **目的**: `spec_inspect.py` は検証のたびに全対象ワークスペースの
  `inspection-report.md` を書き換える。並列 PR 運用（worktree ごとに検証を実行）では
  各 PR が全ワークスペースのレポート差分を抱え、コミットするとマージ競合になる。
  SI-CORE-031/032 では「レポートをコミットに含めず `git restore` で戻す」という
  場当たり指示で回避し、締めの PR（#75）でまとめて反映したが、これを正式な
  機能・運用として規定する。
- **提案する修正**:
  1. `spec_inspect.py` に `--check-only`（レポートファイルを書き込まず判定と標準出力のみ）
     を追加する（テスト先行）
  2. 運用規定を references に追記する: 「検証は各作業者が `--check-only` で行い、
     `inspection-report.md` の更新はデフォルトブランチへのマージ後にまとめて行う
     （締めコミット or マージ担当）」
  3. sdd-implement / sdd-git の並列投入節から本規定を参照する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py`、
  `references/`（運用規定）、sdd-implement / sdd-git の該当節、対応するテスト。
- **確認観点**:
  - `--check-only` で exit code・標準出力が通常実行と同一、かつ全レポートファイルが
    バイト単位で不変であること
  - 既定動作（フラグなし）は現状維持で後方互換であること
- **影響推定・ロールバック**: フラグ追加のみで既定動作は不変。単独 revert 可能。
- **依存**: なし。関連: SI-SDD-017（同キャンペーン発。独立に実装可能）。
- **予備判定（推薦・裁定は人間）**: **accept を推薦**。並列実装は今後も標準運用であり、
  毎回の場当たり指示は漏れると即競合事故になる。追加は後方互換なフラグ1つで
  リスクが小さい。CLI インターフェース（契約）の拡張のため通常フローを推奨
  （実装自体は小さく、要件1件 + タスク1件で足りる見込み）。
- **実施**: 2026-07-19 SDD-FR-133 / SDD-TSK-018 で `--check-only` と
  単一・複数workspaceの非書き込み回帰テストを実装し、verifiedへ遷移。
