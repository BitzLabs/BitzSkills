---
id: SI-FLW-051
raised_by: FLW-REV-013（独立5観点レビュー・FAIL 2.31）
target: FLW-DSN-016・FLW-DSN-014
proposed_change_type: modify
status: open
---
- **目的**: **M2 の出口条件が原理的に充足不能な状態を解消する。** 出口条件が要求する
  「機械強制層」は Claude Code 固有機構でしか定義されておらず、同じ出口条件が
  3プラットフォームでの confirmation を要求している。あわせて、**実装区分の順序が
  自らの品質ゲートを無効化する**問題を解消する。

- **確認済みの欠陥**（`FLW-REV-013:SYN-007` / `SYN-008`。2026-08-13 に実測確認）:

  1. **機械強制層が Claude Code 専用**

     `FLW-DSN-016` §12 の M2 出口条件は「**機械強制層が有効**（permissions ＋ フックで
     receipt なし worktree write をブロック）」を含む。この機構は
     `.claude/settings.json` の `permissions` と `PreToolUse` フックでしか定義されていない。

     一方、同じ §12 は「local-write class の被測定物 confirmation が **3 platform で PASS**」を
     要求し、`FLW-DSN-014` の縮退規則3 は**強制層なしの worktree write 公開を禁じている**。

     実測: `find plugins/bitz-flow -name 'hooks*'` の結果は **0件**。
     bitz-flow はフック実体を配布していない。したがって Codex CLI / Antigravity では
     出口条件が**原理的に充足不能**であり、1/3 の被覆で green になる。

     さらに、permissions の緩和（worktree write を許可する変更）は安全機構の完成
     （M2-1〜M2-5）より**前に main へ落ちる**順序になっている。

  2. **M2-4 が M2-2 の blocking qualification を失効させる**

     M2-4（着手前 reconnaissance ＋ entry protocol）は `flow-core` の SKILL.md を変更する。
     これは **M0 Contract Kernel の構成物**であり、compatibility key に `skill` が含まれる。

     M2-2 の qualification は **blocking**（未達なら M2-3 以降を停止）として設計されているが、
     その後に実行される M2-4 が compatibility key を変えるため、**M2-6 の confirmation 時点で
     qualification は失効している**（TTL 24h でも結論は同じ）。

     `FLW-DSN-016` は同じ機序を `M2-FLT-042` で M1 manifest に対して fixture 化しながら、
     **自区分の順序には適用していない**。qualification の再実行は 20 session の内訳に未計上。

     また §14 の「M0 dispatcher を変更しない」という記述は、M2-4 の存在により**誤りである**。

- **提案する修正**（**選択肢を提示し、裁定を求める**）:

  **(a) 機械強制層の3プラットフォーム対応**

  | 案 | 内容 | 評価 |
  |---|---|---|
  | 案A | **bitz-flow がフック実体を配布する**（`hooks/hooks.json` を3マニフェスト構成へ追加） | 強制層が全 platform で有効になる。ただし Codex / Antigravity のフック仕様差の調査が必要で、M2 の実装量が増える |
  | **案B** | **出口条件を「強制層が利用可能な platform でのみ有効」へ再定義**し、非対応 platform では worktree write を `DEGRADED` として公開する。何が強制され何がされないかを capability matrix で明示する | **推奨。** v2 が既に持つ capability 縮退の枠組みに乗る。「1/3 の被覆で green」という虚偽の充足を、正直な縮退表現へ置き換えられる |
  | 案C | 強制層を出口条件から外す | 安全機構を出口から外すことになり、縮退規則3 の前提が崩れる。非推奨 |

  **推奨は案B。** ただし案B を採る場合、**縮退規則3 の解除条件**（M2 出口で M1 Git write の
  local-write class と M2 worktree を同時公開する）を、platform ごとの capability に
  分解して書き直す必要がある。

  併せて **permissions 緩和の投入時期**を、安全機構の完成後（M2-5 以降）へ移す。

  **(b) 実装区分の順序**

  M2-4（entry protocol 変更）を **M2-2（qualification）より前**へ移す。
  すなわち `M2-1 → M2-4' → M2-2 → M2-3 → M2-5 → M2-6` とし、compatibility key を
  変える変更をすべて qualification より前に済ませる。順序変更が不可能な場合は
  **qualification の再実行を区分として計上**する（+session が必要）。

  あわせて §14 の「M0 dispatcher を変更しない」を実態に合わせて訂正する。

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`（§4 機械強制層・§11 実装境界・§12 出口条件・§14 影響範囲）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（capability matrix・縮退規則3・M2 出口条件）

- **確認観点**:
  - M2 出口条件が**3 platform すべてで判定可能**であること（充足不能な条件が残らない）
  - 強制されない platform で、利用者に**何が強制されないかが伝わる**こと
  - qualification が confirmation の時点で**有効**であること（compatibility key の不変性）
  - permissions 緩和が安全機構の完成後に投入されること

- **影響推定・ロールバック**: 案B は `FLW-DSN-014` の capability matrix と縮退規則3 に波及する。
  実装区分の順序変更は M2 の budget 内訳（`FLW-DSN-016` §11）の書き換えを伴う。
  未実装のため文書改訂のみで戻せる。

- **依存**: `SI-FLW-049`（M2 出口で公開する operation 集合を決める論点と連動）。
  `SI-FLW-053`（budget 内訳の変更を伴うため）。
