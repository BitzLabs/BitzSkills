---
id: ADR-085
title: 適合harnessでUTF-8でない名前とSHA-256のコミットIDを扱い、壊れたリビジョンの設定の診断の形を定める
status: proposed
relations:
  related:
    - ADR-048
    - ADR-080
    - ADR-084
---

# ADR-085 適合harnessでUTF-8でない名前とSHA-256のコミットIDを扱い、壊れたリビジョンの設定の診断の形を定める

## Context

[ADR-084](ADR-084_Gitの読取りの既知の問題を解消し、SHA-256のリポジトリに対応する.md)の適合fixtureを作る中で、次の3点が残った。

1. **UTF-8でない名前**。`setup.materialize`の`to`はJSONの文字列なので、UTF-8でないバイトの名前を作れない。ADR-084の決定1（UTF-8でないパスの名前）を、
   適合fixtureで確かめられない。
2. **SHA-256のコミットID**。適合fixture仕様 §4の正規化は、`revision.base`と`revision.commit`を「40桁の小文字16進」であることだけを検査する。
   ADR-084の決定5でコミットIDは64桁にもなり得るが、64桁の期待値を書けない。
3. **壊れたリビジョンの設定の診断の形**。ADR-084の決定2の`MULTI-REVISION-ROOT-CONFIG-INVALID`（`SPEC-MULTI-CONFIG-001`）について、診断の`source`を仕様が定めていない。

## Decision

1. **名前をバイト列で指定する**（[ADR-048](ADR-048_適合fixtureの生成入力とGit構造の準備の処理を確定する.md)の部分改訂）。`setup.materialize`の各要素は、`to`の代わりに
   `toBytes`（付け替えた後のパスのバイト列を、16進の小文字の文字列で表したもの。`/`はセグメントの区切りとしてそのまま含む）を持てる。`to`と`toBytes`は排他とする。
   `toBytes`を使うfixtureは、`setup.materialize`の既存の規則と同じくLinux専用とする。
2. **コミットIDの桁数**。正規化は、`revision.base`と`revision.commit`が、fixtureのリポジトリのオブジェクトの形式（`setup.objectFormat`）に応じて
   40桁（`sha1`）または64桁（`sha256`）の小文字16進であることだけを検査し、期待値には同じ桁数の`0`を置く。
3. **壊れたリビジョンの設定の診断の形**。`MULTI-REVISION-ROOT-CONFIG-INVALID`の診断の`source`は、既存の`SPEC-MULTI-CONFIG-001`と同じく、`kind`を`file`、
   `workspaceId`を現在版のルートワークスペースのID、`path`を`.spec/bitz.yaml`とする。ファイル全体を設定として読めないので、`key`は置かない。

## Consequences

- ADR-084の決定1、2、5を、適合fixtureで固定できる。
- 適合fixture仕様 §3.1、§4、マニフェストのスキーマ、参照harnessの正規化を改める。複合ワークスペース仕様 §2に、診断の形を書き足す。
- 既存の適合fixtureの期待値は変わらない（どれも`sha1`で、40桁の`0`を置いている）。

## Alternatives

1. **UTF-8でない名前は単体試験だけで確かめる**: 準備の入力を変えないが、`check`と全体事前検査の振る舞いを適合fixtureで固定できない。採らない（ユーザーの決定）。
2. **壊れたリビジョンの設定の診断の`workspaceId`を`null`にする**: 既存の`SPEC-MULTI-CONFIG-001`と形が分かれる。採らない（ユーザーの決定）。

## Notes

- 2026-11-28に、利用者がDecisionの1と3の案を選んだ。Decisionの2は、ADR-084の決定5から一つに決まる帰結として起票者が定めた。`toBytes`という名前は起票者の案である。
- 本ADRは、ADR-048の決定4（準備の入力）を部分改訂する。そのほかの決定は変えない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-11-28 | 起票（`proposed`） | ADR-084 |
