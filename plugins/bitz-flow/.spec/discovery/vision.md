---
id: FLW-DSC-001
title: "bitz-flow プロダクトビジョン（Vision Board + PR-FAQ 圧力試験）"
status: draft
version: 1.0
updated: 2026-07-18
owner: hide
---

# ビジョン（Vision Board + PR-FAQ）

> 切り出し discovery。bitz-flow は bitz-sdd の sdd-git から Git / GitHub 開発フローを
> SDD 非依存に汎用化して切り出した新設プラグイン（SI-CORE-008 / CORE-FR-014、2026-07-18）。
> 内容は sdd-git で実証済みだが、新設時点では sdd-git が無変更で併存する。
> ここで「なぜ独立プラグインとして存在するか」を明文化し、以後の FLW- 起票の錨とする。

## Product Vision Board（Roman Pichler）— 5要素

1. **Vision** — AI エージェントで開発する個人〜小規模チームが、Git / GitHub の開発フロー
   （フロー選択・worktree 並列・コミット規約・PR・失敗時復元）を**毎回ゼロから考えずに済む**世界。
   規約を「エージェントの即興判断」から「プラグインが規定する再現可能な作法」へ移す。
2. **Target Group**（セグメント必須）
   - **主要**: AI エージェント（Claude Code / Antigravity / Codex CLI）で開発する個人開発者
     （現時点では作者 hide 本人。ドッグフーディング）。SDD 採用・非採用の**両方**を含む。
   - **二次**: 小規模チームで、worktree 並列と GitHub Issue 駆動 PR フローの規約を揃えたい開発者。
   - **除外**: 独自の確立した Git 運用（GitLab Flow / trunk-based の社内標準等）を既に持ち、
     エージェント向けの規約注入を必要としないチーム。
3. **Needs**（解決する問題）
   - エージェントに並列開発をさせるたび、worktree の作り方・命名・破棄・マージバックを毎回指示するのは高コスト。
   - コミット規約（Conventional Commits + Implements フッター）や squash merge・未マージ依存の扱いが
     エージェント／セッションごとにブレると履歴と PR が汚れる。
   - 失敗したタスクを「巻き戻す」際にガードレール（`git reset --hard` / `--force` 禁止）と衝突しがち。
     破棄→再投入という安全な復元パターンを規約として持ちたい。
4. **Product**（際立つ少数の差別化要素、機能全リストではない）
   - **flow-core**: 状況別フロー選択（単独=ブランチ / 並列=worktree / チーム=Issue 駆動 PR）・
     コミット規約・失敗時復元（worktree 破棄に一本化、checkpoint を置かない）を規定。
   - **flow-worktree**: **1エージェント = 1 worktree = 1ブランチ**の並列運用（作成・マージバック・破棄）。
   - **flow-pr**: GitHub Issue 駆動 + Draft PR + squash merge + **未マージ依存の原則**（前提を先に land）。
   - 共通の差別化: **SDD 非依存で単体完結**する。bitz-sdd を導入していなくても Git フローだけ使える。
     bitz-sdd 併用時のみ、各スキルの「併用節」が接続点（Implements フッター・`.spec/tasks` 連携）を規定する。
5. **Business Goals**
   - 直接の収益目標なし（OSS / 個人開発）。ゴールは **BitzSkills エコシステムの開発フロー品質の底上げ**と、
     SDD を採らないユーザーにも届く**入口プラグイン**としての裾野拡大。
   - 将来的な間接便益: bitzskills マーケットプレイスの魅力向上。数値目標は `TBD`。

**Mission**: Git / GitHub フローの規約を自己完結スキルとして提供し、エージェントが毎回考えずに
再現可能な運用（並列・PR・復元）を実行できるようにする。SDD の有無に依存しない。
**Values**: (1) 単体で価値が立つこと（bitz-sdd 非依存を主張の核にする）。(2) ガードレール
（破壊的操作の禁止）と衝突しない復元パターンのみ規定する。(3) 手法は自己完結、連携はスキル名の言及で行う。

## PR-FAQ（圧力試験）

**プレスリリース（要約）**
見出し: 「BitzFlow — AI エージェント向けの Git / GitHub 開発フロー規約プラグイン」。
エージェントで開発する個人・小規模チームは、フロー選択・worktree 並列・コミット規約・PR・失敗時復元を
bitz-flow に委ね、毎回の即興指示なしに再現可能な運用ができる。差別化は「SDD 非採用でも単体で使え、
bitz-sdd 併用時だけ SDD 連携が接続される」点。

**外部 FAQ（抜粋）**
- 価格: 無償（OSS、bitzskills マーケットプレイス経由）。
- 使い方: `agy plugin install` / `/plugin install bitz-flow@bitzskills` / `codex plugin add`。
- 単体で使えるか: **はい**。bitz-sdd 非導入でも Git フロー規約として機能する。これが存在意義。

**内部 FAQ（荷重を受ける部材）**
- 市場規模: TAM/SAM/SOM とも `TBD`（OSS のため厳密な市場定義は未実施。実利用者は現状1名＝作者）。
- 競合状況: 詳細は positioning.md（FLW-DSC-005）。特に sdd-git（bitz-sdd 同梱）との棲み分けが焦点。
- リスク: (1) SDD 非採用プロジェクトでの**単体需要が未検証**（作者は SDD 採用ユーザーであり n=1 も SDD 側）。
  (2) sdd-git との二重規定（SI-CORE-010 で sdd-git を委譲ポインタ化するまで併存）。
  (3) 一般的な Git フロー手法（git-flow / GitHub Flow）に対する優位が「エージェント向け規約」に限られる。
- **Go/No-Go 基準**（後段 assumptions.md が執行）:
  - D1: エージェント開発で「Git フロー規約をプラグインに委ねたい」場面が実在する
    → **作者のドッグフーディングで worktree 並列 or Issue 駆動 PR が実運用で最低1回使われたら Go 寄り**。
  - F1: 3スキルが SDD 非依存で自己完結して機能する → sdd-git で実証済み。転記の破綻がないことを検証可能。

## Open Questions

- SDD **非採用**プロジェクトでの単体需要（Desirability）は未検証。作者自身が SDD 採用者のため n=1 も偏る。`TBD`。
- sdd-git の委譲ポインタ化（SI-CORE-010）後も本ビジョンが不変か（規定の正が bitz-flow に移るだけで不変の見込み）。
