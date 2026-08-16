---
id: SI-FLW-065
raised_by: FLW-REV-017 consistency（RVC-101）
target: 公開経路 E2E の出力形式カバレッジと next_action の契約適合
proposed_change_type: modify
status: accepted
---

- **目的**: 公開 CLI が**既定の出力形式**で壊れないことを検査対象に含める。

- **発見した事実**（`FLW-REV-017:RVC-101`、critical）:
  - `SI-FLW-064` が追加した `worktree.audit` の `next_actions` が result 契約の形
    （`domain` / `action` / `args`）に従わない自作 dict だったため、**既定の compact 形式で
    `render_compact` が `KeyError: 'domain'` を投げる**。JSON 形式では正常に返る。
  - 見逃した理由は構造的である。公開経路 E2E の `_dispatch` が `--format json` を固定しており、
    **dispatcher テストが既定 renderer を一度も通っていなかった**
    （`grep render_compact tests/` は 0 件）。
  - 既定形式は利用者が実際に見る出力であり、そこが落ちる状態を出荷しかけた。
  - `result.next_action(domain, action, **args)` という契約用ヘルパが既に存在し、
    他の operation はそれを使っていた。新規追加だけが自作 dict を渡していた。

- **実装した修正**:
  1. `next_actions` を `R.next_action("worktree", "audit", external=len(external))` へ。
  2. 公開 operation を**既定 renderer で描画する専用テスト**を追加する。
     副作用の無い operation（read 系と write の plan）に加え、
     **外部変更を検出した audit（NEXT 行が出る経路）**を含める。
  3. `next_actions` の各要素が `{domain, action, args}` であることを検査する。

- **確認観点**:
  - 公開 operation が既定形式で例外を投げず描画できること。
  - 外部変更検出時の NEXT 行が出ること（`next_actions` を持つ経路を実際に通る）。
  - `_dispatch` を二重実行にしない（write が2回走り nonce が消費されるため、
    既定 renderer の検査は副作用の無い経路で行う）。

- **影響推定・ロールバック**: 公開 CLI の出力形式に閉じる。

- **依存**: `SI-FLW-064` の追加分に対する是正。
