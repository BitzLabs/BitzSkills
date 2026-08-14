---
id: SI-FLW-056
raised_by: FLW-REV-015 M2 Exit再レビュー
target: M2 worktree write実行アダプタ・dispatcher統合・実動confirmation
proposed_change_type: modify
status: open
---

- **目的**: M2 の安全判断核を実際の `worktree.create` / `resume` / `finish` / `discard`
  実行経路へ接続し、公開 dispatcher 入口から単回承認 capability を in-band 検証したうえで
  Git worktree を変更・収束できるようにする。実動経路を対象に3platform confirmationを再実施する。

- **発見した事実**:
  - `flow.py` / `flowlib/cli.py` は M0 read-only 3 operationだけを公開し、worktree operationは
    `UNSUPPORTED` のままである。
  - `flowlib/worktree.py` と `worktree_cleanup.py` は observation と receipt step から判断を返す
    純粋関数で、`git worktree add/remove`、registry/nonce/receipt永続化、各副作用直前の
    capability再検証を結合した apply adapter が無い。
  - `local_confirmation_subject.py` は単体テスト9ファイルを再実行するだけで、dispatcherから
    worktree writeを起動していない。それにもかかわらず active manifest は `worktree.*` を
    PASS としているため、M2出口条件の「被測定物 confirmation」としては証拠不足である。

- **提案する修正**:
  1. 既存の guard / capability / durable evidence / worktree state / cleanup 核を組み合わせる
     worktree plan/apply adapterを追加する。
  2. dispatcherへ `worktree.plan|audit|create|resume|finish|discard` を公開契約どおり接続する。
     remote writeはM3まで `UNSUPPORTED` を維持する。
  3. 全mutating stepの直前に同じ単回capability scopeとnonce状態を再検証し、失敗時は
     副作用0またはreceipt prefixからのreconcile-onlyへ収束させる。
  4. 独立tmp repositoryで実際のworktree作成・再開・完了・discardをdispatcher経由で行う
     positive controlとfault injectionをconfirmation subjectへ追加する。
  5. 3platform actual confirmationを再実行し、現在のactive manifestを新compatibility keyの
     証跡で置換してからCompletion Gateを再レビューする。

- **確認観点**:
  - `M2-FLT-001`〜`057`の既存契約を変えず、実動E2E fixtureを追加できること。
  - capability未提示・期限切れ・nonce再利用・path/instance差替えは最初のwrite前に停止すること。
  - crash境界ごとにreceipt chainが実副作用のstrict prefixと一致すること。
  - repo外rootは承認済みrootに限定し、platform capability不足時は`UNSUPPORTED`になること。
  - confirmationのtest母数とrequired check IDをplatform間で一致させること。

- **影響推定・ロールバック**: 既存要件の意味は変更せず、未接続だった実行経路を実装する。
  主影響は `flow.py` / `flowlib/cli.py`、新規worktree adapter、confirmation harness、
  `tests/test_flow_m2_*`。公開operation追加を含むため通常フローとCompletion Gate再レビューが必要。
  worktree operation単位でfeature flag/dispatch表から外せる構造にし、単独revert可能とする。

- **予算**: M2実装枠6 PRは#246/#248/#250/#252/#254/#256で消化済み。是正には
  **追加2 PR（実動統合1、confirmation・Exit再レビュー1）/ 最大6 session**を推薦する。
  既定規則に従い、着手前に人間のscope/budget裁定を要する。

- **予備判定（推薦・裁定ではない）**: **accept推薦**。

  | 判定軸 | 結果 |
  |---|---|
  | 既存要件との矛盾 | なし。FLW-FR-006 / FLW-CON-005 / 006 / FLW-NFR-011の未実装部分を埋める |
  | ガードレール抵触 | あり得るため、実動テストは独立tmp repoに限定しrepo外rootへ書かない |
  | 影響範囲 | FLW-FR-006 impact: test-spec 2件・task 2件・root test 1件。加えてdispatcher/confirmation |
  | 軽量レーン適否 | 不可。公開CLIとdestructive worktree operationへ接続するため通常フローが必要 |
- **目的**: TODO
- **提案する修正**: TODO
- **対象ファイル**: TODO
- **確認観点**: TODO
- **影響推定・ロールバック**: TODO
- **依存**: TODO
