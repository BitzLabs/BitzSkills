# 検証体系（三層）

## L1: 仕様の検証（spec-lint） — draft→approved の前提条件

1. **EARS構文**: 各受入基準は `WHEN <単一トリガ> THEN <システム> SHALL <単一の観測可能な応答>`。1文に複数トリガ/複数SHALLの混在禁止
2. **測定不能語の検出**: `_lint-rules.md` の禁止語辞書（「高速に」「適切に」「十分な」等）。検出時は数値・閾値への書き換えを要求
3. **verification_method 必須**: 空の要件は approved に進めない
4. **構造検証**: spec_inspect.py（孤児・幽霊・重複/欠番・未登録ドメイン）

機械化できない「意図に合っているか」は人間の approved 承認が担う。だから approved は人間専権。

## L2: コードの検証 — verification_method 統制語彙

全要件の frontmatter に必須。この語彙以外は使わない:

| 値 | 主な対象 | green の定義 |
|----|----------|-------------|
| `pbt` | FR（不変条件を持つロジック） | property が規定ケース数を通過 |
| `example-test` | FR（入出力例が有限） | EARS 1文 = 1テストで全通過 |
| `unit-test` | FR（自動ユニット／回帰テスト） | 収集した対象テストが全通過し、未許容スキップがゼロ |
| `benchmark` | NFR-性能 | 要件本文に明記した数値閾値（p95等）内 |
| `sast` / `dep-audit` | NFR-セキュリティ | 該当ルール違反ゼロ |
| `load-test` | NFR-可用性/容量 | 明記した負荷条件下でエラー率が閾値内 |
| `manual-check` | 自動化が割に合わないもの | 要件内に列挙した手順を人間が実施し記録 |

`benchmark` / `load-test` を選んだ要件は本文に**数値閾値の明記が必須**（lint対象）。`manual-check` は濫用されやすいため metrics.md で比率を監視し、20%超で見直す。

`unit-test` は bitz-sdd 1.11.4 以降で利用できる。有限の入出力例そのものを受入基準にする
`example-test` と、自動化された単体・回帰テスト群を検証手段として宣言する `unit-test` を区別する。
既存要件の `example-test` は有効なままとし、遡及変更しない。固定している bitz-sdd が 1.11.4
未満のワークスペースでは `unit-test` を使用せず、先にプラグインを更新する。

## テスト作成規則

- テスト名またはタグに要件IDを含める（例: `test_FR012_token_expiry`）。traceability の証跡になる
- PBT を書くときは EARS の SHALL 節を property（不変条件）に翻訳し、specs/<feature>/ のマッピング表に対応を記録する
- tombstone テストには `@tombstone(旧ID, superseded_by=新ID)` を付けて skip

## L3: プロセスの検証 — traceability matrix

Verify フェーズで spec_inspect.py を実行し `inspection-report.md` を生成。green の定義:

- approved 以降の全要件が「≥1タスク ∧ verification_method に応じた ≥1検証」で覆われている
- 幽霊参照ゼロ、stale マークゼロ

レポートは人間に提示する。機械判定を上書きしない（人間も上書きしない — 例外は仕様変更として正規の手続きへ）。
