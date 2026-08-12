---
id: FLW-REV-013
title: "bitz-flow V2 M2 worktree安全性設計の独立再レビュー"
status: pending
version: 1.0
updated: 2026-08-13
owner: br7.hide
decision: FAIL
---

# 設計レビュー統合レポート — FLW-REV-013

- **review_id**: FLW-REV-013
- **対象**: `FLW-DSN-016`（M2 worktree安全性 詳細設計 v1.4）を主対象とし、`FLW-DSN-014` / `015` / `012` / `006`、`ROADMAP.md`、`FLW-NFR-007` / `FLW-CON-006` / `FLW-FR-007`、`SI-FLW-043`〜`046`、裁定記録および ABA 検出調査記録
- **判定**: **FAIL**
- **集計スコア**: 2.31（PASS ≥ 3.5 / CONDITIONAL ≥ 2.5）
- **位置づけ**: `FLW-REV-011`（FAIL 2.47）が立てた18件の gate precondition へ回答した設計に対する再レビュー。5観点すべてを独立エージェントが担当した

## 観点別スコア

| 観点 | スコア | 重み（正規化後） | 主要所見 |
|---|---|---|---|
| consistency | 2.10 | 0.15 | §15 の GP 対応表が実ファイルの状態と乖離し、出口条件の「正」が3文書で循環参照している |
| data-integrity | 2.30 | 0.25 | §6 の解除区分と §8 の step 順が相互に矛盾し、discard の中断状態がすべて恒久 quarantine へ落ちる |
| operations | 2.30 | 0.20 | 機械強制層が Claude Code 専用のため3プラットフォーム出口条件が原理的に充足不能 |
| risk | 2.30 | 0.25 | finish / discard が destructive から local-write へ降格され、tip OID 保全なしで M2 出口の公開集合に入る |
| business | 2.60 | 0.15 | M2 が M3 へ送った残債に budget 増分が無く、SI-FLW-045 が是正した断絶が下流で再発している |

findings: 統合前 74 件 → 重複排除後 67 件（P0: 14 / P1: 9 / P2: 24 / P3: 20）

全5観点が 2.1〜2.6 に収まり、PASS 条件4項目（集計 ≥3.5・critical 0・major ≤3・全観点 ≥3.0）はいずれも不成立。CONDITIONAL_PASS の下限 2.5 にも届かない。**本レビューが上書きする `FLW-REV-011`（2.47）を下回る。**

### 自己レビューとの乖離

直前の `FLW-REV-012` は同一対象に対する自己レビューで 3.62（CONDITIONAL_PASS）だった。独立レビューの 2.31 との差は **+1.31** である。観点別では business が自己 3.8 に対し独立 2.6。自己レビューを Design Gate の判定材料に用いない根拠として本数値を記録する。

## P0 — Blocker

- **SYN-001** [BIZ-001] M2 が M3 へ送った残債に budget が付いておらず、SI-FLW-045 が是正した断絶が再発している
  - 問題: SI-FLW-045 は「M1-6 が送った残債の受け側が存在しない」ことを問題とし、その是正として M2 へ +1 PR / +3 session を移送させた（FLW-DSN-016 §11 の内訳表、FLW-DSN-014.md:664-669）。ところが同じ裁定（案A）で M2 が M3 へ送った remote-write class の confirmation（git.publish-branch / git.delete-
  - 是正: M2 出口条件を凍結する前に、(a) M3 の budget を remote-write confirmation と coordinator 証明手段の増分見積り付きで再校正し FLW-DSN-014 の M3 行へ反映する、(b) それが M2 着手前に確定できないなら、FLW-DSN-016 §12 の M2 出口条件へ「M3 budget の再校正が人間へ提示済みであること」を明示的な出口項目として加える。いずれも行わない場合
  - tracked_by: `FLW-REV-013:GP-007`
- **SYN-002** [BIZ-002] v2 計画全体が 1.8 倍に膨張しているのに、上位計画（bitz-sdd V4）への影響評価が本書にも裁定記録にも無い
  - 問題: FLW-DSN-014.md:631-637 の milestone 表では、旧 budget 合計 M1〜M5 = 13 PR / 52 session に対し、新 budget 合計は 28 PR / 94 session（PR 2.15 倍・session 1.81 倍）である。M2 単体でも 2 PR / 8 session → 6 PR / 20 session（session 2.5 倍）。一方 plugins/bitz-f
  - 是正: FLW-DSN-016 §14 へ「上位計画への影響」小節を追加し、(1) M2 の +6 session が bitz-flow V2 完了時期に与える遅延、(2) その遅延が bitz-sdd V4 Charter 開始（フェーズ4→5）へ与える影響、(3) 累積膨張（52→94 session）に対する program レベルの継続 / scope 縮小 / No-Go の再確認要否、を明記する。ROADMAP『予算と縮退の運用』
  - tracked_by: `FLW-REV-013:GP-007`
- **SYN-003** [DIN-001, OPS-002] §8 が選んだ step 順序が生む中断状態が §6 のどの解除区分にも落ちず、順序選択の根拠が §6 表自身によって反証されている
  - 問題: §6 の解除区分は directory / registry entry / local-ref の三者を存在軸として分類する（`worktree-no-effect` は三者とも不在、`worktree-residue-retained` は『directory だけ残存。registry entry と ref は不在』、`worktree-registry-stale` は『registry entry だけ残存』、`worktr
  - 是正: §6 の区分表を三者（dir / registry / local-ref）の存在パターン 8 通りをすべて覆う決定表へ書き換える。最低限、`worktree-ref-only-residue`（ref だけ残存 — delete-local-branch 未実行）と `worktree-dir-and-ref-residue`（registry のみ除去済み — §8 が選んだ順序の第一中断点）を独立区分として新設し、それぞれの必須証
  - tracked_by: `FLW-REV-013:GP-001`
- **SYN-004** [DIN-002] worktree_state が直交する 3 軸を単一 enum へ潰しており、dirty × MERGED_EXACT の同時成立で finish が未コミット作業ごと削除しうる
  - 問題: §2 の `worktree_state` は `ABSENT, ACTIVE_CLEAN, ACTIVE_DIRTY, PR_OPEN, MERGED_EXACT, REMOTE_ADVANCED, WORKTREE_MISMATCH, ORPHAN, FAILED_RETAINED` の 9 値を単一 field の閉集合とする。しかし判定条件（FLW-DSN-006「audit分類」表）を見ると、これらは**独立した 3 軸**で
  - 是正: (1) `worktree_state` を直交軸へ分解する（`worktree_content_state: CLEAN/DIRTY` と `worktree_lifecycle_state: ABSENT/ACTIVE/PR_OPEN/MERGED_EXACT/REMOTE_ADVANCED/MISMATCH/ORPHAN` 等）か、単一 enum を維持するなら §2 へ**危険度の全順序**を明示し、同時成立時にどの値へ倒すかを
  - tracked_by: `FLW-REV-013:GP-004`
- **SYN-005** [DIN-003, RSK-001] worktree.finish の sync-main step が guard 集合に含まれない target（main の branch ref・index）を変更し、GP-003 が塞いだ穴と同型の穴が残っている
  - 問題: operation catalog（§1 の表）は `worktree.finish` の canonical mutation target を『`worktree-dir` ＋ `worktree-registry` ＋ `local-ref` ＋ `index`』とする。ここでの `index` は §3 の包含規約が定める『**W に属する** index target』（`canonical_index_target(comm
  - 是正: (1) `sync-main` を `worktree.finish` の step から外し、独立した `git.sync` operation として前段に置く（`FLW-CON-006` の自動連結禁止と同じ扱い。finish の precondition に『main が最新であること』を置き、満たさなければ `BLOCKED`）。これが最も本書の設計原則に一致する。(2) step として残すなら、operation cata
  - tracked_by: `FLW-REV-013:GP-002`
- **SYN-006** [DIN-004] worktree-no-effect が「discard 成功」と観測上区別できず、M1 の confirmed-done に相当する区分が worktree 版に存在しない
  - 問題: M1 の quarantine 解除区分（`FLW-DSN-015`）は `confirmed-done`（intent・CAS receipt・現在 ref・object・fencing 一致）と `no-effect`（snapshot 不変、対象全体の副作用不存在）を**別区分として証跡で識別**していた。両者を分ける必要があるのは、前者なら operation は完了しており再実行してはならず、後者なら未実行なので新 plan 
  - 是正: (1) `worktree-confirmed-done` を独立区分として新設し、必須証跡を『intent の `expected_effect_digest` と一致する不在化 receipt、削除対象 manifest の全 entry の不在、fencing token 一致、hash-chain 上の該当 operation ID の完了 entry』とする。receipt は §4 のとおり common-dir 配下（wo
  - tracked_by: `FLW-REV-013:GP-001`
- **SYN-007** [OPS-001, RSK-010] 機械強制層が Claude Code 専用機構でしか定義されておらず、3 platform 出口条件と縮退規則3 が同時に成立しない
  - 問題: §12 の M2 出口条件は「機械強制層が有効（permissions ＋ フックで receipt なし write をブロック）」と「local-write class の被測定物 confirmation が 3 platform で PASS」を**同時に**要求する（FLW-DSN-016.md:653,655）。しかし §4 の機械強制層は `.claude/settings.json` の permissions と Pr
  - 是正: (1) §4 へ platform 別の強制手段表を追加し、Claude Code（permissions ＋ PreToolUse）、Antigravity（hooks.json）、Codex CLI（提供可否を実測）それぞれの実現方式と、提供できない platform での扱い（worktree write を当該 platform で `UNSUPPORTED` とするのか、出口条件から除外するのか）を明記する。(2) 強制層をプ
  - tracked_by: `FLW-REV-013:GP-005`
- **SYN-008** [OPS-003] M2-4 の entry protocol 変更が M0 の公開挙動と compatibility key を変え、M2-2 の blocking qualification を M2-6 の confirmation 前に無効化する
  - 問題: §14 は「本書は M2 実装前の設計であり、現行の M0 read-only dispatcher を変更しない」と述べる（FLW-DSN-016.md:678）。しかし §11 の M2-4 は「着手前 reconnaissance ＋ **entry protocol**」であり（FLW-DSN-016.md:615）、§12 も「着手前 reconnaissance が **entry protocol で必須化**されている」
  - 是正: (1) §14 の「M0 dispatcher を変更しない」を撤回し、entry protocol 改訂が M0 の公開挙動変更であること、縮退規則1 との関係（M0 出口判定に用いた active manifest の再測定要否）を明記する。(2) 区分順を `M2-4（entry protocol 改訂）→ M2-2（qualification）` へ入れ替えるか、M2-6 に qualification 再実行を明示的な ste
  - tracked_by: `FLW-REV-013:GP-005`
- **SYN-009** [RSK-002] `worktree.finish` / `discard` の class が `destructive` から `local-write` へ無断降格され、M2 出口で公開される operation 集合が実質的に変わっている
  - 問題: `FLW-DSN-012` の公開 action catalog（FLW-DSN-012.md:54-55）は `worktree.finish` と `worktree.discard` を **`destructive`** class・`retry: manual-only`（discard）と定め、`git.delete-remote-branch` も `destructive`（FLW-DSN-012.md:51）としている
  - 是正: (1) 意図的な再分類なら、§14 の表へ4件目として『`worktree.finish` / `discard` / `git.delete-remote-branch` の class 変更』を追加し、`FLW-DSN-012` を同じ変更セットで更新したうえで、**縮退規則3 の解除条件と confirmation 分割の文言を class 名ではなく operation の明示列挙へ改める**（class を鍵にしたまま cla
  - tracked_by: `FLW-REV-013:GP-003`
- **SYN-010** [RSK-003] discard / finish が local branch を削除するのに、削除する tip OID の保全規定が無く、未 push commit が gc で恒久喪失しうる
  - 問題: `worktree.discard` の step は `freeze-manifest → verify-manifest-scope → remove-registry-entry → remove-worktree-dir → **delete-local-branch**`（FLW-DSN-016.md:532-534）であり、finish も `delete-local-branch` を持つ（同:528-530）。本書は未コ
  - 是正: (1) `delete-local-branch` の precondition に『削除対象 tip が (a) default から到達可能、または (b) remote へ published 済み、または (c) 保全 ref（例 `refs/bitz-flow/retained/<work-id>-<nonce>`）へ複製済み、のいずれか』を課し、(c) を discard の既定経路とする。保全 ref があれば objec
  - tracked_by: `FLW-REV-013:GP-003`
- **SYN-011** [RSK-004] `worktree-dir` の CAS 相当が stat メタデータのみで content digest を欠き、racily-clean な編集を原理的に検出できない
  - 問題: §5 の『代替の CAS 述語』は削除対象 manifest の各 entry を `(相対 path, type, dev+ino, size, mtime_ns)` とし、その全体 digest を apply 直前に再計算する（FLW-DSN-016.md:369-373）。ここには **内容の digest が無い**。したがって『size を変えず、同一の mtime 値のまま行われた変更』は検出できない。これは理論上の話では
  - 是正: (1) manifest entry へ **regular file の content digest** を加える（大規模 worktree の費用が問題なら、tracked file は Git の blob OID を用い、untracked / ignored のみ実 digest を取る二段構えにする）。(2) dirty 判定を『Git status ＋ index の再検査』ではなく『HEAD tree との conte
  - tracked_by: `FLW-REV-013:GP-002`
- **SYN-012** [RVC-001, BIZ-003] M2 出口条件の fixture 範囲が 049 と 044 で3文書食い違い、出口ゲートが機械判定できない
  - 問題: FLW-DSN-016 §12 は出口条件を「`M2-FLT-001`〜`049` 全件 PASS」とし、§9 の catalog も実測で 001〜049 の 49 件（M2-1:9 / M2-2:6 / M2-3:8 / M2-4:3 / M2-5:13 / M2-6:10 = 49、未割当0・重複0）を採番している。一方 plugins/bitz-flow/.spec/design/FLW-DSN-014.md:649 と plu
  - 是正: FLW-DSN-014.md:649 と ROADMAP.md:158 を同一変更セットで `M2-FLT-001`〜`049` へ更新する。恒久策として、可変の上限番号を3文書へ複写する構造をやめ、要約側は「`FLW-DSN-016` §9 の catalog 全件」と参照で書き、件数の正を §9 に一本化する（本書が §2 の enum に対して採った『唯一の正を1箇所に置く』方針と同型の扱いにする）。
  - tracked_by: `FLW-REV-013:GP-006`
- **SYN-013** [RVC-002] §15 の GP-018 応答が「実ファイル更新済み」と主張するが、FLW-DSN-006 / FLW-DSN-012 の状態語は未変換で version だけ上がっている
  - 問題: GP-018 の原文は「FLW-DSN-006 / FLW-DSN-012 の状態語を表記規則へ揃え、version と updated を上げる」。§15 の応答は「§2 ＋ 実ファイル更新（`FLW-DSN-006` 1.1 / `FLW-DSN-012` 1.2 / `FLW-DSN-015` 1.1 を同じ変更セットで）」であり、対応済みと読める。実測では version は確かに上がっている（FLW-DSN-006 = 1.1
  - 是正: (1) FLW-DSN-006 の audit 分類表と FLW-DSN-012 の写像表の状態語を大文字スネークへ変換し、両表へ「enum 値の正は FLW-DSN-016 §2」の委譲注記を付ける（decision-2026-08-12-write-state-notation.md が write_state に対して行ったのと同じ処置）。(2) FLW-DSN-006 の audit 分類表へ `ABSENT` を含めるか、含め
  - tracked_by: `FLW-REV-013:GP-006`
- **SYN-014** [RVC-003] FLW-DSN-006 の「再実行で前進再開する」が残存し、§8 の「自動前進 0」と正面から矛盾している
  - 問題: FLW-DSN-016 §8 は「『前進再開』の経路」として、「`FLW-DSN-006` は『途中失敗は `PARTIAL` を返し再実行で前進再開する』と書くが、`FLW-DSN-015` は `PARTIAL` を `reconcile-only` とし残 step 自動 apply を禁止している。**後者へ統一**し…」と明記し、§9 の `M2-FLT-030` は「`PARTIAL`、残 target の自動削除 0、**
  - 是正: FLW-DSN-006 の failure / discard 節を「途中失敗は `PARTIAL` と残存要素を返し、reconcile で completed / remaining を確定させる。残 step の自動 apply と再実行による自動前進は行わない（正は FLW-DSN-015 / FLW-DSN-016 §8）」へ改める。finish 手順も §8 の8 step 契約へ差し替えるか、「step 契約の正は FLW
  - tracked_by: `FLW-REV-013:GP-006`

## P1 — Must Fix

- **SYN-015** [BIZ-007, OPS-004] 新設した reconnaissance 結果の出力量に上限規定が無く、North Star（token / byte 効率）と Must 要件に反する
  - 問題: FLW-FR-007 1.1 の新受入基準は『repo 全体の in-flight branch を列挙し、各 branch が default branch との差分で触れている path 集合と、これから触る path との重なりを返すこと』を求める。これは branch 数 × 変更 path 数で膨らむ出力であり、v2 の North Star（.spec/discovery/success-metrics.md の Token
  - 是正: §9 へ『大量 in-flight branch（例: 50 branch × 数百 path）での reconnaissance 出力』の fixture を追加し、期待結果を「compact / json とも上限内に収まり、省略が可視化される」と定義する。併せて §12 の M2 出口条件へ token-byte benchmark の再測定（reconnaissance 追加後も NFR-008 の閾値を満たすこと）を加える。
  - tracked_by: `FLW-REV-013:GP-008`
- **SYN-016** [DIN-009, RVC-006] 要件層（FLW-FR-007）が返す値は小文字のままで設計 §2 と食い違い、三者照合の対象が要件を含まないため恒久的に沈黙する
  - 問題: §2 は `branch_audit_state` を `ACTIVE, MERGED_EXACT, REMOTE_ADVANCED, WORKTREE_IN_USE, ORPHAN` の大文字スネークで定義し、『`FLW-FR-007` の受入基準はこの一本化に合わせて改訂する』と書く。実測すると `FLW-FR-007` は 1.1（2026-08-12）へ改訂済みだが、改訂されたのは `indeterminate` の削除だけで、
  - 是正: (1) `FLW-FR-007` の受入基準の値を `ACTIVE` / `MERGED_EXACT` / `REMOTE_ADVANCED` / `WORKTREE_IN_USE` / `ORPHAN` へ改め、version を 1.2 へ上げる。§2 の宣言（『受入基準はこの一本化に合わせて改訂する』）を実際に履行する。(2) 三者照合を**四者照合**へ拡張し、要件本文中のバッククォート囲み enum 値も照合対象に含める（`s
  - tracked_by: `FLW-REV-013:GP-006`
- **SYN-017** [DIN-010, RSK-011] recovery class 識別子が 2 系統に分裂し、FLW-DSN-013 の worktree 4 クラスは §8 と矛盾する挙動を規定したまま残っている
  - 問題: 本書 §1 の operation catalog は recovery class を `REC-WT-CREATE` / `REC-WT-RESUME` / `REC-WT-FINISH` / `REC-WT-DISCARD` / `REC-RM-DELETE` と採番する。しかし `FLW-DSN-012.md:51-55` は同じ operation に `REC-REMOTE-DELETE` / `REC-WORKTREE-C
  - 是正: (1) recovery class 識別子を 1 系統に統一する。既存 3 文書に登録済みの `REC-WORKTREE-*` / `REC-REMOTE-DELETE` を正とし、本書 §1 の表を改めるのが変更量・破壊性ともに最小である。改名を採るなら `FLW-DSN-012` / `FLW-DSN-013` を同一変更セットで更新する。(2) `REC-WORKTREE-RESUME` を新設し `FLW-DSN-013` へ
  - tracked_by: `FLW-REV-013:GP-003`
- **SYN-018** [RSK-005] guard key が path digest である一方 CAS は dev+ino を使うため、bind mount / 別 mount 経路では同一実体が別 key となり、`M2-FLT-006` が要求する収束は原理的に達成できない
  - 問題: §3 は `worktree-dir` の canonical key を『canonical common-dir identity ＋ worktree の canonical path の digest』と定め、『symlink・相対 path・case 差・別 clone を正規化して同一 worktree へ収束させる』とする（FLW-DSN-016.md:199-202）。しかし canonical path 解決（real
  - 是正: (1) 既存 worktree を対象とする `resume` / `finish` / `discard` については、guard key を『common-dir identity ＋ worktree-dir の stable file identity（dev+ino 相当）』へ改め、path digest は監査用の副次情報に落とす。(2) 対象がまだ存在しない `create` については stable identity を
  - tracked_by: `FLW-REV-013:GP-002`
- **SYN-019** [RSK-006] FLW-NFR-007 緩和が開いた escape 面に対し、Unicode 正規化と Windows 固有 path 表現の回避経路が規則にも fixture にも無い
  - 問題: `FLW-NFR-007` 1.3（FLW-NFR-007.md:21）は repo 境界外 parent への write を『承認済み root 配下 / canonicalize 後に root 外へ escape しない / 単回 capability』の3条件で許可へ転じた。ゆえに escape 判定は、従来の『repo 外は一律 BLOCKED』という粗いが堅い禁止に代わる**唯一の境界**になった。ところが本書の cano
  - 是正: (1) §3 の canonicalize 規則へ『path の Unicode 正規化形式を root ごとに probe し（case 感度と同じ扱いで承認時に測定して intent へ記録）、比較・digest 化は測定した形式へ正規化してから行う。判定不能なら `BLOCKED`』を追加する。(2) `M2-FLT-007` を『Unix 変種』と『Windows 変種（8.3 名・`\\?\`・末尾ドット/空白・ADS・jun
  - tracked_by: `FLW-REV-013:GP-008`
- **SYN-020** [RSK-007] 承認 capability の署名鍵の保管境界が未規定で、実行主体が自己承認できるなら capability 層は事故防止にしかならない
  - 問題: §4 は M1 の capability envelope（Ed25519・trusted key ID・signed payload・signature）を再利用し、`worktree_dir_guard_key` / `parent_dir_identity` / `nonexistence_digest` / `nonce` などを署名対象とする（FLW-DSN-016.md:292-306）。これは TOCTOU と承認使い回し
  - 是正: (1) §4 へ『脅威モデル』小節を設け、capability が防ぐ対象（TOCTOU・使い回し・取り違え）と防がない対象（署名鍵を握る主体の意図的な逸脱）を明記する。(2) 署名鍵の保管境界を規定する: 最低限『実行 process の権限で読めない場所に置く』『鍵が実行主体から到達可能な構成では、その旨を plan と result の evidence へ明示する（degraded 承認）』のいずれかを必須とする。(3) `M2
  - tracked_by: `FLW-REV-013:GP-008`
- **SYN-021** [RSK-008] repo 外 worktree root の filesystem 能力（lock・原子性・identity 安定性・時刻粒度）を root ごとに probe する規定が無く、M1 の前提が検証なしに持ち込まれている
  - 問題: M1 の write 安全性は『安全な advisory lock・owner-only 永続領域・fsync のいずれかを提供できない platform では write を `UNSUPPORTED`』（FLW-DSN-015.md:148-149）、『native index lock・atomic rename・同一 filesystem を提供できない platform では stage/commit/sync を `UNSU
  - 是正: (1) §5 の capability 縮退表へ、承認済み root に対する probe 項目として『advisory lock の実効性』『atomic rename』『fsync 耐久性』『stable file identity の安定性』『mtime 粒度』『common-dir と root が同一耐久ドメインか』を追加し、取得不能・不十分な場合の縮退先（`worktree.create` / `discard` を `UN
  - tracked_by: `FLW-REV-013:GP-008`
- **SYN-022** [RSK-009] `worktree-residue-retained` に前進経路が無く、唯一の脱出がリポジトリ規約で禁止されている手動削除になる
  - 問題: §6 は `worktree-residue-retained`（directory だけ残存）を『repository-owner ＋ evaluation-reviewer で解除可。**残存 directory は削除しない**』と定める（FLW-DSN-016.md:404）。§14 も『`worktree-residue-retained` で保全した directory は**ロールバックでも削除しない**』とする（同:69
  - 是正: (1) §6 へ『退避付き解放』の正規経路を追加する: 残存 directory を削除するのではなく、承認済み root 配下の隔離領域（例 `<root>/.quarantine/<work-id>-<nonce>/`）へ **rename で退避**し、退避後に元 path を解放する。rename なら内容は失われず、`worktree-residue-retained` の趣旨（未コミット作業を消さない）を保ったまま行き止まり
  - tracked_by: `FLW-REV-013:GP-001`
- **SYN-023** [RSK-012] Activity API 依存の失敗分類（timeout / rate limit / 部分ページ）が未定義で、『判定不能を更新なしへ倒さない』が文でしか担保されていない。加えて ABA へのリスク配分が discard 側と逆転している
  - 問題: §8 の ABA 3経路（FLW-DSN-016.md:511-521）と `FLW-DSN-014` の capability matrix は、`GET /repos/{owner}/{repo}/activity` を Must capability として `git.delete-remote-branch` の判断材料にする。しかしこの API 呼び出しの失敗様態が経路 A/B/C のどれへ写像されるかが定義されていない。実在
  - 是正: (1) §8 へ Activity 照会の失敗分類表を追加し、timeout / rate limit / 部分ページ / 遡及範囲不足 / truncation をすべて**経路 C（ABA 不検出）へ写像する**と明記する。『`T0` まで遡れたことを証明できた場合だけ経路 B』という肯定条件で書く（不在証明の弱さを扱う本書の論理と一貫させる）。(2) 照会の bounded wait（timeout 上限、ページ数上限）を定め、超
  - tracked_by: `FLW-REV-013:GP-008`

## P2 — Should Fix

- **SYN-024** [BIZ-004] M2-6 が過負荷で、移送した +3 session が実質的に新規実装費へ流用されている
  - 是正: M2-6 を「delete-remote-branch ＋ ABA」と「local-write confirmation ＋ 出口ゲート」の2区分へ分割し、fixture 件数と M1 実績（confirmation = 3 session）に基づいて再配賦する。総枠 20 session を維持するなら M2-4（r
- **SYN-025** [BIZ-005] M2 に early quick win が無く、縮退が二値のため 20 session を投じて出荷可能増分ゼロになり得る
  - 是正: §11 または §12 へ「予算超過時の M2 内 scope 縮小ladder」を追加し、公開できる最小の安全境界（例: local-write confirmation ＋ worktree.audit/create/resume まで＝縮退規則3 の部分解除）と、そのとき UNSUPPORTED へ残す oper
- **SYN-026** [BIZ-006] SI-FLW-046 の M2 内取り込みが裁定4（v2 完成条件は Must のみ）に照らして検討されておらず、配置が取り込み理由と矛盾する
  - 是正: (1) §13 へ『SI-FLW-046 を Should として Promotion Gate 後へ回す』案とその却下理由を追加し、裁定4 の例外として扱う根拠（FLW-FR-007 という既存 Must 要件の受入基準改訂に収まること）を明記する。(2) reconnaissance が read-only である
- **SYN-027** [DIN-005] worktree-registry-stale の必須証跡「非存在証明」は §8 が ABA 節で自ら否定した否定的主張であり、区分が原理的に空になる
  - 是正: §8 の 3 経路と同じ構造を §6 へ適用する。すなわち `worktree-registry-stale` の判定を (A) 親 directory を列挙して当該 entry 名が無いことを**肯定的に**確認でき、かつ親 directory 自体が承認済み root 配下で読み取り可能、(B) 親が読めるが判定
- **SYN-028** [DIN-006] create / resume の canonical guard key が「まだ存在しない path」に対して定義されておらず、SYN-002 が guard key 側で再発する
  - 是正: §3 へ『不在 path の canonical 化アルゴリズム』を明記する。推奨は『**存在する最も近い祖先まで実体解決（realpath）し、そこから先の未解決成分は字句的に正規化（`.` 除去・`..` を字句的に解決・case 感度は §3 の測定値で折り畳み）して連結する**』（§3 が case 感度判定で
- **SYN-029** [DIN-007] create / resume の step 契約が存在しないのに PARTIAL / reconcile-only が割り当てられており、completed / remaining の一意化が実装不能
  - 是正: (1) §8 の step 契約へ `worktree.create` / `worktree.resume` の step 閉集合を追加する。順序は §8 が discard / finish で採った原則（durability commit point ＝ registry entry の atomic 公開時点を
- **SYN-030** [DIN-008] 状態 enum の判定述語（決定表）が本書に無く、三者照合は値集合しか見ないため「値は一致するが意味が乖離する」経路が塞がっていない
  - 是正: (1) §2 へ `worktree_state` / `branch_audit_state` / `work_unit_state` の**決定表**（値 × 必須証跡 × 排他条件 × 許可 operation）を移設し、`FLW-DSN-006` の audit 分類表は §2 を参照する記述へ置き換える（値と
- **SYN-031** [DIN-011] manifest digest が内容 hash を持たず mtime 精度に依存し、nonexistence_digest の導出規則も未定義で、いずれも capability 縮退表に無い
  - 是正: (1) manifest entry へ**内容 digest** を追加する（通常ファイルは content sha256、symlink は link target、directory は子 entry 名集合の digest）。大規模 worktree のコストが問題なら、`size + mtime` が一致した
- **SYN-032** [DIN-012] work_unit_state は 12 値の列挙のみで遷移関係が無く、worktree_state 9 値のうち 3 値は FLW-DSN-012 の写像表から到達できない
  - 是正: (1) §2 へ `work_unit_state` の**遷移表**（from / to / trigger operation / precondition）を追加し、到達不能状態と吸い込み状態が 0 であることを三者照合テストと同じ機械検査の対象にする。(2) `REMOTE_ADVANCED` / `WORKT
- **SYN-033** [OPS-005] 診断可能性が主張だけで、quarantine・intent・receipt を運用者が列挙・参照する read 経路が operation catalog に無い
  - 是正: (1) M2 catalog へ read-only の診断 operation（例: `worktree.doctor` — quarantine 中の worktree、pending intent、未解除 receipt、§6 区分の判定に必要な証跡を1回で返す）を追加し、§11 の区分へ割り当てる。M2-3（r
- **SYN-034** [OPS-006] quarantine の運用規定（解除の目標時間・滞留の棚卸し・恒久 quarantine のエスカレーション・RACI 更新）が無い
  - 是正: §6 へ運用契約の小節を追加し、(a) 区分別の解除目標時間と超過時のエスカレーション先、(b) quarantine 滞留の定期棚卸し（頻度・実行 operation・報告先）、(c) `worktree-unresolved` の再評価トリガと最終決着手順、(d) FLW-DSN-015.md:370-376 の 
- **SYN-035** [OPS-007] discard の manifest CAS が mtime_ns を含むため生きた worktree で容易に STALE となり、退避との順序も未規定で再承認ループを起こす
  - 是正: (1) §5 へ manifest の再計算不一致に対する扱いを細分化する — 削除対象集合（path 集合と type）が同一で `mtime_ns` / `size` だけが変化した場合を『内容変化』として区別し、その場合に再承認を要するかを裁定して明記する。区別しないなら、静穏性の前提（監視プロセスの停止・wor
- **SYN-036** [OPS-008] capability 縮退が非対称で、作成はできるが削除できない worktree を生み得る（事前開示の規定も無い）
  - 是正: (1) §5 へ縮退の結合規則を追加する — `worktree.discard` が `UNSUPPORTED` の環境では `worktree.create` も `UNSUPPORTED`（あるいは『後始末が手作業になる』ことの明示的承認を create の precondition にする）とし、片付けられない
- **SYN-037** [OPS-009] ABA 経路 C が UNAVAILABLE（一時的）と UNSUPPORTED（恒久）を混同し、既存の capability 判定規則に反して承認材料の質を誤って伝える
  - 是正: 経路表を4経路へ分割する — A（更新あり → `BLOCKED`）、B（`AVAILABLE` かつ更新なし → 承認要求・不在証明でない旨を明示）、C（`UNSUPPORTED` = host が機能を持たない → 承認要求・恒久的に検出不能である旨を明示）、D（`UNAVAILABLE` = auth / rat
- **SYN-038** [OPS-010] M2 が新設する永続成果物に SLI・retention・backup/restore・改ざん検知の規定が無く、create 時 nonce は routine な Git 保守で消える
  - 是正: (1) §6 または新節へ M2 成果物の運用契約表（対象・保持期間・backup 有無・改ざん検知手段・欠損時の扱い）を追加し、FLW-DSN-015.md:357-367 の表と同じ粒度で埋める。少なくとも「receipt / nonce / manifest を失った場合は当該 worktree の write 
- **SYN-039** [OPS-011] 承認要求の頻度が構造的に高い一方、承認者が何を確認すべきかの手順と観測指標が無く rubber-stamping を招く
  - 是正: (1) §4 へ承認提示物の必須内容（対象 path、instance identity の要約、経路種別、その経路で**確認できていないこと**の明示、拒否すべき典型条件、エスカレーション先）を規定し、`expires_at` の既定値を定める。(2) 経路 C が恒常化する環境向けに、承認を1件ずつではなく期間・範
- **SYN-040** [RVC-004] M2 出口条件の「正」が3文書で相互に別の文書を指しており、RVC-001 の食い違いを解決できない
  - 是正: M2 出口条件と budget について正を1つ選び、他2文書から『正は X』の相互指名を削って一方向の参照だけを残す。推奨は enum と同じ扱い（詳細設計 FLW-DSN-016 を正とし、FLW-DSN-014 と ROADMAP は数値を複写せず参照だけ置く）。複写を残す場合は、複写箇所を release_ch
- **SYN-041** [RVC-005] §6 の quarantine 解除区分が本文「3区分」・表4行・§15「4区分」・fixture「3区分」で不一致
  - 是正: §6 の導入文と `M2-FLT-034` の期待結果を「4区分」へ揃える。恒久策として、区分数のような数え上げを散文へ書かず「§6 の表の全区分」と参照で書く。
- **SYN-042** [RVC-007] M2 operation catalog に M2-4（reconnaissance / entry protocol）に対応する行が無く、「catalog 外は UNSUPPORTED」と衝突する
  - 是正: (1) catalog へ reconnaissance の行を追加する（`worktree.audit` の受入基準拡張として扱うなら audit 行の canonical mutation target / recovery 欄はそのままに、実装区分を「M2-3（基本）/ M2-4（in-flight 拡張）」と分
- **SYN-043** [RVC-008] `guard_identity_kind` の5値閉集合が output-contract.md にも存在するが、三者照合の対象外で第4のコピーとして残る
  - 是正: §14 の変更対象へ output-contract.md:102 を加え、§2 の三者照合テストの照合対象に output-contract.md の閉集合列挙も含める（実質「四者照合」にする）か、output-contract.md 側の列挙を削って schema への参照に置き換える。
- **SYN-044** [RVC-009] FLW-CON-006 1.3 が ABA の旧2分岐モデルのままで、v1.4 の3経路（経路A / B）に対応する受入基準が無い
  - 是正: FLW-CON-006 へ経路A（更新イベントを観測した場合は削除を BLOCKED にし検出した更新を提示する）と経路B（観測結果が空でも不在証明ではない旨を明示して人間承認を要求する）の2条を追加し 1.4 へ上げる。併せて §14 の表の根拠欄を「要件 1.4 で反映」へ更新し、v1.4 の変更が要件へ降りている
- **SYN-045** [RVC-010] accepted な SI-FLW-046 が対象に挙げた FLW-DSN-006 に、reconnaissance の記述が1文字も無い
  - 是正: FLW-DSN-006 の create / resume 節の前に「着手前 reconnaissance」を追加し（正は FLW-DSN-016 §11 / FLW-FR-007 1.1 への参照でよい）、v1.2 へ上げる。意図的に FLW-DSN-016 側だけへ集約するなら、SI-FLW-046 の targe
- **SYN-046** [RVC-011] frontmatter の origin / decision_ref が本書の実際の駆動要因を指しておらず、幽霊参照と欠落の両方がある
  - 是正: `origin` へ `SI-FLW-046` と `FLW-REV-012` を追加し、`decision_ref` を `.spec/reports/decision-2026-08-12-si-flw-043-046.md` へ（複数指定が許されるなら m2-design-gaps との併記へ）改める。あわせて 
- **SYN-047** [RVC-012] budget の「人間へ再提示して確定した」という記述に対応する裁定記録が存在しない
  - 是正: budget 再校正（4 PR/14 session → 6 PR/20 session）の提示と確定を裁定記録として起こし、§11 と FLW-DSN-014 の該当箇所から decision-ref で参照する。実際にはまだ人間へ提示していないのであれば、両文書の「確定した」を「提示予定（未確定）」へ直し、M2 着

## P3 — Consider

- **SYN-048** [BIZ-008] M2 出口条件の confirmation 項目に閾値・母数が inline されておらず、本書だけでは合否を判定できない
- **SYN-049** [BIZ-009] 人間承認の発生頻度・所要コストが定量化されておらず、Persona B（AIエージェント）の自律性への影響が評価されていない
- **SYN-050** [DIN-013] cause namespace は三者照合の対象と宣言されながら設計側の閉集合が本書に無く、11 namespace 中 1 つで照合が成立しない
- **SYN-051** [OPS-012] 署名鍵の保管と署名手順が未定義で、承認 capability の実効性を運用で担保できない
- **SYN-052** [OPS-013] M2 出口ゲートが、M2 出口時点では出荷できない delete-remote-branch と同一区分に束ねられている
- **SYN-053** [RSK-013] `create` / `resume` の step 契約が無いまま、recovery matrix と fixture が step 境界の crash を前提にしている
- **SYN-054** [RSK-014] quarantine 解除が二者承認を要求するが本プロジェクトは単独体制であり、統制が名目化する。human-stop / quarantine の蓄積に対する指標も無い
- **SYN-055** [RSK-015] 出口条件の正である `FLW-DSN-014` / ROADMAP が fixture 上限 `044` のままで、今回 ABA 対策として追加した `048` / `049` がゲートの外にある
- **SYN-056** [RVC-013] §2 が FLW-DSN-012 の既に是正済みの記述を、未是正のものとして引用している
- **SYN-057** [RVC-014] §15 の GP-015 応答が「後者を採用」と書くが、§2 本文は前者（output-contract.md への条文新設）も実施する
- **SYN-058** [RVC-015] §9 の fixture 表の並びが非単調（038 → 048 → 049 → 039 → … → 047）で、範囲表記と機械抽出に弱い
- **SYN-059** [RVC-016] `worktree_state` の `WORKTREE_MISMATCH` を返す規定・fixture・recovery 行がどこにも無い孤立値になっている
- **SYN-060** [RVC-017] 多重語一覧の導出規則が「全 namespace」を対象とするが、`cause` の値が本書に無く導出結果を再現・検証できない
- **SYN-061** [RVC-018] FLW-REV-012 の GP-004 が参照する実装区分（M2-5）が、v1.3 の6区分再構成で陳腐化している
- **SYN-062** [RVC-019] 同一の出口条件項目が FLW-DSN-014 では修飾と参照 ID 付き、FLW-DSN-016 では裸で書かれている
- **SYN-063** [BIZ-010] 良い点 — トレードオフ判断の文書化とトレーサビリティは模範的
- **SYN-064** [DIN-014] 検算して正しかった点 — 多重語表・fixture 区分割当・instance nonce・registry-before-dir の順序根拠
- **SYN-065** [OPS-014] 良い点 — recovery matrix の網羅性、縮退の全否定、防げないものを防げると書かない誠実さ
- **SYN-066** [RSK-016] 良い点 — 不在証明の否定、capability 縮退の一貫性、残留物を消さない既定は risk 観点で高く評価できる
- **SYN-067** [RVC-020] 良い点 — GP 逐語併記・fixture 割当の完全性・enum の正の一本化は整合性の観点で加点

## Gate precondition

`kind: blocking` かつ未消化のものが Design Gate 通過の阻止条件。`agenda` は Gate で決める論点であり阻止には用いない。

| ID | kind | basis | 要旨 |
|---|---|---|---|
| `GP-001` | blocking | verified | §6 解除区分の定義軸と §8 step 順の同時再裁定 |
| `GP-002` | blocking | verified | guard identity 方式の統一と step→target 全射性の保証 |
| `GP-003` | blocking | verified | operation class の所有権確定（destructive の扱い） |
| `GP-004` | blocking | verified | `worktree_state` の軸分離または全順序の定義 |
| `GP-005` | blocking | verified | 機械強制層の3プラットフォーム対応と実装区分の順序 |
| `GP-006` | blocking | verified | 文書間定数の SSOT 化と機械検証の先行構築 |
| `GP-007` | blocking | verified | 残債移送に伴う budget 配賦の確定と下流への伝達経路 |
| `GP-008` | agenda | assumed | M2 運用規定（reconnaissance 上限・quarantine 運用・診断経路ほか） |

## 持ち越し（carried_over）

過去レビューの未 resolved な P0 / P1 を 27 件引き継いだ。

| 引き継ぎ元 | 件数 | 備考 |
|---|---:|---|
| `FLW-REV-006`（FAIL 2.50 / 2026-08-07） | 9 | 未消化のまま2レビュー分を経過している |
| `FLW-REV-011`（FAIL 2.47 / 2026-08-12） | 18 | 本設計が回答対象とした GP 群。うち `SYN-003` / `SYN-005` / `SYN-007` / `SYN-010` / `SYN-018` は本レビューで**未閉鎖であることが実測確認された** |

## 人間への裁定依頼

この判定は推奨です。Design Gate の裁定は上記を確認のうえ行ってください。2026-08-13 時点で以下2件は裁定済みです。

- M3 budget を 8 PR / 26 session へ増額（残債移送分 +1/+3、coordinator 証明手段の設計 +1/+3）
- M2 設計再整備を M2 実装予算の別枠として 2〜3 PR / 6〜9 session で新設

残る裁定事項は `GP-001`〜`GP-006` の論点群（critical 11件の帰結）および `GP-008` の運用規定である。`GP-006` は**文書修正より先に機械検証を構築する**という順序制約を含む。
