# Gate C認定記録

## 2026-09-27: フェーズ1（2環境の適合試験・単体試験の証拠の基盤）

Gate Cの状態は`Pending`である。フェーズ1は最終認定ではなく、次の自動検査の基盤を実装する。

- `minimum`と`reference`の2つの環境のロールを、別々の新しいチェックアウトで実行する
- 証拠を同じ40桁のコミットのSHAへ結び付け、実行の前と後でチェックアウトがクリーンであることを要求する
- CPython 3.12／Linux以外の証拠を拒否する
- Step 1〜5のすべてのfixtureについて、集合、順序、件数、終了コード、`allPassed`、各差分のないことを照合する
- Coreの単体試験が実行され、終了コード0であることを照合する
- 環境固有のパスとツールの情報を除いた適合試験の結果が、2環境で一致することを要求する
- 欠落、重複、未知のfixture、偽の件数、クリーンでないチェックアウト、失敗を成功とした証拠を、陰性対照で拒否する

実装は次の3ファイルが所有する。

| ファイル | 責務 |
|---|---|
| `certify_gate_c.py` | 新しいチェックアウトでの1環境の実行と、2環境の証拠を集約する入口 |
| `gate_c.py` | 証拠の検証、環境間の照合、フェーズ1の結果の構築 |
| `test_gate_c.py` | 成功する経路と、失敗時に通さない扱いの陰性対照 |

2環境の証拠を集約できた場合も、フェーズ1の結果は`gateCFoundation: "Passed"`、
`gateC: "Pending"`とする。次の3項目は後続のフェーズで実証する。

1. 性能のベースラインとSLO
2. 簡易フローと、通常のMarkdownを使う条件との比較
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

基準環境のマニフェストは`fixtures/performance/environments/core-1-reference.json`である。
フェーズ1でも、OS、プラットフォームの種別、アーキテクチャ、CPU、論理コア数、RAM、ストレージ、ファイルシステム、Python、Git、cgroup v2を実測し、
マニフェストのハッシュ値と比較条件が一致しない`reference`の証拠、および環境フィンガープリントが同じ2つのロールを拒否する。
ネットワークの無効化などの隔離の条件は
性能ランナーで制御するため、性能のベースラインとともに引き続き未認定である。

## 2026-09-28: フェーズ2（初回の性能ベースライン）

基準環境`core-1-linux-wsl2-ryzen-9-9900x`で、Coreのコミット
`4b3d95982e33bf77486068df57faf3111a1c1152`をクリーンな状態から測定した。
ランナーが`PrivateNetwork`を強制し、`HOME`、キャッシュ、`TMP`をそれぞれ専用にし、cgroup v2のプロセスの木構造のメモリ、
Coreの永続キャッシュなし、レポートなし、逐次実行を強制し、観測した環境はマニフェストの比較キーと一致した。

| ケース | 中央値 | 最大ピークRSS | 判定 |
|---|---:|---:|---|
| `single-changed-check` | 734.527 ms | 29,028,352バイト | `passed` |
| `single-context-20` | 259.796 ms | 18,722,816バイト | `passed` |
| `single-full-check` | 729.439 ms | 29,876,224バイト | `passed` |
| `single-doctor` | 122.267 ms | 16,662,528バイト | `passed` |
| `single-verify-overhead` | 260.130 ms（Coreのオーバーヘッド） | 22,917,120バイト | `passed` |
| `multi-workspace-full-check` | 1,948.049 ms | 31,956,992バイト | `passed` |
| `multi-workspace-context-20` | 315.664 ms | 25,251,840バイト | `passed` |

受入の成果物は
`fixtures/performance/baselines/core-1-linux-wsl2-ryzen-9-9900x/4b3d95982e33bf77486068df57faf3111a1c1152.json`
であり、ファイルのSHA-256は
`7f46db745fe9a7f8fe87bce8b9e5f4e87124cd87dcf990e7fa3de7c90c61f72a`である。

`validate_benchmarks.py`は、スキーマへの適合だけでなく、パスの環境IDとコミット、コミットの祖先関係、
観測した環境、データセットのハッシュ値、ケースの集合と順序、中央値、最大RSS、`verify`のオーバーヘッド、固定のSLOを
測定値の配列から再計算する。改変した`status: passed`だけでは監査を通過できない。

初回のベースラインと固定のSLOの受入は完了した。Gate Cの集約処理へ、このベースラインの監査を直接接続するまでは
`accepted performance baseline integration`を未完了として残す。簡易フローと通常のMarkdownの条件の
比較証拠、および未解決P0/P1の閉包も残るため、Gate C全体は`Pending`を維持する。

## 2026-09-28: フェーズ3（性能ベースラインのGate Cの集約への統合）

`certify_gate_c.py collect`は、`minimum`と`reference`の証拠と同じ対象コミットを新しくチェックアウトし、
`validate_benchmarks.py`を直接実行する。監査は、受入済みのベースラインのスキーマ、来歴、基準環境、データセットのハッシュ値、
測定値の再計算、固定のSLO、データセット生成の決定性、形状の陰性対照を検査する。

Gate Cの集約は、監査の対象コミット、新しいチェックアウトのクリーンな状態、終了コード、レポートのハッシュ値、監査の件数、
ベースラインの環境ID・Coreのコミット・ケースの件数・ファイルのハッシュ値を、失敗時に通さない扱いで照合する。
監査の欠落、失敗、偽の`Passed`、重複したベースラインは拒否する。通過した場合は`gateCPerformance: "Passed"`を記録する。

性能ベースラインのGate Cの集約への統合は完了した。残件は次の2項目であり、Gate C全体は`Pending`を維持する。

1. 簡易フローと通常のMarkdownの条件の比較証拠
2. 未解決P0/P1の閉包

## 2026-09-29: フェーズ4（比較タスクの実測をGate Cから除外）

管理者が[ADR-058](../../docs/02.設計書/10_決定記録/ADR-058_Gate-Cから比較タスクの実測を外す.md)を承認し、
簡易フローと通常のMarkdownによる比較タスクの実測をGate Cの条件から外した。比較タスクの固定済みの資産は
任意研究用として保持し、有効な結果を取得するまで生産性の優位性を主張しない。

Gate Cの集約の未完了項目から、比較証拠を除いた。残件は未解決P0/P1の閉包だけであり、
Gate C全体は`Pending`を維持する。

1. 未解決P0/P1の閉包

## 2026-09-29: フェーズ5（P0/P1閉包の監査）

管理者が[ADR-059](../../docs/02.設計書/10_決定記録/ADR-059_Gate-CのP0-P1閉包を既存受入証拠で判定する.md)を承認した。
Core用の正式な仕様文書と継続的な課題の追跡は、Coreを利用する`bitz-sdd`などの作成支援を利用可能にした後へ移行する。
Gate Cでは、提案25が識別した次の11件を、既存の受入の証拠へ対応付けて閉包する。

| 優先度 | ID | Gate Cで再監査する証拠 |
|---|---|---|
| P0 | `FIN-FIX-001` | Step 1〜5のすべての適合fixtureの集合、順序、完全一致 |
| P0 | `FIN-DIAG-001` | `SINGLE-089`〜`095`、Diagnostic意味網羅review |
| P0 | `FIN-EAI-001` | `SINGLE-096`〜`103` |
| P0 | `FIN-OUT-001` | `SINGLE-104`〜`106` |
| P0 | `FIN-TARGET-001` | `SINGLE-107`〜`113` |
| P0 | `FIN-FM-001` | `SINGLE-114`〜`120` |
| P1 | `FIN-DIGEST-001` | `SINGLE-042`、`MULTI-002-01`、`SINGLE-121`〜`124` |
| P1 | `FIN-IO-001` | `SINGLE-125`群 |
| P1 | `FIN-PROC-001` | `SINGLE-126`群 |
| P1 | `FIN-CLI-001` | `SINGLE-127`群 |
| P1 | `FIN-PERF-001` | 受入済みの性能ベースラインと固定のSLOの監査 |

`priority_closure.py`は、提案25のP0／P1の見出しが上記11件と一致すること、各fixture群がmatrix全体に存在すること、
Diagnostic意味網羅reviewが`Passed`かつ未解決0件であることを検査する。`certify_gate_c.py collect`は、
対象コミットの新しいチェックアウトでこの監査を再実行し、コミット、クリーンな状態、終了コード、レポートのハッシュ値、fixtureの件数、
11件の個別の証拠を`gate_c.py`で独立に照合する。欠落、未知のID、偽の件数、未解決のレビュー、改変した個別の証拠は拒否する。

フェーズ5で閉包の監査の基盤は実装したが、変更を確定した後の同じコミットに対する、下限／基準の2環境の証拠は、まだ集約していない。
その最終の集約が`gateC: "Passed"`を返すまでは、Gate Cの記録上の状態を`Pending`とする。

下限環境の証拠の採取は通常のCIから分離し、`.github/workflows/gate-c-minimum.yml`の
`workflow_dispatch`で対象のGitの参照を選んだ場合だけ起動する。PR、`main`へのプッシュ、定期実行では採取しない。
