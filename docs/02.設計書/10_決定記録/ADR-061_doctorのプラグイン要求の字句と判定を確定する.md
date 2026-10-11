---
id: ADR-061
title: doctorのプラグイン要求の字句と判定を確定する
status: accepted
relations:
  related:
    - ADR-016
    - ADR-051
---

# ADR-061 doctorのプラグイン要求の字句と判定を確定する

## Context

[`doctor`仕様](../../03.詳細設計/03_操作仕様/04_doctor.md) §2〜§4・§8、[診断レジストリ](../../03.詳細設計/00_共通契約/05_診断レジストリ.md)の
`DOCTOR-PLUGIN-FORMAT`、`DOCTOR-API-VERSION`、`DOCTOR-CAPABILITY`、[ADR-016](ADR-016_Agent-Plugins準拠の複数プラグインの配布.md)は、
プラグインが渡す要求（ID、バージョン、要求するCore APIの範囲、対応機能）を`doctor`で判定することをCore 1.0の契約にしている。

一方、Coreは`--plugin`、`--plugin-version`、`--require-core-api`、`--require-capability`を受け付けるが判定に使っておらず、
Core APIや対応機能が要求を満たさなくても`passed`を返す。互換性の判定の正本が偽の成功を返す状態である。また、次が定められていない。

- プラグインのIDの字句、バージョンと範囲の文法
- 要求の一部だけを指定した場合の扱い
- 検査項目の名前、診断の発生元と根拠

## Decision

1. **字句**。次に一致しない値は、[Core実行環境・CLI基盤契約](../../03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md) §5の
   「バージョンまたは範囲の構文に一致しない値」として終了コード4とし、操作の結果を作らない。
   - `--plugin <id>`: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`に一致する64文字以下の文字列（例: `bitz-sdd`）。
   - `--plugin-version <semver>`: SemVer 2.0.0のバージョン（`MAJOR.MINOR.PATCH`。先行版とビルドの付記を許す）。Coreはプラグインの実体を
     探索しないため（`doctor` §4）、字句だけを検査し、何とも照合しない。
   - `--require-core-api <semver-range>`: 空白1文字で区切った1件以上の比較子の論理積。比較子は、`>=`、`>`、`<=`、`<`、`=`のいずれか
     （省略時は`=`）に`MAJOR.MINOR`を続けたもの、または`^MAJOR.MINOR`（`>=MAJOR.MINOR <(MAJOR+1).0`の略記）とする。`MAJOR`と`MINOR`は
     先頭に`0`を含まない十進の非負整数（`0`だけは可）とする。`~`、`x`、`*`、`||`、ハイフンの範囲、パッチバージョンは受け付けない。
   - `--require-capability <capability-name>`: `^[a-zA-Z][a-zA-Z0-9]*\.v[1-9][0-9]*$`（例: `context.v1`）。同じ値は1件へ重複排除する（同契約 §5）。
2. **要求の組合せ**。4種のオプションのどれかを指定した場合を、1つのプラグインの要求として扱う。
   - `--plugin`、`--plugin-version`、`--require-core-api`の3つを同時に指定する。一部を暗黙に補わない（`doctor` §2）。
     `--require-capability`は0件以上とする。
   - 3つのうち欠けたものがあれば、診断`SPEC-DOCTOR-PLUGIN-001`（`failed`）とし、検査2と検査3は行わない。
   - 4種のどれも指定しない通常の実行は、検査2と検査3を行わず、その検査項目も結果へ置かない（`doctor` §4）。
3. **判定**。
   - 検査2（検査項目`plugin`）: CoreのAPIのバージョン（Core 1.0は`1.0`）が要求する範囲のすべての比較子を満たさなければ、
     診断`SPEC-DOCTOR-API-001`（`blocked`）とする。メジャーバージョンが異なる場合も同じである（ADR-016）。
   - 検査3（検査項目`capability`）: 要求した対応機能のうち、Coreが公開しないもの（未知の名前を含む。`doctor` §4）があれば、
     診断`SPEC-DOCTOR-CAPABILITY-001`（`blocked`）とする。要求した対応機能が0件なら通過する。
   - 検査2と検査3は互いに独立に行う。マイナーバージョンの差は、範囲とすべての対応機能を満たす場合だけ許可する（`doctor` §4。上の2つで満たされる）。
4. **結果**。
   - 検査項目`plugin`の状態は、要求の組合せが不完全なら`failed`、範囲を満たさなければ`blocked`、満たせば`passed`とする。
     検査項目`capability`は、要求の組合せが完全な場合だけ置き、不足があれば`blocked`、なければ`passed`とする。
   - 単一ワークスペースでは、検査項目`core`の直後に`plugin`、`capability`の順で置く。`--all-workspaces`では最上位の`checks[]`に1回だけ置き、
     メンバーへ複製しない（`doctor` §3・§7）。
   - 3つの診断の発生元は`{kind: environment, component: "plugin"}`とし、`--plugin`を指定した場合は`identifier`にそのIDを置く。
     `evidence`は、`SPEC-DOCTOR-PLUGIN-001`では欠けたオプションの名前の辞書順の配列`{"missing": [...]}`、`SPEC-DOCTOR-API-001`では
     `{"coreApi": "1.0", "required": "<指定した範囲>"}`、`SPEC-DOCTOR-CAPABILITY-001`では不足した対応機能の辞書順の配列`{"missing": [...]}`とする。
5. **実装計画**。この判定は実装計画のどのStepにも含まれていなかったため、`doctor`を扱うStep 1の範囲の補正として記録し、
   Step 1の完了条件へ適合fixtureを追加する（ADR-051）。fixtureを追加したStepのGate Bは判定し直す。

## Consequences

- プラグインは、Core APIと対応機能の要求を`doctor`へ渡すだけで、互換性を機械的に判定できる。偽の`passed`がなくなる。
- 範囲の文法を最小に保つため、npm形式の範囲をそのまま渡すことはできない。プラグイン側で`^1.0`または比較子の形へ書き直す必要がある。
- `--plugin-version`は字句だけを検査するため、プラグインの実体とバージョンが一致しているかはCoreでは分からない。

## Alternatives

1. **npm形式の範囲（`~`、`x`、`||`など）も受け付ける**: Core APIのバージョンは`MAJOR.MINOR`だけで、最小形で十分に表せる。文法、判定の規則、
   適合fixtureが大きくなるため採らない（ユーザーの決定）。
2. **`--require-core-api`の省略を許し、省略時はAPIの検査を行わない**: 要求の一部を暗黙に補うことになり、`doctor` §2に反するため採らない（ユーザーの決定）。
3. **`--plugin-version`を何かと照合する**: 照合先となるプラグインの宣言の仕組みが新たに必要になり、`doctor` §4の「インストール先を探索しない」と
   衝突するため採らない（ユーザーの決定）。
4. **字句の不一致を`SPEC-DOCTOR-PLUGIN-001`にする**: 同契約 §5がバージョンと範囲の構文の不一致を終了コード4と定めているため採らない。
   `SPEC-DOCTOR-PLUGIN-001`は、字句は正しいが要求の組合せが不完全な場合に使う。

## Notes

- 実装の確認事項C6（`doctor`が`--plugin`などを受け付けるが使っておらず、`doctor` §3の検査2と検査3を出していない）を解消するための決定である。
