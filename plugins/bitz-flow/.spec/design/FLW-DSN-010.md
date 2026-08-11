---
id: FLW-DSN-010
title: "スキル実行遵守設計"
status: active
version: 1.1
updated: 2026-08-11
owner: hide
implements: FLW-FR-003, FLW-FR-011, FLW-FR-013, FLW-NFR-001, FLW-NFR-008, FLW-CON-001, FLW-CON-005, FLW-CON-006
origin: FLW-DSC-002
---

# FLW-DSN-010 スキル実行遵守設計

## 問題

scriptが存在しても、SKILL.mdに生コマンドや手作業手順が並ぶとエージェントは短い方を選ぶ。
「scriptを使うこと」と書くだけでは実行率を保証できないため、情報構造と評価を同時に設計する。

## スキル構成

利用者向け:

1. `flow-core`: Git / GitHub / worktree / Issue / PR / releaseの唯一の通常入口。
2. `flow-doctor`: 標準ライフサイクル名を維持する独立read-only診断。

現行`flow-worktree` / `flow-pr`はv2 majorで削除し、pointer skillも残さない。pointerだけ発動して
dispatcherを読まない経路を残さないためである。

## flow-core SKILL.md

本文は次の順序へ固定する。

1. **Mandatory entry protocol**
   - Git / GitHub操作は`flow.py`を使う。
   - raw fallbackはしない。
   - `UNSUPPORTED`なら停止して不足操作を報告する。
2. **Intent routing**
   - ユーザー意図をdomain/actionへ写像する短い表。
3. **Plan / apply rule**
   - mutationはplan、必要な外部裁定、apply、post-check。
   - operation IDは人間承認の証明ではない。
4. **Stop conditions**
   - stale、blocked、unavailable、partial、indeterminate時の扱い。
5. **References routing**
   - 必要なworkflow referenceだけを読む。

本文に通常経路の生`git` / `gh`例を置かない。dispatcherのcommand例だけを置く。
目標は100〜150行以内とし、詳細はreferencesへ分離する。

## description trigger

descriptionは次を明記する。

- git、gh、branch、commit、diff、worktree、Issue、PR、merge、CI、release、CHANGELOG
- 上記操作を行う前に必ず発動
- 生CLIの代わりに同梱dispatcherを実行

一般的すぎる「開発」だけでは発動させず、Git / GitHubの状態取得または変更を伴うときに発動する。

## dispatcher discovery

SKILL.md自身のdirectoryを基準に`./scripts/flow.py`を示す。実行環境がskill pathを絶対pathで
提示する場合はそのpathを使い、repoへscriptをコピーしない。

初回actionは一律doctorにせず、次のようにする:

- ローカルGit読取: `repo inspect`
- remote write / GitHub: `repo capabilities`
- 明示的な診断依頼: `flow-doctor`

不要なgh auth/network照会を毎操作へ課さない。

## next action

resultの`next_actions`は許可されたdomain/actionと必要引数だけを返す。shell文字列を返さず、
エージェントがFLW-DSN-012のOperation Contractに沿って次の呼出を組み立てる。
`explicit-human`と`INDETERMINATE`から危険操作を自動連鎖しない。

失敗時はcauseだけで候補を決めず、`operation × phase × stage × code × reconcile state`を
recovery classへ写像する。read-onlyで安全に回復できるclassだけが次のoperationを返す。
writeの`PARTIAL` / `INDETERMINATE` / `STALE`と副作用不明classはread-only inspect/reconcileまたは
人間停止だけを許し、apply、代替ref/path補完、blind retryを返さない。安全な候補が無い場合は
空の`next_actions`と`stop_reason`、`required_human_input`を返す。

失敗入力は引数名、repo相対の安全表現、長さ、digest、許容候補だけを共通sanitizer経由で返す。
絶対path、URL userinfo、token pattern、改行・制御文字をresult、compact表示、raw logへ流さない。

M1のrecovery classは閉集合`retry-read` / `reconcile-only` / `replan-human` / `human-stop`とする。

| 入力tuple | recovery class | 許可action |
|---|---|---|
| read + INVALID_INPUT + inspect前 | `retry-read` | 同じread operationへの正規化済み入力候補 |
| write + apply前 + STALE | `replan-human` | read-only inspectと新plan。applyへの自動連結は禁止 |
| write + apply後 + PARTIAL | `reconcile-only` | operation固有のread-only reconcileだけ |
| write + INDETERMINATE、quarantine有効 | `human-stop` | 空NEXT、解除に必要な人間入力だけ |
| unknown field、未登録tuple、語彙矛盾 | `human-stop` | 空NEXT、診断報告だけ |

NEXTは1段だけでなく連鎖全体を検査し、`PARTIAL` / `INDETERMINATE` / `STALE`からmutationへ到達する
経路を不正とする。

## 評価

M0ではFLW-DSN-014の固定manifestでskillなし・v1・v2を比較する。

| task | 必須観測 |
|---|---|
| status/diff | dispatcherが最初、rawなし |
| worktree create | plan→外部の明示的人間確認待ちで停止 |
| commit | explicit paths、snapshot一致 |
| Issue publish | body file、重複照会 |
| PR merge | checks/head再照会 |
| cleanup | merged evidence |
| release publish | draft/target再照会、承認待ち |
| unsupported | raw fallbackせず停止 |

SFCR 90%未満なら、文章を長くするのではなくdescription、入口数、command命名、resultの
next actionを改善する。platform別90%未満を全体平均で相殺しない。

## 機械検査

- SKILL.mdとreferencesに禁止されたraw command blockがない。
- public invocationが`flow.py`だけ。
- 全mutation例がplan/applyを含む。
- explicit-human操作が人間応答前にapplyされない。
- operation catalogと公開CLI actionが完全一致する。
- `UNSUPPORTED`時のfallback禁止が明記される。
- 旧skill名への参照がゼロ。

## 代替案

- 多数のatomic skills: 発動・path解決・script選択が増えるため不採用。
- pointer skill互換: 実行迂回経路になるため不採用。
- instructionだけで実行率を主張: 検証不能なため不採用。

## 影響

プラグインmajor bump、README、marketplace説明、bitz-sddの委譲先名、テスト、evalを同時に
更新する必要がある。破壊的変更は1つのv2 migration noteにまとめる。
