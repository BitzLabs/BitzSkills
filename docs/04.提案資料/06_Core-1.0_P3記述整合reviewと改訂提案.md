# Core 1.0 P3記述整合レビューと改訂提案

**状態**: **Closed（P3 6件裁定・反映済み）**

**作成日**: 2026-08-31

**裁定日**: 2026-08-31

## 1. 目的

P2残存運用契約レビューを反映した正本を対象に、既存決定を変更しない記述、JSON例、用語の
同期漏れを確認した。レビュー03の旧P3 5件は裁定済みであり、本書はその後に残った別の6件を扱う。
現在の正本は`docs/02.設計書`と`docs/03.詳細設計`であり、本書の例だけを実装根拠にしない。

## 2. P3指摘

### 2.1 TASKの要約が規範文なしTECHを含まない

TASKの型制約とverify契約は規範文なしTECHの文書IDを`addresses`対象として許可していたが、
最小トレース図、Contextの関係説明、`implement`閉包の要約は規範文だけを対象としていた。

### 2.2 warning結果のJSON例に原因がない

共通結果、Context、doctor、モノレポの例に、`status: passed_with_warnings`でありながら
対応するDiagnosticまたは対象別warningがない例が残っていた。

### 2.3 `check`結果例に`revision.base`がない

Git基準版の契約は`check`結果へ`revision.base`を記録すると定めていたが、共通結果の`check`例には
`revision`自体がなく、ADR-025反映後の外形を示していなかった。

### 2.4 SHA-256の例と入力形式が曖昧

Context Digest、Projection Digest、`semanticHash`、`fileHash`の例は16桁の短縮値であり、
`--expect-digest`も`<hex>`とだけ記載していた。SHA-256の正規出力と入力形式を例から判断できなかった。

### 2.5 レポートファイル名の表記が一致しない

レポート名が`<timestamp>`、`<UTC basic timestamp>`、一意なUTC timestampと複数の表現になっていた。
同名時に連番を付ける規則は存在したが、ファイル名の正規形に現れていなかった。

### 2.6 Diagnostic表の列名がJSONフィールド名と一致しない

Diagnostic一覧の列名が`result status`である一方、必須JSONフィールドは`resultStatus`であり、
表の値が実行時フィールドへ直接対応することが読み取りにくかった。

## 3. 裁定

| 項目 | 裁定 | 対応 |
|---|---|---|
| TASK要約 | 採用・反映済み | 最小トレース、Context関係説明、`implement`閉包へ規範文なしTECHを追記 |
| warning結果例 | 採用・反映済み | ContextとdoctorへDiagnosticを追加し、単純な共通例とモノレポ例は`passed`へ変更 |
| `check`の`revision` | 採用・反映済み | 共通結果例へ`base`、`commit`、`dirty`を追加 |
| SHA-256表記 | 採用・反映済み | `sha256:[0-9a-f]{64}`を正規形とし、CLI文法、JSON例、試験条件を同期 |
| レポート名 | 採用・反映済み | `<YYYYMMDDTHHMMSSZ>-<operation>[-<sequence>].json`へ統一 |
| `resultStatus`列 | 採用・反映済み | Diagnostic一覧6表の列名を必須JSONフィールド名へ統一 |

既存決定の意味を変更せず正本の同期だけを行うため、新規ADRは作成しない。

## 4. 主な反映先

- `02.設計書/01_共通アーキテクチャ.md`
- `02.設計書/02_specディレクトリ仕様.md`
- `02.設計書/03_CLI統合設計.md`
- `02.設計書/08_実装ロードマップ.md`
- `03.詳細設計/01_EARS-AI規格/06_AST・パーサー仕様.md`
- `03.詳細設計/02_SPECファイル規定/06_参照・トレース・検証仕様.md`
- `03.詳細設計/02_SPECファイル規定/07_更新・互換性・安全性.md`
- `03.詳細設計/02_SPECファイル規定/08_Markdown本文構成・スタイル.md`
- `03.詳細設計/02_SPECファイル規定/10_Context Resolution仕様.md`
- `03.詳細設計/02_SPECファイル規定/11_doctor仕様.md`
- `03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md`

## 5. 実装前チェックリスト

- [x] TASKの図、型制約、Context閉包、verifyが規範文なしTECHを同じ語彙で扱う
- [x] `passed_with_warnings`のJSON例からwarningの根拠を追跡できる
- [x] `check`結果例にGit基準版、実行時HEAD、dirty状態がある
- [x] すべてのSHA-256例と`--expect-digest`が64桁小文字16進数を使用する
- [x] レポート名のUTC形式と衝突時連番が1つの正規形で表される
- [x] Diagnostic表の結果効果列が`resultStatus`へ統一されている

## 6. クローズ判定

P3 6件は正本同期として裁定・反映した。既存決定を変更せず、要約、JSON例、CLI入力、ファイル名、
Diagnostic表の読み違いを解消したため、P3記述整合レビューは**完了**とする。
