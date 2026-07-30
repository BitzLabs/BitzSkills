---
id: SDD-DSN-011
title: "ReviewFinding の独立と tracked_by 必須化・未消化指摘の持ち越し"
status: active
version: 1.3
updated: 2026-07-30
owner: hide
implements: 
origin: SI-SDD-031
---

# SDD-DSN-011 ReviewFinding の独立と tracked_by 必須化・未消化指摘の持ち越し

Design Gate 裁定3（2026-07-29「独立させ `tracked_by` を必須にする」）の設計。
ROADMAP フェーズ3 順序6。SDD-DSN-010（GatePassage）と並行実装可能。

- **背景 / 課題**:
  - SDD-REV-004（2026-07-22）は自身の P1 を「別途 spec-issue 化を推奨」と書いたうえで
    `verdict: PASS` とした。起票はされず、8日後の現在も未対応である。レビュー指摘が
    synthesis の内部データであり**追跡先を持つ場所が無い**ことが構造的な原因（SDD-DSN-009 問題(3)）。
  - **schema が機械検証されておらず、実測でドリフトしている**。同じ `findings[]` なのに
    キー集合がレビューごとに違う:

    | レビュー | findings のキー |
    |---|---|
    | SDD-REV-004 | `id` / `priority` / `source_ids` / `perspectives` / `title` / `recommendation` |
    | SDD-REV-006 | `id` / `source` / `priority` / `severity` / `title` / `tracked_by` / `note` |

    `synthesis.md` Step 4 の宣言はさらに別で、`severity` / `tracked_by` / `note` /
    `gate_preconditions` / `untracked_p0_p1` / `design_gate` はどれも宣言に無い。
    **SDD-REV-006 は必要な項目を場でその都度手作りしている**。
  - **finding ID がレビュー内連番であり横断で一意でない**。SDD-REV-004 の `SYN-001` と
    SDD-REV-006 の `SYN-001` は別物である。SDD-REV-006 自身が `tracked_by` に
    `SDD-REV-006:GP-003` と書いており、**修飾形式を既に手で使っている**。
  - **`review-synthesis.json` は最新1件で上書きされ、アーカイブは手作業に依存する**。
    実測した運用は「次のレビューを記録するコミットで**前回分を番号付きファイルとして追加する**」
    であり（`SDD-REV-005` は REV-006 を記録した `72ea46b` で追加された）、SDD-REV-006 が
    まだ番号付きで存在しないのは規定どおりの状態である。**問題は機械的な強制が無いこと**で、
    次のレビュー作成者がこの手順を飛ばせば、`.spec/` から前回分が消える
    （git 履歴には残るが、`.spec/` を正とする規律の外に出る）。SDD-REV-004 の P1 が
    消えたのと同じ「手作業に依存した工程」である。

- **設計判断**:
  1. **`ReviewFinding` を独立エンティティとして定義するが、物理的には synthesis JSON 内の
     配列のままとする**。エンティティ性は同一性（ID）とライフサイクルの有無で決まり、
     ファイル分離を要求しない。現存する finding は4レビューで計21件であり、
     これをファイルに割るコストに見合う利得がない。
  2. **finding ID をレビュー横断で一意にする**。正式 ID を `<REV-ID>:SYN-NNN` とする
     （例: `SDD-REV-006:SYN-001`）。SDD-REV-006 が既に使っている形式の正式化であり、移行が要らない。
  3. **`findings[]` の schema を固定し機械検証する**。必須キー:

     ```
     id            <REV-ID>:SYN-NNN
     priority      P0 | P1 | P2 | P3
     severity      critical | major | minor | info
     source        [観点別 finding ID]          （旧 source_ids を統一）
     title         短い要約
     recommendation  実行可能な是正内容
     tracked_by    SpecIssue ID または <REV-ID>:GP-NNN。P0/P1 は必須
     status        open | tracked | resolved     （持ち越し判定に使う）
     ```

     `tracked_by` は**実在検査**を行う（指す spec-issue が存在すること）。既存の幽霊参照検査と同型。
  4. **未紐づけの P0/P1 がある状態で `verdict: PASS` を出せないようにする**（裁定3）。
     検査の置き場は **`spec_inspect`** とする（SI-SDD-031 提案4 の答え）。
     - 理由は境界の言葉で言える。判定は Core（SDD-DSN-009 のコンテキスト1「仕様ライフサイクル」）が
       持ち、コンテキスト6「可視化」は**読み取り専用の読取モデル**である。`sdd_report` に置くと
       「レポートを生成しなければ Gate を通せてしまう」構造になる。
     - レビュー成果物はコンテキスト3「上流と設計」に属し、コンテキスト1 とは
       Customer-Supplier（上流が供給側）で結ばれている。**供給物の受け入れ検査を下流が持つのは
       この関係では自然**である。
  5. **アーカイブを強制し、未消化指摘を持ち越す**（提案3）。
     - 各レビューは `SDD-REV-NNN.json` として保存を必須とし、`review-synthesis.json` は
       「最新へのビュー」へ位置づけを格下げする。
     - `spec_inspect` が「`review-synthesis.json` の `review_id` に対応する `<REV-ID>.json` が
       存在しない」を検出する（＝アーカイブ漏れ）。**実測の SDD-REV-006 がこれに当たり、
       導入直後に1件検出される**。
     - 新しい synthesis を生成するとき、過去の全 `SDD-REV-*.json` から
       `status != resolved` の P0/P1 を `carried_over[]` として取り込む。
  6. **`gate_preconditions` の schema を固め、2種類の混同を止める**（提案2 ＋ SI-SDD-035 の発見）。
     - `kind`: **`blocking`**（Gate 通過前に消化する条件）/ **`agenda`**（Gate で決める論点）。
       SDD-REV-006 はこの区別を持たず、GP-001 と GP-005 が「前提条件なのに Gate で決めること」
       という循環を起こした（裁定記録が自ら認めている）。機械検証は
       **`kind: blocking` かつ未消化のものだけ**を Gate 通過阻止に使う。
     - `basis`: **`verified`**（実測で確認済み）/ **`assumed`**（未検証の想定）。
       不変条件として **`basis: assumed` を根拠に `kind: blocking` を立てられない**とする。
       SI-CORE-038 が未検証の想定を根拠に最先行タスクへ据えられた事故（SI-SDD-035）の再発防止。
     - 注: `basis` の必須化は **SI-SDD-035 の提案3 と重なる**。同 spec-issue は未裁定であり、
       accepted されたらここへ合流させる（裁定点 D7）。
  7. **遡及しない**。schema 検証は新規に生成された synthesis から適用する。既存の
     SDD-REV-002〜005 は `schema_version` を持たないものとして検査対象外とし、
     遡及的に不整合としない（確認観点どおり）。

- **契約境界**:
  | 種別 | 対象 | 性質 |
  |---|---|---|
  | 変更 | `review-synthesis` JSON schema（`sdd-review` の公開成果物） | 既存4件は対象外にして加法的に運用 |
  | 加算 | `spec_inspect` の検査3種（未紐づけ P0/P1・`tracked_by` 幽霊参照・アーカイブ漏れ） | 加法的 |
  | 加算 | `findings[].id` の修飾形式・`carried_over[]`・`gate_preconditions[].kind` / `.basis` | 加法的 |
  | **不変** | `verdict` の算出式（`synthesis.md` Step 3 の閾値） | 変更しない |

- **代替案と却下理由**:
  1. **findings を個別ファイル（`.spec/reviews/findings/<REV>-SYN-NNN.md`）へ分離する** — 却下。
     21件のためにファイルを増やす割に得るものが少ない。エンティティであることはファイル分離を
     要求しない。件数が増えた段階で再検討する。
  2. **検査を `sdd_report` に置く**（提案4 の別案） — 却下。設計判断4 の理由。読取モデルに判定を
     持たせると Gate 通過がレポート生成の有無に依存する。
  3. **`review-synthesis.json` を廃止し番号付きのみにする** — 却下。「最新を見る」導線が失われる。
     ビューとして残すほうが移行コストが低い。
  4. **finding ID をレビュー内連番のまま、`tracked_by` 側で文脈を持たせる** — 却下。
     `SDD-REV-004:SYN-001` と `SDD-REV-006:SYN-001` を機械が区別できない。
  5. **持ち越しを人間の手作業に委ねる**（現状） — 却下。SDD-REV-006 は実際に手で追跡表を作ったが、
     その SDD-REV-006 自身がアーカイブされておらず次のレビューで消える状態にある。
     手作業は同じ失敗を繰り返した。

- **影響範囲・ロールバック**:
  - 影響: `sdd-review`（`SKILL.md` / `references/synthesis.md` / `assets/review-report.md`）、
    `sdd-core`（`spec_inspect.py` / `references/gates.md`）、関連テスト、bitz-sdd マニフェスト。
  - ロールバック: 検査は3種それぞれ独立に無効化できる。schema だけ残して検査を止めても
    成果物は壊れない（SI-SDD-031 の「検査だけ無効化して schema は残せる」に一致）。
  - 他プラグインへの波及: `sdd-review` を使うワークスペースのみ。

  > **訂正（2026-07-30、実装時の実測）**: 上記の波及範囲は「bitz-env / bitz-flow / bitz-ddd に
  > レビュー成果物は無いため、当面は bitz-sdd とルートだけが対象」と書いていたが**事実誤認**で
  > あった。実測では**全5ワークスペース**（ルート / bitz-sdd / bitz-ddd / bitz-env / bitz-flow）が
  > `review-synthesis.json` を持ち、bitz-sdd 以外の4件は一度もアーカイブされていなかった
  > （bitz-env に至っては `review_id` すら無い）。アーカイブ漏れ検査の導入で4件が検出されたため、
  > 実装時に4ワークスペースのレビューを番号付きへ退避した。SI-SDD-035 と同じく
  > **未検証の想定を設計ノートに書いた**もので、`basis: verified` / `assumed` の区別
  > （設計判断6）はまさにこの種の誤りを止めるための仕組みである。

- **実装順序**:
  1. **`review-synthesis.*` の「ビュー」への格下げ**（自前の `id:` を持たせない、または
     番号付きファイルへのポインタにする）。**これを先に済ませないとアーカイブできない** —
     実測（2026-07-30）で、`review-synthesis.md`（`id: SDD-REV-006`）を番号付きへコピーすると
     `spec_inspect` が `[重複] SDD-REV-006: IDが重複している` で **FAIL** する。
     `.spec/reviews/` は走査対象であり、既存の重複 ID 検査が正しく発火する
  2. `SDD-REV-006.*` のアーカイブ（1 の完了後に実施可能）
  3. `synthesis.md` の schema 固定と `sdd-review` SKILL.md の更新
  4. `spec_inspect` の検査3種を追加（アーカイブ漏れ → `tracked_by` 実在 → 未紐づけ P0/P1）
  5. `carried_over[]` の生成手順を `synthesis.md` に規定

  当初は「2 を先に単独実施してデータを保全する」としていたが、実測により 1 が前提であることが
  判明したため順序を入れ替えた。データ自体は git 履歴に保全されており緊急性はない。

- **Design Gate 入力（裁定を要する点）**:
  | # | 裁定点 | 選択肢 | 推奨 |
  |---|---|---|---|
  | D5 | findings の物理形 | JSON 内の配列のまま / 個別ファイルへ分離 | **配列のまま**（21件にファイル分離は過剰） |
  | D6 | 検査の置き場 | `spec_inspect` / `sdd_report` | **`spec_inspect`**（判定は Core が持つ） |
  | D7 | `gate_preconditions.basis` の必須化 | 必須化する（SI-SDD-035 と合流） / 本ノートでは扱わない | **必須化**（ただし SI-SDD-035 の裁定に従う） |
  | D8 | 既存レビューの扱い | SDD-REV-002〜005 を検査対象外 / 遡及して schema を揃える | **対象外**（確認観点どおり） |

- **Design Gate 裁定**: **2026-07-30・対話裁定で D5〜D8 すべて裁定済み**。裁定者 hide、
  裁定記録は `.spec/reports/decision-2026-07-30-design-gate-order6.md`。

  | # | 裁定 | 推奨との異同 |
  |---|---|---|
  | D5 | findings は JSON 内の配列のまま | 推奨どおり |
  | D6 | 検査は `spec_inspect` に置く | 推奨どおり |
  | D7 | `gate_preconditions.basis` を必須化する | 推奨どおり。**SI-SDD-035 提案3 の論点はここで決着** |
  | D8 | SDD-REV-002〜005 は検査対象外 | 推奨どおり |

  本ノートは裁定を受けて `draft → active`。実装は要件化（Plan フェーズ）から開始する。

  **1.2 での訂正（裁定後・2026-07-30）**: 裁定時点では「実装順序1（アーカイブ）は要件化を
  待たずに実施してよい」としていたが、実測でアーカイブが `review-synthesis.*` のビュー化を
  前提とすることが判明したため、実装順序を入れ替えた。**D5〜D8 の裁定内容は変わらない**
  （物理形・検査の置き場・`basis` 必須化・遡及範囲のいずれにも影響しない）。
