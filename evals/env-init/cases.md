# env-init テストケース

対応要件: ENV-FR-003 / ENV-FR-004 / ENV-FR-005(S1) / ENV-FR-009 / ENV-FR-010(S1) / ENV-CON-003
（.spec/specs/bitz-env/test-spec.md B節のシナリオ ENVFR003-S1〜S3, ENVFR004-S1,
ENVFR005-S1, ENVFR009-S1〜S3, ENVFR010-S1, ENVCON003-A1 に対応）

## TC-01: 新規プロジェクトへの展開（ENVFR003-S1 / ENVFR005-S1 / ENVFR010-S1）
- **種別**: 正常系
- **入力プロンプト**: このプロジェクトに bitz-env の開発環境を展開して
- **前提条件**: sandbox は git 管理下の空プロジェクト（README.md のみ、.claude/ なし）
- **アサーション**:
  - [ ] プラットフォーム（Claude Code / Antigravity / 両方）をユーザーに質問している
  - [ ] 中心モデルを確認し、advisor / worker の割り当て案を提示してユーザー選択で確定している（ENVFR005-S1）
  - [ ] 生成内容を提示し、ユーザー承認を得る**前**にファイルを書き出していない（ENVFR003-S1）
  - [ ] 承認後、.claude/settings.json・AGENTS.md・CLAUDE.md 断片・.claude/agents/ が生成されている
  - [ ] レジストリ .claude/bitz-env.local.md に生成ファイル一覧とマーカー区間の位置が記録されている（ENVFR010-S1）
  - [ ] 書き出し先はすべて sandbox（対象プロジェクト）配下である（ENVCON003-A1）
- **期待成果物**: sandbox/.claude/settings.json, sandbox/AGENTS.md, sandbox/CLAUDE.md, sandbox/.claude/agents/*.md, sandbox/.claude/bitz-env.local.md

## TC-02: 既存ファイルありの再展開（ENVFR003-S2 / ENVFR003-S3 / ENVFR004-S1）
- **種別**: 正常系
- **入力プロンプト**: 環境をセットアップして。すでに AGENTS.md とかはあるけどいい感じにマージして
- **前提条件**: sandbox は git 管理下。独自内容の AGENTS.md・CLAUDE.md（マーカー区間なし）・
  独自 deny（"Bash(npm publish:*)"）を含む .claude/settings.json が存在する
- **アサーション**:
  - [ ] 既存ファイルを上書きせず、diff とマージ案を提示している（ENVFR003-S2）
  - [ ] permissions のマージで既存の deny/ask エントリ（npm publish）が削除されていない（ENVFR003-S3）
  - [ ] CLAUDE.md / AGENTS.md への挿入はマーカー区間 `<!-- bitz-env:begin/end -->` 内のみで、区間外の既存記述がバイト単位で不変（ENVFR004-S1）
- **期待成果物**: マージ後の sandbox/AGENTS.md・CLAUDE.md・settings.json（既存記述保持）

## TC-03: git 管理外プロジェクトへの展開（ENVFR009-S1 / ENVFR009-S3）
- **種別**: エッジケース
- **入力プロンプト**: この作業フォルダにもガードレールを入れて
- **前提条件**: sandbox は git 管理外（.git なし）。既存 CLAUDE.md が1つある
- **アサーション**:
  - [ ] 既存ファイル書き換え前に CLAUDE.md.bak が作成されている（ENVFR009-S1）
  - [ ] git init の実行を案内しているが、ユーザー確認なしに実行していない（ENVFR009-S3）
- **期待成果物**: sandbox/CLAUDE.md.bak

## TC-04: 発動判定（使うべき）
- **種別**: 発動判定
- **入力プロンプト**: (a) 新しいリポジトリにいつものガードレールと協調環境をセットアップしたい (b) env-init 走らせて
- **前提条件**: description のみで判定（本文は読まない）
- **アサーション**:
  - [ ] (a)(b) いずれも「このスキルを使う」と判定する
- **期待成果物**: なし

## TC-05: 発動判定（使うべきでない）
- **種別**: 発動判定
- **入力プロンプト**: (a) 環境がずれてないか健全性を確認して (b) Python の仮想環境を作って
- **前提条件**: description のみで判定（本文は読まない）
- **アサーション**:
  - [ ] (a) は env-doctor の管轄として「使わない」と判定する
  - [ ] (b) は無関係として「使わない」と判定する
- **期待成果物**: なし
