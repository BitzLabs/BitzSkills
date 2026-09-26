---
id: ADR-056
title: 適合試験の分割実行とCIのGate B集約を確定する
status: accepted
relations:
  requires:
    - ADR-048
    - ADR-049
    - ADR-051
    - ADR-052
---

# ADR-056 適合試験の分割実行とCIのGate B集約を確定する

## Context

通常の適合試験とGate B認定を別に実行すると、mainのCIでは同じ全適合fixtureを3回実行する。
上限境界の実寸検査と独立checkout間の再現性を維持し、分割実行と結果の統合で待ち時間を短縮する。
2026-09-26に管理者が、計時の常設、mainの重複整理、適合試験の分割という方針を承認した。

## Decision

1. **計測と判定の分離**: harnessの合否reportの外形と比較方法を維持する。fixtureごとの総時間、
   生成、setup、実行環境準備、process実行、比較、副作用snapshotの時間は別JSONへ記録する。
   進捗は標準エラーへ出し、合否の標準出力へ混ぜない。時間の値はGateの決定性比較へ含めない。
2. **選択と分割**: `run_conformance.py`は`--shard`と`--shards`で対象を決定的に分割する。
   合否条件は分割によって変えない。初期の配分は大規模relation・traceケースの観測とdimension別の
   推定重みを用いる。重みは性能baselineではなく、検証の配置だけを決める補助値とする。
   main CIの独立2組から得たfixture時間の中央値で重みを校正し、境界内外で早期終了の有無を分ける。
   固定した観測元commitとrunをコードに残し、各分割の予測job時間をCIのjob名とStep Summaryへ表示する。
   予測値は合否、timeout、性能要件には使用しない。
   開発用に`--suite standard`と`--suite scale`を提供するが、認定は必ず`full`の全対象を使う。
3. **独立した2組**: ADR-052 Decision 4の単一commandによる認定に加え、CIで分割結果を集約する
   認定を許可する。CIでは独立実行番号1・2の各組に対し、分割ごとに固定した同一HEADから新しいcloneを
   作成してCoreをbuildする。Coreのwheel・venv・fixture作業tree・Coreの観測結果をworker間で共有しない。
   依存packageのdownload cacheの利用は許可する。各組は全fixtureをちょうど1回実行し、Step 2以降は
   各組の分割1のcloneでParser adapterも実行する。既存の2 clone方式を置き換える場合も、全件の独立2回と
   Parser adapterの独立2回という条件を弱めない。
4. **集約**: `tests/bitz-core/ci_gate_b.py`が各workerのcommit、CI run/attempt、分割番号、独立実行番号、
   checkout識別子、実行前後のclean状態、harness終了コード、Parser結果を検査する。全分割の欠落・重複・
   未知ID・順序不整合・失敗・集計不整合を拒否する。分割間と2組間で実行環境も一致させる。
   各組のfixture列を`steps.json`の累積順序へ戻し、既存のGate B比較関数で2組の全件結果とParser出力を比較する。
   成果物は同一CI run/attemptのworkerからだけ受け入れる。PRの1組だけの成功をGate B Passedと呼ばない。
5. **CIの構成**: PRは4分割の1組を実行する。main push・週次・手動は4分割の2組を実行し、通常の適合試験は
   1組目を兼ねる。これとは別の3回目の適合試験を実行しない。Gate Aは独立したjobで実行する。
   全体としての認定にはGate AとGate Bの両方の成功が必要であり、一方の成功が他方を代替しない。
   同時worker数の初期値は4とする。
6. **既存契約**: fixtureの入力・期待値・副作用比較・上限境界・timeout条件を変更しない。harnessからCoreをimport
   しないというADR-049の依存方向を保つ。CIの集約とParser実行は`tests/bitz-core/`が所有する。

## Consequences

- 並列化は待ち時間を短くするが、workerごとのbuild・起動分の計算量は増える。不要な3回目の適合試験を減らすことで
  総実行量も減らす。CIの実測値を見て分割重みと同時実行数を調整する。
- 部分実行で全件の適合や認定を主張してはならない。集約器の陰性対照を単体試験で常時実行する。
- 分割結果の比較は同じCI run/attemptを要求するため、CIを再実行するときは全jobを再実行する。
- 既存の`certify_gate_b.py --step N`はローカルの逐次・2 clone認定として引き続き利用できる。

## Alternatives

- 境界の値を縮める、上限超過だけを残す、独立実行を1回にする案は、実寸・境界内・再現性の保証を失うため採らない。
- 実行結果のcacheを合否に使う案は、今回のcommitでの実行を証明しないため採らない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-26 | main CIの独立2組で配分を校正し、分割ごとの予測時間表示を追加 | GitHub Actions run 36248419060 |
| 2026-09-26 | 計時、分割、独立2組の集約とCIの重複整理を確定 | ADR-052、実装計画 |
