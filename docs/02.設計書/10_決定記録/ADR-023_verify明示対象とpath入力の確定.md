---
id: ADR-023
title: verify明示対象とpath入力の確定
status: accepted
relations:
  related:
    - ADR-010
    - ADR-019
---

# ADR-023 verify明示対象とpath入力の確定

## Context

公開文法は`bitz verify`へSPEC ID、規範文ID、pathを渡せるとしていたが、詳細手順は要求IDと
規範文IDしか定義していなかった。TECH、TASK、ADR、SPEC path、コードpath、テストpath、複数対象の
扱いを実装者が決定できず、直接テストpathを指定して句単位coverageを迂回する実装も可能だった。

## Decision

1. Core 1.0の明示対象はREQ ID、TECH ID、規範文ID、TASK ID、REQ／TECH／TASKのSPECファイルpathとする。
2. SPECファイルpathはFrontmatter IDへ正規化し、ID指定と同じ規則で処理する。
3. コードpath、テストpath、ディレクトリ、ADR ID／pathは受け付けず、引数不正として終了コード4を返す。
4. REQ／規範文ありTECHは、文書ID指定なら所有する全規範文、規範文ID指定なら指定句を起点とする。
   規範文ID指定時の兄弟句は`adjacent`として表示し、検証対象へ暗黙追加しない。
5. 規範文なしTECHは宣言済み`tests`を文書単位で実行する。
6. TASKは`addresses`に列挙された句と`requires`閉包を対象とする。
7. 複数対象は同一request workspaceに限定し、IDへ正規化後に和集合と重複排除を行う。
8. 形式が正しいが存在しないIDは`CTX-ROOT-MISSING-001`、不在・範囲外のSPEC pathは
   `SPEC-PATH-INVALID-001`、実行可能なテストまたはコマンド不足は`SPEC-VERIFY-BLOCKED-001`を使用する。

## Consequences

- 明示指定と引数なしverifyの対象規則を同じContext／coverage契約へ接続できる。
- テストpathの直接指定によるcoverage迂回を防止できる。
- TASK単位で対象句を限定した検証ができる。
- ADRは実行可能契約を所有しないため、verify対象にならない。
- CLI文法、Contextのtarget statement選択、verify手順を同時に更新する必要がある。

## Alternatives

1. **コード・テストpathを受理する**: 逆索引と曖昧な多対多解決が必要で、句単位coverageを迂回できるため採用しない。
2. **REQだけを受理する**: 規範文なしTECHとTASK境界を利用できなくなるため採用しない。
3. **ADRも受理する**: ADRはテスト、実装path、検証コマンドを所有しないため採用しない。

## Notes

- 本ADRは2026-08-31のP1残存契約レビュー「verify明示対象の未定義」に対する裁定である。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | verifyの対象種別とpath入力を確定 | — |
