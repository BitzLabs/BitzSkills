---
id: SI-FLW-054
raised_by: FLW-REV-013（独立5観点レビュー・FAIL 2.31）
target: FLW-DSN-016・FLW-FR-007
proposed_change_type: modify
status: open
---
- **目的**: **M2 が新設する機構の運用規定を決める。** 安全機構は定義されているが、
  それを日常的に回すための規定（上限・失敗時の扱い・棚卸し・診断経路）が無い。
  規定が無いまま出荷すると、安全機構が運用を阻害するか、逆に形骸化する。

- **本 issue の位置づけ**: `FLW-REV-013` の `GP-008` は **`kind: agenda`**（Gate で決める論点）
  として立てられている。他の GP と異なり実測による裏取りを行っていないため、
  **Design Gate 通過の阻止条件にはしない**。ただし M2 出荷前に決める必要がある。

- **裁定を求める論点**（`FLW-REV-013:SYN-015` / `SYN-019` 〜 `SYN-021` / `SYN-023` /
  `SYN-031` / `SYN-033` 〜 `SYN-039`）:

  1. **着手前 reconnaissance の上限と失敗時の扱い**（`SYN-015`）

     `SI-FLW-046` で新設した reconnaissance は**全 write の必須前置**になっている。
     しかし出力量の上限・実行時間の上限・失敗時および `INDETERMINATE` 時の運用規定が無い。

     - 出力量に上限が無いことは、v2 の North Star（token / byte 効率）と Must 要件に反する
     - 全 write の必須前置でありながら失敗時規定が無いことは、**新しい単一障害点**になる

     決めること: 出力量の上限（件数 / byte）、実行時間の上限、超過時の縮退（打ち切って
     警告するか、`BLOCKED` にするか）、失敗時に write を許すか否か。

  2. **quarantine の運用規定**（`SYN-020`）

     解除の目標時間、滞留の棚卸し頻度、恒久 quarantine のエスカレーション先、RACI の更新。
     `SI-FLW-047` で解除経路を直しても、運用規定が無ければ quarantine は蓄積する。

  3. **診断のための read 経路**（`SYN-019`）

     `FLW-DSN-016` は診断可能性を主張するが、**quarantine / intent record / receipt を
     運用者が列挙・参照する operation が catalog に無い**。
     証跡は書かれるだけで読めない。read operation を catalog へ追加するか裁定する。

  4. **承認要求の頻度と rubber-stamping 対策**（`SYN-023`）

     ABA 経路 B / C はいずれも「承認要求」に落ちる設計であり、承認要求は構造的に頻発する。
     一方で**承認者が何を確認すべきかの手順が無く、観測指標も無い**。
     決めること: 承認画面に提示する最小情報、承認率の観測指標、
     承認疲れを検出する閾値。

  5. **capability 縮退の非対称**（`SYN-021`）

     現在の縮退は「作成はできるが削除できない worktree」を生み得る。
     事前開示の規定も無い。決めること: 削除できない環境で作成を許すか、
     許すなら作成時に何を開示するか。

  6. **ABA 経路 C の capability 語彙**（`SYN-031`）

     経路 C が `UNAVAILABLE`（一時的）と `UNSUPPORTED`（恒久）を混同しており、
     既存の capability 判定規則に反する。承認材料の質を誤って伝えるため、
     経路 C を2つに分けるか裁定する。

  7. **M2 永続成果物の retention と改ざん検知**（`SYN-033`）

     M2 は新しい永続成果物（intent record・receipt・quarantine 記録・instance nonce）を
     作るが、SLI・retention・backup / restore・改ざん検知の規定が無い。
     とくに **create 時の nonce は routine な Git 保守（gc・prune）で消える**。

  8. **repo 外 worktree root の filesystem 能力 probe**（`SYN-034`）

     `FLW-NFR-007` の緩和で repo 境界外の parent が条件付きで許可されたが、
     その root の filesystem 能力（lock の可否・原子性・identity の安定性・時刻粒度）を
     **root ごとに probe する規定が無く**、M1 の前提が検証なしに持ち込まれている。

  9. **承認 capability の署名鍵の保管境界**（`SYN-035`）

     未規定。**実行主体が自己承認できるなら capability 層は事故防止にしかならず、
     悪意ある操作への防御にはならない**。何を守る機構なのかを明示する。

  10. **Activity API 依存の失敗分類**（`SYN-039`）

      ABA 検出が依存する Activity API の timeout / rate limit / 部分ページの扱いが未定義。
      「判定不能を『更新なし』へ倒さない」が散文でしか担保されていない。

- **提案する修正**: 上記10論点を裁定し、結果を `FLW-DSN-016` の新節（運用規定）と
  `FLW-DSN-014` の capability matrix へ反映する。
  (1) は `FLW-FR-007` の受入基準にも波及する（上限を要件として書く場合）。

  **優先順位の提案**: (1)(3)(7) は M2 の実装区分に直接影響するため**先に決める**。
  (2)(4)(5) は出荷前で足りる。(6)(8)(9)(10) は個別に小さく、まとめて裁定できる。

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`（運用規定の新節・operation catalog）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（capability matrix）
  - `plugins/bitz-flow/.spec/requirements/FLW-FR-007.md`（(1) を要件化する場合）

- **確認観点**:
  - reconnaissance の出力が上限内に収まること（fixture で検証）
  - quarantine / intent / receipt が operation 経由で**読める**こと
  - 承認要求の頻度が観測されていること
  - nonce が Git 保守で消えないこと

- **影響推定・ロールバック**: 運用規定の追加であり、機構そのものの再設計ではない。
  ただし (3) は operation catalog への追加を伴い、(7) は永続化方式の変更を伴う可能性がある。
  未実装のため文書改訂のみで戻せる。

- **依存**: `SI-FLW-047`（quarantine の解除経路が決まらないと (2) の運用規定は書けない）。
  `SI-FLW-051`（capability 縮退の枠組みと (5)(6) が連動）。
