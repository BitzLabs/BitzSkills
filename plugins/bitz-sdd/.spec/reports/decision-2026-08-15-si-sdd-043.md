# 裁定記録 — SI-SDD-043

- **日付**: 2026-08-15
- **裁定者**: hide
- **対象**: `SI-SDD-043`（`spec_inspect.py` のクロスワークスペース参照識別子が
  チェックアウト先ディレクトリ名に依存する）
- **裁定原文**: 選択肢提示に対して `SI-SDD-043` = accept
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

`SI-SDD-043` を **accept** する。

`external_refs_for()` が参照元を `f"{w.name}/{s}"` で畳んでおり、ルートワークスペースだけ
`w.name` がチェックアウト先のディレクトリ名になる。このため同じ commit・同じ内容でも、
worktree から検査すると `inspection-report.md` に一時ディレクトリ名が焼き付く。

実例として BitzSkills の main に、削除済み worktree 名を含む参照が5行入った（PR #272）。
消費側リポジトリでは AGENTS.md の締め工程規約（メイン作業ツリーから実行する）で
暫定回避しているが、規約依存を解消する。

## 起票元

BitzSkills リポジトリの運用（`inspection-report.md` が毎回 git 差分に現れる問題の調査）から
起票した。同じ調査の消費側対応は BitzSkills の PR #273 で完了している。

## 予算

bitz-sdd 側の修正であり、bitz-flow V2 の予算とは独立。着手時期は bitz-sdd の
ROADMAP に従って決める。
