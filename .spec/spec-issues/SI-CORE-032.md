---
id: SI-CORE-032
raised_by: SI-CORE-028 実施後のフォローアップ（2026-07-19 ユーザー要望: CORE-CON-009 の実装横展開）
target: 配置先に状態を残すプラグイン（bitz-env / bitz-sdd 等）の update スキルとマイグレーション機構の未実装
proposed_change_type: new
status: accepted
origin: root
delegated_to: bitz-env:ENV-FR-011
---
- **目的**: CORE-CON-009（SI-CORE-028 由来）で制定した update のバージョン移行
  （累積マイグレーション）機構は現状**規約のみ**で、`update` スキルを実装した
  プラグインが1つも無く実体化していない。配置先に状態を残すプラグインへ
  `<接頭辞>-update` スキルを横展開し、バージョンアップ時の形式変更を
  マイグレーションステップで安全に移行できるようにする。
- **提案する修正**:
  1. **対象プラグインの確定**（設計工程、SI-CORE-031 の必要操作マトリクスと統合判定）。一次案:
     - bitz-env（**本命**）: 配置先状態が最多（settings.json の permissions・
       AGENTS.md / CLAUDE.md のマーカー区間・`.claude/agents/` の advisor / worker・
       `.claude/bitz-env.local.md` レジストリ）。`env-init` / `env-doctor` / `env-uninstall`
       に続く4操作目として `env-update` を追加
     - bitz-sdd: ワークスペースの `.spec` 系 frontmatter 書式が配置先状態に相当
       （CORE-CON-009 の説明文にも明記）。書式変更を伴う版上げ時の `sdd-update` を検討
     - bitz-ddd / bitz-flow / plugin-creator / skill-creator: 配置先に状態を残さなければ
       対象外（CORE-CON-009 は任意能力であり、全プラグイン必須ではない）
  2. 各対象プラグインの `update` は CORE-CON-009 の受入基準（EARS）に準拠して実装する:
     `references/migrations/<from>-to-<to>.md`（1ファイル1ステップ・guard 必須の宣言的
     Markdown）、チェーン解決（D < to <= T の to 昇順解決・連続性検査）、断裂・欠落時の
     書き込み前安全側停止、冪等性（guard による二重適用 no-op）、リポジトリ外書き込み時の
     dry-run 差分提示 + ユーザー承認
  3. 初回実装時点では形式変更がまだ無いため、migrations/ は**空でよい**
     （機構と検証フィクスチャだけ整備し、最初の形式変更時にステップを追加する運用を規定）。
     ただし実装検証として plugin-creator の `migration-steps.md` 記載の合成フィクスチャ手順で
     冪等性・安全側停止を実際に確認する
  4. 実装は各プラグインワークスペースへ委任（`delegated_to:` で双方向記録）し、
     1プラグイン = 1要件・1タスクの粒度で分割する
- **対象ファイル**: `plugins/bitz-env/skills/env-update/SKILL.md`（新規）、
  `plugins/bitz-sdd/skills/sdd-update/SKILL.md`（判定次第で新規）、
  各 `references/migrations/`（雛形）、対象プラグインの `.spec/`（委任先要件・タスク）、
  各マニフェスト bump。
- **確認観点**:
  - CORE-CON-009 の受入基準7項目（EARS）を対象プラグインの `update` が満たすこと
  - 合成フィクスチャで「チェーン断裂時の安全側停止」「同一ステップ二重適用の no-op」を
    実際に確認できること
  - リポジトリ外への書き込みが dry-run 提示 + ユーザー承認後のみであること
    （AGENTS.md ガードレール準拠）
  - `release_check.py` / `spec inspect --workspace . plugins/*` PASS、
    skill-validator チェックリスト通過
- **影響推定・ロールバック**: 新スキル追加のみで既存スキルの動作変更なし。
  CORE-CON-009 / migration-steps.md（規約側）は変更しない。プラグイン単位で独立に revert 可能。
- **依存**: **SI-CORE-031**（ライフサイクルスキル横展開。update は同マトリクスの一部のため、
  031 の設計工程で対象判定を統合して行う）。前提: SI-CORE-006 / SI-CORE-028（実施済み）、
  CORE-CON-008 / CORE-CON-009（規約の正）。
- **予備判定（推薦・裁定は人間）**: **accept を推薦**。
  - 既存要件との矛盾: なし（CORE-CON-009 が想定した「実プラグインが migrations を同梱した
    時点」の検証を実体化するもので、規約の適用そのもの）
  - ガードレール抵触: なし（リポジトリ外書き込みの承認フローは CORE-CON-009 の受入基準に
    織り込み済みで、実装がそれに従う）
  - 影響範囲: 新スキル追加のみ。規約文書を変更しないため stale 伝播なし
  - 軽量レーン適否: 各プラグインの公開スキル面（契約）が増え、`.spec` スキーマ・配置先
    frontmatter という契約に触れる実装のため**通常フロー**（要件化 + Design Gate）を推薦
  - 裁定時の論点: SI-CORE-031 と統合して1本で進めるか、doctor 先行（031）→ update 後続（032）の
    2段で進めるか。推薦は**2段**（doctor は読み取り専用で低リスク・即効、update は
    マイグレーション検証を伴い重いため）
- **裁定（2026-07-19, 人間）**: チャット指示により accept（「031 と 032 を accepted にして進めましょう」）。
  推薦どおり doctor 先行（SI-CORE-031）→ update 後続の2段構成を採用しつつ、実装は並列で進める。
  対象は bitz-env のみ（ENV-FR-011 として委任）。bitz-sdd の sdd-update は
  「形式変更の発生時に実装」として保留（根拠は DSN-003 の代替案節）。
