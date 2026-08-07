---
id: SI-FLW-023
raised_by: ユーザー要望（2026-08-07 セッション）
target: 新規 settings apply operation・FLW-CON-005（明示的人間承認）・FLW-CON-006（破壊操作境界）・discovery/scope.md
proposed_change_type: new
status: open
---
- **目的**: `SI-FLW-022` の audit で検出した設定の逸脱を、**希望する設定へ変更**できるようにする
  （repository / organization settings の write）。plan / apply 分離と明示的人間承認の下でのみ許す。

- **現状（なぜ未対応か）**: v2 の write 対象は Git 操作・Issue・PR・release だけであり、
  **repository / organization の設定を変更する operation は設計に存在しない**。
  `scope.md` の Won't は「任意 shell / 任意 `gh api` passthrough」を禁じているため、
  設定変更を実装するなら許可された field を source code へ固定する形しか取れない。

- **提案する修正**:
  1. 新規 operation `settings plan` / `settings apply`（仮）を FR として起票し、
     `FLW-FR-005`（plan / apply 契約）と同じ規律に載せる。
     plan は副作用ゼロ、apply は plan の operation ID と **stale snapshot 拒否**を要求する。
  2. **変更可能な field を allowlist で固定**する。allowlist 外は `UNSUPPORTED` を返し、
     汎用の設定書換え口を提供しない。
  3. `FLW-CON-005` の明示的人間承認を必須にする。設定変更は「リポジトリ全体の
     ガードレールを緩める」方向にも働くため、承認なしの apply を構造的に不可能にする。
  4. **緩める方向の変更を特別扱い**する（例: branch protection の解除、required review の
     引き下げ、secret scanning の無効化、force push の許可）。既定では拒否し、
     明示 opt-in flag + 承認の二重条件でのみ通す。`FLW-CON-006`（破壊操作境界）へ
     「設定の緩和は破壊操作に準じる」旨を追記する。
  5. organization 単位の変更は repository 単位より影響が広い。**初期版は repository scope
     のみ**とし、organization は audit（`SI-FLW-022`）だけに留める案を推薦する。

- **対象ファイル**: `plugins/bitz-flow/.spec/discovery/scope.md`、新規 `requirements/FLW-FR-0xx`、
  `requirements/FLW-CON-006`（改訂）、新規詳細設計 `FLW-DSN-0xx`、`FLW-DSN-014`（capability）。

- **確認観点**:
  - **べき等性**（`FLW-NFR-005`）: 応答喪失後の再実行で二重適用にならないか。設定 API は
    PATCH 主体で自然にべき等だが、apply 前後の観測で postcondition 確認が要る。
  - 失敗時に**部分適用**が残る（複数 field を1 operation で変更した場合）。
    `FLW-NFR-003` の Forward Recovery に載せ、ロールバックではなく前進収束で扱えるか。
  - 変更前値の記録（誰が何をどう変えたかの証跡）をどこに置くか。`.spec` は仕様の SSOT で
    実行状態を持たない（`FLW-CON-003`）ため、`.spec` へ書かない設計にすること。
  - 必要な admin scope を doctor が事前に検出できるか。apply の途中で 403 にしない。
  - **セキュリティ**: 本 operation は事実上「リポジトリの防御設定を変えられる CLI」になる。
    AGENTS.md のガードレール（事前確認が必要な操作）と整合させ、エージェントが自律的に
    緩和方向へ apply できない構造にすること。

- **影響推定・ロールバック**: v2 の write 境界を settings へ広げるスコープ拡張であり、
  Design Gate の再裁定が要る。`FLW-CON-006` の改訂を伴うため既存承認済み要件へ波及する。
  実装は独立 operation なので単独 revert 可能だが、CON 改訂は別 PR に分けること。

- **依存**: `SI-FLW-022`（audit）。audit の観測・期待値モデルが先に固まらないと
  apply の差分定義ができない。逆順 revert で安全に戻せるよう、必ず 022 → 023 の順に実装する。

- **予備判定（推薦・裁定ではない）**: **条件付き accept 推薦（ただし v2 初期版では Could / 保留を推薦）**。
  | 判定軸 | 結果 |
  |---|---|
  | 既存要件との矛盾 | `FLW-CON-006` の破壊操作境界と要調整（緩和方向の変更の扱い）。矛盾ではなく拡張 |
  | ガードレール抵触 | **要注意**。防御設定の緩和はエージェント単独で実行させてはならない類の操作 |
  | 影響範囲 | 新規 operation + CON 改訂。M0 未通過の現況では M5 以降の位置づけが妥当 |
  | 軽量レーン適否 | **不可**（公開契約・CON 改訂・Design Gate 再裁定） |

  理由: 要望としては妥当で価値もあるが、v2 は M0（read-only thin slice）すら出口未達である。
  write 境界を Git / GitHub の協調操作から**リポジトリ統治設定**へ広げるのは v2 の目的
  （3プラットフォームで同じ判断に収束する実行契約）とは別軸の拡張であり、
  M1〜M5 を圧迫する。audit（022）を先に出し、apply は v2 の Promotion Gate 後、
  または v2.1 として切り出す判断を推薦する。
