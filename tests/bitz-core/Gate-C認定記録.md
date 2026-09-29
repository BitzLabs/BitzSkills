# Gate C認定記録

## 2026-09-27: Phase 1（2環境の適合・単体試験証拠基盤）

Gate Cの状態は`Pending`である。Phase 1は最終認定ではなく、次の自動検査基盤を実装する。

- `minimum`と`reference`の2環境roleを別のfresh checkoutで実行する
- 証拠を同じ40桁commit SHAへ結び付け、実行前後がcleanであることを要求する
- CPython 3.12／Linux以外の証拠を拒否する
- Step 1〜5の全fixtureについて、集合、順序、件数、終了コード、`allPassed`、各差分なしを照合する
- Core単体試験が実行され、終了コード0であることを照合する
- 環境固有のpathとtool情報を除いた適合結果が2環境で一致することを要求する
- 欠落、重複、未知fixture、偽の件数、dirty checkout、失敗を成功とした証拠を陰性対照で拒否する

実装は次の3fileが所有する。

| file | 責務 |
|---|---|
| `certify_gate_c.py` | fresh checkoutでの1環境実行と2環境証拠の集約入口 |
| `gate_c.py` | 証拠の検証、環境間照合、Phase 1結果の構築 |
| `test_gate_c.py` | 成功経路とfail-closedの陰性対照 |

2環境の証拠を集約できた場合も、Phase 1の結果は`gateCFoundation: "Passed"`、
`gateC: "Pending"`とする。次の3項目は後続Phaseで実証する。

1. 性能baselineとSLO
2. Small Flowと通常Markdown条件の比較
3. 未解決P0/P1の閉包

実行例:

```text
uv run tests/bitz-core/certify_gate_c.py run \
  --role minimum --environment-id minimum-cpython-3-12 --python 3.12 \
  --output /path/to/minimum.json
uv run tests/bitz-core/certify_gate_c.py run \
  --role reference --environment-id core-1-linux-wsl2-ryzen-9-9900x --python 3.12 \
  --output /path/to/reference.json
uv run tests/bitz-core/certify_gate_c.py collect \
  --input /path/to/minimum.json --input /path/to/reference.json
```

基準環境manifestは`fixtures/performance/environments/core-1-reference.json`である。
Phase 1でもOS、platform class、architecture、CPU、論理core数、RAM、storage、filesystem、Python、Git、cgroup v2を実測し、
manifestのhashと比較条件が一致しないreference証拠、およびenvironment fingerprintが同じ2 roleを拒否する。
network無効などのisolation条件は
性能runnerで制御するため、性能baselineとともに引き続き未認定である。

## 2026-09-28: Phase 2（初回性能baseline）

基準環境`core-1-linux-wsl2-ryzen-9-9900x`で、Core commit
`4b3d95982e33bf77486068df57faf3111a1c1152`をcleanな状態から測定した。
runnerがPrivateNetwork、専用HOME／cache／TMP、cgroup v2 process tree memory、
Core永続cacheなし、reportなし、逐次実行を強制し、観測環境はmanifestのcomparison keyと一致した。

| case | 中央値 | 最大peak RSS | 判定 |
|---|---:|---:|---|
| single-changed-check | 734.527 ms | 29,028,352 byte | passed |
| single-context-20 | 259.796 ms | 18,722,816 byte | passed |
| single-full-check | 729.439 ms | 29,876,224 byte | passed |
| single-doctor | 122.267 ms | 16,662,528 byte | passed |
| single-verify-overhead | 260.130 ms（Core overhead） | 22,917,120 byte | passed |
| multi-workspace-full-check | 1,948.049 ms | 31,956,992 byte | passed |
| multi-workspace-context-20 | 315.664 ms | 25,251,840 byte | passed |

受入成果物は
`fixtures/performance/baselines/core-1-linux-wsl2-ryzen-9-9900x/4b3d95982e33bf77486068df57faf3111a1c1152.json`
であり、file SHA-256は
`7f46db745fe9a7f8fe87bce8b9e5f4e87124cd87dcf990e7fa3de7c90c61f72a`である。

`validate_benchmarks.py`はSchema適合だけでなく、pathの環境IDとcommit、commitの祖先関係、
観測環境、dataset digest、case集合と順序、中央値、最大RSS、verify overhead、固定SLOを
測定配列から再計算する。改変した`status: passed`だけでは監査を通過できない。

初回baselineと固定SLOの受入は完了した。Gate C集約処理へこのbaseline監査を直接接続するまでは
`accepted performance baseline integration`を未完了として残す。Small Flowと通常Markdown条件の
比較証拠、および未解決P0/P1の閉包も残るため、Gate C全体は`Pending`を維持する。

## 2026-09-28: Phase 3（性能baselineのGate C集約統合）

`certify_gate_c.py collect`は、minimum／reference証拠と同じ対象commitをfresh checkoutし、
`validate_benchmarks.py`を直接実行する。監査は受入済みbaselineのSchema、provenance、基準環境、
dataset digest、測定値の再計算、固定SLO、dataset生成の決定性と形状陰性対照を検査する。

Gate C集約は監査の対象commit、fresh checkoutのclean状態、終了コード、report hash、監査件数、
baselineの環境ID・Core commit・case件数・file hashをfail-closedで照合する。監査の欠落、失敗、
偽の`Passed`、重複baselineは拒否する。通過時は`gateCPerformance: "Passed"`を記録する。

性能baselineのGate C集約統合は完了した。残件は次の2項目であり、Gate C全体は`Pending`を維持する。

1. Small Flowと通常Markdown条件の比較証拠
2. 未解決P0/P1の閉包

## 2026-09-29: Phase 4（比較タスクの実測をGate Cから除外）

管理者が[ADR-058](../../docs/02.設計書/10_決定記録/ADR-058_Gate-Cから比較タスクの実測を外す.md)を承認し、
簡易フローと通常のMarkdownによる比較タスクの実測をGate Cの条件から外した。比較タスクの固定済み資産は
任意研究用として保持し、有効な結果を取得するまで生産性の優位性を主張しない。

Gate C集約の未完了項目から比較証拠を除いた。残件は未解決P0/P1の閉包だけであり、
Gate C全体は`Pending`を維持する。

1. 未解決P0/P1の閉包

## 2026-09-29: Phase 5（P0/P1閉包監査）

管理者が[ADR-059](../../docs/02.設計書/10_決定記録/ADR-059_Gate-CのP0-P1閉包を既存受入証拠で判定する.md)を承認した。
正式なCore用SPECと継続的な課題追跡は、Coreを利用するbitz-sdd等の作成支援を利用可能にした後へ移行する。
Gate Cでは、提案25が識別した次の11件を既存の受入証拠へ対応付けて閉包する。

| 優先度 | ID | Gate Cで再監査する証拠 |
|---|---|---|
| P0 | `FIN-FIX-001` | Step 1〜5の全適合fixtureの集合、順序、完全一致 |
| P0 | `FIN-DIAG-001` | `SINGLE-089`〜`095`、Diagnostic意味網羅review |
| P0 | `FIN-EAI-001` | `SINGLE-096`〜`103` |
| P0 | `FIN-OUT-001` | `SINGLE-104`〜`106` |
| P0 | `FIN-TARGET-001` | `SINGLE-107`〜`113` |
| P0 | `FIN-FM-001` | `SINGLE-114`〜`120` |
| P1 | `FIN-DIGEST-001` | `SINGLE-042`、`MULTI-002-01`、`SINGLE-121`〜`124` |
| P1 | `FIN-IO-001` | `SINGLE-125`群 |
| P1 | `FIN-PROC-001` | `SINGLE-126`群 |
| P1 | `FIN-CLI-001` | `SINGLE-127`群 |
| P1 | `FIN-PERF-001` | 受入済み性能baselineと固定SLOの監査 |

`priority_closure.py`は、提案25のP0/P1見出しが上記11件と一致すること、各fixture群が全matrixに存在すること、
Diagnostic意味網羅reviewが`Passed`かつ未解決0件であることを検査する。`certify_gate_c.py collect`は、
対象commitのfresh checkoutでこの監査を再実行し、commit、clean状態、終了コード、report hash、fixture件数、
11件の個別証拠を`gate_c.py`で独立に照合する。欠落、未知ID、偽の件数、未解決review、改変した個別証拠は拒否する。

Phase 5で閉包監査基盤は実装したが、変更確定後の同一commitに対する下限／基準の2環境証拠は未集約である。
その最終集約が`gateC: "Passed"`を返すまでは、Gate Cの記録上の状態を`Pending`とする。

下限環境の証拠採取は通常のCIから分離し、`.github/workflows/gate-c-minimum.yml`の
`workflow_dispatch`で対象のrefを選んだ場合だけ起動する。pull request、`main`へのpush、定期実行では採取しない。
