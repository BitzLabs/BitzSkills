# ルール：適応・再伝播エンジン (adapt-change)

`/product:adapt-change`のリファレンスである。このエンジンは変更を受け取り、`work/traceability.json`から影響範囲を計算し、人間（または`--auto`）に確認を取り、影響を受けるSkill**のみ**を再実行し、一貫性をチェックする。原則は**最小限の再実行**であり、変更が及ばないSkillには決して触れない。

## `work/traceability.json` — エッジストア

すべてのSkillは最終ステップとしてここに自身のIDを追記するため、エンジンはこの1つのファイルのみを読み取ればよい。

```jsonc
{
  "schema_version": 1,
  "nodes": [
    { "id": "FEAT-012", "type": "feature", "title": "...", "skill": "define-features",
      "source_file": "reports/02_spec/feature-list.md",
      "upstream": ["JOB-003", "JNY-005", "NSM-001"] }
  ]
}
```

`upstream`はノードが派生する元のノードを指す。**ダウンストリーム**方向（誰が私に依存しているか）は`upstream`の逆であり、伝播が従う方向である。

## エンジンのステップ (design.md §7.2)

1. **Intake（取り込み）** — 変更を`change-log.md`に記録する（説明、`--type`、渡されたタイムスタンプ）。
2. **Candidate blast radius（候補となる影響範囲） (deterministic)** — 変更が直接触れるノードを見つけ、`upstream`エッジを逆にたどることでその**downstream transitive closure（ダウンストリームの推移的閉包）**を計算する。これは純粋なグラフ作業であり、まだ判断は行わず、候補を提案するのみである。
3. **Judgment pass（判断パス） (opus)** — 各候補を調べ、変更があったにもかかわらずそのアップストリームの参照が*まだ有効か*どうかを決定し、セットを**拡大または縮小**する。グラフが提案し、判断パスが決定する。「変更 → 影響を受けるID → 再評価の要否 + 理由」を`impact-analysis.md`に記録する。
4. **Human confirmation（人間の確認）** — 確定した影響セットを`AskUserQuestion`経由で提示する（`--auto`の場合はスキップされる）。
5. **Minimal re-run（最小限の再実行）** — 確定した影響を受けるSkillのみを再実行し、既存の成果物を入力として与え、`traceability.json`の対応するエッジを更新する。
6. **Coherence check（一貫性チェック）** — `review`（一貫性およびトレーサビリティの観点）を実行し、再伝播によって導入された矛盾を捕捉する。

## 原則 (§7.3)

- **Minimal re-run（最小限の再実行）** — 推移的閉包と判断の組み合わせにより、行き過ぎ（影響を受けないSkillに触れること）と不十分（真の依存関係を見逃すこと）の両方を防ぐ。
- **Reversibility（可逆性）** — `change-log.md`は再実行されるすべての成果物の変更前後の差分サマリーを記録するため、変更を理解し元に戻すことができる。
- **Human checkpoint（人間のチェックポイント）** — いかなる成果物も書き換えられる前に、影響セットが確認される（`--auto`の場合を除く）。
- **Idempotent edges（べき等なエッジ）** — 再実行後、`traceability.json`は新しい現実を反映する。同じ変更を再実行しても何も起こらない（no-op）。

## 変更タイプ

`--type=constraint | market | competitor | tech | regulation`は、変更がグラフのどこに入力されるかのヒントとなる（例：`constraint` → `CON-`/`SCP-`、`market`/`competitor` → 市場状況/ポジショニング、`regulation` → 制約/NFR）。このヒントはステップ2の「直接触れる」セットの種となる。

## 情報源

- design.md §7（このPluginの適応エンジン仕様）
