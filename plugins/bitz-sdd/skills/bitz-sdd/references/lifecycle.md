# 要件ライフサイクル・ID・変更管理

## 状態遷移

```
[*] → draft → approved → implementing → verified → promoted
                 ↓            ↓ (中断で approved に戻る)
             deprecated ← verified / promoted (supersede)
```

| 遷移 | トリガ | 実行権限 | 副作用 |
|------|--------|----------|--------|
| → draft | 起票 | 人間 / planエージェント | `_counter.md` からID払い出し |
| draft → approved | 承認 | **人間のみ** | spec-lint 合格 + verification_method 記入が前提 |
| approved → implementing | tasks/ に `implements:` 出現 | planエージェント | traceability matrix に行追加 |
| implementing → verified | 全検証 green + stale ゼロ | 機械判定 | matrix 緑化 |
| verified → promoted | Promotion Gate | **人間のみ** | docs/ 更新・アーカイブ（references/gates.md） |
| * → deprecated | 廃止 or supersede | **人間のみ** | `superseded_by:` 記入、テストは tombstone 化 |

**不変条件**: implementing 以降の要件のEARS節は書き換え不可。

## 採番規則 — 仕様フェーズのみ・直列

- プレフィックスは型分類 `FR` / `NFR` / `CON` で**起票時に凍結**。type フィールドは持たない（二重管理禁止）
- domain・priority 等の他属性はすべて frontmatter（可変）。domain は domains.md の統制語彙のみ
- ID払い出しは Plan フェーズ（直列区間）でのみ `_counter.md` を read→increment→commit
- **実装中の並列エージェントは採番禁止**。新要件の発見は spec-issue（仮番号 `SI-<branch>-<n>`）で起票し、人間裁定時に正式IDへ変換する。これで採番衝突は構造的にゼロ

## 改訂 vs 継承の判定 — 「緑を赤にし得るか」

要件を変更したいとき、判定基準はこの1つだけ:

> その変更は、既存の green なテストを red にし得るか？

- **No**（明確化・誤字・等価な書き直し）→ 同一IDで `version:` を bump（1.0→1.1）。Revision History に1行追記
- **Yes**（受入基準の意味的変更）→ **supersede**。新IDを起票し、旧IDに `status: deprecated` + `superseded_by:`、新IDに `supersedes:` を記入

IDは「契約の同一性」を指す。意味が変わったのに同じIDを使うと「このテストはどの契約に対して緑だったか」の履歴が壊れる。

## 変更伝播（impact 分析）

要件が bump / supersede されたら必ず実行:

```bash
python scripts/spec_inspect.py <repo-root> --impact FR-012
```

`implements:` / `refs:` / 本文参照で FR-012 に依存する全成果物が列挙される。各成果物に `stale: FR-012@<新version>` マークを付け、取り込み更新が済んだものから外す。**stale が1つでも残る feature は verified に進めない。**

## deprecated 要件のテスト — tombstone 方式

supersede された要件のテストは即削除せず `@tombstone(FR-012, superseded_by=FR-045)` タグで skip 化する。後継テストが green になったことを人間が確認した後、Promotion Gate のチェック項目として物理削除する。regression 検出力を失う瞬間を無自覚に作らないため。
