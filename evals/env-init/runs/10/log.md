# TC-02 実行ログ（スキルあり・SI-ENV-008 反映後の再テスト）

- **ケースID**: TC-02（既存ファイルありの再展開）
- **モード**: スキルあり（SKILL.md v0.3.0 + references/permissions.md, templates/* に忠実）
- **実行日時**: 2026-07-12
- **目的**: runs/6 で不合格だった ENVFR004-S1（マーカー区間直前に区切り空行1行が
  区間外へ追加されていた）が、SKILL.md「原則」への追記（SI-ENV-008 の裁定反映 ——
  「区間外へ新規バイトを追加しない。区切りの空白・改行は開始タグの内側に含める」）で
  解消されるかを確認する。

## 前提条件
- sandbox は git 管理下（独自3ファイルをコミット済み）
- 独自内容の AGENTS.md（3見出し・独自運用ルール2件）・CLAUDE.md（マーカー区間なし）
- 独自 deny（`Bash(npm publish:*)`）・ask（`Bash(git push:*)`）を含む `.claude/settings.json`

## 手順の記録（時系列）
1. ユーザープロンプト「環境をセットアップして。すでに AGENTS.md とかはあるけどいい感じにマージして」を受領。
2. SKILL.md 手順1に従い、プラットフォームをユーザーに質問 → シミュレート回答「Claude Code」。
3. 既存ファイルの有無を確認 → `.claude/settings.json` / `AGENTS.md` / `CLAUDE.md` は存在、
   `.claude/agents/` は存在しない。
4. Git リポジトリか確認 → 既に git 管理下（初期コミット済み）。
5. 手順2（書き込み前チェック）: git 管理下のため `.bak` 作成は省略可 → 省略。
6. 手順3（中心モデルと役割の割り当て）: ユーザーに中心モデルを質問
   → シミュレート回答「Sonnet（中位）」。表に従い advisor=Opus, worker=Haiku を提案
   → シミュレート承認。
7. 手順4（生成、すべて確認付き）: 書き込み**前**に以下のマージ案を提示した
   （この時点でファイルへは一切書き込んでいない。承認前の sandbox は original/ と同一）。
   - `.claude/settings.json`: 既存 deny/ask を残したまま、references/permissions.md の
     テンプレート deny 9件・allow 8件を和集合として追加する案（ask の
     `Bash(git push:*)` は既存と完全一致するため重複追加しない）
   - `AGENTS.md`: 既存9行の**直後**に `<!-- bitz-env:begin -->`〜`<!-- bitz-env:end -->` の
     ガードレール節を追記する案。**今回の変更点**: 区間外に区切り用の空行を追加せず、
     既存内容の最終バイトの直後に `<!-- bitz-env:begin -->` を直接続ける。
     見出しとの区切りに必要な空行は開始タグの**内側**（`<!-- bitz-env:begin -->` の次の行）
     に入れる
   - `CLAUDE.md`: 既存5行の直後に同様の方式（区切り空行はタグ内側）でマーカー区間を追記する案
   → シミュレート承認を得てから、上記の内容で実際に書き込みを行った。
8. `.claude/agents/advisor.md`（model: opus）・`.claude/agents/worker.md`（model: haiku）を
   新規生成（表の規則どおり、中心が中位のため両方生成）。
9. 手順5（生成物トラッキング）: `.claude/bitz-env.local.md` を新規作成し、
   新規生成ファイル一覧・マーカー区間の位置・settings.json のマージ内容・
   バックアップ有無（今回は不要）・割り当てを記録した。
10. 手順6（検証と報告）: `python3 -m json.tool .claude/settings.json` でパース確認 → 成功。

## 成果物一覧
- sandbox/.claude/settings.json（既存 deny/ask を保持したままテンプレートと和集合マージ）
- sandbox/AGENTS.md（既存9行はそのまま、直後にマーカー区間付きで追記。区間外への追加バイトなし）
- sandbox/CLAUDE.md（既存5行はそのまま、直後にマーカー区間付きで追記。区間外への追加バイトなし）
- sandbox/.claude/agents/advisor.md（model: opus）
- sandbox/.claude/agents/worker.md（model: haiku）
- sandbox/.claude/bitz-env.local.md（レジストリ）

## 機械確認結果（ENVFR004-S1 は厳密判定）
- `diff original/AGENTS.md <(sed '/<!-- bitz-env:begin/,/<!-- bitz-env:end/d' sandbox/AGENTS.md)`
  → **差分なし（完全一致）**。マーカー区間を取り除くと original/AGENTS.md とバイト単位で
  一致することを確認。区間外への新規バイト追加（区切り空行を含む）がないことを示す。
- `diff original/CLAUDE.md <(sed '/<!-- bitz-env:begin/,/<!-- bitz-env:end/d' sandbox/CLAUDE.md)`
  → **差分なし（完全一致）**。CLAUDE.md も同様に区間外は原本とバイト一致。
- `grep -c "npm publish" sandbox/.claude/settings.json` → 1（既存 deny エントリ保持）
- `python3 -c "json.load(...)['permissions']['ask']"` → `['Bash(git push:*)']`
  （重複追加されていない。既存の1件のみ）
- `python3 -m json.tool sandbox/.claude/settings.json` → JSON valid
- `grep -c "bitz-env:begin" sandbox/AGENTS.md sandbox/CLAUDE.md` → 各1件確認
- 全成果物パスが `sandbox/` 配下であることを `find` で確認

## アサーション結果
- [x] 既存ファイルを上書きせず、diff とマージ案を提示している → ✅（ENVFR003-S2）
  証拠: 手順7で書き込み前にマージ案（settings.json の和集合案、AGENTS.md/CLAUDE.md の
  追記案・区切り位置の変更点）を提示し、承認後に書き込んだ。
- [x] permissions のマージで既存の deny/ask エントリ（npm publish）が削除されていない
  → ✅（ENVFR003-S3）。証拠: grep で `Bash(npm publish:*)` が sandbox/.claude/settings.json
  内に残存を確認。
- [x] CLAUDE.md / AGENTS.md への挿入はマーカー区間内のみで、区間外の既存記述が
  バイト単位で不変 → ✅（ENVFR004-S1、厳密判定で合格）。証拠: 上記 `diff` +
  `sed` によるマーカー区間除去後の完全一致。**runs/6 で検出された「区間外への
  区切り空行1行の追加」は今回発生していない** —— SKILL.md「原則」節の
  SI-ENV-008 反映（区切りはタグ内側に含める）により解消したことを確認した。

## 備考
- runs/6 との差分は「区切り空行の位置」のみ。既存内容の直後に開始タグを直接続け、
  タグ内側で改行を挟むという読み方をすることで、機械的な `sed` 除去による厳密判定と
  人間可読性（見出し前の空行）を両立できた。
- 本ケースの他の観点（settings.json の和集合マージ、deny/ask の非削除、
  advisor/worker の生成規則）は runs/6 から変化がないため、SI-ENV-008 の
  修正影響範囲どおり ENVFR004-S1 のみを重点確認した。
