---
id: ADR-055
title: Core 1.0の対象OSをPOSIXに限定する
status: accepted
relations:
  related:
    - ADR-007
    - ADR-045
    - ADR-053
---

# ADR-055 Core 1.0の対象OSをPOSIXに限定する

## Context

Core 1.0の規範は対象のCPython版（[ADR-053](ADR-053_CPythonの下限を3.12へ引き上げる.md)）を定めているが、対象OSを
定めていない。対象OSに触れていたのは、[ADR-009](ADR-009_小規模チーム向け軽量CoreとEARS-AI中核化.md)で置き換えられた
[ADR-007](ADR-007_Core実行体の配布形態.md)の「3OS」（Linux、macOS、Windows）だけである。Gate Cの「2環境」も
CPythonの版を指し、OSを指さない。

一方、Core 1.0の規範と実装は、すでにPOSIXの機能を前提にしている。

- `verify`のtimeout状態機械は、新しいprocess groupへの起動とgroupへのsignal送信を使う
  （[verify仕様 §5.2](../../03.詳細設計/03_操作仕様/03_verify.md#52-timeoutと有限時間終了)）
- 実行fileの解決は、通常fileと実行権限の判定を使う（同 §5.1）
- 明示reportの保存は、`.spec`と`.spec/reports`をsymlinkを辿らないdirectory fdとして開き、そのfd基準で
  一時fileの作成、確定、除去を行う（REQ-003、[結果・Diagnostic・終了コード §8](../../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#8-report)）

Windowsはdirectory fd基準の操作（`dir_fd`、`O_DIRECTORY`、`O_NOFOLLOW`）とprocess groupへのsignalを持たない。
Windowsを対象に含めると、reportの保存を検査と書込みの競合に弱い方式へ戻すか、別の実装を用意する必要があり、
`verify`の有限時間終了の保証も同じ形では成り立たない。Core 1.0は小規模チーム向けの軽量Core
（ADR-009）であり、未releaseの今、対象OSを明示するのが最も安い。

## Decision

1. **対象OS**: Core 1.0の対象OSはPOSIX系のLinuxとmacOSとする。Windowsは対象外とし、Windowsの利用者には
   WSL上での利用を案内する。
2. **必要な機能がない環境での挙動**: Coreは、安全性の保証に必要なOSの機能（directory fd基準のfile操作、
   `O_NOFOLLOW`、process groupへのsignal）が使えない環境で、その保証を弱めた代替動作へ切り替えない。
   明示reportの保存は書き込まずに`SPEC-REPORT-WRITE-001`を返す。
3. **適合の確認**: Gate Cの確認はLinuxで行う。macOSは検証環境を用意できないため、Core 1.0ではmacOSでの
   確認を行わず、動作を検証済みとして扱わない。macOSでの利用は、POSIXの機能だけを使う実装の設計に基づく
   ものであり、適合を保証しない。本項は[実装計画 §9.1](../../04.提案資料/12_Core-1.0実装計画.md#91-gate-c-core-10-release受入)の条件に反映する。
4. 対象OSの追加は、Core minor以上の変更とする（ADR-045 Decision 6の下限versionの扱いと同じ）。

## Consequences

- Windowsでネイティブに動かすことはCore 1.0の対象外になる。WSLでは対象になる。
- 実装はPOSIXの機能を前提にでき、安全性の保証を弱める分岐を持たない。
- Gate CでOSについて確認するのはLinuxだけである。macOSでdirectory fd基準の操作やprocess groupへのsignalが
  期待どおり動くことは実測せず、Core 1.0ではmacOSでの動作を検証済みとして扱わない。検証環境を用意できた時点で、
  macOSでの確認をGate Cまたは後続releaseの条件へ加えられる。

## Alternatives

1. **Windowsも対象にする**: 利用者は広がるが、reportの保存では検査と書込みの競合を防げず、REQ-003の保証が
   成り立たない。`verify`のprocess管理も別実装が要る。Core 1.0の規模と釣り合わないため採用しない。
2. **対象OSを定めない**: 実装が根拠のない前提を持ち、Windowsでの挙動が規範から決まらない。採用しない。

## Notes

- 人間の管理者が2026-09-26に承認した。Small Flow実証のTASK-001（REQ-003）のhuman reviewで、実装が
  規範にない「対象はPOSIXのみ」という前提を持っていたことが判明したのが起点である。
- 反映先: [Core実行環境・CLI基盤契約 §2](../../03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#2-実行環境と配布物)、
  [Core 1.0実装計画 §9.1](../../04.提案資料/12_Core-1.0実装計画.md#91-gate-c-core-10-release受入)。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-26 | Core 1.0の対象OSをLinuxとmacOSに限定し、Gate CにmacOSでの確認を加える | ADR-045、ADR-053 |
| 2026-09-26 | 検証環境を用意できないため、Gate CでmacOSの確認を行わず、macOSでの動作を検証済みとして扱わないよう Decision 3とConsequencesを改める（管理者の決定） | 実装計画 §9.1 |
