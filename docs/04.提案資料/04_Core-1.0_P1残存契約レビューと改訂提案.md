# Core 1.0 P1残存契約レビューと改訂提案

**状態**: **Closed（P1 3件裁定・反映済み）**

**作成日**: 2026-08-31
**裁定日**: 2026-08-31

## 1. 目的

レビュー03の17件を反映した正本を対象に、矛盾、定義不足、遷移の妥当性を再確認した。
本書は実装前に解消が必要と判定したP1 3件の原文、裁定、反映先を保持する。
現在の正本は`docs/02.設計書`と`docs/03.詳細設計`であり、本書の例だけを実装根拠にしない。

## 2. P1指摘

### 2.1 Diagnosticのseverity、操作status、sourceが確定しない

共通Diagnosticは`severity`と`source`を必須とする一方、Context、doctor、モノレポの一覧には
操作結果だけを記載した行があり、severityを決定できなかった。またCore版不一致、Git不在、
Capability不足はファイル位置を持たず、従来の`source.path`例では表現できなかった。

### 2.2 不正な規範文IDがParserへ到達しない

従来のScannerは正しい`statement-id`に一致する行だけを解析対象としたため、3桁未満ID、未知prefix、
3階層ID、ID欠落を通常本文として無視できた。このままでは`EAI-CORE-ID-001`と必須タグ不足の
Diagnosticが該当入力へ到達しない。

### 2.3 `bitz verify`の明示対象が未定義

公開文法はSPEC ID、規範文ID、pathを受け付ける一方、詳細手順は要求IDと規範文IDしか定義していなかった。
TECH、TASK、ADR、SPEC path、コードpath、テストpath、複数対象の処理が実装裁量になり、
テストpathから句単位coverageを迂回できる余地があった。

## 3. 裁定

| 項目 | 裁定 | 対応 |
|---|---|---|
| Diagnostic共通契約 | 採用・反映済み | [ADR-021](../02.設計書/10_決定記録/ADR-021_Diagnostic-severity・操作status・source-Schemaの分離.md)。severityとstatusを分離し、`source.kind`を3形式で定義 |
| 規範行候補Scanner | 採用・反映済み | [ADR-022](../02.設計書/10_決定記録/ADR-022_規範行候補抽出とID構文検証の分離.md)。候補抽出と完全な構文検証を分離 |
| `verify`明示対象 | 採用・反映済み | [ADR-023](../02.設計書/10_決定記録/ADR-023_verify明示対象とpath入力の確定.md)。REQ/TECH/規範文/TASK/SPEC pathへ限定 |

## 4. 反映先

- `02.設計書/01_共通アーキテクチャ.md`
- `02.設計書/03_CLI統合設計.md`
- `02.設計書/08_実装ロードマップ.md`
- `03.詳細設計/01_EARS-AI規格/01_Core構文仕様.md`
- `03.詳細設計/01_EARS-AI規格/02_拡張プロファイル仕様.md`
- `03.詳細設計/01_EARS-AI規格/06_AST・パーサー仕様.md`
- `03.詳細設計/02_SPECファイル規定/04_要求SPEC仕様.md`
- `03.詳細設計/02_SPECファイル規定/06_参照・トレース・検証仕様.md`
- `03.詳細設計/02_SPECファイル規定/10_Context Resolution仕様.md`
- `03.詳細設計/02_SPECファイル規定/11_doctor仕様.md`
- `03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md`

## 5. 実装前チェックリスト

- [x] 全Core Diagnostic一覧がseverityとresult statusを持つ
- [x] ファイルを持たない環境診断の`source`形式がある
- [x] 不正IDの規範行候補がLexer／Parser／Validatorへ到達する
- [x] GFM checkbox、コードブロック、引用ブロックを規範文として誤検出しない規則がある
- [x] `approved` REQの妥当な規範文0件にDiagnosticがある
- [x] 明示`verify`の対象種別、複数対象、path、拒否対象が定義されている

## 6. クローズ判定

P1 3件はADR-021〜023として裁定し、正本へ反映した。適合性fixtureと実装コードはロードマップに従って
Phase 1以降で作成する。設計上のP1残存契約レビューは**完了**とする。
