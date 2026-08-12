---
id: SI-FLW-047
raised_by: FLW-REV-013（独立5観点レビュー・FAIL 2.31）
target: FLW-DSN-016・FLW-DSN-012
proposed_change_type: modify
status: accepted
---
- **目的**: **quarantine の解除区分と write operation の step 順が、互いを無効化している
  状態を解消する。** 現在の設計では discard が中断すると**必ず**恒久 quarantine へ落ちる。
  `FLW-REV-011:GP-005`（正規解放経路を用意する）は本 issue が閉じるまで未消化である。

- **確認済みの欠陥**（`FLW-REV-013:SYN-003` / `SYN-006` / `SYN-022` / `SYN-027` / `SYN-029`。
  2026-08-13 に実ファイルで機械確認）:

  `FLW-DSN-016.md:530-534` の `worktree.discard` の step 順:

  ```
  freeze-manifest → verify-manifest-scope → remove-registry-entry
    → remove-worktree-dir → delete-local-branch
  ```

  `FLW-DSN-016.md:403-405` の解除**可能**な3区分は、いずれも **local-ref 不在を要件**とする:

  | 区分 | 要件 |
  |---|---|
  | `worktree-no-effect` | dir / registry entry / local-ref の**いずれも不在** |
  | `worktree-residue-retained` | directory だけ残存。**registry entry と ref は不在** |
  | `worktree-registry-stale` | registry entry だけ残存。実体 dir 不在（＋非存在の証明） |
  | `worktree-unresolved` | 三者が矛盾 → **解除不可・quarantine 継続** |

  local-ref の削除が **step 順の最後**にあるため、discard の中断点2箇所は次のようになる:

  | 中断点 | dir | registry | local-ref | 該当区分 |
  |---|---|---|---|---|
  | `remove-registry-entry` 直後 | 有 | 無 | **有** | 該当なし → `unresolved` |
  | `remove-worktree-dir` 直後 | 無 | 無 | **有** | 該当なし → `unresolved` |

  **中断すれば必ず恒久 quarantine になる。** さらに `FLW-DSN-016.md:540` は registry 先行の
  根拠を「残った実体は `worktree-residue-retained` へ一意に確定できる」と記すが、
  同区分の要件は ref 不在である。**設計の順序選択根拠を、同一設計内の別の表が反証している。**

- **併発する欠陥**:

  1. `worktree-registry-stale` の必須証跡は「entry の `gitdir` が指す path が存在しないこと
     **の証明**」だが、同じ `FLW-DSN-016` の ABA 節は「否定的主張は観測から導けない」と
     結論している。**この区分は原理的に空になる**（`SYN-006`）
  2. `worktree-no-effect`（三者＋nonce 不在）は **discard 成功後の観測と完全に一致**する。
     M1 が証跡で区別していた `confirmed-done` に相当する worktree 区分が無く、
     「未実行」と誤って解除すると新 plan が**新しい instance を削除**する
     （`FLW-REV-011:SYN-004` の再侵入。`SYN-022`）
  3. `worktree-residue-retained` の唯一の脱出が手動削除だが、それは
     リポジトリのガードレールで禁止されている（`SYN-027`）
  4. `create` / `resume` は step 契約を持たないのに `PARTIAL` / reconcile-only が
     割り当てられており、`completed_steps` / `remaining_steps` の一意化が実装不能（`SYN-029`）

- **提案する修正**（**選択肢を提示し、裁定を求める**）:

  | 案 | 内容 | 長所 | 短所 |
  |---|---|---|---|
  | **案A** | **step 順を変える**。local-ref 削除を最初に置き、`registry → dir` を後段にする | 既存の区分表を変えずに済む | ref を先に消すと「どの branch の worktree だったか」を失い、residue の帰属が不明になる |
  | **案B** | **区分の定義軸を「三者の存在パターン」から「証跡（instance nonce / receipt）」へ移す**。存在パターンは補助情報にする | 中断点を網羅でき、(2) の「未実行と成功が区別できない」も同時に解決する | 証跡の永続化が前提になり、M2 の実装量が増える |
  | **案C** | 存在パターン軸を維持しつつ、**8通りすべてに区分を定義**する（現在は3通りのみ） | 変更が局所的 | (1)(2) は解決しない。区分数が増え運用が複雑になる |

  **推奨は案B。** (1) の「非存在の証明が原理的に不可能」と (2) の「未実行と成功が
  観測上同一」は、いずれも**存在パターンだけを見ている限り解決しない**ためである。
  M1 は同じ問題を intent record と receipt で解決済みであり、機構を新規開発せず流用できる。

  裁定後、選んだ軸のもとで **discard / finish の step 順に課される制約を導出**し、
  `FLW-DSN-016` §6・§8 と `FLW-DSN-012` の recovery 表を**同時に**改訂する。
  あわせて `create` / `resume` の step 契約を定義する。

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`（§6 解除区分・§8 recovery matrix と step 契約）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-012.md`（recovery 表・`completed_steps` 写像）

- **確認観点**:
  - discard / finish の**全中断点**がちょうど1つの区分へ落ちること（決定表として機械検査する）
  - 解除**可能**な区分から必ず前進経路があり、手動削除に依存しないこと
  - 「未実行」と「成功済み」が区別できること
  - 区分数が本文・表・§15・fixture で一致すること（現在は 3 / 4 / 4 / 3 で不一致）

- **影響推定・ロールバック**: M2-1（guard core）と M2-5（finish / discard）の設計が変わる。
  案B を採る場合は M2-2 の証跡機構にも波及する。`FLW-DSN-016` は未実装（status: draft）で
  あるため、実装のロールバックは発生しない。文書改訂のみで戻せる。

- **依存**: `SI-FLW-048`（guard identity と mutation target）と**同時に裁定する必要がある**。
  区分の軸を証跡へ移す場合、証跡の identity が guard identity と整合していなければならない。
