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

Verify フェーズで spec_inspect.py を実行する。単独・締め工程では `inspection-report.md` を生成し、
並列PR・worktreeでは `--check-only` によりレポートを変更せず同じ判定を得る。green の定義:

- implementing 以降の全要件が「≥1タスク ∧ verification_method に応じた ≥1検証」で覆われている
- approved でタスク未紐付けの要件は実装待ちWARNとして可視化される（単独ではFAILにしない）
- 幽霊参照ゼロ、stale マークゼロ

### 「テスト/実装からの参照」の判定範囲

要件 ID の参照は次の範囲から集める:

| 走査対象 | 対象ファイル | 幽霊参照判定 |
|---|---|---|
| `.spec/specs`・`.spec/tasks`・`tests`・`test`・`src` | 文書とコード | 対象 |
| `scripts`・`hooks`・`skills/<name>/scripts` | **コードのみ**（`SKILL.md` 等は数えない） | 対象外 |

実装コードを追加対象としたのは、`src/` 以外へ実装を置く構成でもトレースを拾うため。
これらのコードは docstring や `--help` に使用例としての ID を書くため、幽霊参照の
判定には使わない（SDD-FR-147）。

モノリポで `--workspace . plugins/*` のように複数ワークスペースを同時検査すると、
テストがリポジトリルートの `tests/` に集約されていても、参照はグローバル ID で
集約され所有ワークスペースの要件へ還流する（SDD-FR-146）。単一ワークスペース検査では
集約しない。`verification_method: manual-check` の要件はテスト参照が原理的に生じないため、
未参照の報告を専用の見出しへ分けて表示する（SDD-FR-148）。

### 検証証跡（`.spec/verification/`）

green 判定の根拠は、実行のたびに手で書き写す数値ではなく、コマンド実出力から生成した
機械可読証跡を正とする（SDD-FR-151）。証跡は `sdd-test` の `spec_verify.py record` が書き、
`spec_inspect.py` が検査する:

| 区分 | 項目 | 扱い |
|---|---|---|
| 安定項目 | schema / command_id / command / commit / recorded_at / tool / exit_code / counts / requirements | 一致判定の対象 |
| 観測値 | `observed.duration_seconds` | 非正規。再実行で変動するため判定に使わない |

- 1 実行 = 1 ファイル（`<command-id>--<commit短縮>.json`）。同一 commit・同一 command-id の
  再実行は同じファイルを上書きするため冪等で、実行時間の揺れだけでは diff が出ない
- raw stdout/stderr・環境変数・秘密値・実行者のホームパスは保存しない（SDD-FR-152）
- `spec_inspect.py` の判定（SDD-FR-153）: schema 不正・必須キー欠落・非ゼロ終了・
  failed 件数・参照切れは **FAIL**。HEAD と違う commit の証跡、証跡が無い verified 要件は
  **WARN** に留める。`.spec/verification/` を持たないワークスペースは従来どおり無検査
- `manual-check` の要件は自動証跡が生じないため、証跡欠落の WARN 対象から外す

レポートは人間に提示する。機械判定を上書きしない（人間も上書きしない — 例外は仕様変更として正規の手続きへ）。
