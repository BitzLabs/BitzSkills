# CLI引数境界fixture review

2026-09-14。SINGLE-127の引数解析error 9件を追加する。CoreのCLI解析は実装・実行しない。

| ID | 唯一の不正条件 | 期待 |
|---|---|---|
| SINGLE-127-01 | `--format json`を2回指定 | 同値でも重複を拒否 |
| SINGLE-127-02 | `--full`を2回指定 | 重複flagを拒否 |
| SINGLE-127-05 | checkのtargetに空文字列を1件指定 | 引数なしcheckへ置換せず拒否 |
| SINGLE-127-06 | contextの起点を指定しない | 必須起点の不足を拒否 |
| SINGLE-127-07 | doctorの`--workspace`値が空文字列 | workspace探索前に拒否 |
| SINGLE-127-08 | verifyの`--timeout 0` | 下限外を拒否 |
| SINGLE-127-09 | verifyの`--timeout 3601` | 上限外を拒否 |
| SINGLE-127-10 | verifyの`--timeout +1` | 数値範囲内でも非canonical表記を拒否 |
| SINGLE-127-11 | checkの`--report=out.json` | 未知option形式を拒否し、任意pathへ書かない |

根拠は[CLI基盤契約 §5・§7](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#5-共通cli-argv解析)と
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の該当ID。
全件で終了コード4、標準出力なし、共通結果・statusなし、report生成0件とする。
標準エラーは`bitz: <operation>: <reason>`の1行で、理由を必須とし端末制御文字を許さない。
理由の自然言語文字列そのものは契約が固定していないため一致対象にしない。
既存の`cli-output.json`とoperation別の出力検査を共用する。

入力は既存SINGLE-042の有効な単一workspace corpusを物理copyし、引数以外の不正を混ぜない。
REQ-001は存在し、timeout caseへ未知targetを混ぜない。空文字列はmanifestのargv配列で保持し、
shellを介して消失させない。checkのbase指定は不要で、argv拒否後にGit基準版を解決してはならない。
副作用期待値はrepository、Git status/index、隔離HOME/cache/TMPDIRのbefore/after完全一致とする。

準備検証はmanifest・出力契約・入力byte列・副作用Schemaを照合し、各fixtureを2回隔離setupして
固定snapshotと一致させる。回帰試験は重複や空引数の除去、有効timeoutへの置換、出力file追加などを拒否する。
これは期待値の破損検出であり、Coreが実際にargvを拒否した証拠ではない。
Coreの終了コード、stream、副作用と操作開始前の拒否は対応するGate Bで検証する。
