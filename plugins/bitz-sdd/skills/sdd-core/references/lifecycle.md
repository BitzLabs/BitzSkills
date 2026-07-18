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

## 軽量レーンの verified 検証証跡

軽量レーンでは `.spec/specs/<feature>/test-spec.md` を必須としない。version 管理される
`.spec/STATE.md` の遷移記録を検証判定の正本とし、actor には次をすべて記録する:

- 対象リビジョン（commit SHA。未コミットなら base HEAD と working tree である旨）
- 秘匿情報を除いた実行コマンド、収集した期待件数、成功・失敗・スキップ件数、終了コード
- release_check / spec inspect 等の機械チェック結果と実行日
- スキップがある場合は、各理由と要件または検収規律が許容する根拠

失敗・中断・結果欠落・期待件数不一致・未許容スキップが1件でもあれば verified へ遷移しない。
PR がある場合は秘匿情報を除いた実出力を PR 本文にも記録し、STATE.md と不一致なら STATE.md を
正として PR を訂正する。verified 後に PR を提出・更新した場合も reviewer が再照合し、不一致が
解消するまでマージしない。PR がない場合は STATE.md だけで検証結果を再判定できなければならない。

token・credential・その他の秘密値は、STATE.md と PR 本文を含む version 管理証跡へ記録しない。
秘密値を含み得る引数はプレースホルダー化し、完全ログが必要なら安全な CI run または保護ログへの
参照だけを残す。通常フローは従来どおり `.spec/specs/<feature>/` にテスト仕様を記録する。
本規律は導入後の遷移に適用し、既存の verified 要件へ証跡の遡及追加を要求しない。

## verification_method の語彙補足

統制語彙と green 定義の正は `verification.md` とする。`unit-test` は自動ユニット／回帰テストを、
`example-test` は有限の入出力例を表す。`unit-test` は bitz-sdd 1.11.4 以降で利用可能であり、
既存の `example-test` 要件は遡及変更しない。

## 採番規則 — 仕様フェーズのみ・直列

- プレフィックスは型分類 `FR` / `NFR` / `CON` で**起票時に凍結**。type フィールドは持たない（二重管理禁止）
- domain・priority 等の他属性はすべて frontmatter（可変）。domain は domains.md の統制語彙のみ
- ID払い出しは Plan フェーズ（直列区間）でのみ行う。採番・雛形生成は `scripts/spec_scaffold.py`
  が担い（プレフィックスの既存最大番号 + 1 を決定的に採番。spec_inspect PASS の雛形を生成）、
  手書きの採番・書式ブレを排除する（CORE-FR-004）
- **実装中の並列エージェントは採番禁止**。新要件の発見は spec-issue（仮番号 `SI-<branch>-<n>`）で起票し、人間裁定時に正式IDへ変換する。これで採番衝突は構造的にゼロ

## status 遷移の実行 — スクリプトによる権限強制

status 遷移は上表の権限マトリクスを `scripts/spec_update.py` がコードで強制する（CORE-FR-005）:

```bash
python3 scripts/spec_update.py <workspace> <ID> --to <status> [--by-human] [--actor 名前]
```

- **人間専用遷移**（draft→approved / open→accepted / verified→promoted / 任意→deprecated）は
  `--by-human` の明示がない限り拒否される
- **エージェント許容遷移**（approved→implementing / implementing→verified 等）は無フラグで適用
- **権限マトリクス未定義の遷移**は誰の権限でも拒否（不正遷移）
- 遷移適用時に対象 frontmatter の `status` を書き換え、`.spec/STATE.md` に
  遷移記録（対象 ID・旧→新 status・実行主体）を追記する

## spec-issue のライフサイクル補足

spec-issue の状態遷移は要件と別建てで、`spec_update.py` の `TRANSITIONS["spec-issue"]` が正:

```
[*] → open → accepted → (実施) → 要件化 or 軽量レーンで反映済み
              │
              └→ superseded（重複解消。人間専用）
            open → rejected
```

- `open → accepted` / `open → rejected` は人間専用（sdd-issue の推薦を受けて人間が裁定）
- `accepted → superseded` も人間専用。重複が判明した spec-issue を統合先へ寄せて正式クローズする
  ときに使う。`superseded_by:` frontmatter への統合先 ID 記入は人間が手動で行う
  （`spec_update.py` は status 行のみを書き換え、他 frontmatter には触れない）

### 完了記録の語彙統一（CORE-FR-012 検知との対応）

spec-issue が実際に実装された時点（軽量レーンでの直接反映、または要件化パスで対応する
requirement が `verified` に達した時点）で、当該 spec-issue 本文に
`- **実施**: <日付> <根拠>` を追記する。この語彙は固定とし、「実装完了」等の類義語は使わない
（`spec_status.py` の accepted 未着手検知（CORE-FR-012）は `**実施**:` の固定パターンでのみ
完了を検知するため、表記ゆれがあると誤検知の原因になる）。

### origin: の限界

要件の `origin:` frontmatter は**初回起票元の spec-issue のみ**を記録する構造的な割り切りで、
後続の改訂・追加起票を追跡しない。ある要件を後から改訂した spec-issue がある場合、その記録先は
`origin:` ではなく**改訂側の spec-issue 本文の `**実施**:` マーカー**で行う。CORE-FR-012 の
未着手検知が `origin:` と実施マーカーの両方を突き合わせる設計になっているのはこのため
（`origin:` だけでは改訂の実施記録を追えない）。

## 改訂 vs 継承の判定 — 「緑を赤にし得るか」

要件を変更したいとき、判定基準はこの1つだけ:

> その変更は、既存の green なテストを red にし得るか？

- **No**（明確化・誤字・等価な書き直し）→ 同一IDで `version:` を bump（1.0→1.1）。Revision History に1行追記
- **Yes**（受入基準の意味的変更）→ **supersede**。新IDを起票し、旧IDに `status: deprecated` + `superseded_by:`、新IDに `supersedes:` を記入

IDは「契約の同一性」を指す。意味が変わったのに同じIDを使うと「このテストはどの契約に対して緑だったか」の履歴が壊れる。

## 変更伝播（再伝播プロトコル）

変更の入口は2系統。どちらも同じ5ステップで処理する。

- **(a) 要件起点** — 要件が bump / supersede された: `--impact FR-012` で依存成果物を列挙
- **(b) docs 起点** — 人間が active な docs/ 文書を改訂した: `--impact-docs docs/…` で `derived_from` を逆引きし、派生要件（記録 SHA と現行 SHA の乖離）を列挙

```bash
python scripts/spec_inspect.py <repo-root> --impact FR-012
python scripts/spec_inspect.py <repo-root> --impact-docs docs/02-design/ARCHITECTURE.md
```

### 5ステップ

1. **intake** — 変更内容・種別（要件起点/docs 起点）・docs のコミット SHA を STATE.md に記録する
2. **候補列挙（決定的）** — 上記コマンドで影響候補を機械列挙する。**グラフは候補を提案するだけ**で、影響の確定はしない
3. **判定パス** — 各候補について「上流参照（derived_from / implements / refs）は変更後も依然成立するか」を個別に判定し、候補集合を**拡張または縮小**する。判定と理由を STATE.md に記録する
4. **人間確認** — 確定した影響集合を提示し裁定を受ける。要件の意味的変更を伴うなら「緑を赤にし得るか」基準で bump / supersede を人間が裁定する（エージェントは spec-issue 起票まで）
5. **最小再実行** — 確定した影響成果物**のみ**に `stale: <ID>@<新version>`（docs 起点は `stale: docs/…@<新SHA>`）を付与し、取り込み更新が済んだものから外す。各更新の before/after 要約を STATE.md に記録する（可逆性の担保）

**stale が1つでも残る feature は verified に進めない。** 影響が広範囲（3ファイル以上の docs/ 改訂等）に及んだ場合は、整合確認として `sdd-review` の consistency 観点を実行する。

### 再伝播の原則

- **最小再実行** — 変更が届かない成果物には触れない。過剰伝播（無関係な更新）も過少伝播（依存の見落とし）も判定パスで防ぐ
- **可逆性** — すべての再実行は before/after が STATE.md から追えること
- **人間チェックポイント** — 影響集合の確定と要件改訂の裁定は人間を通す。機械列挙だけで書き換えを始めない

## deprecated 要件のテスト — tombstone 方式

supersede された要件のテストは即削除せず `@tombstone(FR-012, superseded_by=FR-045)` タグで skip 化する。後継テストが green になったことを人間が確認した後、Promotion Gate のチェック項目として物理削除する。regression 検出力を失う瞬間を無自覚に作らないため。
