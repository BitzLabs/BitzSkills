# verify process終了fixture review

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify)の
`SINGLE-057`、`SINGLE-058`、`SINGLE-059`を扱う。`SINGLE-069-01/02`（出力の切り詰め）と、保留した
`SINGLE-066`／`SINGLE-068`は別の段階で扱う。いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 3件とも事前検査を通過した後に失敗する

[verify仕様 §6](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#6-command結果)は、`commands[]`の要素を作らず
`bindingRefs`を空にする「環境不足」と、process生成を試みた後の失敗とを分ける。3件は後者に属するので、いずれも
`commands[]`の要素を記録し、`bindingRefs: ["root::default"]`を保ち、`exitCode: null`と`status: error`を返す。
結果Schemaは、`exit`以外のすべての終了理由にこの組合せを強制する。

Diagnosticは`source.kind: environment`で最上位に置く。registryが`VERIFY-SPAWN-ERROR`、`VERIFY-SIGNAL`、
`VERIFY-TIMEOUT`に定める形であり、3件とも継続単位は`skip-binding`である。
[verify仕様 §6](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#6-command結果)は、単一workspaceではbindingの
Diagnosticを最上位に置く。

| fixture | command file | 終了理由 | code |
|---|---|---|---|
| `SINGLE-057` | `bin/badformat` | `spawn_error` | `SPEC-VERIFY-COMMAND-001` |
| `SINGLE-058` | `bin/signal.sh` | `signal` | `SPEC-VERIFY-COMMAND-001` |
| `SINGLE-059` | `bin/hang.sh` | `timeout` | `SPEC-VERIFY-TIMEOUT-001` |

`bin/badformat`は実行bitを持つ通常fileで、内容はELFでもshebang付きscriptでもない。
[verify仕様 §5.1](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#51-実行fileと環境)は、通常fileでない、存在しない、
実行不能なfileをspawnの*前*に拒否する。このfileは3条件をすべて通過し、その後`execve`が`ENOEXEC`で失敗する。
Coreはshellを使わないので、代わりに解釈する経路もない。これがmatrixの「実行bit付きだがOSが拒否する実行形式」である。

## 監査はcommand fileを自分で実行する

各fixtureのcommand fileを、Coreを介さず直接実行し、入力がreview済みの原因を今も再現することを確かめる。
`bin/badformat`がspawn時にOSのerrorを起こすこと、`bin/signal.sh`が`SIGTERM`で終了すること、`bin/hang.sh`が
process group全体へのgraceful terminationを生き延びて強制終了を必要とすることである。これがなければ、期待値は
誰も実行していない入力についての主張になる。

この回の作成中に、実際の欠陥が2件見つかった。どちらも監査ではなくfixtureの欠陥である。

1. 最初の`bin/hang.sh`は前景で`sleep 60`を実行していた。process groupへの`SIGTERM`でsleepが終了すると、shellの
   waitが戻ってscriptが終了するため、強制終了が必要にならなかった。現在は、前景のsleepが終了されてもloopを続け、
   pipeを保持する子processも`TERM`を無視する。
2. 監査がspawnの直後、shellがtrapを設定する前にsignalを送っていたため、保護されていない起動直後を終了できることしか
   示していなかった。現在のscriptはtrapの設定*後*に準備完了の行を出力し、監査はその行を待ってからsignalを送る。

## `SINGLE-059`は準備完了の行を保持する

準備完了の行は実際の出力なので、fixtureの期待する`stdoutExcerpt`（`"hang-ready\n"`）にもなる。空の抜粋より価値が
ある。子孫が継承したpipeを開いたまま保持するため、この行が結果に現れるのは、CoreがEOFを待たず、timeoutの状態機械で
streamを読み切ってread handleを閉じる場合だけである
（[verify仕様 §5.2](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#52-timeoutと有限時間終了)）。
元のstreamは64 KiBを大きく下回るので、`stdoutTruncated`は`false`のままである。

実効timeoutは、設定が受け付ける最小値である1秒を`verify.timeoutSeconds`で与える。状態機械を通しつつfixtureを速く
保てる。この値はDigest材料なので`SINGLE-059`は固有のContext Digestを持つ。`SINGLE-057`と`SINGLE-058`も、`argv`
templateによって固有のDigestを持つ。

## 限界

- Coreは実行していない。timeout到達から5秒以内にbindingの結果を確定する要件を含め、Coreとの一致はGate Bで判定する。
- 監査は、`bin/hang.sh`に強制終了が*必要*であることを示す。Core自身の2秒の段階的な終了手順は、Coreができるまで
  観測する手段がないため測らない。
- `ENOEXEC`は、Step 0Bで固定した基準環境のLinuxが、ELFでもshebangでもない実行可能fileに対して示す挙動である。
  fixtureは特定のerrnoではなく、観測できる結果（spawnの失敗）を固定する。
- 基準環境の`/bin/sh`は`dash`であり、scriptはPOSIXの構文だけを使う。
