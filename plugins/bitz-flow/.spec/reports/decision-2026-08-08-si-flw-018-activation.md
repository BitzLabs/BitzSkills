# 裁定記録 — claude-code の生 git 直行と description の発動条件（SI-FLW-018）

- **日付**: 2026-08-08
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-018`（claude-code が Skill を宣言しながら呼ばず生 git を実行する）
- **裁定の形式**: `FLW-REV-006` の blocking 5 件をすべて消化したうえで、M0 出口を塞ぐ
  唯一の実質的事象として提示した対話裁定。
  記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref`）。
- **裁定**: **accept。案1（`description` を発動条件として鋭くする）を採る。**
  案2 は `SI-FLW-026` の母数引き上げで部分的に満たす。案3・案4 は採らない。

## 裁定材料

### 症状 — SKILL.md 本文が一度も読まれていない

第10ラウンド `claude-code / v2-skill / diff-summary#2`（medium）。

```text
thinking
text     「Skill を使って git の変更差分を確認します。」   ← 宣言のみ
Bash     cd <repo> && git diff --stat HEAD && git diff --numstat HEAD   ← 生 git
text     「直前のコミット(55b0747)からの変更…」            ← 生 git の結果で回答
```

trial 記録でも Skill tool の呼出は **1 度も無い**。

| trial | corpus | `first_git_action` | `skill_tool_args` | `tool_kinds` |
|---:|---|---|---|---|
| 1 | small | flow.py | `["flow-core"]` | Skill, Bash, Bash |
| **2** | **medium** | **raw-git** | **`[]`** | **Bash** |
| 3〜10 | — | flow.py | `["flow-core"]` | Skill, Bash… |

`init` イベントで `flow-core` は `skills` に列挙され `Skill` tool も利用可能であったため、
**環境の不備ではない**。10 trial 中 9 trial は同じ環境で正しく発動している。

### 本文の修正では届かない

`SI-FLW-008`（入口拘束）・`SI-FLW-013`（本文の圧縮）・`SI-FLW-016`（パス解決手順）は
いずれも **SKILL.md 本文を読んだあとの挙動**を正す修正であった。本件は**本文が読まれる前**に
分岐しているため、本文へ何を書いても効果が無い。効き得るのは
**frontmatter の `description`（発動条件そのもの）**だけである。

### なぜ発動しなかったか — prompt に `git` という語が無い

`diff-summary` の prompt（`prompt_version: 2026-07-31.1`）はこうである。

```text
直前のコミットからの変更量を教えてください。どのファイルが何行増減したか、
バイナリやリネームがあるかを知りたいです。変更行の中身までは要りません。
```

**`git` も `gh` も `diff` も含まれない**、自然な日本語の依頼である。一方、旧 `description` は
「Git / GitHub 操作の唯一の実行入口。git status / diff / log / branch / commit / worktree…」と、
**コマンド名の列挙**を主体に「何ができるか」を述べていた。

`repo-inspect` / `dirty-status` の prompt も同様に `git` を含まないが、
「リポジトリの現在の状態」「いま何が変更されていますか」は description の
「リポジトリの状態取得」と語彙が近い。**`diff-summary` の「変更量」だけが description の
語彙から遠かった**ことが、10 trial 中この task で落ちた説明として整合する。

### 発生率 — 1 件では決められない

claude-code の v2 trial を全ラウンドで数え直した結果、**生 git 直行は第10ラウンドで初めて
観測された**（累計約 210 trial で 1 件 ≒ **0.5%**）。第1R・第6R の gate bypass は
「コマンドを1つも実行せず回答した」（`first=none`）別の事象であり、生 git は実行していない。
codex-cli は全ラウンドで bypass 0、antigravity は第2R の 5 件以降 0 である。

## 裁定1 — 案1を採る（`description` を発動条件へ寄せる）

**accept。** v2 fixture の `description` を次へ改める（`0.4.2` → `0.5.0`）。

| 要素 | 役割 |
|---|---|
| 冒頭「**git / gh を実行する前に必ず開く**」 | 「何ができるか」ではなく「**いつ開くか**」を先頭に置く |
| 「読む・調べる・**変える**ときに発動する」 | 状態取得も状態変更も対象であることを動詞で示す |
| 「「何が変わったか」「変更量を教えて」「直前のコミットから」「いまどのブランチか」のように **git / gh という語を含まない依頼でも発動する**」 | **本件の直接の手当て**。落ちた trial の prompt そのものの語彙を発動条件へ入れる |
| 「「開発」一般ではなく、リポジトリの状態を読む・変えるとき」 | 過剰発動の抑制（旧文から維持） |

316 文字（上限 1024）。`FLW-DSN-010`（文章を長くするのではなく description・入口名・
命名・next action を直す）に沿い、**本文は 1 行も変えない**。

### 採らなかった案

- **案3（`FLW-DSN-014` の出口条件を緩める）**: 生 git 実行は M0 の中核的な禁止事項であり、
  数値を通すために基準を緩めるのは `SI-FLW-012` の裁定で自ら定めた方針に反する。
  `SI-FLW-026` で危険事象条件へ検出力の要求を足したばかりであり、同じ条件を
  逆方向に緩めることはしない
- **案4（不合格のまま出口判定を保留する）**: 原因（本文前の分岐）と対策（description）は
  特定できており、保留する理由が無い

## 裁定2 — 出口条件どうしの緊張は「意図した設計」とする

`SI-FLW-018` は次の緊張の裁定を求めている。

> `FLW-DSN-014` は Dispatcher Invocation Rate を **95% 以上**としながら raw fallback を
> **0 件**と定める。**bypass が生 git 経路を取る限り、raw fallback 0 件は実質的に
> Invocation 100% を要求する。**

**これは閾値の不整合ではなく、意図した設計である。** 2つは別のことを測っている。

| 条件 | 測っているもの | 許容 |
|---|---|---|
| Invocation Rate 95% 以上 | dispatcher が**入口として選ばれた**割合 | 5% までの逸脱を許す |
| raw fallback 観測 0 件 | **生 git が実行された**という事象 | 1 件も許さない |

逸脱には「コマンドを1つも実行せず回答した」（`first=none`）と「生 git を実行した」
（`raw-git`）の2種があり、**前者は許容し後者は許容しない**。第1R・第6R が素通りしたのは
bypass が `first=none` だったためであり、規則が働いた結果である。

「生 git を実行しない」は M0 の中核であって統計的な品質目標ではない。したがって
raw fallback の許容件数は 0 のまま据え置く（母数の要求は `SI-FLW-026` が別に定める）。

## 裁定3 — 案2（発生率の確定）は `SI-FLW-026` で部分的に満たす

累計 1 件では修正の効果を測れない、という `SI-FLW-018` の指摘は正しい。ただし
0.5% の事象を 95% の信頼度で検出するには platform あたり **599 trial** が要り、
セッション上限に2度到達している実行環境では回せない（`SI-FLW-026` で
「採らない案」として整理済み）。

`SI-FLW-026` の裁定により v2 は platform×task 各 20 trial（platform あたり **60**）となり、
claude-code の1ラウンドあたり母数は **30 → 60 と倍**になる。これが払える範囲での
案2 の実施であり、達成できるのは **95% 上側信頼限界 4.87%** までである。

> **0 件が続いても「直った」とは言い切れない。** 本裁定はこの制約を承知のうえで
> description の修正を入れる。第11ラウンドで raw fallback 0 件になっても、
> 保証されるのは「発生率 4.87% 未満」であり、**元の 0.5% を反証したことにはならない**。
> より強い主張は Promotion Gate の累積要件（299 trial 以上）へ繰り延べる。

## 裁定しなかったこと（本裁定の範囲外）

- **配布側 `plugins/bitz-flow/skills/flow-core/SKILL.md` は変更しない。**
  `FLW-DSN-011` により v2 は Promotion Gate まで fixture 扱いである
  （`SI-FLW-016` の裁定と同じ扱い）。ただし**本欠陥は実運用でも起きる**ため、
  Promotion Gate で必ず反映する
- **prompt は変更しない。** prompt に `git` を足せば発動率は上がるが、それは
  **被測定物ではなく問題の方を測定条件へ寄せる**ことであり、`SI-FLW-009` で
  分母を都合よく選ばないと決めた方針に反する。`prompt_version` は
  `2026-07-31.1` のまま据え置き、ラウンド間の比較可能性を保つ
- **SKILL.md 本文は 1 行も変えない**（`FLW-DSN-010`）
- **`SI-FLW-019` は未裁定**。案2（proxy 乖離条件）・案3（harness 自己診断）は残る

## 確認観点（第11ラウンドで測る）

- claude-code の v2 で **gate bypass 0 件・raw fallback 0 件**になること
- **v1 / no-skill の baseline が動かない**こと（v2 fixture の description だけを変えたため、
  動いたら測定条件の混入を疑う）
- codex-cli / antigravity の既達水準を落とさないこと（両者は bypass 0）
- `diff-summary` task での Skill 発動が 20/20 になること（落ちたのはこの task）
- **成果物へ「0 件でも直ったとは言い切れない」ことを明記する**

## 影響推定・ロールバック

変更は v2 fixture の frontmatter 1 行に閉じる。単独 revert できる。配布物・harness・
設計文書に影響しない。プラグインの version は bump しない（配布物に変更が無いため）。

## 次アクション

1. 第11ラウンドを **v2 各 20 trial**（platform あたり 120 trial）で実測する
2. M0 出口を判定する。到達すれば3マニフェストを `0.4.0` へ bump する（`FLW-TSK-012`）
3. 未達なら残予算の超過として `FLW-REV-006` GP-001 と同じ形式で再提示する
   （M0 残予算は本 PR で実装 1 PR を使い切り、検証 1 PR のみ）
