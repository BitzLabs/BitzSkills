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
  --role reference --environment-id core-1-reference --python 3.12 \
  --output /path/to/reference.json
uv run tests/bitz-core/certify_gate_c.py collect \
  --input /path/to/minimum.json --input /path/to/reference.json
```

基準環境manifestは`fixtures/performance/environments/core-1-reference.json`である。
性能比較keyとの一致は性能baseline取得時に判定するため、Phase 1の適合・単体試験証拠には含めない。
