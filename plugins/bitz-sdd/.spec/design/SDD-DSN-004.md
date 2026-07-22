---
id: SDD-DSN-004
title: "単一スコープ委譲判定と実施記録欠落検出（spec_status 拡張）"
status: active
version: 1.0
updated: 2026-07-22
owner: claude
implements: SDD-FR-141, SDD-FR-142
origin: SI-SDD-015, SI-SDD-025
---

# SDD-DSN-004 単一スコープ委譲判定と実施記録欠落検出（spec_status 拡張）

## 背景 / 課題

SI-SDD-025 は「`accepted_unaddressed` がクロスワークスペース委譲済み spec-issue を
永久に未着手と誤報告する」と起票された。設計着手時の実測で前提を次のとおり補正する:

- **一括実行（`--workspace . plugins/*`）では誤報告は発生しない**。CORE-FR-012 実装済みの
  クロス WS origin 集約（`main()` が全 WS の `origin:` を集めて各 `collect()` に渡す）により、
  ルート SI-CORE-016/017/003 は委譲先 bitz-sdd の SDD-FR-120/121/001 の `origin:` 参照で
  既に「対応済み」と判定される（2026-07-22 実測: 一括実行のルート `accepted_unaddressed` は空）。
- **欠陥は単一スコープ実行時のみ**（例: `spec status .`）。スコープ外 WS の `origin:` を
  参照できないため、委譲済み 3 件が `['SI-CORE-003', 'SI-CORE-016', 'SI-CORE-017']` として
  誤報告される（2026-07-22 実測で再現）。SI-SDD-025 案1 の括弧書き
  「単体実行時は判定不能として据え置く」が本設計の実対象である。

SI-SDD-015 は独立の記録可読性の問題: origin 要件が verified に到達しても spec-issue 本文に
`- **実施**:` マーカーが無いと、判定は正しくとも issue 単体から実装根拠・PR・verified 要件が
読めない（実例: SI-FLW-001、およびルート SI-CORE-016/017/003 自身）。手順明文化
（SI-SDD-005）だけでは漏れが再発したため、機械警告で補強する。

両者は同じ `_accepted_issue_ids` / `accepted_unaddressed` 周辺を触るため co-design とする
（2026-07-22 人間裁定で両 issue accepted 化・同時設計を承認済み）。

## 設計判断

### 1. accepted spec-issue の分類を 3 値化する（SI-SDD-025）

`collect()` の accepted 判定を次の 3 分類に拡張する。優先順は上から:

1. **対応済み（従来どおり非表示）**: 本文に `- **実施**:` マーカーがある、または
   実行スコープ内のいずれかの WS の要件 `origin:` に ID の言及がある
2. **委譲済み・未解決（新設）**: frontmatter に `delegated_to:` があり、かつ 1 に該当しない
   — 新規加算フィールド `accepted_delegated_unresolved` に ID を計上し、
   `accepted_unaddressed` には**含めない**
3. **未着手（従来どおり）**: 上記いずれにも該当しない — `accepted_unaddressed` に計上

`delegated_to:` の書式は lifecycle.md 既定の `<ws>:<ID>` カンマ区切りを正とし、
値の解析は「フィールドの有無」判定に留める（委譲先ファイルの実在検証は spec_inspect の
管轄であり本ツールでは行わない — 読み取り専用・軽量照会の責務を維持）。

`next_actions` には `accepted_delegated_unresolved` が 1 件以上のとき
「委譲済み spec-issue が N 件未解決 — 委譲先ワークスペースを含む `--workspace` 一括実行で
判定するか、委譲先の要件化状況を確認する」を追加する。単一スコープの「判定不能」と
一括スコープの「委譲先が本当に未着手」の両方をこの 1 フィールドが表現する
（スコープにより意味が変わることを警告文言に含める）。

### 2. 実施記録欠落の機械警告 `completion_record_missing`（SI-SDD-015）

分類 1 のうち「origin 参照で対応済みと判定されたが、参照元要件の status が
verified / promoted で、issue 本文に `- **実施**:` マーカーが無い」ものを
新規加算フィールド `completion_record_missing` に計上する。

- `_origin_texts()` を（origin テキスト, 要件 status）のペア収集に内部変更する
  （関数は非公開ヘルパであり公開契約外）
- 警告は**読み取り専用**: `next_actions` に「実施記録の欠落が N 件 — 対象 issue に
  `- **実施**:`（参照要件 ID・PR 等）を追記する」と修正候補（要件 ID・status）を提示し、
  自動追記は行わない
- verified / promoted 未満（draft / approved / implementing 等）の origin 参照は
  警告しない（実装が完了していないため記録漏れではない）
- 新しい status・新しいマーカー語彙は追加しない（SI-SDD-005 の `- **実施**:` 固定書式を再利用。
  SI-SDD-025 案2 の新規「委譲実施」マーカーは不採用 — 語彙重複と書き忘れリスクの再生産を避ける）

両機構の合流点: クロス WS 委譲の完了は一括実行の origin 集約（既存機構）が判定し、
本警告が「委譲先で verified 済みなのに委譲元 issue に記録が無い」を人間に催促する。
機械判定の正しさ（025 = false-positive 除去）と issue 単体の可読性（015 = 記録の督促）を
分離したまま両立させる。

### 3. データ衛生（同一 PR で実施）

ルート `.spec/spec-issues/` の 3 件に確立済み書式で後付けする:

| ファイル | frontmatter 追加 | 本文追加 |
|---|---|---|
| SI-CORE-016 | `delegated_to: bitz-sdd:SDD-FR-120` | `- **実施**:` （PR #45・SDD-FR-120 verified） |
| SI-CORE-017 | `delegated_to: bitz-sdd:SDD-FR-121` | `- **実施**:` （PR #45・SDD-FR-121 verified） |
| SI-CORE-003 | `delegated_to: bitz-sdd:SDD-FR-001` | `- **実施**:` （SDD-FR-001 reverse-derived・verified） |

後付け後は単一スコープ実行でもルートの誤報告が消える（マーカー除外による）。
検証手順として「後付け**前**に新警告 2 種が実データで発火すること → 後付け**後**に
両方消えること」を PR の検証結果に記録し、恒久策の実効性を実データで実証する。

### 4. CORE-FR-012 の改訂（ルート WS・人間承認事項）

CORE-FR-012 v1.1 の第 1 節は「いずれの workspace の `origin:` にも言及が無い THEN
未着手として集計 SHALL」であり、分類 2（delegated_to 持ちを未着手から除外）は
この節への**例外追加**にあたる。v1.2 として非破壊的な例外節
「WHEN `delegated_to:` を持ち origin 参照が無い THEN `accepted_unaddressed` ではなく
`accepted_delegated_unresolved` に計上すること SHALL」を追記する（既存節は変更しない。
verified 要件の改訂につき人間承認と再検証が必要）。
bitz-sdd WS には SI-SDD-025 / SI-SDD-015 を origin とする新規要件 2 件を draft 起票し、
本設計の実装契約とする（Design Gate 通過後に起票）。

### 5. テスト先行の契約固定

`tests/test_spec_status.py` に fixture で次を固定する:

1. accepted + `- **実施**:` マーカー → どのフィールドにも計上しない（既存回帰）
2. accepted + 同一 WS origin 参照 → unaddressed に計上しない（既存回帰）
3. accepted + クロス WS origin 参照（一括実行）→ unaddressed に計上しない（既存回帰の明文化）
4. accepted + `delegated_to` あり・スコープ内 origin 参照なし（単一実行）→
   `accepted_delegated_unresolved` に計上し unaddressed に含めない（025 本体）
5. accepted + `delegated_to` あり・一括実行でも origin 参照なし → 同上＋next_actions 文言
6. origin 参照あり・要件 verified・マーカーなし → `completion_record_missing` に計上（015 本体）
7. origin 参照あり・要件 draft/approved/implementing・マーカーなし → 警告しない
8. origin 参照あり・要件 verified・マーカーあり → 警告しない
9. open / deprecated / superseded の spec-issue → いずれの新フィールドにも計上しない
10. JSON 既存フィールド（`accepted_unaddressed` ほか）のキー・型が不変（公開契約の回帰）

## 代替案と却下理由

- **`delegated_to` の委譲先を実際に辿って verified を確認する（SI-SDD-025 案1 原案）**:
  一括実行では既存の origin 集約が同じ結論をより単純に出せる。単一実行では原理的に
  辿れない。委譲先実在検証は spec_inspect の管轄で、軽量照会ツールへの越境になるため却下。
- **新規「委譲実施」マーカーの導入（SI-SDD-025 案2）**: 既存 `- **実施**:` が手動記録として
  既に機能しており語彙が重複する。人手記録依存は SI-SDD-015 が問題にした書き忘れを
  再生産する。SI-SDD-015 確認観点「固定語彙を再利用し新 status を追加しない」に反するため却下。
- **`completion_record_missing` の自動追記（自己修復）**: `.spec/` への書き込みは
  CORE-FR-012 / spec_status の読み取り専用契約に反するため却下。修正候補の提示に留める。
- **単一スコープ実行時に delegated_to 持ちを従来どおり未着手に計上し続ける（現状維持）**:
  AGENTS.md は本リポで一括実行を正規コマンドと定める（SI-CORE-023）が、spec_status.py は
  配布ツールであり、他プロジェクト・部分スコープでの単一実行は正当な使い方。恒常的な
  false-positive が「本当に未着手の accepted」を覆い隠す実害（SI-SDD-025 起票動機）が
  残るため却下。

## 影響範囲・ロールバック

- 実装: `skills/sdd-core/scripts/spec_status.py`（`collect()` / `_accepted_issue_ids` /
  `_origin_texts` / `next_actions`）
- 回帰テスト: `tests/test_spec_status.py`（fixture 追加）
- 規律文書: `skills/sdd-core/references/lifecycle.md`（完了記録と委譲判定の節を補強）
- 仕様証跡: 新規 SDD-FR 2 件（origin: SI-SDD-025 / SI-SDD-015）、CORE-FR-012 v1.2 改訂
  （ルート WS・人間承認）、SI-SDD-015 / SI-SDD-025 実施記録、STATE
- データ衛生: ルート `.spec/spec-issues/SI-CORE-016/017/003`（frontmatter + 本文追記のみ）
- 版管理: sdd-core スキル minor bump・bitz-sdd プラグイン minor bump（JSON 加算フィールド）

JSON 出力への変更は加算のみ（新フィールド 2 つ・next_actions 文言追加）で、既存フィールドの
キー・型・意味は`accepted_unaddressed` の false-positive 除去を除き不変。データ移行は不要。
ロールバックは spec_status.py・テスト・要件・データ後付けを同一 PR ごと revert すればよく、
旧挙動（単一スコープの誤報告あり）へ戻る。永続 DB・ネットワーク・認証情報は扱わない。
