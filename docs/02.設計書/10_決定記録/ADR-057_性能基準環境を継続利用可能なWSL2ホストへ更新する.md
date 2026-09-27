---
id: ADR-057
title: 性能基準環境を継続利用可能なWSL2ホストへ更新する
status: accepted
relations:
  requires:
    - ADR-051
    - ADR-053
    - ADR-055
  related:
    - ADR-042
    - ADR-043
---

# ADR-057 性能基準環境を継続利用可能なWSL2ホストへ更新する

## Context

性能基準環境manifestはIntel Core i5-13500Hを固定していたが、そのhardwareを継続利用できない。
Gate C Phase 1の実測照合により、利用可能な環境はAMD Ryzen 9 9900X上のWSL2であり、旧manifestとは
CPU、論理core数、storage classが一致しないことを確認した。存在しない環境名を自己申告して証拠を作ることはできない。

性能baselineはまだ1件も受け入れていないため、基準環境を今変更しても比較可能な履歴を失わない。
一方、GitHub hosted runnerはhardwareが固定されないため性能baselineには使えないが、性能値を判定しない
下限CPython環境の適合試験には利用できる。

## Decision

1. **性能基準環境**: `fixtures/performance/environments/core-1-reference.json`の基準を、継続利用できる
   AMD Ryzen 9 9900X（24 logical core）上のWSL2へ更新する。environment IDは
   `core-1-linux-wsl2-ryzen-9-9900x`とする。CPython 3.12.x、Git 2.30以上、ext4、cgroup v2による
   process tree全体のmemory計測という条件は維持する。
2. **仮想化境界**: comparison keyへ`platformClass`を追加し、基準環境は`WSL2`とする。
   WSL2のvirtual diskは物理媒体をLinux guestから証明できないため、`storageClass`は
   `wsl2-virtual-disk`と記録する。native Linuxや別storage classの結果は`not_comparable`とする。
3. **二環境の独立性**: Gate Cのminimum roleはCPython 3.12を使う別のLinux実行環境で取得し、
   GitHub Actionsを利用してよい。reference roleは本ADRの基準環境で取得する。両roleは別fresh checkoutに加え、
   OS、kernel、architecture、CPU、logical core、platform class、storage class、filesystemから作る
   environment fingerprintが異ならなければならない。同一ホストのrole名だけを変えた2実行は認定しない。
4. **隔離条件**: network無効、Core永続cacheなし、`--report`なし、逐次実行という性能測定の隔離条件は維持する。
   Phase 1の適合・単体試験証拠はcomparison keyとrequired toolsを照合し、隔離条件は性能runnerで強制する。
5. **既存SLO**: elapsed timeとmemoryの固定SLO、dataset、測定回数、暖機、回帰許容は変更しない。
   最初のbaselineを新しいenvironment IDの下で取得するまではGate Cを`Pending`とする。

## Consequences

- 用意できないhardwareへの依存を除き、同じhostでbaselineと将来の回帰測定を継続できる。
- WSL2はWindows hostの負荷や電源状態の影響を受ける。測定時は他の高負荷処理を止め、逐次実行し、
  不安定なrunを採用しない。固定SLOを満たすことは引き続き必要である。
- WSL2 virtual diskをlocal SSDと推定しない。比較可能性は観測できるguest側の条件だけで判定する。
- 基準環境manifestとSchemaは性能fixtureの変更なので、ADR-051に従ってGate Aを再認定する。
- 旧環境のbaselineは存在しないため、移行または保存すべき測定結果はない。

## Alternatives

1. **i5-13500Hを維持する**: 実行できず、Gate Cと性能baselineを永久に確定できないため採らない。
2. **GitHub hosted runnerを性能基準にする**: hardwareと仮想化条件がrunごとに変わり、回帰比較を安定して
   行えないため採らない。minimum roleの機能適合証拠に限って利用する。
3. **WSL2 diskをlocal SSDとみなす**: guestから物理媒体を証明できず、実測照合を自己申告へ戻すため採らない。
4. **二roleを同一hostで実行する**: cross-environmentの再現性を示さないため、最終認定には採らない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-27 | 未取得baselineの基準環境を利用可能なWSL2 hostへ更新し、二環境fingerprintを必須化 | Gate C Phase 1 |
