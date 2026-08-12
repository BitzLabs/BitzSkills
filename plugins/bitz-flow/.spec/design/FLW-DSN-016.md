---
id: FLW-DSN-016
title: "M2 worktree safety詳細設計"
status: draft
version: 1.4
updated: 2026-08-12
owner: hide
implements: FLW-FR-006, FLW-FR-007, FLW-NFR-006, FLW-NFR-007, FLW-NFR-011, FLW-NFR-012, FLW-CON-005, FLW-CON-006
origin: SI-FLW-041, SI-FLW-042, SI-FLW-043, SI-FLW-044, SI-FLW-045, FLW-REV-011
decision_ref: .spec/reports/decision-2026-08-12-m2-design-gaps.md
---

# FLW-DSN-016 M2 worktree safety詳細設計

## 責務と規範性

本設計は M2 worktree-first の実装詳細について、`FLW-DSN-006` のライフサイクル、
`FLW-DSN-015` の write safety、`FLW-DSN-013` の forward recovery、`FLW-DSN-014` の検証原則を
結合する規範設計である。M1 に対する `FLW-DSN-015` と同じ位置づけを持つ。

**本書は `FLW-REV-011`（FAIL、2.47、P0 5系統 / Gate 前提条件 18件）への回答である。**
`decision-2026-08-12-m2-design-gaps.md` は「補強詳細設計は作らない」と判断したが、
`FLW-REV-011` が「P0 5系統のうち4系統は `FLW-DSN-006` にも `FLW-DSN-015` にも書かれていない
新しい安全機構を要求しており、spec-issue の追記で収まる規模ではない」として同判断の見直しを
求めた。**この見直しは 2026-08-12 に人間裁定で承認され、本書の作成に至った。**

4文書と矛盾する場合は本書の M2 固有表を優先し、一般原則の変更が必要なら
元文書も同じ変更セットで更新する。

### 追加の人間裁定（2026-08-12）

`FLW-REV-011` が挙げた裁定依頼3件のうち、依頼1（補強設計の要否）は上記のとおり。
残る2件は次のとおり裁定された。本書はこれを前提に設計する。

| 依頼 | 裁定 | 本書での扱い |
|---|---|---|
| 2. `registered-active` の扱い | **`ACTIVE_CLEAN` へ統合する** | §2。統合の原則を `FLW-DSN-012` の再構成規則から導出し、同型の値も併せて整理する |
| 3. guard 取得を承認の前へ倒すか | **後のまま。capability 化で閉じる** | §4。却下理由を明記し、TOCTOU と承認使い回しを capability で閉じる |

## M2 operation catalog

catalog 外は `UNSUPPORTED` である。`FLW-REV-011:SYN-006`（finish / resume が3者 guard の
対象から抜けている）を受け、**worktree を変える4 operation すべてを3者 guard の対象**とする。

| operation | class | canonical mutation target | recovery | 実装区分 |
|---|---|---|---|---|
| `worktree.audit` | read | なし | retry-read | M2-3 |
| `worktree.create` | local-write | `worktree-dir` ＋ `worktree-registry` ＋ `local-ref` ＋ **`index`** | REC-WT-CREATE | M2-3 |
| `worktree.resume` | local-write | 同上 | REC-WT-RESUME | M2-3 |
| `worktree.finish` | local-write | 同上 | REC-WT-FINISH | M2-5 |
| `worktree.discard` | local-write | 同上 | REC-WT-DISCARD | M2-5 |
| `git.delete-remote-branch` | remote-write | `remote-ref` | REC-RM-DELETE | M2-6 |

`index` が入るのは §3 の包含規約による。`create` と `resume` は
**公開 operation 名を分ける**（`FLW-REV-011` の P2 で未確定だった点をここで確定する）。
plan は共通だが、既存 worktree の有無で到達する状態が異なり、
`FLW-DSN-012` の「各公開 operation は1つの milestone だけへ所属する」と
result schema の operation 名一意性を満たすためである。

## §2 状態 enum の三者一致

対応 GP: **GP-001 / GP-012 / GP-014 / GP-015 / GP-016 / GP-018**

### 原則 — audit 分類は外部事実から再構成できる観測状態に限る

`FLW-DSN-012` は「**状態遷移は外部事実から毎回再構成する**」と定める。
したがって「自分が作った」という由来情報を含む状態は audit 分類になり得ない。
`registered-active`（create 終端）は「registry entry を公開し双方向一致を確認した」という
**実行主体側の履歴**であり、外部から観測すると create 直後の worktree は clean であるため
`ACTIVE_CLEAN` と区別できない。よって **`ACTIVE_CLEAN` へ統合する**（裁定2）。

同じ原則を一貫して適用し、`PLANNED` / `APPROVED` も `worktree_state` から除く。
これらは worktree の観測状態ではなく **plan のライフサイクル**であり、
`write_state`（`PLANNED` / `GUARDED` / `PENDING_INTENT` …）が既に表している。
`FLW-DSN-012` の写像表で WorkUnit `planned` に対応する worktree state は
`absent/planned` と書かれているが、worktree が存在しない以上 **`ABSENT` の一値**へ改める。

### 閉集合（本書を唯一の正とする）

`FLW-REV-011:SYN-001` は「`FLW-DSN-015` の表が『値の正は他文書』と委譲したため、
どちらを見ても正が確定しない」ことを P0 とした。**委譲文を削り、本表を唯一の正**とする。
`FLW-DSN-006` / `FLW-DSN-012` 側は本表を参照する記述へ改める（GP-018）。

| namespace | field | 値の性質 | closed enum |
|---|---|---|---|
| write 機械 | `write_state` | 状態 | `PLANNED, GUARDED, PENDING_INTENT, MUTATING, RECONCILING, DONE, PARTIAL, STALE, QUARANTINED` |
| operation 結果 | `result_code` | 判定結果 | `DONE, PARTIAL, INDETERMINATE, STALE, BLOCKED, INVALID_INPUT, UNSUPPORTED` |
| intent 記録 | `intent_record_state` | 状態 | `PENDING, RECONCILING, PARTIAL, STALE, QUARANTINED, RELEASED` |
| Gate | `gate_status` | 判定結果 | `PASS, FAIL, BLOCKED` |
| attempt | `attempt_status` | 判定結果 | `STARTED, PASS, FAIL, ABORTED, UNKNOWN` |
| **WorkUnit** | `work_unit_state` | 状態 | `PLANNED, ISOLATED, ACTIVE, VERIFIED, PR_DRAFT, REVIEW_READY, MERGE_READY, MERGED, AUDITED, CLEANED, FAILED_RETAINED, DISCARDED` |
| **worktree** | `worktree_state` | 状態 | `ABSENT, ACTIVE_CLEAN, ACTIVE_DIRTY, PR_OPEN, MERGED_EXACT, REMOTE_ADVANCED, WORKTREE_MISMATCH, ORPHAN, FAILED_RETAINED` |
| **branch 単体** | `branch_audit_state` | 状態 | `ACTIVE, MERGED_EXACT, REMOTE_ADVANCED, WORKTREE_IN_USE, ORPHAN` |
| guard target 種別 | `guard_identity_kind` | 種別 | `index, local-ref, remote-tracking-ref, fetch-head, remote-ref, worktree-dir, worktree-registry` |
| qualification trial 種別 | `trial_kind` | 種別（**規則の反例**） | `Q-NORMAL, Q-REJECT, Q-CORRUPT` |
| 診断 cause | `cause` | 分類 | `FLW-DSN-005` の許可語彙（本書で変更しない） |

三者照合テスト（下記）の対象は**本表の全 namespace** とする。`cause` は値の正を
`FLW-DSN-005` に置いたままだが、照合対象から外さない — 外した namespace は
`guard_identity_kind` と同じ経路（設計と実装の乖離が沈黙する）で腐るためである。

`work_unit_state` は `FLW-DSN-012` の正規 WorkUnit state **12値**と1対1に対応する
（`planned` → `PLANNED` … `discarded` → `DISCARDED`）。`FLW-REV-011:SYN-001` が指摘した
6欠落（`review-ready` / `merge-ready` / `audited` / `cleaned` / `failed-retained` / `discarded`）を
回復し、2捏造（`PR_OPEN` は worktree 側の語、`FAILED` は実在しない）を除いた。
`audited` は `worktree.finish` の唯一の許可前提、`cleaned` / `discarded` は終端であり、
いずれも M2 の対象 operation である。

`FLW-FR-007` の audit 分類 `indeterminate` は `branch_audit_state` に**置かない**。
`result_code: INDETERMINATE` へ一本化する（同名別概念を作らないため）。
`FLW-FR-007` の受入基準はこの一本化に合わせて改訂する。

### 表記規則の判定基準（GP-016）

`FLW-REV-011:SYN-016` は「表記規則に反例があり判定基準が明文化されていない」ことを指摘した。
判定基準は **field 名ではなく値の性質**とする。

| 値の性質 | 表記 | 例 |
|---|---|---|
| 状態・判定結果（有限の遷移先・合否） | 大文字スネーク | `ACTIVE_CLEAN` / `INVALID_INPUT` / `PASS` |
| 分類・語彙・種別（対象を種類分けするラベル） | 小文字 kebab | `not-repository` / `local-ref` / `claude` |

上表の「値の性質」列がこの判定を機械可読にする。**既知の反例**は
`trial_kind` の `Q-NORMAL` / `Q-REJECT` / `Q-CORRUPT` であり、種別でありながら大文字である。
これは M1 で凍結済みの契約であるため**改名せず、反例として明示**する
（規則に例外があること自体を隠さない）。新規 enum に例外を追加してはならない。

### 多重語一覧は schema から機械導出する（GP-014）

`FLW-REV-011:SYN-014` は「複数 namespace に現れる語の一覧が 4/10 漏れている」とした。
**手で維持する一覧は必ず腐る**ため、schema の enum から機械導出する。

導出規則: 全 namespace の closed enum を集め、2つ以上の namespace に現れる値を列挙する。
本設計時点の導出結果は次のとおり（実装時は生成物と本表を照合する）。

| 語 | 現れる namespace |
|---|---|
| `PLANNED` | `write_state` / `work_unit_state` |
| `DONE` | `write_state` / `result_code` |
| `PARTIAL` | `write_state` / `result_code` / `intent_record_state` |
| `STALE` | `write_state` / `result_code` / `intent_record_state` |
| `RECONCILING` | `write_state` / `intent_record_state` |
| `QUARANTINED` | `write_state` / `intent_record_state` |
| `BLOCKED` | `result_code` / `gate_status` |
| `PASS` / `FAIL` | `gate_status` / `attempt_status` |
| `ACTIVE` | `work_unit_state` / `branch_audit_state` |
| `MERGED_EXACT` | `worktree_state` / `branch_audit_state` |
| `REMOTE_ADVANCED` | `worktree_state` / `branch_audit_state` |
| `ORPHAN` | `worktree_state` / `branch_audit_state` |
| `FAILED_RETAINED` | `work_unit_state` / `worktree_state` |

`worktree_state` と `branch_audit_state` に共通して現れる3語
（`MERGED_EXACT` / `REMOTE_ADVANCED` / `ORPHAN`）は、**判定述語を namespace ごとに分離**する。
worktree の有無で照合する証跡集合が変わるためである
（`worktree_state` 側は registry entry と実体の双方向一致を含み、`branch_audit_state` 側は含まない）。

### 三者照合の機械化（GP-012）

`FLW-REV-011:SYN-012` は「設計は7種・契約は5種で乖離し、照合テストが片方向のため沈黙する」とした。
実測でも `schemas/result-v1.schema.json` / `schemas/intent-record-v1.schema.json` の
`guard_identity_kind` と `flowlib/guard.py` の `GUARD_IDENTITY_KINDS` はいずれも5種である。

**三者（設計の閉集合・schema の enum・実装の定数）を双方向で照合するテスト**を追加する。

- 照合対象は上表の全 namespace とし、`guard_identity_kind` だけを特別扱いしない。
- **片方向にしない**。設計 ⊆ schema と schema ⊆ 設計の両方を検査し、
  どちらかの欠落で FAIL させる。現在の片方向照合が沈黙した原因はここにある。
- 実装定数は既存の `GUARD_IDENTITY_KINDS` のように**タプル定数として1箇所に置く**。
  設計文書から機械抽出できる形式（本書の表）を正とし、テストが差分を出す。
- 多重語一覧（上節）も同テストで生成・照合する。

### closed enum への値追加の互換性（GP-015）

`FLW-REV-011:SYN-015` は「『key 集合は加算のみ』を enum 値追加の互換性根拠に誤用している」とした。
`output-contract.md` の「key 集合は加算のみ」は **object の key** に関する規定であり、
**closed enum の値追加**を正当化しない。読み手が閉集合を前提に分岐を書いている場合、
値の追加は未知値として分岐から漏れるためである。

本書は互換性を根拠にせず、次を採る。

- `guard_identity_kind` への2値追加と `work_unit_state` / `worktree_state` /
  `branch_audit_state` の新設は、**M2 の契約凍結時点の破壊的変更**として扱う。
- write は未公開であり外部消費者が存在しないため、実害は生じない。
  **「互換だから安全」ではなく「未公開だから影響が無い」**という根拠に置き換える。
- `output-contract.md` へ closed enum の値追加に関する条文を新設し、
  「未公開 operation に限り凍結前の追加を許す。公開後の追加は major 扱い」と明記する。

## §3 guard identity の拡張

対応 GP: **GP-003 / GP-008 / GP-009**

### 導出規則

`FLW-DSN-015` の閉集合へ2種を追加する。既存5種の導出規則は変更しない。

| target type | canonical key |
|---|---|
| `worktree-registry` | canonical common-dir identity ＋ **registry entry 名** |
| `worktree-dir` | canonical common-dir identity ＋ worktree の canonical path の digest |

`worktree-dir` も **raw path を key にしない**。canonical path は digest 化し、
symlink・相対 path・case 差・別 clone を正規化して同一 worktree へ収束させる。

**instance identity（§5）を guard key へ含めてはならない。** key に instance を混ぜると、
同じ path に対する「旧 instance の discard」と「新 instance の create」が**別 key になり
互いに排他しなくなる**。両者が同時に進行すれば SYN-004 の事故を防ぐどころか
直列化そのものが失われる。guard key は **path に対して安定**（instance 非依存）とし、
すべての operation を同じ key で直列化する。instance の同一性は
**precondition（`snapshot_digest`）で照合**する — これが `FLW-REV-011:GP-004` の
「instance identity を precondition に入れ、apply 直前に CAS 照合する」の意味である。

| 役割 | 置き場 | 目的 |
|---|---|---|
| 直列化 | guard key（path に対して安定） | 同一 path への並行 operation を最大1件にする |
| 同一性の照合 | precondition / `snapshot_digest` | 承認時と apply 時が**同じ instance**であることを保証する |

### binding 検証と `worktree_id` の canonical 導出（GP-008）

`FLW-REV-011:SYN-008` は「2 key を独立に定義するだけで、両者が同じ worktree を指すことの
検証規定が無い」「`worktree_id` は呼び出し側の自由文字列で、唯一の呼出が
`git_sync.py:234` で literal `"main"` を渡している」とした。実測で確認済みである。

1. **authoritative 側を registry とする**。`common-dir/worktrees/<name>/gitdir` の内容を読み、
   そこから worktree のパスを得る。worktree 側 `.git` file が指す entry と
   **相互参照が一致すること**を precondition にする。片側だけ成立する状態は
   `ORPHAN` として `BLOCKED` にし、推測で補完しない。
2. **`worktree_id` の canonical 導出関数を `guard.py` に置き、literal を渡せない形にする**。
   導出は registry entry 名からのみ行い、呼び出し側が文字列を組み立てられないようにする。
   main worktree（registry entry を持たない）は専用の sentinel を返す別関数とし、
   `git_sync.py:234` の literal `"main"` はこれへ置き換える。
3. 3者（`worktree-dir` / `worktree-registry` / `local-ref`）と §3 の `index` は
   **canonical key の昇順で1回の acquire にまとめて取得**する。
   途中失敗時は逆順解放・副作用 0 で `BLOCKED`。

### index 包含規約（GP-003）

`FLW-REV-011:SYN-003` は「`git.stage` の canonical mutation target は index のみで branch ref を
取らないため、discard が3者を保持していても別 operation が index key だけを取って stage を
実行できる。key 集合が交差しないため双方とも `BLOCKED` にならない」とした（P0）。

**包含規約**: worktree W の `worktree-dir` または `worktree-registry` を取る operation は、
**W に属する `index` target を同じ acquire に必ず含める**。

- W の index target は `canonical_index_target(common_dir, worktree_id)` で導出し、
  `worktree_id` は上記 canonical 導出関数から得る（自由文字列を渡せないため機械的に強制される）。
- 逆向き（`index` だけを取る `git.stage`）に worktree guard の取得は要求しない。
  包含は**片側で足りる** — discard 側が index を握るため、stage は同じ index key で待たされる。
- 実装は acquire の入口で「worktree 系 kind が含まれるなら対応する index target を自動付加する」
  正規化を行い、呼び出し側の記述漏れを構造的に排除する。

### case 感度判定の是正（GP-009）

`FLW-REV-011:SYN-009` は「`_case_sensitive_filesystem` は probe が存在しない場合に
case-sensitive と判定するが、worktree-dir は create 時に必ず不在」とした。実測で確認済み
（不在 path に対し `True` を返す）。

1. **存在する最も近い祖先まで遡って probe する**。現行の「対象 path または
   その parent だけ」を、root に達するまでの祖先探索へ改める。
2. 承認済み worktree root の case 感度を**承認時に1度測って intent へ記録**し、
   以後は記録値を再利用する（root は承認時点で必ず存在するため測定できる）。
3. 祖先が root まで到達しても判定できない場合は **判定不能として `BLOCKED`**。
   case-sensitive 側へ倒す現行の既定は、case-insensitive FS で同一 directory への
   並行 create を2本通すため採らない。
4. fault fixture に「**不在 path の case 差**」を追加する（`M2-FLT-009`）。

## §4 承認の capability 化と機械強制層

対応 GP: **GP-002 / GP-010 / GP-011**

### guard を承認の後に取る選択の維持と却下理由（裁定依頼3）

裁定により **guard は承認の後**のまま維持する。前へ倒す案の却下理由を明記する
（`FLW-REV-011` が「却下理由の明記が要る」とした点への回答）。

- **却下案**: guard を承認より先に取る。key が承認時点で束縛され TOCTOU が原理的に消える。
- **却下理由**: 人間の承認待ちは分単位から時間単位になり得る。その間 guard を保持すると、
  同じ worktree の `index` を含む3者以上が `BLOCKED` になり続ける。
  §3 の包含規約により `git.stage` まで巻き込むため、**承認待ち1件が当該 worktree の
  全 write を停止させる**。M1 が「無期限 BLOCKED を安全側既定とする」のは
  異常時であり、正常な承認フローで恒常的に発生させる設計は運用に耐えない。
- **代替手段**: TOCTOU と承認使い回しは、guard の保持ではなく**署名付き単回 capability**で閉じる。
  これは M1 が quarantine 解除後の mutation に対して既に採っている方式であり、新規機構ではない。

### repo 外承認 capability（GP-002 / GP-011）

`FLW-REV-011:SYN-002`（P0）は「承認は人間が読んだ path 文字列に対して与えられ、
guard key は canonical path の digest である。承認から guard 取得・apply までの間に
親 directory の symlink 差し替え、別 process の先行占有、`worktree_root` 設定変更が起きても
承認は再検査されない」とした。`SYN-011`（P1）は「承認 → guard 取得失敗 → 再試行のループで
承認が使い回せる」とした。

M1 の capability envelope（`algorithm=Ed25519` の閉集合、trusted key ID、key generation、
signed payload、signature）を**そのまま再利用**し、署名対象を worktree 用に定める。

| 署名対象 field | 目的 |
|---|---|
| `worktree_dir_guard_key` | 承認と guard key を結合する（SYN-002 の核心） |
| `worktree_registry_guard_key` | 同上（registry 側） |
| `parent_dir_identity` | 親 directory の stable file identity。symlink 差し替えを検出する |
| `nonexistence_digest` | **`create` 専用**。対象が存在しないことの証明 digest。先行占有を検出する |
| `instance_identity_digest` | **`resume` / `finish` / `discard` 専用**。§5 の4要素の digest。承認時と apply 時が同じ instance であることを保証する |
| `worktree_root_canonical` | 承認時の root。設定変更・移設を検出する |
| `case_sensitivity` | §3 で測定した root の case 感度 |
| `expires_at` | 期限 |
| `nonce` | 単回。再利用を拒否する（SYN-011） |
| `operation_id` | 対象 operation |

**再照合点**は次の2箇所とし、いずれかで不一致なら `STALE`（`replan-human`）とする。

1. guard 取得**直後**
2. 各副作用の**直前**

nonce は M1 と同じく target guard 内で linearizable CAS し、
`UNUSED → USED_PENDING` を fsync してから mutation する。結果は `USED_DONE` または
`QUARANTINED` へ追記し、`USED_PENDING` のまま crash した場合は reconcile 完了まで再利用不可とする。

`FLW-CON-005` の「`--approval-ref` は参照の存在だけで apply 可否を変更しない」原則は維持する。
capability は**署名の検証結果**が可否を決めるのであって、参照の存在ではない。

### 機械強制層（GP-010）

`FLW-REV-011:SYN-010` は「`AGENTS.md` はリポジトリ外への書き込みを事前確認必須とし
機械的ブロックを `settings.json` の permissions で強制すると定めるが、worktree root に
該当する規則が無い。M2 は repo 外書き込みを常用化する最大の変更でありながら
機械層は無変更である」とした。

**M2 の出口条件を機械層まで含む定義にする。**

1. `.claude/settings.json` の permissions へ worktree root パターンを追加する。
2. **承認 receipt を伴わない worktree write を PreToolUse フックでブロックする。**
3. receipt は intent と同じ **common-dir 配下の owner-only 領域**へ追記し、監査可能にする
   （worktree 実体側に置くと discard で消えるため）。
4. `AGENTS.md` のガードレール節と permissions の対応関係を維持する
   （片方だけ緩めない。`env-doctor` の同期チェック対象）。

## §5 instance identity と CAS 相当

対応 GP: **GP-004 / GP-007**

### instance identity（GP-004）

`FLW-REV-011:SYN-004`（P0）は「key に instance 識別子が無く work-id は決定的なので、
discard の承認待ち中に別 session が同じ work-id で create すると manifest も guard key も
一致するため誰も止めず、**新しい実体（未コミットの作業を含む）を削除する**」とした。
レビューはこれを「`FLW-REV-008` が捕まえた commit 誤帰属の worktree 版」と位置づけている。
**失うものは remote branch と違って復元できない。**

instance identity を precondition に含め、apply 直前に CAS 照合する。

| 構成要素 | 取得元 |
|---|---|
| registry entry の `gitdir` 内容 | `common-dir/worktrees/<name>/gitdir` |
| worktree 側 `.git` file が指す entry | worktree 実体 |
| `HEAD` OID | registry entry の `HEAD` |
| **create 時 nonce** | create の intent へ焼いた単回値。registry entry 配下の owner-only file へ保存 |

この4つを `snapshot_digest` へ含め、apply 直前に再計算して一致した場合だけ mutation する。
不一致は **`STALE`** とし、自動再 apply を禁止する（人間の新しい plan を要求する）。

create 時 nonce があるため、**同じ path・同じ work-id で作り直された worktree は
必ず別 instance として識別される**。これが SYN-004 を閉じる決定的な要素である。

### `worktree-dir` の CAS 相当（GP-007）

`FLW-REV-011:SYN-007` は「M1 は local target に『存続中の OS exclusive lock と CAS』を
必須とするが、directory に対する CAS 相当が定義されていない」とした。
`worktree-dir` は Git ref でも index でもないため、expected-OID CAS も native lock も存在しない。

**代替の CAS 述語**を次で定義する。

1. plan 時に **削除対象 manifest** を作る。各 entry は
   `(相対 path, type, dev+ino, size, mtime_ns)` とし、全体の digest を取る。
2. apply 直前に**再計算**し、plan 時 digest と一致した場合だけ削除する。
   不一致は `STALE`（`replan-human`）。
3. 削除は **dirfd 相対**で行い、apply 中の path 再解決による escape を防ぐ。
4. §5 の instance identity と併せて照合する（manifest 一致だけでは SYN-004 を防げないため）。

**capability 縮退**（`FLW-DSN-015` の「提供できない platform は `UNSUPPORTED`」と同じ規律）:

| 必要 capability | 取得不能時 |
|---|---|
| stable file identity（`dev+ino` 相当）の取得 | `worktree.discard` を `UNSUPPORTED` |
| dirfd 相対削除 | 同上 |
| 承認済み root への owner-only 書き込み | `worktree.create` を `UNSUPPORTED` |
| root の case 感度判定（§3） | 判定不能時は `BLOCKED` |

これにより `worktree-dir` の防御水準は `git.delete-remote-branch` **と同等以上**になる。
ただし `SI-FLW-044` により基準側の `git.delete-remote-branch` 自体も
再照会一致から CAS へ厳格化される前提である。

## §6 quarantine 解除と解放経路

対応 GP: **GP-005**

`FLW-REV-011:SYN-005`（P0）は「quarantine 解除の区分表5種はすべて Git object と ref を
前提としており、directory・registry の残留に当てはまる結論が1つも無い。
`worktree-dir` guard が quarantine に落ちると**正規の解除手順が存在しない**」とした。

`FLW-DSN-015` の解除区分表へ worktree 用3区分を追加する。

| 観測結論 | 必須証跡 | 解除可否 |
|---|---|---|
| `worktree-no-effect` | dir / registry entry / local-ref のいずれも不在。instance nonce も不在 | evaluation-reviewer 承認で可 |
| `worktree-residue-retained` | **directory だけ残存**。registry entry と ref は不在。残存 path 一覧を receipt へ記録 | repository-owner ＋ evaluation-reviewer で可。**残存 directory は削除しない** |
| `worktree-registry-stale` | **registry entry だけ残存**。実体 directory は不在で、entry の `gitdir` が指す path が存在しないことを証明できる | evaluation-reviewer 承認で可。**stale entry の除去を正規の残 step として許可**する |
| `worktree-unresolved` | 三者が矛盾（例: registry entry と実体が別 instance を指す） | **不可。quarantine 継続** |

`worktree-registry-stale` を独立区分にするのは、外部要因（人間の手動削除・外部ツール）で
**実体だけが消える**のが最も起きやすい残留形であり、これを `worktree-unresolved` に落とすと
**回復可能な状態が恒久 quarantine に固定される**ためである（GP-005 が求める「正規の解放経路」が
最頻ケースで存在しないことになる）。除去対象は registry entry のみで、
ref と実体には触れない。判定には「`gitdir` が指す path の非存在証明」を必須とし、
単に見えないだけ（mount 未接続・権限不足）と区別できない場合は `worktree-unresolved` とする。

- `worktree-residue-retained` で directory を削除しないのは、未コミット作業を含み得るためである
  （M1 の `orphan-object-no-reachable-effect` で object を削除しないのと同じ判断）。
- 解除 receipt は reviewer、根拠 digest、旧・新 fencing token、結論、時刻を hash-chain へ追記する。
- 解除後の mutation には §4 の単回 capability と新 operation ID を要求する。

### owner process 停止証明の具体（GP-005 後段）

`FLW-DSN-015` は「coordinator は lease 満了だけで guard を再発行しない。owner process の終了、
子 Git process の終了、OS lock 解放、対象 postcondition の read-only reconcile を
coordinator-operator が証明した後だけ新 token を発行する」と定めるが、
worktree の場合の**置き場**が未定義だった。

| 証明対象 | 置き場・取得方法 |
|---|---|
| owner process | intent の `owner_process`（非秘密 opaque id）と、common-dir 配下 owner-only 領域の PID file |
| OS lock | **common-dir 配下**に置く lock file（worktree 実体側には置かない — discard で消えるため） |
| 子 Git process | owner process の子プロセス群の終了確認 |
| postcondition | dir / registry / ref / instance nonce の read-only 再照合 |

## §7 ORPHAN の起因分離

対応 GP: **GP-017**

`FLW-REV-011:SYN-017` は「`ORPHAN` を『防げる』と書いたが guard 外要因の復旧手順が無い」とした。

3者 guard が防げるのは **bitz-flow 起因**の `ORPHAN`（自分の operation の中断による三者のずれ）だけである。
**guard 外要因**（人間の手動 `rm -rf`、外部ツール、OS クラッシュ、別クローンからの操作）は防げない。
断定を bitz-flow 起因に限定し、外部起因には**検出と復旧手順**を用意する。

| 起因 | 防止 | 対応 |
|---|---|---|
| bitz-flow の operation 中断 | **3者 guard ＋ intent で防ぐ** | reconcile で残 step を確定 |
| 外部要因（手動削除・外部ツール・crash） | **防げない** | audit が `ORPHAN` を検出 → §6 の解除区分へ接続 |

外部起因の復旧手順を `worktree.audit` の結果から辿れるようにし、
fault fixture へ「外部からの手動削除」「外部からの registry 改変」を加える
（`M2-FLT-013` / `M2-FLT-014`）。

## §8 M2 recovery matrix

対応 GP: **GP-013**

未登録 tuple、未知 field、code/cause 矛盾は `human-stop` へ fail-closed にする
（`FLW-DSN-015` の規定を継承）。

**「前進再開」の経路**: `FLW-DSN-006` は「途中失敗は `PARTIAL` を返し**再実行で前進再開する**」と
書くが、`FLW-DSN-015` は `PARTIAL` を `reconcile-only` とし残 step 自動 apply を禁止している。
**後者へ統一**し、前進は「reconcile で完了/残 step を確定 → 残 step だけの新 plan →
人間承認（§4 の新 capability）→ **新 operation ID** で apply」とする。

| operation | phase | code・状態 | recovery class | 許可 NEXT | 禁止 |
|---|---|---|---|---|---|
| `worktree.audit` | 照合中 | `INDETERMINATE` | `human-stop` | 空 NEXT ＋ `required_human_input` | 分類の推測 |
| `worktree.create` | 承認 capability 不一致 | `STALE` | `replan-human` | 再承認、新 plan | 旧 capability の再利用 |
| `worktree.create` | registry 公開前 | `STALE` | `replan-human` | audit、新 plan | 実体残置のまま再 create |
| `worktree.create` | registry 公開後・双方向不一致 | `PARTIAL` | `reconcile-only` | 双方向一致の read-only 照合 | 実体の自動再作成 |
| `worktree.create` | case 感度判定不能 | `BLOCKED` | `human-stop` | root の承認・再測定 | case-sensitive への既定倒し |
| `worktree.resume` | instance identity 不一致 | `STALE` | `replan-human` | audit、新 plan | 別 instance の再開 |
| `worktree.finish` | merge 証跡不足 | `BLOCKED` | `human-stop` | 証跡の再照会 | 差分の見かけによる削除 |
| `worktree.finish` | step 境界で中断 | `PARTIAL` | `reconcile-only` | completed / remaining の確定 | 残 step の自動 apply |
| `worktree.discard` | manifest digest 不一致 | `STALE` | `replan-human` | manifest 再生成、新 plan | 旧 manifest での削除 |
| `worktree.discard` | instance identity 不一致 | `STALE` | `replan-human` | audit、新 plan | 作り直された実体の削除 |
| `worktree.discard` | manifest に root 外 path | `BLOCKED` | `human-stop` | manifest 再生成 | apply の続行 |
| `worktree.discard` | 一部 target 削除済み | `PARTIAL` | `reconcile-only` | 残存 target 一覧の確定 | 残 target の自動削除 |
| `worktree.*` | quarantine 既存 | `BLOCKED` | `human-stop` | §6 の解除区分へ | 新 plan / apply |
| `git.delete-remote-branch` | CAS 不成立 | `STALE` | `replan-human` | remote ref 再照会、新 plan | delete 再実行 |
| `git.delete-remote-branch` | 応答喪失 | `INDETERMINATE` | `human-stop` | remote ref 再照会 | 旧 plan での再削除 |
| `git.delete-remote-branch` | ref activity に `T0` 以降の更新あり | `BLOCKED` | `human-stop` | 検出した更新の提示 | 削除の続行 |
| `git.delete-remote-branch` | ref activity に更新なし（capability あり） | `BLOCKED` | `human-stop` | 「観測範囲では更新なし。不在証明ではない」と明示した承認要求 | 一致のみを根拠とする削除 |
| `git.delete-remote-branch` | ref activity capability なし | `BLOCKED` | `human-stop` | ABA 不検出を明示した承認要求 | 一致のみを根拠とする削除 |

NEXT は許可グラフの到達可能性を検査する。`PARTIAL` / `STALE` / `INDETERMINATE` から
人間の新しい裁定なしに mutation node へ到達するグラフは不正とする。特に
**`worktree.finish` の結果 NEXT に `git.delete-remote-branch` の apply node が現れないこと**を
明示的に検査する（`FLW-CON-006` の自動連結禁止の機械化）。

### ABA 検出の3経路（GP-004 の実証結果）

`FLW-REV-012:GP-004` が求めた capability の実在性確認を実施した
（記録: `.spec/reports/investigation-2026-08-12-aba-detection-capability.md`）。

**capability は実在する。** GitHub の `GET /repos/{owner}/{repo}/activity` が
`activity_type`（`push` / `force_push` / `branch_creation` / `branch_deletion` / `pr_merge`）、
`before` / `after` / `ref` / `timestamp` を返し、`ref` と `activity_type` で絞り込める。
`force_push` は第一級の種別であり、実測でも検出できた。

**ただし ABA の「不在」を証明する用途には使えない。** ABA 検出が必要とするのは
「`T0` から `T1` の間に更新が1件も無い」という**否定的な主張**だが、Activity API が
提供できるのは「これらの更新が記録されている」という**肯定的な主張**だけである。
Git Refs API と Activity API は別サブシステムであり、両者の整合性は保証されていない。
攻撃者の force push が Refs へ反映済みで Activity へ未反映なら、
「更新なし」と誤って結論する。**観測遅延の上限は実験で確定できない**
（速いことは示せても、遅くならないことは示せない）。

したがって **capability の有無は承認の要否を変えない。変わるのは証跡の質だけ**である。

| 経路 | 条件 | 結果 |
|---|---|---|
| A | capability あり ＋ activity に `T0` 以降の更新**あり** | **`BLOCKED`**（積極的検出。最も強い証跡） |
| B | capability あり ＋ activity に更新**なし** | 承認要求。**「観測範囲では更新なし。これは不在証明ではない」**と明示 |
| C | capability **なし**（GHES・権限不足・API 不提供） | 承認要求。**「ABA 不検出」**と明示 |

- **どの経路も人間承認を省略しない。** capability があっても自動では削除しない。
- capability 判定不能を「更新なし」へ倒さない（経路 C として扱う）。
- 3経路すべてが到達可能であるため **死に枝は生じない**（GP-004 の趣旨を満たす）。
- capability の検出は `FLW-DSN-014` の capability matrix（`ref activity read`）に従う。
  GHES での提供状況は未確認であり、実行時検出に委ねる。

### step 契約

step 名を閉集合とし、`FLW-DSN-012` の `completed_steps` / `remaining_steps` へ写像する。
**全 step がちょうど1つの mutation target に対応する**（残存 target を一意化するため）。

`worktree.finish`:
`verify-pr-merge` → `verify-target-oid` → `verify-reachability` → `sync-main` →
`remove-registry-entry` → `remove-worktree-dir` → `delete-local-branch` → `report-remote-candidate`

`worktree.discard`:
`freeze-manifest` → `verify-manifest-scope` → `remove-registry-entry` →
`remove-worktree-dir` → `delete-local-branch`

**`remove-registry-entry` を `remove-worktree-dir` より先に置く**。cross-filesystem 時の
durability commit point が「registry entry の atomic 公開時点」であり registry を正とするため、
実体削除を先に行うと「registry が正＝実体を再作成すべき」という誤結論へ収束する。
registry を先に消せば、残った実体は「registry 外の孤立ディレクトリ」として
§6 の `worktree-residue-retained` へ一意に確定できる。

`report-remote-candidate` は **read-only の step** であり remote ref 削除を含まない。

## §9 fault fixture catalog

各 fixture はちょうど1つの実装区分へ割り当てる。未割当・重複割当 0 を完了条件とする。

| ID | 注入点 | 期待結果 | 区分 |
|---|---|---|---|
| `M2-FLT-001` | 3者＋index の逆順 acquire 要求 | canonical 昇順へ正規化、または副作用 0 で `BLOCKED` | M2-1 |
| `M2-FLT-002` | worktree guard を取る operation が index を含めない | 包含規約により自動付加、欠落時はテスト FAIL | M2-1 |
| `M2-FLT-003` | discard 保持中に別 process が `git.stage` | 同一 index key で待機。同時 mutation 最大 1 | M2-1 |
| `M2-FLT-004` | `worktree_id` に literal を渡す | canonical 導出関数以外から生成不能（型・API で拒否） | M2-1 |
| `M2-FLT-005` | registry entry と `.git` の相互参照不一致 | `ORPHAN` として `BLOCKED`、推測補完 0 | M2-1 |
| `M2-FLT-006` | 別 clone・別 mount から同一 worktree 要求 | 同一 guard へ収束 | M2-1 |
| `M2-FLT-007` | path escape 4変種（`..` / symlink / bind mount / hardlink） | 全変種を apply 前に拒否、副作用 0 | M2-1 |
| `M2-FLT-008` | root 自身が symlink / 承認後に差し替え | 解決後 canonical を承認対象とし、差し替えで再承認要求 | M2-1 |
| `M2-FLT-009` | **不在 path の case 差**（祖先も root まで不在） | 祖先遡りで判定、判定不能なら `BLOCKED`。既定の case-sensitive 倒しをしない | M2-1 |
| `M2-FLT-010` | capability の nonce 再利用・別 target 転用・期限切れ | mutation 前に拒否 | M2-2 |
| `M2-FLT-011` | 承認後・guard 取得前に親 directory を symlink 差し替え | `parent_dir_identity` 不一致で `STALE` | M2-2 |
| `M2-FLT-012` | 承認後・apply 前に対象 path を別 process が先行占有 | `nonexistence_digest` 不一致で `STALE` | M2-2 |
| `M2-FLT-013` | **外部からの手動削除**（guard 外要因） | audit が `ORPHAN` 検出 → 解除区分へ接続。防止は主張しない | M2-2 |
| `M2-FLT-014` | 外部からの registry 改変 | 同上 | M2-2 |
| `M2-FLT-015` | 承認 receipt を伴わない worktree write | permissions ＋ フックでブロック | M2-2 |
| `M2-FLT-016` | registry 公開の各点（temp / fsync / rename / dir fsync）で crash | 双方向一致の照合で `DONE` / `STALE` / `INDETERMINATE` へ一意化 | M2-3 |
| `M2-FLT-017` | 完全一致の既存 worktree へ create 要求 | 重複作成せず `resume` へ分岐 | M2-3 |
| `M2-FLT-018` | 部分一致（path 一致・branch / HEAD 不一致） | `BLOCKED` | M2-3 |
| `M2-FLT-019` | 同 branch を使う既存 worktree | `BLOCKED`、`WORKTREE_IN_USE` を提示 | M2-3 |
| `M2-FLT-020` | dirty worktree を audit | `ACTIVE_DIRTY`、status / diff / commit のみ許可 | M2-3 |
| `M2-FLT-021` | branch-only / remote-only の legacy target | `branch_audit_state` を返す（決定表どおり） | M2-3 |
| `M2-FLT-022` | audit 証跡が競合し一意化不能 | `result_code: INDETERMINATE`、分類の推測 0 | M2-3 |
| `M2-FLT-023` | 未知の enum 値を schema へ投入 | 三者照合テストで FAIL、暗黙 default 0 | M2-3 |
| `M2-FLT-024` | finish 各 step 境界で crash（8点） | `PARTIAL` の completed / remaining が一意に確定 | M2-5 |
| `M2-FLT-025` | finish 結果 NEXT へ `git.delete-remote-branch` apply を混入 | NEXT グラフ検査 FAIL | M2-5 |
| `M2-FLT-026` | squash 相当で到達性証跡が不足 | `BLOCKED`、差分の見かけによる削除 0 | M2-5 |
| `M2-FLT-027` | **discard 承認待ち中に同じ work-id で worktree を再作成**（SYN-004） | create 時 nonce 不一致で `STALE`。新 instance を削除しない | M2-5 |
| `M2-FLT-028` | plan 後 apply 前に manifest 内容が変化 | manifest digest 不一致で `STALE` | M2-5 |
| `M2-FLT-029` | discard manifest へ root 外 path・root 外 symlink を混入 | apply せず `BLOCKED` | M2-5 |
| `M2-FLT-030` | discard を部分完了で中断 | `PARTIAL`、残 target の自動削除 0、再実行での自動前進 0 | M2-5 |
| `M2-FLT-031` | **dirty worktree の discard**（SYN-019） | 退避要求を提示し、退避なしの apply を `BLOCKED` | M2-5 |
| `M2-FLT-032` | discard 対象に submodule / ignored file / symlink | manifest へ計上、列挙 target 外の変更 0 | M2-5 |
| `M2-FLT-033` | stable file identity / dirfd 相対削除が取得不能 | `worktree.discard` を `UNSUPPORTED` | M2-5 |
| `M2-FLT-034` | worktree guard を quarantine へ落とす | §6 の3区分へ一意に確定。正規の解除経路が存在する | M2-5 |
| `M2-FLT-035` | lease 満了だけで guard 再発行を要求 | owner / 子 process / OS lock 停止証明までは再発行拒否 | M2-5 |
| `M2-FLT-036` | 未登録 recovery tuple（未知 cause / code 矛盾） | 空 NEXT ＋ `human-stop` | M2-5 |
| `M2-FLT-037` | plan 後 apply 前に remote ref が別 SHA へ進行 | CAS 不成立で削除 0 | M2-6 |
| `M2-FLT-038` | force push で同一 SHA へ復帰（ABA）＋ activity に更新あり | **経路A**: `BLOCKED`。検出した更新を提示 | M2-6 |
| `M2-FLT-048` | 同上だが activity が空（capability あり） | **経路B**: 承認要求。「不在証明ではない」を明示。自動削除0 | M2-6 |
| `M2-FLT-049` | ref activity capability が取得不能（権限不足・API 不提供） | **経路C**: 承認要求。「ABA 不検出」を明示。**判定不能を「更新なし」へ倒さない** | M2-6 |
| `M2-FLT-039` | 条件なし削除の要求 / CAS 非検証 protocol | 前者を拒否、後者を `UNSUPPORTED` | M2-6 |
| `M2-FLT-040` | `REMOTE_ADVANCED` の target へ delete plan 要求 | plan 生成自体を `BLOCKED` | M2-6 |
| `M2-FLT-041` | default branch から到達不能な ref の削除 | `BLOCKED` | M2-6 |
| `M2-FLT-042` | M1 active manifest を M2 Gate 根拠として提示 | compatibility key 不一致または TTL 失効で `blocked` | M2-6 |
| `M2-FLT-043` | qualification 未 PASS で confirmation 母数を開始 | confirmation 未起動 | M2-6 |
| `M2-FLT-044` | remote-write operation の confirmation を M2 で要求 | `UNSUPPORTED`（M3 へ送った残債であることを提示） | M2-6 |
| `M2-FLT-045` | worktree 未展開・未 push・PR 不在の local branch が存在 | in-flight 列挙に現れる（**事故で見落とした条件そのもの**） | M2-4 |
| `M2-FLT-046` | これから触る path と重なる in-flight branch が存在 | 重なり付きで返る。branch 名・work ID が異なっても検出する | M2-4 |
| `M2-FLT-047` | reconnaissance を省いて書込み WorkUnit を開始 | entry protocol で停止。着手させない | M2-4 |

## §10 P2 の処理

| finding | 対応 |
|---|---|
| `SYN-019` dirty worktree の discard に退避要求が無い | `freeze-manifest` が dirty / untracked を検出したら、**退避（patch 出力または stash 相当）の完了を precondition** にする。退避なしの apply を `BLOCKED`（`M2-FLT-031`） |
| `SYN-020` guard 記録の置き場と create 時の OS lock 対象が未定義 | §6 後段のとおり **common-dir 配下**の owner-only 領域に統一。create 時は対象がまだ無いため、**親（承認済み root）に対して OS lock** を取る |
| `SYN-021` canonical 化に root 包含判定が無い | §3 の canonicalize に **承認済み root 配下であることの包含判定**を組み込み、判定を通らない path は guard 導出以前に `BLOCKED`。namespace 表の積み残しは §2 で解消 |

## §11 実装境界

| 区分 | 関心事 | session 上限 | 完了条件 |
|---|---|---|---|
| M2-1 | guard core（閉集合拡張・binding・包含規約・canonical 化・case 感度） | 4 | `M2-FLT-001`〜`009` PASS。worktree operation 実装へ進まない |
| M2-2 | 承認 capability ＋ 機械強制層 ＋ M2 qualification | 3 | `M2-FLT-010`〜`015` PASS、qualification PASS（**blocking**）。未達時は M2-3 以降を停止 |
| M2-3 | create / resume / audit ＋ enum 三者照合 | 3 | `M2-FLT-016`〜`023` PASS |
| M2-4 | 着手前 reconnaissance ＋ entry protocol | 3 | `M2-FLT-045`〜`047` PASS（`SI-FLW-046`） |
| M2-5 | finish / discard ＋ quarantine 解除 | 4 | `M2-FLT-024`〜`036` PASS |
| M2-6 | delete-remote-branch ＋ confirmation | 3 | `M2-FLT-037`〜`044`、`048`、`049` PASS、M2 出口 |

- 依存は `M2-1 → M2-2 → M2-3 → M2-4 → M2-5 → M2-6` の直列。
  各区分は直前を main へ land してから分岐する。
- **M2-1 が通らなければ以降へ進まない**（M1 の `M1-1` と同じ blocking core）。
- **M2-2 の qualification は blocking**（`SI-FLW-037` が M1 で確立した構造の適用）。
- **M2-4 を M2-3 の直後に置く**のは、reconnaissance が audit の branch 列挙に依存するためである。
  `SI-FLW-046` の accept（M2 着手前）を受けた区分であり、
  ここを通せば **v2 自身の開発が同じ事故を繰り返さなくなる**（早い位置に置く理由）。
- 合計 **6 PR / 20 session**（4 + 3 + 3 + 3 + 4 + 3）。内訳は次のとおりで
  `FLW-DSN-014` の「M2出口条件・budget・M3入口条件」節と一致する。

  | 内訳 | PR | session |
  |---|---:|---:|
  | M0 実績による再校正 | 4 | 14 |
  | M1-6 confirmation 区分の移送（`SI-FLW-045`） | +1 | +3 |
  | `SI-FLW-046` の scope 追加（M2-4） | +1 | +3 |
  | **合計** | **6** | **20** |

  移送分は**区分の付け替えであって余裕の増加ではない**。
  scope 追加分は 2026-08-12 に人間へ再提示して確定した。
- fixture 件数の偏り（M2-5 が 13 件で最多）に合わせて M2-5 へ 4 session を配った。
  M2-5 は finish・discard・quarantine 解除を同時に扱うため最も超過しやすい区分である。
- **`SI-FLW-046` の増分見積りの根拠**: 実装自体は read-only で既存 Git read adapter に乗るため安い。
  リスクは entry protocol の変更にあり、ここは M0 で最も eval 反復を要した領域である。
  +3 session はその反復を見込んだ値で、実装費ではなく検証費が主である。
- いずれかの区分が上限を超える見積りになった時点で、総枠内であっても着手前に人間へ再提示する。

## §12 M2 出口条件

`FLW-DSN-014` の M2 行を次へ改訂する（`SI-FLW-045`）。

- repo identity 衝突 0
- repo 外 worktree root の承認（**capability 化されたもの**）
- `M2-FLT-001`〜`049` 全件 PASS
- **enum 三者照合テストが green**（設計 ⊆ schema ⊆ 実装の双方向）
- **機械強制層が有効**（permissions ＋ フックで receipt なし write をブロック）
- **着手前 reconnaissance が entry protocol で必須化**されている（`FLW-FR-007` 1.1。`SI-FLW-046`）
- **local-write class の被測定物 confirmation が 3 platform で PASS** し active manifest 発行済み

**縮退規則3の解除条件**（現行は解除条件を持たない）: 上記を満たした時点で
M1 Git write（local-write class）と M2 worktree を同時に公開できる。
remote-write は M3 の confirmation まで `UNSUPPORTED` を維持する。

## §13 代替案と却下理由

- **guard を承認の前へ倒す**: §4 のとおり、承認待ち中に当該 worktree の全 write を
  停止させるため不採用。TOCTOU は capability で閉じる。
- **`registered-active` を12値目として残す**: `FLW-DSN-012` の「状態は外部事実から毎回再構成する」
  原則に反する（由来情報は再構成できない）ため不採用。
- **discard で実体を先に削除する**: cross-filesystem 時の commit point 定義と逆転し、
  crash 後の reconcile が「実体を再作成すべき」という誤結論へ収束するため不採用。
- **多重語一覧を手で維持する**: 必ず腐る（現に 4/10 漏れた）ため不採用。schema から機械導出する。
- **enum 値追加を「key 集合は加算のみ」で正当化する**: object の key の規定であり
  closed enum には適用できないため不採用。「未公開だから影響が無い」へ根拠を置き換える。
- **`ORPHAN` を3者 guard で防げると書く**: 外部起因は防げないため不採用。
  bitz-flow 起因に限定し、外部起因は検出と復旧で扱う。
- **worktree 実体側に lock / receipt を置く**: discard で消えるため不採用。common-dir 配下に置く。

## §14 影響範囲・ロールバック

本書は M2 実装前の設計であり、現行の M0 read-only dispatcher を変更しない。
M1 operation の guard 導出規則・recovery matrix・qualification プロトコルは変更せず追加のみである。
ただし次の3点は M1 で凍結した契約・要件に触れる。

| 対象 | 変更 | 根拠 |
|---|---|---|
| `guard_identity_kind` | 5種 → 7種（schema ＋ `guard.py`） | `SI-FLW-041`（accepted） |
| `FLW-NFR-007` | repo 境界外 parent の無条件 `BLOCKED` を3条件付き許可へ | `SI-FLW-043`（**accepted**。要件 1.3 で反映済み） |
| `FLW-CON-006` | 削除を再照会一致から expected-OID CAS へ厳格化 | `SI-FLW-044`（**accepted**。要件 1.3 で反映済み） |

M2 が未完了または fixture 未達なら、`worktree.*` と `git.delete-remote-branch` を
`UNSUPPORTED` のまま維持し、縮退規則3により M1 Git write も公開しない。
**path 安全検査・承認 capability・機械強制層を無効化して worktree write だけを公開する縮退は認めない。**

ロールバック時も intent、ledger、manifest、digest、解除 receipt を監査証跡として保持する。
`worktree-residue-retained` で保全した directory は**ロールバックでも削除しない**。

## §15 FLW-REV-011 の Gate 前提条件との対応

**GP の原文を逐語で併記する。** 節番号だけを指す対応表は、
「その節が GP を満たしているか」を読み手に確認させない。実際に本書 v1.0 は
GP-004 に対し「§5」とだけ書いて対応済みとし、**原文が求める `precondition` ではなく
`guard key` へ instance identity を入れる**という取り違えを機械検査で素通りさせた
（`FLW-REV-012:SYN-001`。P0）。原文と応答を1行に並べれば、この不一致は目で見える。

原文は `FLW-REV-011.json` の `gate_preconditions[].statement` から**逐語転記**する。
要約・言い換えをしない（言い換えた時点で取り違えが隠れるため）。

| GP | 原文（`FLW-REV-011` より逐語） | 応答 |
|---|---|---|
| GP-001 | work_unit_state と worktree_state の値を FLW-DSN-012 / FLW-DSN-006 と一致させ、三者照合を機械化してから M2 の契約を凍結する | §2 — 本書の表を唯一の正とし、`work_unit_state` を12値へ回復。設計 ⊆ schema ⊆ 実装の双方向照合テストを規定 |
| GP-002 | repo 外承認を capability 化し、guard key・親 directory identity・非存在証明・期限・単回 nonce を署名対象に含めて apply 直前に再照合する | §4 — 署名対象表に全5要素を列挙。再照合点は guard 取得直後と各副作用直前の2箇所 |
| GP-003 | worktree の guard を取る operation は、その worktree に属する index target を同じ acquire に含める包含規約を定める | §3 — 包含規約。acquire 入口で index target を自動付加する正規化により記述漏れを構造的に排除 |
| GP-004 | worktree の instance identity（gitdir 内容・HEAD OID・create 時 nonce）を precondition に入れ、apply 直前に CAS 照合する | §5 — **precondition（`snapshot_digest`）**へ4要素を含め apply 直前に CAS 照合。**guard key へは入れない**（v1.1 で是正） |
| GP-005 | worktree guard の quarantine 解除区分を定義し、正規の解放経路を用意する | §6 — worktree 用4区分（`no-effect` / `residue-retained` / `registry-stale` / `unresolved`）と owner process 停止証明の置き場 |
| GP-006 | worktree.finish と resume を3者 guard の対象へ加える | operation catalog — `create` / `resume` / `finish` / `discard` の4つすべてを3者＋index の対象とする |
| GP-007 | worktree-dir の CAS 相当（manifest digest の apply 直前再計算）と capability 縮退を定義する | §5 — manifest を `(相対 path, type, dev+ino, size, mtime_ns)` の digest とし apply 直前に再計算。capability 縮退表つき |
| GP-008 | worktree-dir と worktree-registry の binding 検証と worktree_id の canonical 導出を定める | §3 — registry を authoritative とする相互参照一致を precondition 化。`worktree_id` は canonical 導出関数のみで生成し literal を渡せなくする |
| GP-009 | case 感度の判定を存在する最も近い祖先まで遡らせ、判定不能なら BLOCKED にする | §3 — 祖先遡り＋承認時の root 測定値の再利用。判定不能は `BLOCKED`（case-sensitive への既定倒しをしない） |
| GP-010 | settings.json の permissions へ worktree root を加え、承認 receipt を伴わない worktree write を機械的に止める | §4 — permissions ＋ PreToolUse フック。receipt は common-dir 配下の owner-only 領域へ追記 |
| GP-011 | destructive worktree operation の承認へ M1 の capability envelope を再利用し単回化する | §4 — M1 の Ed25519 envelope を再利用。nonce は target guard 内で linearizable CAS |
| GP-012 | 設計の閉集合・schema enum・guard.py 定数の三者照合テストを追加する | §2 — **双方向**照合（片方向が沈黙した原因）。対象は namespace 表の全 namespace |
| GP-013 | M2-FLT-* を採番し、worktree の fault fixture と recovery matrix 行を定義する | §8（recovery matrix）／ §9（`M2-FLT-001`〜`049`。各 fixture をちょうど1区分へ割当） |
| GP-014 | 複数 namespace に現れる語の一覧を schema から機械導出して文書と照合する | §2 — 手で維持する表を置かず schema から導出。本書の表は導出結果の期待値 |
| GP-015 | closed enum への値追加の互換性条文を output-contract.md へ作るか、互換性を根拠にしない記述へ改める | §2 — **後者を採用**。「key 集合は加算のみ」は object の key の規定であり closed enum に適用できないため、根拠を「未公開だから影響が無い」へ置換 |
| GP-016 | 表記規則の判定基準（field 名ではなく値の性質）と反例を明記し、namespace 表へ性質列を足す | §2 — 判定基準を「値の性質」と明記し性質列を追加。反例（`trial_kind` の `Q-NORMAL`）を隠さず記載 |
| GP-017 | ORPHAN の断定を bitz-flow 起因に限定し、外部起因の復旧手順と fault 項目を追加する | §7 — 3者 guard が防げるのは bitz-flow 起因のみと明記。外部起因は検出＋復旧（`M2-FLT-013` / `014`） |
| GP-018 | FLW-DSN-006 / FLW-DSN-012 の状態語を表記規則へ揃え、version と updated を上げる | §2 ＋ 実ファイル更新（`FLW-DSN-006` 1.1 / `FLW-DSN-012` 1.2 / `FLW-DSN-015` 1.1 を同じ変更セットで） |

この逐語併記は `SI-SDD-042`（レビュー指摘の受領検証）が提案する機械照合の**手動先行版**である。
同 issue が accept されて照合が機械化されれば、本表が検査対象になる。

## Revision History

- 1.4 (2026-08-12) `FLW-REV-012:GP-004`（ABA 検出 capability の実在性）を実証し反映。
  **capability は実在するが ABA の不在証明には使えない**（Activity API と Git Refs API は
  別サブシステムで整合性が保証されず、観測遅延の上限を実験で確定できない）。
  2分岐（capability あり→停止 / なし→承認）を**3経路**へ再構成し、
  **どの経路も人間承認を省略しない**ことを明示した。fixture へ `M2-FLT-048` / `049` を追加（計49件）。
  記録は `.spec/reports/investigation-2026-08-12-aba-detection-capability.md`。
- 1.3 (2026-08-12) `SI-FLW-043`〜`046` の裁定（accept）と budget 再校正を反映。
  実装境界を5区分→**6区分**へ再構成し、`SI-FLW-046` の着手前 reconnaissance を **M2-4**（audit の直後）
  として独立させた。fixture へ `M2-FLT-045`〜`047` を追加（計47件）。
  budget を **6 PR / 20 session** へ更新（`FLW-DSN-014` 1.15 と一致）。
  §14 の要件改訂2件を「要裁定」から accepted・反映済みへ更新。
- 1.2 (2026-08-12) §15 の GP 対応表を「節番号のみ」から**原文の逐語併記**へ変更。
  v1.0 が GP-004 に「§5」とだけ書いて取り違えを素通りさせた再発を防ぐ。
  `SI-SDD-042`（レビュー指摘の受領検証）が提案する機械照合の手動先行版にあたる。
- 1.1 (2026-08-12) 起案者による批判的検証（`FLW-REV-012`）の指摘を反映。
  - **P0**: `worktree-dir` の guard key から instance identity を除いた。key に instance を
    含めると「旧 instance の discard」と「新 instance の create」が別 key になり
    **互いに排他しなくなる**（SYN-004 を防ぐどころか直列化そのものを失う）。
    key は path に対して安定とし、instance の同一性は precondition で照合する。
  - **P1**: quarantine 解除区分へ `worktree-registry-stale` を追加。外部要因で
    実体だけが消える最頻ケースが `worktree-unresolved` に落ちて**恒久 quarantine に
    固定される**穴を塞いだ。
  - **P2**: session 合計を 18 → **17** へ是正（`SI-FLW-045` の移送分と一致させた）。
    fixture 件数の偏りに合わせて M2-4 を 4 session へ、M2-2 / M2-3 を 3 session へ再配分。
  - **P2**: capability 署名 field の適用範囲を明示（`nonexistence_digest` は `create` 専用、
    既存 target 側は `instance_identity_digest`）。
  - **P2**: namespace 表へ `trial_kind` と `cause` を追加し、三者照合の対象を
    「本表の全 namespace」と明示。
- 1.0 (2026-08-12) `FLW-REV-011`（FAIL、P0 5系統 / GP 18件）への回答として起票。
