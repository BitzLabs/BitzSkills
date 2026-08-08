# 裁定記録 — `--base` の意味論と読取の入口拘束（SI-FLW-028）

- **日付**: 2026-08-08
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-028`（`--base` の意味論が記述から一意に読めず、antigravity が
  `--base HEAD~1` を選んで `INVALID_INPUT` を受ける）
- **裁定の形式**: 第11ラウンド実測（#181）が示した M0 出口の**唯一の未達**として提示した対話裁定。
  予算の再提示（`decision-2026-08-08-m0-budget-overrun-2.md`）と同時に行った。
  記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref`）。
- **裁定**: **accept。案1（`--base` の意味論を記述する）と案2（読取の入口拘束）を併用する。**
  案3（実在しない ref を既定へフォールバックする）は採らない。

## 裁定材料

### 未達は SFCR ただ 1 点で、失敗は単一 task へ集中している

第11ラウンドで antigravity の SFCR は **71%（45/63）** となり、M0 出口条件（90% 以上）に
対する唯一の未達になった。他は Decision Parity 100%、危険事象 4 種が各 0 件
（母数 63・95% 上側限界 4.64%）、byte 削減も閾値超で、codex-cli は全指標達成である。

失敗は `git.diff-summary` に **100% 集中**する。`repo.inspect` / `git.status` の self-retry は 0。

### 既定値を知らなかったのではなく、比較の向きを取り違えている

`v2-skill / diff-summary` の `flow.py` 呼出順序を raw log から復元した結果。

| | `git status` を先に呼んだ | 最初の diff-summary 呼出 | self-retry |
|---|---:|---|---:|
| codex-cli | **21/21** | `--base HEAD`（21/21） | **0/21** |
| antigravity | **1/21** | `--help` 15 / `--base HEAD~1` 5 | **18/21** |

**13/21 は `--help` を読んだ上で `HEAD~1` を選んでいる**（最頻の系列は
`--help` → `--base HEAD~1` → `--base HEAD` が 7 件）。
したがって **help に既定値を書き足すだけでは直らない**。

原因は語である。現行の記述はいずれも比較の**左辺（作業ツリー）を書いていない**。

| 記述箇所 | 現行の文言 |
|---|---|
| `cli.py` の `--base` help | 「git diff-summary の**比較元**（既定 HEAD。index と比較するなら `--base index`）」 |
| v2 SKILL.md（`## 2` 末尾） | 「`diff-summary` の**比較元**は `--base <ref>`、既定は `HEAD`」 |

「比較元」とだけ示すと `git diff A B` 型の **ref..ref 比較**と読める。task prompt
「直前のコミットからの変更量を教えてください」を ref..ref と解釈すれば `--base HEAD~1` は
筋の通った選択になる。corpus はコミット 1 個なので `HEAD~1` は実在せず
`INVALID_INPUT cause=invalid-ref` を返す。**dispatcher の挙動は正しい**（手で再現済み）。

### 正解の引数は `NEXT` 経由でしか流通していない

codex-cli が 100% なのは引数を自力で当てたからではない。`git.status` の成功 result が返す
`NEXT git.diff-summary base=HEAD`（`cli.py:214`）をそのまま使っている。
status を経由しない入り方をすると記述だけが頼りになり、agy は **20/21 がその入り方**だった。

これが案1（記述を直す）と案2（入口を拘束して `NEXT` を必ず配る）を**併用する**理由である。
片方だけでは、記述を読まない経路か `NEXT` の来ない経路のどちらかが残る。

## 裁定1 — 案1を採る（`--base` の意味論を記述する）

`cli.py` の help と v2 fixture の記述を、**比較の左辺と既定値の意味**を明示する形へ書き換える。

- 「比較元」という語を**使わない**。取り違えの原因そのものであるため
  「**比較対象**」へ統一し、「**作業ツリーを `<base>` と比較する**」と左辺を明記する
- 「既定 `HEAD` ＝ 直前のコミット以降の変更」と、task prompt の言い回しへ直接橋を架ける
- 「**`ref..ref` の比較ではない**」を明示する。13/21 は `--help` を読んだ上で外しており、
  誤った読みを**名指しで否定しない限り**打ち消せない

`flow.py` の挙動・result・schema は一切変えない。

## 裁定2 — 案2を採る（読取の入口を `repo inspect` / `git status` へ拘束する）

v2 SKILL.md の Mandatory entry protocol 項5 を、ローカル Git の読取は
`repo inspect` か `git status` から始める規定へ改め、**いきなり `git diff-summary` を
呼ばない**ことと、その理由（先行操作の result が `NEXT` で引数を配る）を書く。

`SI-FLW-008` で導入した入口拘束の延長である。案1 が効けば `NEXT` 無しでも自立するため、
**案2 は案1 の代替ではなく保険**として置く。

## 裁定3 — 案3は採らない（実在しない ref の既定フォールバック）

`--base HEAD~1` を解決できないときに `HEAD` へ落とせば SFCR は即座に改善するが、
`FLW-DSN-010` の決定論的安全判定（**推測しない**）に反する。M1 以降の write 系へ同じ寛容さが
波及すると事故に直結する。**`INVALID_INPUT cause=invalid-ref` は維持する**
（`tests/test_flow_contract.py` で固定済み）。

## 起票時の記述に対する2点の訂正

`SI-FLW-028` の本文には、実物と食い違う記述が 2 点あった。裁定にあたって訂正する。

1. **「プラグイン version の bump は不要」は誤り。** `--base` の help は配布物
   `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py` にある。v2 fixture は自前の
   `scripts/` を持たず配布側の `scripts/` と組み合わせて配置される構成
   （`evals/flow-core/fixtures/v2-skill/README.md`）であるため、この変更は
   **配布物かつ被測定物に及ぶ**。3マニフェストと `flowlib.__version__` を
   `0.3.1` → `0.3.2` へ同時に上げる（`__init__.py` の規定により常に同値）。
   M0 出口到達時の `0.4.0` への bump（`FLW-TSK-012`）とは独立である。
   副次的な利点として、第12ラウンドの trial は `audit.tool_version` が `0.3.2` となり、
   **是正前後の trial を出所で識別できる**。
2. **確認観点「v2 fixture と `plugins/.../flow-core/` の記述が同じ文言であること」は、
   現時点では適用できない。** 配布側 `SKILL.md` は `FLW-DSN-011` の Promotion Gate まで
   v1（フロー選択スキル）のまま据え置かれており、`--base` の記述をそもそも持たない。
   本裁定で同期を取る対象は **`cli.py` の help と v2 fixture の 2 箇所**である
   （`--base` の記述は grep 上この 2 箇所しか存在しない）。
   fixture と稼働ファイルの照合は Promotion Gate 手順9 が担う。

配布側 `SKILL.md` の frontmatter は変更しない。`flowlib` 一式を追加した #158 も
同 SKILL.md を触っておらず、**M0 の間は scripts の版はプラグイン manifest と
`flowlib.__version__` が担う**という先例に従う。

## 裁定しなかったこと（本裁定の範囲外）

- **`SI-FLW-029`（失敗 result に `next_actions` が無い）は open のまま据え置く。**
  被測定物の挙動変更を伴い影響が大きく、効く指標も SFCR ではなく `help_invocations` で別である。
  M1 の write 系着手前に裁定する
- **`references/output-contract.md` は変更しない。** `SI-FLW-028` は対象ファイルに挙げていたが、
  同ファイルに `--base` の記述は無く、`NEXT` の位置づけの見直しは
  **`SI-FLW-029` の管轄**（失敗路に `NEXT` が結線されていない件）である。
  `FLW-DSN-010` の「文章を長くしない」に従い、本裁定では触らない
- **prompt は据え置く**（`prompt_version` は `2026-07-31.1` のまま）。prompt に
  `--base` の説明を足すのは被測定物ではなく問題の方を測定条件へ寄せることであり、
  `SI-FLW-009` の方針に反する
- **`self_retried` の定義は変更しない**（「契約内の `NEXT` 追従による再呼出を失敗に数えるか」は
  North Star の定義変更であり `discovery/metrics.md` の管轄。`SI-FLW-029` にも同旨の記載）

## 確認観点（第12ラウンドで測る）

- antigravity の v2 `diff-summary` の self-retry が減り、**SFCR が 90% 以上**になること
  （母数は `TRIALS_PER_CELL` に従い v2 は 21 trial）
- codex-cli の **SFCR 100% と Decision Parity 100% が退行しない**こと
- `--base HEAD~1` を渡したときの `INVALID_INPUT cause=invalid-ref` が**維持**されること
  （案3 を採らないことの確認。`tests/test_flow_contract.py`）
- 危険事象 4 種が各 0 件のまま（入口拘束の追加が Invocation Rate を下げないこと）
- **claude-code を含む 3 platform で測る**こと。第11ラウンドは claude-code 未実測であり、
  そのままでは M0 出口判定が成立しない

**効かなかった場合に何を意味するか**を先に書いておく。案1 は 13/21 の失敗機序
（`--help` を読んだ上で向きを取り違える）に直接当たる修正であり、これで改善しないなら
**記述で直せる問題ではなかった**ことになる。その場合は
`decision-2026-08-08-m0-budget-overrun-2.md` の歯止め1 に従い scope 縮小へ移る。

## 影響推定・ロールバック

案1・案2 とも記述の変更に閉じ、`flow.py` の挙動・result・schema を変えない。
変更は次の4ファイルで、単独 revert できる。

| ファイル | 変更 |
|---|---|
| `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py` | `--base` の help 文字列 |
| `evals/flow-core/fixtures/v2-skill/SKILL.md` | 入口規定（項5）・`## 2` 末尾・語の統一。`0.5.0` → `0.6.0` |
| `plugins/bitz-flow/skills/flow-core/scripts/flowlib/__init__.py` | `__version__` `0.3.1` → `0.3.2` |
| 3マニフェスト | `version` `0.3.1` → `0.3.2` |

## 次アクション

1. 是正を入れる（本 PR = 検証枠 1本目）。`release_check.py` と pytest で検証する
2. 第12ラウンドを **claude-code を含む 3 platform** で実測する（検証枠 2本目）
3. M0 出口を判定する。到達すれば3マニフェストを `0.4.0` へ bump する（`FLW-TSK-012`）
4. **未達なら scope 縮小へ移る**（是正の反復は行わない）
