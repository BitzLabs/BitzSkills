# TC-01 実行ログ

- **ケースID**: TC-01（新規プロジェクトへの展開）
- **モード**: スキルあり（SKILL.md + references/permissions.md, templates/* に忠実）
- **実行日時**: 2026-07-11

## 前提条件
- sandbox は git 管理下の空プロジェクト（README.md のみ、.claude/ なし）

## 手順の記録（時系列）
1. ユーザープロンプト「このプロジェクトに bitz-env の開発環境を展開して」を受領。
2. SKILL.md 手順1に従い、プラットフォームをユーザーに質問
   → シミュレート回答「Claude Code」。
3. 既存ファイル（.claude/settings.json / AGENTS.md / CLAUDE.md / .claude/agents/）の
   有無を確認 → いずれも存在しない（新規プロジェクト）。
4. Git リポジトリか確認 → 既に git 管理下（README.md 済みコミット）。
5. 手順2（書き込み前チェック）: git 管理下のため `.bak` 作成は省略可 → 省略。
6. 手順3（中心モデルと役割の割り当て）: ユーザーに中心モデルを質問
   → シミュレート回答「Sonnet（中位）」。表に従い advisor=Opus, worker=Haiku を提案
   → シミュレート承認。
7. 手順4（生成）: 生成内容（settings.json のテンプレート・AGENTS-template.md の
   {{project}} 置換内容・CLAUDE-fragment.md の {{center_model}}/{{advisor_model}}/
   {{worker_model}} 置換内容・advisor.md/worker.md）を**提示してユーザー承認を得てから**
   書き出した（承認前は一切ファイルを作成していない）。
8. references/permissions.md のテンプレートをそのまま .claude/settings.json に適用。
9. references/templates/AGENTS-template.md の `{{project}}` を `sample-project` に
   置換し、マーカー区間 `<!-- bitz-env:begin -->`〜`<!-- bitz-env:end -->` を含めて
   AGENTS.md を新規作成。
10. CLAUDE.md は既存が無いため新規作成し、references/templates/CLAUDE-fragment.md の
    プレースホルダを手順6の割り当て（Sonnet/Opus/Haiku）で置換してマーカー区間ごと
    書き込んだ。
11. 中心が「中位」のため advisor.md（model: opus）・worker.md（model: haiku）を
    ともに生成（表の規則どおり、両方省略しない）。
12. 手順5（生成物トラッキング）: `.claude/bitz-env.local.md` を新規作成し、
    新規生成ファイル一覧・マーカー区間の位置・バックアップ有無（今回は不要）・
    割り当てを記録した。
13. 手順6（検証と報告）: `python3 -m json.tool .claude/settings.json` で
    パース確認 → 成功。

## 成果物一覧
- sandbox/.claude/settings.json（permissions.md のテンプレート通り）
- sandbox/AGENTS.md（マーカー区間付き、{{project}} → sample-project 置換済み）
- sandbox/CLAUDE.md（マーカー区間付き、割り当て表を反映）
- sandbox/.claude/agents/advisor.md（model: opus）
- sandbox/.claude/agents/worker.md（model: haiku）
- sandbox/.claude/bitz-env.local.md（レジストリ）

## 機械確認結果
- `python3 -m json.tool sandbox/.claude/settings.json`: JSON valid
- `grep -c "bitz-env:begin" sandbox/AGENTS.md sandbox/CLAUDE.md`: 各1件確認
- 全成果物パスが `sandbox/` 配下であることを `find` で確認

## アサーション結果
- [x] プラットフォーム確認を質問している → ✅
- [x] 中心モデル確認＋advisor/worker 割り当て案をユーザー選択で確定 → ✅（ENVFR005-S1）
- [x] 承認前にファイルを書き出していない（提示→承認→書き出しの順） → ✅（ENVFR003-S1）
- [x] 承認後、settings.json・AGENTS.md・CLAUDE.md 断片・.claude/agents/ が生成 → ✅
- [x] レジストリに生成ファイル一覧とマーカー区間位置が記録 → ✅（ENVFR010-S1）
- [x] 書き出し先はすべて sandbox 配下 → ✅（ENVCON003-A1）

## 備考
- SKILL.md 手順3の表では「中位モデルなら advisor=Opus, worker=Haiku」に該当し、
  advisor/worker とも生成対象。判定に迷いはなかった。
