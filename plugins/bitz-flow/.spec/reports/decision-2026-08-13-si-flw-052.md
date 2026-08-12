# 裁定記録 — SI-FLW-052（宣言と実体の乖離を機械検証で塞ぐ）

- **日付**: 2026-08-13
- **裁定者**: hide
- **対象**: `SI-FLW-052`
- **提示方法**: issue の推薦つき選択肢に、実測で判明した実行不能性（下記 1.）を加えて提示し、選択を得た
- **前提**: `FLW-REV-013`（独立5観点レビュー・FAIL 2.31）。
  先行して `SI-FLW-047` / `048`、`049` / `055`、`050`、`051`、`053` を裁定済み。
  **本 issue の検査群には、それら6裁定すべてから検査項目が流れ込む**
- **裁定方針（裁定者の明示）**: **v2 へ向けた設計段階であり、手戻りを許容して
  最善かつシンプルな構成を採る**（先行5裁定と同一方針）

## 裁定

**accept。** 選択は次のとおり。

| 論点 | 裁定 |
|---|---|
| 順序制約 | **accept（新案 — 2段階に分ける）** — issue の「全検査を文書修正前に構築」は実行不能なため、検査を2群に分けて段階化する |
| 実装場所 | **accept** — **汎用検査は bitz-sdd の `spec_inspect` へ、bitz-flow 固有の定数照合はリポジトリ側（`release_check.py` / `tests/`）へ**分ける |
| 既知乖離の扱い | **accept** — **件数付きの既知例外リスト**へ登録して CI を green に保ち、文書改訂で1件ずつ外す。**リストへの新規追加は禁止**する |

## 検証で確認した乖離（2026-08-13、実測）

| 乖離 | 実測値 |
|---|---|
| `M2-FLT` の範囲 | fixture 実数 **49件**。`FLW-DSN-016:651` は `049`、`ROADMAP.md:158` と `FLW-DSN-014:649` は **`044`** |
| quarantine 解除区分数 | 本文 `:399`「3区分」／ §6 の表 **4行** ／ §15「4区分」／ fixture `:583`「3区分」 |
| M2 出口条件の「正」 | `ROADMAP:155` → `FLW-DSN-014` ／ `FLW-DSN-014:634` →「下記を正とする」／ 同 `:640` →「**正は `FLW-DSN-016`**」／ `FLW-DSN-016:645` →「`FLW-DSN-014` の M2 行を改訂する」＝ **循環参照** |
| `REC-*` 識別子 | 2系統。`REC-WT-RESUME` 未定義（`SI-FLW-049` の裁定で `REC-RM-DELETE` も別名と判明し統一済み） |
| 状態語の表記 | `FLW-FR-007:21` は `active` / `merged-exact` / `remote-advanced` / `worktree-in-use` / `orphan`（**小文字**）。設計 §2 は大文字閉集合 |
| `guard_identity_kind` | `skills/flow-core/references/output-contract.md:102` は **5値のまま**（`index` / `local-ref` / `remote-tracking-ref` / `fetch-head` / `remote-ref`）。設計 §2 は7値 |

### issue の記述より深刻だった1件

`guard_identity_kind` は第4のコピーが古いだけでなく、**設計文書が自己矛盾している**。

- `FLW-DSN-016:94` — 7値を列挙
- `FLW-DSN-016:161` — 「`guard_identity_kind` と `flowlib/guard.py` の `GUARD_IDENTITY_KINDS` は
  **いずれも5種である**」
- `FLW-DSN-016:684`（§14）— 「5種 → 7種（schema ＋ `guard.py`）」を変更予定として記載

`:161` は変更前の記述が残ったままである。**同一文書内の矛盾であり、文書間の照合では捕まらない。**
検査の設計に「同一文書内での閉集合の再宣言」を含める必要がある。

## 1. 順序制約 — 2段階に分ける

issue の提案5は「上記検査を `SI-FLW-047`〜`051` の裁定後・**文書修正前**に構築する」だが、
**検査は2種類に分かれ、後者は文書修正前には構築できない。**

### 第1群 — 現行構造に対して今すぐ書け、今 FAIL する検査

**文書修正の前に構築する**（issue の趣旨をここで満たす）。

- `M2-FLT` の範囲（fixture catalog を SSOT とし `ROADMAP.md` / `FLW-DSN-014` を照合）
- quarantine 解除区分数（区分表を SSOT とし本文・§15・fixture を照合）
- `REC-*` 識別子（**定義の実在**と**参照の解決**を双方向で検査）
- enum 値（**要件層を三者照合の対象へ含める**。現在は設計・schema・実装のみ）
- **同一文書内での閉集合の再宣言**（`guard_identity_kind` 型の自己矛盾）
- 「正」の一意性（同一事項に「正はこの文書」が複数あり相互に指し合う場合を検出）
- **裁定記録の実在照合**（「確定」「裁定済み」と主張する記述に対応する `decision-*.md` があるか。`SI-FLW-053`）
- **設計 ↔ verified 制約の違反照合**（`FLW-CON-001` 型。`SI-FLW-051`）
- **設計 ↔ 出荷済み catalog の5項目照合**（`operation` / `class` / `approval` / `retry` / `recovery`。`SI-FLW-055`）
- 残債移送の記録と受け側 budget 増分の照合（`SI-FLW-053`）
- 跨ワークスペース参照値の照合（bitz-sdd ROADMAP の bitz-flow budget 参照値。`SI-FLW-053`）

これらが**現在の乖離を実際に検出すること**（構築時点で FAIL すること）を確認する。

### 第2群 — 改訂後の構造が存在しないと書けない検査

**該当文書の改訂と同一 PR で構築する。**

- **mutating step → 宣言 mutation target の全射性**（`SI-FLW-048`。step の型分離が未実装）
- **class の2軸と4値導出値の一致**、M2 出口の公開集合が class から導出できること（`SI-FLW-049`。まだ4値のみ）
- **判定述語（決定表）の三者照合**（`SI-FLW-050`。決定表が未執筆）
- **中断状態の網羅性**（`SI-FLW-047`。証跡軸が未導入）

第2群を「文書修正前」に構築することは原理的に不可能である。
検査と対象構造を同一 PR で入れることで、**改訂が「構成上正しい」状態で完了する**という
issue の目的は達成される。

## 2. 実装場所 — 汎用と固有で分ける

### bitz-sdd の `spec_inspect` へ入れる（汎用 — SDD の規律そのもの）

- 裁定記録の実在照合
- 「正」の一意性検査
- 設計 ↔ verified 制約の違反照合

これらは bitz-flow 固有ではなく **SDD ワークフローの規律**であり、
全ワークスペース（root / bitz-ddd / bitz-env / bitz-sdd / plugin-creator / skill-creator）に効かせるべきである。
bitz-flow だけに入れると、他ワークスペースで同じ欠陥が沈黙し続ける。

**コスト**: bitz-sdd の新版リリースと、本リポジトリが消費する固定版の更新が必要
（`.spec/PROJECT.md` の pin と `scripts/spec` の解決対象）。**別 PR・別ワークスペースとして扱う。**

### リポジトリ側（`scripts/release_check.py` / `tests/`）へ入れる（bitz-flow 固有）

- `M2-FLT` の範囲、quarantine 区分数、`REC-*`、`guard_identity_kind` 型の自己矛盾
- 設計 ↔ 出荷済み catalog の5項目照合
- 残債移送・跨ワークスペース参照値
- 第2群のすべて（class 2軸・step 全射性・判定述語・中断状態網羅性）

既存の `release_check.py` は「実装側定数を SSOT とし HTML コメントマーカーで文書側の可読表と
照合する」機構を持ち、対訳辞書・フェーズ語彙・同期マッピングで実績がある。同じ機構を流用する。

**検査は新規の設計文書・fixture を登録なしで対象に含めること**
（`tests/test_skill_script_reference.py` の動的収集と同じ方式）。

`scripts/` の共有スクリプトを変更するため、**全 pytest スイートの実行が必要**。

## 3. 既知乖離の扱い — 件数付きの既知例外リスト

検査を追加した時点で上記の乖離は FAIL する。文書改訂は `SI-FLW-053` が別枠計上した
設計再整備（3 PR / 9 session）で行うため、その間 CI を red にし続けることはできない。

- 現在の乖離を**件数付きの既知例外リスト**へ登録し、CI を green に保つ
- **リストへの新規追加を禁止する**（検査自体がリストの増加を FAIL とする）。
  これにより新規の乖離は即 FAIL になり、既知分だけが猶予される
- 文書改訂で**1件ずつリストから外す**。**残件数が進捗の機械指標**になる

`warning` として入れて後で `error` へ昇格する案は採らない。昇格を忘れれば検査は永久に沈黙し、
`FLW-REV-012` と同じ失敗形式（宣言はあるが効いていない）を再生産するためである。

## 根本原因の確認

`FLW-REV-012`（自己レビュー 3.62）と `FLW-REV-013`（独立 2.31）の差 **+1.31** は、
「対応した」という宣言を検証せずに受け入れる工程が機能していないことの実測値である。

本裁定の一連（`SI-FLW-047`〜`055`）でも、同じ工程が**3回**再現した。

1. `SI-FLW-053` 本文が裁定記録の無い値を「裁定済み」と記載
2. `decision-2026-08-13-si-flw-047-048.md` がその値を確定値として引用
3. `FLW-DSN-014:669` が、裁定記録が「含まれない」と明記するものを「確定」と記載

**第1群の「裁定記録の実在照合」があれば3件とも自動検出できた。**
これが第1群を文書修正より先に構築する最大の根拠である。

## 波及と次の作業

- `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py` — 汎用3検査（**別 PR・別ワークスペース**）
- `plugins/bitz-sdd` の版更新と、本リポジトリの固定版 pin の更新（**別 PR**）
- `scripts/release_check.py`・`tests/` — bitz-flow 固有の検査と第2群
- `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`・`FLW-DSN-014.md`・`ROADMAP.md`・
  `plugins/bitz-flow/.spec/requirements/FLW-FR-007.md` — マーカー付与と値の統一
- `plugins/bitz-flow/skills/flow-core/references/output-contract.md` —
  `guard_identity_kind` の5値→7値（**出荷済み reference の変更**。M1 の compatibility key に
  `skill` が含まれるため qualification への影響を改訂時に確認する）

`SI-FLW-052` は bitz-sdd の `SI-SDD-042`（レビュー指摘の受領検証）と同型の問題であり、
**そちらの裁定結果と整合させる**。

## 未解決として次へ送る論点

| 論点 | 送り先 |
|---|---|
| `output-contract.md` の値更新が qualification に影響するかの判定 | 改訂 PR 時（compatibility key の再確認） |
| bitz-sdd 側3検査の実装と版更新 | 別 PR（bitz-sdd ワークスペース） |
| `SI-SDD-042` との整合 | bitz-sdd の裁定時 |
