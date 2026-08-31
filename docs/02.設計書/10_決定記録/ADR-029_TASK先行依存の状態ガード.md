---
id: ADR-029
title: TASK先行依存の状態ガード
status: accepted
relations:
  requires:
    - ADR-024
  related:
    - ADR-010
---

# ADR-029 TASK先行依存の状態ガード

## Context

TASKの`requires`は「TASK実行前に必要なSPECまたは先行TASK」を示し、TASK間の`requires`循環は実行順序を
決められないためエラーとしている。一方、Context Resolution仕様の状態表は`open` TASKをWork、`done` TASKを
Historyへ分類するだけで、`open`の先行TASKをblocking条件にしていない。

このため`TASK-B(open) requires TASK-A(open)`という宣言があっても、TASK-Bを起点とする
`purpose=implement`のContext Bundleは完全解決し、先行作業を飛び越えて実装を開始できた。
「先行TASK」という宣言の意味と、Coreが実際に強制する内容が一致していなかった。

## Decision

1. TASKを起点とする`purpose=implement`および`purpose=verify`では、起点TASKの`requires`が指すTASKが
   すべて`done`であることを要求する。
2. `open`の先行TASKが1件以上残る場合、`CTX-TASK-DEPENDENCY-001`／error／`blocked`とし、未完了の
   先行TASK IDを返す。Coreは先行TASKを暗黙に完了扱いしない。
3. `purpose=interpret`では停止せず、未完了の先行TASKをWork区分として表示する。解釈は先行作業の完了に
   依存しないためである。
4. `requires`が指すREQ、TECH、accepted ADRに対する既存の適用可能性判定は変更しない。本決定はTASK
   targetの状態ガードだけを追加する。
5. TASK間循環は従来どおり`CTX-CYCLE-001`とし、状態ガードと別コードで識別できるようにする。
6. 実行順序を持たない単なる関連作業には`related`を使い、`requires`を使わない。

## Consequences

- 「先行TASK」の宣言が実行可能性の機械契約になり、`open -> open`と`done -> open`で開始可否が一意になる。
- 先行TASKを`done`にし忘れた作業は`blocked`となるため、TASKの完了操作が運用上必須になる。
- `interpret`は従来どおり成功するため、仕様の読み取りと計画立案は先行TASKの状態に妨げられない。
- 循環検査と状態ガードがDiagnosticコードで区別でき、利用者が取るべき対処を判別できる。

## Alternatives

1. **`requires`先TASKの状態を検査しない**: 宣言の意味とCoreの強制内容が乖離したままとなり、
   TASK依存を運用規約でしか守れないため採用しない。
2. **warningとして継続する**: 先行作業を飛ばした実装をCoreが黙認することになり、`blocked`を維持する
   TASK境界の方針と整合しないため採用しない。
3. **`interpret`でも`blocked`にする**: 先行TASKが未完了でも仕様の読解と計画は成立するため、
   利用価値のあるContextを不要に遮断することになり採用しない。

## Notes

- 本ADRは2026-08-31のユースケース・フロー遷移レビューUC-FLOW-002に対する裁定である。
- 関連文書: [SPECファイル規定/05](../../03.詳細設計/02_SPECファイル規定/05_補助SPEC仕様.md),
  [SPECファイル規定/06](../../03.詳細設計/02_SPECファイル規定/06_参照・トレース・検証仕様.md),
  [SPECファイル規定/10](../../03.詳細設計/02_SPECファイル規定/10_Context%20Resolution仕様.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | TASK `requires`先の状態ガードと`CTX-TASK-DEPENDENCY-001`を確定 | — |
