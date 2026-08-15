# 分析 — bitz-flow V2 の scope と安全機構の再評価

- **日付**: 2026-08-15
- **作成**: claude（`FLW-REV-016:GP-005`（M2 是正の追加予算再裁定）の裁定材料として）
- **裁定者**: hide（本書は裁定ではない。選択肢と根拠の提示にとどまる）
- **対象**: bitz-flow V2 の要求・設計・milestone 構成の妥当性

## 要旨

**ビジョンと North Star の見直しは不要**である。価値仮説は M0 で実測 1.0（目標 90%）で
実証済みで、しかも**まだ一度も出荷されていない**。

見直しの対象は **M1 / M2 の安全機構の設計**である。採用した機構が、設計自身が宣言した
脅威モデルより重く、かつ機構が効く前提（外部の鍵保持者）を `FLW-CON-005` が
明示的に scope 外としている。

## 1. 価値仮説は実証済みで未出荷

`evals/flow-core/m0-eval/run-manifest-3platform-2026-08-11-r14.json`（M0 出口、第14ラウンド）:

| 指標 | 目標 | 実測 |
|---|---:|---:|
| SFCR（North Star Metric）claude-code | 90%以上 | **1.0** |
| SFCR codex-cli | 90%以上 | **1.0** |
| SFCR antigravity | 90%以上 | **1.0** |
| Dispatcher Invocation Rate | 95%以上 | **1.0**（ベースライン 0.0） |
| Cross-model Decision Parity | 100% | **1.0** |
| 危険操作率の上限 | 0.05 未満 | 0.0464 |

ベースライン（スキルなし）の invocation rate が 0.0 なので、効果の帰属も明確である。

一方 `ROADMAP.md` の縮退規則3 により、**M2 が閉じるまで M1 の Git write も公開しない**。
その M2 は 2026-08-15 の `FLW-REV-016` で **FAIL 2.85**、出口8項目中3項目が BLOCKED である。
結果として、実証済みの read-only 3 operation を含め**何も出荷されていない**。

## 2. 投資規模と予算の乖離

`FLW-DSN-014` の milestone 予算表（L634-638）と実績:

| 区分 | 当初 | 再校正後 |
|---|---|---|
| M1〜M5 合計 | 13 PR / 52 session | 30 PR / 100 session |
| ＋設計再整備（`SI-FLW-049`〜`055` 対応） | — | +3 PR / +9 session |
| ＋M2 是正枠（`SI-FLW-056`） | — | +2 PR / +6 session |
| **承認総額** | **13 PR / 52 session** | **35 PR / 115 session**（PR 2.7倍 / session 2.2倍） |

実績（`git log origin/main -- plugins/bitz-flow evals/flow-core`）:

| 項目 | 値 |
|---|---:|
| main 上で bitz-flow を変更したコミット（squash merge = ほぼ PR 数） | **113** |
| うち実装・テストを変更したもの | 47 |
| 期間 | 2026-07-18 〜 2026-08-15（4週間） |
| 到達点 | M2 出口 FAIL。M3〜M5 未着手 |

仕様在庫は 要件31 / 設計17 / spec-issue 59（accepted 52・open 6）/ タスク81。

**M1〜M5 全体の承認総額 35 PR に対し、M0＋M1＋未完の M2 で 113 コミットを消費している。**
予算制度が実態を捕捉できていない（`FLW-REV-016:SYN-015` — M2 の run manifest が0件で、
ROADMAP 自身が定める実績記録の運用規則が未履行）。

## 3. レビュー採点が上がらない構造

集計スコアの推移（`.spec/reviews/FLW-REV-*.json`）:

| ID | 002 | 006 | 007 | 008 | 009 | 010 | 011 | 012 | 013 | 014 | 015 | 016 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| スコア | 4.74 | 2.42 | 4.88 | 2.50 | 4.20 | 4.00 | 2.47 | 3.62 | 2.31 | 4.25 | 3.09 | 2.85 |
| 指摘(raw) | – | – | – | – | – | – | 34 | 9 | 74 | 3 | 8 | 57 |

### 3.1 スコアは品質ではなくレビュー深度を測っている

同一対象を2回測った自然実験が2組ある。

| 組 | 対象 | 結果 |
|---|---|---|
| `FLW-REV-012` vs `013` | 同じ `FLW-DSN-016` | 9件 / **3.62** vs 74件 / **2.31** |
| `FLW-REV-015` vs `016` | 同じ M2 Exit | 8件 / **3.09** vs 57件 / **2.85** |

方式を明記しているのは `013` と `016` だけで、いずれも「5観点すべて独立エージェント」である。
高得点回（`009` 4.20、`014` 4.25）はいずれも同一対象の残指摘を潰した後の再レビューで、
測っている面積が小さい（`014` は指摘3件）。

**4.2 系列と 2.3 系列は別の物差しであり、時系列に並べた時点で比較になっていない。**
独立レビュー系列だけを並べると 2.31 → 2.85、指摘 74 → 57 で緩やかに改善している。

重み配分は原因ではない（加重平均と単純平均の差は全12回で最大 0.04）。

### 3.2 同じ欠陥類型が層を変えて再発している

| 類型 | `011`（設計） | `013`（設計） | `015`/`016`（実装） |
|---|---|---|---|
| **宣言と実体の二重定義** | closed enum が設計文書と不一致／設計7種・契約5種 | recovery class が2系統に分裂／fixture 範囲が3文書食い違い | step 語彙が安全核と不一致／公開集合が `PUBLISHED_OPERATIONS` と `_HANDLERS` に二重定義 |
| **反証できない検査** | 照合テストが片方向で沈黙する | 「実ファイル更新済み」の主張が実体と不一致 | hazard/residual が定数、`required_checks=2/2` が固定文字列 |
| **核はあるが未接続** | repo 外書き込みの機械強制層が無い／guard 解放経路が未定義 | residue に前進経路が無い／強制層が Claude Code 専用 | 安全核が dispatcher へ未接続／`recovery.py` が未 import／audit が quarantine 未接続 |

「未接続」は `011` → `013` → `015` → `016` の4連続である。

修正が**その回の Gate Precondition の文言を満たす最小実装**になっており、類型自体を
閉じていない。`FLW-REV-016:SYN-002` が典型で、`GP-001` が要求した receipt prefix 収束を
`worktree_runtime` 私有の `MUTATING_STEPS` 内だけで成立させ、`worktree_cleanup.FINISH_STEPS`
とは語彙が別物のまま残した。

## 4. 安全機構が脅威モデルに見合っていない

`FLW-DSN-016:714` の脅威モデル:

> capability は**誤操作、承認再利用、別 process の取り違え**を防ぐ

採用機構は Ed25519 署名付き単回 capability ＋ trusted key registry ＋ nonce ledger ＋
hash-chain receipt である。脅威と必要十分な機構の対応:

| 脅威 | 必要十分な機構 |
|---|---|
| 誤操作 | plan / apply 分離＋plan 鮮度検証 |
| 承認再利用 | 単回 nonce |
| 別 process の取り違え | operation ID ＋ path / instance identity の束縛 |

**署名が防御として効くのは、鍵の保持者が実行主体と別であるときだけである。**
ところが `FLW-CON-005` は次を SHALL で定めている。

- CLI は人間本人を認証しない前提を明示する
- `--confirm` は plan 鮮度と effects 一致だけを検証し、**人間本人の承認証明として扱わない**
- `--approval-ref` は参照の存在だけで apply 可否を変更せず、**本人性を主張しない**

つまり**外部の鍵保持者は要件上存在しない**。実装もそれを反映しており、
`tests/test_flow_m2_runtime.py:52` は各テストが一時ディレクトリに鍵を生成して自ら署名する。
`FLW-REV-016:RSK-204` は「`apply()` は trusted key を呼び出し側から受け取るだけで、
owner-only registry を mutation 境界で強制していない（8件中7件が一時鍵を直接注入）」と
指摘している。

**署名者と検証者が同一なら、署名は儀式であって防御ではない。**
§3.2 の再発3類型は、実体のない層を維持し続けるコストとして現れていると考えられる。

### 4.1 要件粒度の肥大

`FLW-CON-006` は EARS 15節を持ち、うち6節が remote branch 削除の ABA 検出
（Activity API、pagination、rate limit、timeout 分類）である。remote write は M3 送りだが、
その節が M2 の設計と fixture を重くしている。1要件が milestone をまたいで肥大している。

## 5. 選択肢

| 案 | 内容 | 効果 | 副作用・コスト |
|---|---|---|---|
| **A. M0 を先に出荷** | 縮退規則3 の解除を待たず、read-only 3 operation を prerelease として公開する | 実証済みの価値（SFCR 1.0）が4週間ぶりに利用可能になる。以降の判断を実利用のフィードバック付きで行える | 「write はまだ」の説明が要る。縮退規則3 の文面を改める裁定が必要 |
| **B. capability を脅威モデルへ縮退** | Ed25519 署名と trusted key registry を落とし、単回 nonce ＋ plan 鮮度 ＋ operation ID 束縛へ置換する | `SI-FLW-057` の大半が消える。維持すべき層が1つ減り、再発3類型の発生源が減る | `FLW-DSN-016` §4 と `GP-002` / `GP-011` の再裁定が要る。設計の一貫性が一時的に崩れる |
| **C. M2 の scope を絞る** | `worktree.audit` / `create` / `resume` を M2 とし、`finish` / `discard`（破壊系）を M3 へ送る | retention ref・quarantine・receipt chain の複雑さの大半は破壊操作由来。M2 が現実的に閉じる | M3 の負荷が増える。M3 入口条件の再定義が要る |
| **D. 継続** | 追加予算を裁定し現設計のまま進める | 設計の一貫性は保たれる | 承認総額 35 PR に対し実績 113 コミット。同じ曲線が続く見込み |

## 6. 推奨

**A ＋ C を先に、B はその後に別途**。

- **A** は今日実行できる。M0 は独立して green（`FLW-REV-016` の FAIL は M2 の話であり、
  M0 の実測値には影響しない）
- **C** は `SI-FLW-057`〜`059` の裁定と同じ場で決められる
- **B** は設計の再裁定を伴うため、A / C の後に `FLW-DSN-016` の改訂として扱うのが安全

いずれを選ぶ場合でも、`FLW-REV-016:GP-005`（予算再裁定）の材料に
**「North Star は達成済み・未出荷」** という事実を明示的に載せるべきである。
現状の裁定材料はこの事実を含んでいない。

## 7. 本書の限界

- 「113 コミット」は squash merge 前提の近似であり、PR 数と厳密には一致しない
- session 数の実績は記録されていない（`FLW-REV-016:SYN-015`）。PR 数のみで比較している
- §4 は設計の**費用対効果**の指摘であり、実装欠陥の指摘ではない。
  Ed25519 capability が誤りだと主張しているのではなく、宣言された脅威モデルに対して
  過剰であり、その過剰分が §3.2 の再発コストを生んでいる可能性を示している
- 選択肢 B / C の工数見積もりは行っていない。裁定後に `sdd-issue` で起票し見積もる

## 参照

- `evals/flow-core/m0-eval/run-manifest-3platform-2026-08-11-r14.json`（M0 実測）
- `plugins/bitz-flow/.spec/design/FLW-DSN-014.md` L634-638（予算表 SSOT）
- `plugins/bitz-flow/.spec/design/FLW-DSN-016.md` L714（脅威モデル）
- `plugins/bitz-flow/.spec/requirements/FLW-CON-005.md`、`FLW-CON-006.md`
- `plugins/bitz-flow/.spec/reviews/FLW-REV-016.md`、`FLW-REV-016.json`
- `plugins/bitz-flow/.spec/reports/decision-2026-08-14-si-flw-056.md`（消化済みの是正枠）
