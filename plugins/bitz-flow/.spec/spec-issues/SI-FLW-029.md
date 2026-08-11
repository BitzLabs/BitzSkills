---
id: SI-FLW-029
raised_by: 第11ラウンド実測（agy が INVALID_INPUT 後に --help へ退避。2026-08-08）
target: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py の _failure_result、FLW-FR-004 の失敗節、FLW-DSN-010
proposed_change_type: modify
status: accepted
---
- **目的**: 失敗 result は `next_actions` を持たず、**契約の中に復帰経路が無い**。
  v2 SKILL.md は「`NEXT` があるならそれを使う。示された引数はそのまま渡し、同じ情報を
  別の手段で取り直してはならない」と規定しているが、失敗時には `NEXT` が存在しないため、
  エージェントは**契約の外へ出るしかない**。第11ラウンドの agy はここで `--help` へ退避した。

  ```text
  INVALID_INPUT git.diff-summary cause=invalid-ref stage=inspect
  ```

  この1行が失敗 result の全内容である。**どの ref が解決できなかったかも、代わりに何を
  渡せばよいかも載らない。**

- **観測**:
  - `cli.py:316` の `_failure_result()` は `operation` / `code` / `cause` / `stage` だけを
    載せ、`next_actions` を渡していない（`R.build_result` の既定＝空配列）。
  - `schemas/result-v1.schema.json` は `next_actions` を **`required` に含む**。
    つまり失敗 result にも field は必ず存在し、**器はあるのに埋めていない**。
  - 第11ラウンドで agy の v2 `diff-summary` 21 trial のうち **13 件が `--help` を呼んだ**
    （`observation.help_invocations`）。`--help` は operation の実行ではないため
    `SI-FLW-014` の裁定で採点対象外だが、**契約外への退避が常態化していること自体**が問題。
  - 今回 `raw_fallback` は 0 件だった。しかし復帰先が契約内に無い以上、
    **生コマンドへ退避する圧力は構造的に残る**。M1 以降の write 系で同じ状況が起きると
    危険事象へ直結する。

- **これは `SI-FLW-025` / `SI-FLW-027` と同族である**: 裁定・設計で置いた仕組み
  （`next_actions` による復帰誘導）が、実装では**到達不能な形**で置かれていた。
  `SI-FLW-025` は歯止め用 field が 1 runner にしか無かった件、`SI-FLW-027` は記録先が
  定数だった件、本件は**成功路にしか結線されていない**件で、いずれも
  「仕組みはあるが働いていない」ことがデータ構造上検出できなかった。

- **要件側にも穴がある**: `FLW-FR-004` の失敗に関する EARS は
  「WHEN Git command、parse、timeout、path検証のいずれかが失敗する THEN bitz-flow は
  失敗stageと許可語彙causeを区別して返すこと SHALL」で**止まっており**、
  復帰候補を返すことを要求していない。実装が要件に違反しているのではなく、
  **要件が復帰経路を要求していない**。

- **本件を直しても SFCR は改善しない**（重要）。`self_retried` は
  「task 対象の呼出が2件以上あり、うち1件以上が失敗 result code を返したとき」で判定するため、
  契約内で `NEXT` に従って復帰しても失敗として計上される。**SFCR に効くのは `SI-FLW-028`
  （そもそも外さない）であり、本件が効くのは安全性（契約外退避の圧力除去）である。**
  「契約内の NEXT 追従による再呼出を失敗に数えるべきか」という指標定義の論点も派生するが、
  **本 issue では扱わない**（North Star の定義変更は `discovery/metrics.md` の管轄）。

- **提案する修正**:

  1. **失敗 result にも `next_actions` を載せる**。`cause` ごとに復帰候補を決める。
     例: `invalid-ref` なら `NEXT git.diff-summary base=HEAD`（既定へ差し戻す）、
     `not-repository` なら `NEXT repo.inspect`。**shell 文字列を返さない**
     （`FLW-DSN-010:75` の規範を維持する）。
  2. **解決できなかった入力値を `data` に載せる**。現行は `cause` 語彙のみで、
     どの ref が問題だったかが失われている。秘密値を含まない範囲で echo する。
  3. **`FLW-FR-004` に EARS を1節追加する**。「WHEN 入力値が不正で操作を完了できない THEN
     bitz-flow は許可された domain / action の復帰候補を `next_actions` に返すこと SHALL」。
     version 1.0 → 1.1。
  4. **テストで固定する**。`tests/test_flow_contract.py` に「失敗 result の `next_actions` が
     空でないこと」「返る候補が許可 domain/action であること」を追加し、
     空配列へ戻す変異を検出できることを負の対照で確かめる。

- **対象ファイル**:
  - `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`（`_failure_result`）
  - `plugins/bitz-flow/.spec/requirements/FLW-FR-004.md`（失敗節の EARS 追加）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-010.md`（`next_actions` の規範を失敗側へ拡張）
  - `plugins/bitz-flow/skills/flow-core/references/output-contract.md`
  - `evals/flow-core/fixtures/v2-skill/SKILL.md` および flow-core の SKILL.md
    （「出力の読み方」の `NEXT` 説明が成功時前提になっている）
  - `tests/test_flow_contract.py`

- **確認観点**:
  - 失敗 result の `next_actions` が空でないこと（cause 語彙ごとに候補が定まること）
  - 返る候補が `flow.py` の許可 domain / action であり、shell 文字列でないこと
  - 秘密値・絶対パスが `data` へ漏れないこと
  - 第12ラウンド以降で `help_invocations` が減ること（契約外退避の減少。**SFCR ではなく
    この観測値で効果を見る**）
  - schema は変更不要であること（`next_actions` は既に `required`）

- **影響推定・ロールバック**: 変更は**被測定物（`flow.py`）に及ぶ**ため、
  `SI-FLW-028`（記述のみ）より影響が大きい。result の field 構成は変わらず
  （空配列→非空）、schema 互換性は保たれる。プラグイン version の bump が必要。
  単独 revert できる。

- **依存**: `SI-FLW-028`（同じ失敗の表側。順序としては 028 を先に処理してよい）。
  `SI-FLW-025` / `SI-FLW-027`（同族。仕組みが到達不能な形で実装される欠陥）。
  `SI-FLW-014`（`--help` を採点対象外とした裁定）。
  `FLW-FR-004` / `FLW-DSN-010`（正の所在）。
  実測記録は `evals/flow-core/m0-eval/trials-antigravity-2026-08-08-r11.jsonl`。

## FLW-REV-008によるaccept前補強

- `FLW-FR-004`はverifiedのまま改訂せず、失敗時復帰契約を新規`FLW-FR-013`へ分離する。
- `next_actions`はcauseだけで生成せず、`operation × phase × stage × code × reconcile state`のrecovery class許可表から生成する。
- writeの`PARTIAL` / `INDETERMINATE` / `STALE`と副作用不明時は、read-only inspect/reconcileまたは人間停止だけを許し、apply、代替ref/pathの自動補完、blind retryを禁止する。
- 安全な候補が無い失敗では空配列を許し、`stop_reason`と`required_human_input`を返す。
- 入力値そのものはechoせず、引数名、repo相対の安全表現、長さ、digest、許容候補だけを共通sanitizer経由で返す。
- この補強は`FLW-REV-008:SYN-003/008`を解消するaccept条件である。
- recovery classは閉集合とし、未登録tupleをhuman-stopへfail-closedにする。NEXT連鎖全体で`PARTIAL` / `INDETERMINATE` / `STALE`からmutationへ到達不能であることを検証する。
