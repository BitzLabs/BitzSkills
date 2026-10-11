# `doctor`のプラグインの要求のfixtureのレビュー記録

2026-10-11。`SINGLE-160`〜`163`、`SINGLE-164-01`〜`08`の12件を追加する。複合ワークスペースの`MULTI-032`は
[複合ワークスペース全体の`doctor`のレビュー記録](../multi/複合ワークスペース全体のdoctorのレビュー記録.md)の2026-10-11の節に記録する。

## 1. 追加の理由

実装の確認事項C6（`doctor`が`--plugin`、`--plugin-version`、`--require-core-api`、`--require-capability`を受け付けるが判定に使わず、
Core APIや対応機能が要求を満たさなくても`passed`を返し、検査項目`plugin`、`capability`も出していなかった）を解消するために、
[ADR-061](../../../docs/02.設計書/10_決定記録/ADR-061_doctorのプラグイン要求の字句と判定を確定する.md)で字句、組合せ、判定、結果を確定した。
この判定は既存のfixtureが一切固定していなかった。ADR-061 Decision 5に従い、`doctor`を扱うStep 1の完了条件へ追加する（ADR-051の「追加」の手続き）。
Core 1.0の公開の契約を変える追加ではなく、確定した規範文の適合fixtureである。

## 2. 根拠の規範文

- [ADR-061](../../../docs/02.設計書/10_決定記録/ADR-061_doctorのプラグイン要求の字句と判定を確定する.md) Decision 1〜4
- [`doctor`仕様](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md) §3（検査2・3の順序と独立性）、§4（対応機能）、§4.1（プラグインの要求）、§7、§8
- [診断レジストリ](../../../docs/03.詳細設計/00_共通契約/05_診断レジストリ.md) §6（`DOCTOR-PLUGIN-FORMAT`／`DOCTOR-API-VERSION`／`DOCTOR-CAPABILITY`。重大度`error`、継続単位`skip-check`）
- [結果・診断・終了コード](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md) §3（状態の最悪値、終了コード4の出力）、§5（発生元）、§7（診断の並べ替え）
- [Core実行環境・CLI基盤契約](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md) §5（バージョンまたは範囲の構文に一致しない値は終了コード4。反復可能なオプションの重複排除）

## 3. 入力と期待値

全件が最小設定（`SINGLE-001`と同じ`.spec/bitz.yaml`だけ）の、コミットのないリポジトリを使う。`doctor`は読取り専用で、リポジトリ、`HOME`、キャッシュ、
一時ディレクトリを変更しない。プラグインの要求の共通部分は`--plugin bitz-sdd --plugin-version 1.2.0 --require-core-api ^1.0
--require-capability context.v1 --require-capability check.v1`とし、1件につき変えるのは下の1点だけにする。すべて`--format json`で呼ぶ。

| ID | 独立した原因（共通部分からの変更） | 状態／終了コード | 診断 |
|---|---|---|---|
| `SINGLE-160` | なし（互換） | `passed`／0 | なし。`core`の直後に`plugin`、`capability`（ともに`passed`） |
| `SINGLE-161` | `--require-core-api >=1.1` | `blocked`／2 | `SPEC-DOCTOR-API-001`。`plugin`が`blocked`、`capability`は`passed` |
| `SINGLE-162` | `--require-capability context.v2`と`check.v1` | `blocked`／2 | `SPEC-DOCTOR-CAPABILITY-001`。`plugin`は`passed`、`capability`が`blocked` |
| `SINGLE-163` | `--plugin-version`と`--require-core-api`を省く（`--plugin bitz-sdd --require-capability context.v1`だけ） | `failed`／1 | `SPEC-DOCTOR-PLUGIN-001`。`plugin`が`failed`、`capability`なし |
| `SINGLE-164-01` | `--require-core-api ~1.0` | 結果なし／4 | — |
| `SINGLE-164-02` | `--plugin Bitz-SDD` | 結果なし／4 | — |
| `SINGLE-164-03` | `--require-capability context.v0` | 結果なし／4 | — |
| `SINGLE-164-04` | `--plugin-version 1.0` | 結果なし／4 | — |
| `SINGLE-164-05` | `--require-core-api ^1.0.0` | 結果なし／4 | — |
| `SINGLE-164-06` | `--require-core-api ">=1.0  <2.0"`（空白2文字） | 結果なし／4 | — |
| `SINGLE-164-07` | `--plugin-version v1.2.0` | 結果なし／4 | — |
| `SINGLE-164-08` | `--plugin`に65文字のID | 結果なし／4 | — |

## 4. 期待値の導き方（Coreの出力を根拠にしない）

1. **字句**（`164-*`）。ADR-061 Decision 1の正規表現と文法から、各値が一致しないことを導く。`~1.0`は`~`を受け付けない（`01`）。大文字を含む`Bitz-SDD`は
   `^[a-z]...`に一致しない（`02`）。`context.v0`は`v[1-9][0-9]*`に一致しない（`03`）。`1.0`はSemVerの`MAJOR.MINOR.PATCH`にならない（`04`）。
   `^1.0.0`はパッチバージョンを受け付けない（`05`）。比較子は「空白1文字で区切った」ため、空白2文字は空の比較子を含み一致しない（`06`）。
   `v1.2.0`は先頭に`v`があり、SemVer 2.0.0の文法に一致しない（`07`）。65文字は「64文字以下」に反する（`08`）。
   Core実行環境・CLI基盤契約 §5に従い、いずれも終了コード4、標準出力に結果なし、標準エラー出力に理由1行、レポートなしとする。
   1件につき字句の不一致は1つのオプションだけで、残りは字句が正しい。不一致の値を直せば、字句の不一致はなくなる（監査が確かめる）。
2. **判定**（`160`〜`163`）。Core APIは`1.0`（`doctor`仕様 §4、ADR-061 Decision 3）。`^1.0`は`>=1.0 <2.0`なので`1.0`を満たし（`160`、`162`）、`>=1.1`は満たさない（`161`）。
   公開する対応機能は`context.v1`、`check.v1`、`verify.v1`、`doctor.v1`、`multiWorkspace.v1`の5つなので、`context.v2`は不足、`check.v1`は満たす（`162`）。
   検査2と検査3は互いに独立なので、`161`は`plugin`だけ、`162`は`capability`だけが`blocked`になる。
3. **検査項目の並び**。`core`の直後に`plugin`、`capability`を置き、以降は`SINGLE-001`と同じ（`workspace`、`config`、`schema`、`ears`、`git`、`command`、`impact`。`impact`は`info`）。
   検査2・3はワークスペースに依存せず、後続の検査の失敗とも独立なので、`workspace`以降の状態は変わらない（`doctor`仕様 §3）。
   要求が不完全な`163`は検査2と検査3を行わず、`plugin`だけを`failed`とし、`capability`は置かない（ADR-061 Decision 2・4）。
4. **診断**。レジストリの値のとおり、`SPEC-DOCTOR-API-001`と`SPEC-DOCTOR-CAPABILITY-001`は重大度`error`／`blocked`、`SPEC-DOCTOR-PLUGIN-001`は重大度`error`／`failed`。
   発生元は`{kind: environment, component: "plugin", identifier: "bitz-sdd"}`、`evidence`はADR-061 Decision 4のとおり、`161`が
   `{"coreApi": "1.0", "required": ">=1.1"}`、`162`が`{"missing": ["context.v2"]}`、`163`が`{"missing": ["--plugin-version", "--require-core-api"]}`（辞書順）。
5. **状態と終了コード**。操作の状態は診断の`resultStatus`の最悪値（結果・診断・終了コード §3）で、診断のない`160`は`passed`／0、`161`と`162`は`blocked`／2、`163`は`failed`／1。

## 5. `summary`の文字列

規範文は`summary`の文字列を定めない（結果・診断・終了コード §4。人に向けた短い説明）。ランナーは完全一致で比べるため、3つの診断の`summary`は
Coreの`plugins/bitz-core/src/bitz/messages.py`の文言をそのまま使った。**この文字列は規範文から導いた値ではない**。ほかの診断の`summary`を既存のfixtureが
Coreの文言に合わせてきた慣行（`SINGLE-159`のレビュー記録の導出の4）に従った。文言を変えるときは、Coreと期待値を同時に直す別の作業とする。

## 6. 監査と回帰試験

`doctor_plugin_fixtures.py`は、マニフェスト、期待結果、`cli-output.json`、入力のバイト列、読取り専用の副作用の期待値、隔離した2回の準備手順を、
レビュー済みのリテラルと比べる。さらに、引数列だけから期待値を導く参照計算（字句の判定、範囲の比較、検査項目と診断の導出）を、Coreとは別に持ち、
リテラルと一致することを要求する。`test_conformance_audit.py`の回帰試験は、字句の許可と拒否の表、範囲の比較、判定の独立性と診断の並び、
オプションの削除と値の変更、検査項目の欠落・順序・状態の改変、`evidence`と発生元の改変、診断の欠落・混入・重複、終了コードの改変、
字句の不一致のfixtureへの結果の混入を拒否することを確かめる。

## 7. 固定しない範囲

- `--plugin-version`は字句だけを検査し、何とも照合しない（ADR-061 Decision 1）。SemVerの先行版とビルドの付記（`1.2.0-rc.1+build.5`）を受け付ける肯定側の例は、
  fixtureにしない（監査の参照計算の表と、Coreの単体試験が扱う）。
- 検査2と検査3の両方が不適合になる場合の診断の並び（`SPEC-DOCTOR-API-001`、`SPEC-DOCTOR-CAPABILITY-001`の`code`順）は、fixtureにしない。
  `161`と`162`が検査の独立性を両方向から固定し、並びは参照計算の試験が扱う。
- `--require-capability`の同じ値の反復の重複排除、複数の不足の辞書順は、fixtureにしない（`162`の不足は1件）。
- `--format text`の要約行の`targets=`（`checks.length`）への影響、`--workspace`との併用、設定の不在（`SPEC-DOCTOR-WORKSPACE-001`）や
  CPythonの下限未満（`SPEC-DOCTOR-CORE-001`）と同時に起きた場合は扱わない。
- `--plugin`を欠く要求（`SPEC-DOCTOR-PLUGIN-001`の`source`が`identifier`を持たない形）は扱わない。
- `--plugin`の64文字ちょうどの受理（`SINGLE-164-08`は65文字の拒否だけ）は扱わない。

## 8. 確認

- 参照計算とリテラルの期待値は、Coreの出力を見る前に決めた。Coreで一致を確かめたところ、12件とも期待値のまま通過し、期待値をCoreに合わせて直した箇所はない。
- 陰性対照として、修正前のCore（コミット`5927890b`の`cliargs.py`、`doctor.py`、`messages.py`）を作業ツリーの外のコピーに置いて実行した。
  `SINGLE-160`〜`163`は検査項目の欠落（`plugin`、`capability`）と診断・状態・終了コードの相違で、`SINGLE-164-01`〜`08`は終了コード0（拒否されない）で、すべて失敗した。
