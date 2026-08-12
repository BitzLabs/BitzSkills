---
id: SI-FLW-048
raised_by: FLW-REV-013（独立5観点レビュー・FAIL 2.31）
target: FLW-DSN-016
proposed_change_type: modify
status: accepted
---
- **目的**: **guard が守ると宣言した対象と、operation が実際に変更する対象を一致させる。**
  また **guard key と CAS が別々の identity 方式を使っている**状態を解消する。
  `FLW-REV-011:GP-003`（index 包含規約）が塞いだはずの穴が、step 表から再導入されている。

- **確認済みの欠陥**（`FLW-REV-013:SYN-005` / `SYN-011` / `SYN-018` / `SYN-028`。
  2026-08-13 に実ファイルで機械確認）:

  1. **`sync-main` が guard 集合外の target を変更する**

     `FLW-DSN-016.md:50` は `worktree.finish` の canonical mutation target を「同上」＝
     `worktree-dir ＋ worktree-registry ＋ local-ref ＋ index` と宣言する。
     いずれも**対象 worktree に閉じた4点**である。

     一方 `FLW-DSN-016.md:528-530` の finish の step 契約:

     ```
     verify-pr-merge → verify-target-oid → verify-reachability → sync-main
       → remove-registry-entry → remove-worktree-dir → delete-local-branch
     ```

     `sync-main` は **main の branch ref**（および main 作業ツリーの index）を変更する。
     main の local-ref は finish の宣言 target 集合に無い。これは
     `FLW-REV-011:SYN-003`（「guard していない target を別 operation が変更する」）と
     **同型の穴**であり、§8 が「全 step がちょうど1つの mutation target に対応する」と
     宣言している規約そのものにも違反している。

  2. **guard key と CAS の identity 方式が違う**

     guard key は canonical path の digest（`FLW-DSN-016.md:199`）、CAS は dev+ino。
     bind mount / 別 mount 経路から同一実体へ到達すると **path が違えば別 key** になる。
     `M2-FLT-006`（「別 clone・別 mount から同一 worktree 要求 → 同一 guard へ収束」）が
     要求する収束は、この方式の組合せでは**原理的に達成できない**。

  3. **CAS が content digest を欠く**

     `worktree-dir` の CAS 相当が stat メタデータのみで、racily-clean な編集
     （同一 mtime 内の変更）を検出できない。`manifest digest` も内容 hash を持たず
     mtime 精度に依存する。

  4. **`create` / `resume` の guard key が「まだ存在しない path」に対して未定義**

     canonical path digest は実在する path の解決を前提とするが、`create` は定義上
     対象 path が存在しない。`FLW-REV-011:SYN-002` が guard key 側で再発している。

- **提案する修正**（**選択肢を提示し、裁定を求める**）:

  **(a) `sync-main` の扱い** — 次のいずれかを裁定する。

  | 案 | 内容 | 評価 |
  |---|---|---|
  | **案A** | `sync-main` を finish の step から**外す**。独立した local-write operation として、自前の guard 集合と承認のもとで実行させる | **推奨。** operation の責務が単一になり、「宣言 target = 実変更 target」を機械検査できる |
  | 案B | finish の宣言 target に **main の local-ref と index を加える** | finish が main を巻き込んで排他するため、無関係な作業まで待たされる |
  | 案C | `sync-main` を read-only の検査 step に格下げし、同期は利用者に委ねる | 安全だが finish の利便性が落ちる |

  **(b) identity 方式の統一** — guard key と CAS の**双方を同一の identity へ揃える**。
  候補は「canonical path digest に統一」「dev+ino に統一」「両者の組（path, dev+ino）を
  key とし、不一致時は `BLOCKED`」。**推奨は3案目**。bind mount の収束要求
  （`M2-FLT-006`）と、instance 差し替えの検出（`FLW-REV-011:SYN-004`）を同時に満たせる。

  **(c) 不在 path の key 導出** — 「祖先を root まで遡り、最も近い実在祖先の canonical と
  そこからの相対 path を合成して key とする」規則を定義する。
  `M2-FLT-009`（不在 path の case 差）が既に同じ祖先遡り方式を要求しており整合する。

  **(d) content digest** — 破壊的 operation の CAS には**内容 hash を含める**。
  対象範囲（全ファイルか、追跡対象のみか、上限サイズ）と、大規模 worktree での
  性能縮退の扱いを併せて決める。

  裁定後、**全 step がちょうど1つの宣言済み mutation target へ写像すること**を
  機械検査として実装する（`SI-FLW-052` の検証群に含める）。

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`（§1 operation catalog・§3 guard identity・§5 instance identity・§8 step 契約）

- **確認観点**:
  - 各 operation の step 集合 → 宣言 mutation target 集合が**全射**であること（機械検査）
  - bind mount / 別 mount 経由の同一実体が同一 guard key へ収束すること（`M2-FLT-006`）
  - `create` の対象 path が不在でも key が一意に導出できること
  - racily-clean な編集が CAS で検出できること

- **影響推定・ロールバック**: M2-1（guard core）と M2-5（finish / discard）に波及する。
  案A を採ると operation catalog に新 operation が1つ増えるため、
  `FLW-DSN-012` の contract 表と capability matrix の更新が必要。
  `FLW-DSN-016` は未実装のため文書改訂のみで戻せる。

- **依存**: `SI-FLW-047` と**同時に裁定する**（区分の軸を証跡へ移す場合、証跡 identity と
  guard identity の整合が必要）。`SI-FLW-049`（operation class）とも連動する
  （案A で新設する operation の class を決める必要があるため）。
