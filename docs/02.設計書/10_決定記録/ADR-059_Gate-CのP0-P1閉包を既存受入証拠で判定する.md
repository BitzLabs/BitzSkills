---
id: ADR-059
title: Gate CのP0/P1閉包を既存受入証拠で判定する
status: accepted
relations:
  related:
    - ADR-049
    - ADR-052
    - ADR-057
    - ADR-058
---

# ADR-059 Gate CのP0/P1閉包を既存受入証拠で判定する

## Context

実装前最終レビューの提案25は、P0 6件とP1 5件を識別した。P0はGate Aまでに契約、Schema、
適合fixtureへ反映し、P1は該当componentの実装と性能受入までに閉じる方針である。その後、Gate A、
Step 1〜5のGate B、2環境での全適合fixtureとCore単体試験、性能baselineと固定SLOの監査が通過した。

一方、Core 1.0開発全体を表す正式なREQ、TASK、課題追跡はまだ存在しない。repository rootの`.spec/`は
Coreの自己適用を確認する最小構成であり、実装前レビューの全項目を遡って文書化する台帳ではない。
正式なCore用SPECの作成と継続的な課題追跡は、Coreを利用するbitz-sdd等の作成支援を用意した後に行う。

Gate Cで正式なSPEC追跡を要求すると、Coreを完成させるためにCore完成後の作成支援を必要とする循環が生じる。
また、提案25の11件は個別の未実装機能ではなく、現在はGate A、Gate Bおよび性能受入の検査対象へ分解されている。

## Decision

1. Core 1.0のGate CにおけるP0/P1閉包の対象は、提案25で識別したP0 6件とP1 5件とする。
2. `FIN-PERF-001`を除く10件は、Gate C基盤が次をすべて満たした場合に閉じる。
   - 下限環境と基準環境の独立したfresh checkoutでStep 1〜5の全適合fixtureが通過する
   - 両環境でCore単体試験が通過する
   - 環境固有値を除いた適合結果が一致する
   - 各IDに対応するfixture群と静的監査が閉包検査で欠落なく対応する
3. `FIN-PERF-001`は、受入済み性能baselineと固定SLOの監査が対象commitのfresh checkoutで通過した場合に閉じる。
4. Gate C集約は、対象commitのfresh checkoutで提案25の見出し、fixture集合、Diagnostic意味網羅監査を照合する。
   11件すべての個別証拠と受入証拠が通過した場合だけ、`gateCPriorityClosure: "Passed"`、
   `gateC: "Passed"`、`pending: []`を返す。
5. 正式なCore用SPECと継続的な課題追跡が未作成であることを、Core 1.0のGate C未完了条件にしない。
   bitz-sdd等の作成支援を利用可能にした後、正式なREQ、TASKおよび変更履歴へ移行する。
6. Core 1.0のrelease判断前に新しいP0またはP1が判明した場合は、新しいADRまたは提案へ記録し、
   解消と受入証拠の追加が完了するまでGate Cを`Passed`として扱わない。

## Consequences

- Core完成後の作成支援を前提にする循環を避けながら、実装前レビューの既知課題を受入証拠へ結び付けられる。
- Gate Cは一般的な課題管理systemの完全性や、未知の不具合が存在しないことを証明しない。
- `.spec/`の最小自己適用と、将来作る正式なCore用SPECを混同しない。
- 新しいP0/P1を発見した場合は人がrelease判断を止める必要がある。Core 1.0以後は正式なSPEC追跡へ移行する。

## Alternatives

1. **正式なCore用SPECが完成するまでGate Cを保留する**: Core完成後の作成支援へ依存する循環になるため採らない。
2. **提案25とは別の暫定課題台帳を作る**: 短期間だけ使う二重管理となり、正式SPECへの移行時に正本が増えるため採らない。
3. **P0/P1条件を証拠なしで削除する**: 実装前レビューの11件が受入結果へ結び付かないため採らない。
4. **GitHub等の外部課題管理をGate Cの正本にする**: offlineで対象commitから再現できないため採らない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-29 | Gate CのP0/P1閉包を既存受入証拠で判定する案を起案 | 提案25、Gate C Phase 4 |
| 2026-09-29 | 管理者が方針を承認 | Gate C Phase 5 |
