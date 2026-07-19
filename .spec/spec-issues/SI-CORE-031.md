---
id: SI-CORE-031
raised_by: SI-CORE-006 実施後のフォローアップ（2026-07-19 ユーザー要望: 標準の横展開）
target: 全プラグイン（bitz-sdd / bitz-ddd / bitz-flow / plugin-creator / skill-creator）のライフサイクルスキル未整備
proposed_change_type: new
status: open
---
- **目的**: CORE-CON-008 で制定した標準ライフサイクルスキル
  （init / doctor / update / uninstall。仕様は plugin-creator の
  `references/lifecycle-skills.md`）を、先行実装の bitz-env 以外の5プラグイン
  （bitz-sdd / bitz-ddd / bitz-flow / plugin-creator / skill-creator）へ横展開し、
  依存欠如・環境不整合を各プラグイン自身が標準の入口で検出できるようにする。
  標準は「提供する操作だけを標準名で命名」（全4操作の一律実装は不要）であり、
  本件も必要な操作だけを実装する。
- **提案する修正**:
  1. **必要操作マトリクスの確定**（設計工程）: プラグインごとに必要な操作を判定する。一次案:
     - bitz-sdd: `doctor`（`metadata.dependencies: [bitz-flow>=0.2]` の充足、
       `scripts/spec` ラッパーのバージョン非依存解決、`.spec/` 検査環境の診断。
       SI-CORE-010 の確認観点「単体インストール時の依存欠如が doctor で検出できること」に対応）。
       `init`（`.spec/` 初期化）は sdd-core の scaffold との責務重複を設計で整理してから判定
     - bitz-ddd: `doctor`（併用前提である bitz-sdd の有効性診断。
       あわせて `metadata.dependencies` の宣言追加 = CORE-FR-013 準拠を検討）
     - bitz-flow: `doctor`（git / gh CLI 等の前提環境診断）。配置物が無いため init 以降は不要見込み
     - plugin-creator / skill-creator: `doctor` の要否のみ判定（不要なら実装しない判定も正当）
  2. 実装は**読み取り専用の `doctor` を優先**する（低リスク・ガードレール非抵触）。
     `init` / `update` / `uninstall` は対象プロジェクトへ配置物を残すプラグインのみ対象とする
  3. スキル命名（先行実装 bitz-env の接頭辞式 `env-doctor` に合わせた `sdd-doctor` 等）は
     設計時に lifecycle-skills.md の表記と突き合わせて確定する
  4. 実装は各プラグインワークスペースへ委任（`delegated_to:` で双方向記録）し、
     1プラグイン = 1要件・1タスクの粒度で分割する。ルート側は横展開の完了追跡のみ担う
- **対象ファイル**: `plugins/<name>/skills/<接頭辞>-doctor/SKILL.md` 等（新規）、
  各プラグインの `.spec/`（委任先要件・タスク）、各マニフェスト bump、
  必要に応じ `plugins/bitz-ddd/*/plugin.json`（依存宣言追加）。
- **確認観点**:
  - `doctor` が読み取り専用であること（lifecycle-skills.md の最小契約に適合）
  - 依存宣言のあるプラグインで、依存欠如・semver 制約不満足が修正案付きで報告されること
  - `release_check.py` / `spec inspect --workspace . plugins/*` PASS、
    skill-validator チェックリスト通過
- **影響推定・ロールバック**: 新スキル追加のみで既存スキルの動作変更なし。
  lifecycle-skills.md（標準文書）自体は変更しないため stale 伝播なし。
  プラグイン単位で独立に revert 可能。
- **依存**: SI-CORE-006（実施済み・前提）。関連: CORE-CON-008（標準の正）、
  CORE-FR-013（依存宣言書式）、SI-CORE-010（bitz-sdd doctor の確認観点の出所）。
- **予備判定（推薦・裁定は人間）**: **accept を推薦**。
  - 既存要件との矛盾: なし（CORE-CON-008 の適用拡大であり、supersede 対象なし）
  - ガードレール抵触: なし（doctor は読み取り専用。uninstall を実装する場合の
    事前確認義務は標準に規定済み）
  - 影響範囲: `spec inspect --impact CORE-CON-008` の依存成果物は
    CORE-TSK-014 / CORE-TSK-016 / ENV-TSK-013 のみで、標準文書を変更しない本件では波及なし
  - 軽量レーン適否: 各プラグインの公開スキル面（契約）が増えるため**通常フロー**
    （要件化 + Design Gate で必要操作マトリクスを確定）を推薦
