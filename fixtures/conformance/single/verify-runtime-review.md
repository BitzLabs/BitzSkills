# verify argv・実行環境・出力変換fixtureレビュー

2026-09-17。SINGLE-126-01〜05、07、09〜16の14件を追加する。126-06と126-08は後述の理由で保留する。
根拠は[workspace・設定仕様 §6](../../../docs/03.詳細設計/02_SPECモデル/01_workspace・設定仕様.md#6-command定義)、
[verify仕様 §5・§6](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#5-command実行)、
[安全な入出力 §9](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#9-process出力)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)である。

全caseはSINGLE-042のcorpusでcommand定義だけを替え、indexへstageしてから`verify REQ-001 --format json`を実行する。
Git履歴はunbornのため`revision: null`である。実行するcaseでは、auditがfixture自身のscriptを直接起動し、
期待した入力でだけ期待どおりに振る舞うことを観測する。これはCore verifyの実行ではない。
Context Digestは独立した2系統のreference計算で一致を確認する。

## argv template違反（`verify_argv_fixtures.py`）

| ID | 唯一の違反 | status／終了コード | Diagnostic key |
|---|---|---|---|
| SINGLE-126-01 | `argv[1]`がinteger 42 | error／3 | `verify.commands.default.argv[1]` |
| SINGLE-126-02 | `argv[0]`が空string | error／3 | `verify.commands.default.argv[0]` |
| SINGLE-126-03 | `argv[1]`がNULを含む（YAMLの`"a\0b"`） | error／3 | `verify.commands.default.argv[1]` |
| SINGLE-126-04 | templateが257要素 | error／3 | `verify.commands.default.argv` |
| SINGLE-126-05 | `argv[1]`が32,769 byte | error／3 | `verify.commands.default.argv[1]` |

いずれも`SPEC-CONFIG-SCHEMA-001`（`CONFIG-FIELD-TYPE`、`stop-operation`）の1件だけを持つ。設定の型・値域不正は
workspace identityの確定前に停止するため、`workspace.id`とsourceの`workspaceId`はnull、`targetResults`と
`commands`は空とする。要素単位の違反は要素index付きkey、配列全体の違反は配列keyとする。
auditは設定のflow配列を独立にdecodeし、仕様の規則を適用して違反がちょうど1件であることを確認する。
設定fileは64 KiB上限内に収まることも確認する。

## 実行環境（`verify_argv_fixtures.py`）

| ID | 条件 | status／終了コード | 固定する点 |
|---|---|---|---|
| SINGLE-126-07 | `["bin/args.sh", "", "{tests}"]` | passed／0 | 公開`argv`に空stringを保持し、scriptは3引数かつ`$1`が空のときだけ成功 |
| SINGLE-126-09 | `bitz-fixture-absent-command`はPATHにない | blocked／2 | top-levelに`SPEC-VERIFY-BLOCKED-001`（environment、`root::default`）1件、targetは`bindingRefs: []`、`commands: []` |
| SINGLE-126-10 | stdinを読むscript | passed／0 | 即時EOFでだけ成功し、読める行があれば失敗 |
| SINGLE-126-11 | `cwd: tests`、`./probe.awk`、追加環境変数 | passed／0 | 継承した`LANG`・`LC_COLLATE`・任意変数を保持し、`PWD`だけ実効cwdの絶対path |

126-11はmanifestの`env`で`PWD`を存在しないpathにして起動する。POSIX shは起動時に`PWD`を再計算するため、
probeはawkで環境をそのまま読む（`/usr/bin/awk`を前提とする）。`cwd: tests`なので`{tests}`は`test_auth.py`、
`test_session.py`へcwd相対で展開し、公開`tests`はworkspace相対のまま保持する。
auditは、実効`PWD`なら成功し、古い`PWD`、任意変数の欠落、`LANG`の変更ではいずれも失敗することを観測する。
126-09は実行環境の`PATH`に同名commandがないことをauditで確認する。

## process終了と出力変換（`verify_stream_fixtures.py`）

| ID | 条件 | status／終了コード | 固定する点 |
|---|---|---|---|
| SINGLE-126-12 | timeout 1秒、`setsid`で別sessionへ移った子孫がpipeを8秒保持 | error／3 | `termination: timeout`、`exitCode: null`、抜粋は`orphan-ready\n` |
| SINGLE-126-13 | `alpha`がtimeout、辞書順で後の`beta`は`/bin/true` | error／3 | 2 commandとも記録し、`beta`はpassed、Diagnosticは`root::alpha`のtimeoutだけ |
| SINGLE-126-14 | 不正UTF-8、CRLF、単独CR、ESC、C0、DEL、C1、TAB | passed／0 | U+FFFD、LF、``等の小文字16進、TABは保持 |
| SINGLE-126-15 | 環境secretと定型secretをsleepで分割出力 | passed／0 | 全対象が`[REDACTED]`、生値なし |
| SINGLE-126-16 | 環境secret `qz`（2 byte）の6,553回反復 | passed／0 | redaction後65,537 byte、末尾をcode point境界で65,534 byte保持、`stdoutTruncated: false` |

126-12の子孫は、別sessionへ移りTERMを無視するtrapを設定した後にreadiness行を出す。直接processは
graceful terminationで終わるが、EOFは約8秒後まで来ない。EOFを待つ実装はtimeout到達から5秒以内に
結果を確定できない。auditは、直接processがTERMで終了した後も5秒以上pipeがEOFにならないこと、
その後有限時間でEOFになることを観測する。`setsid`（util-linux）を前提とする。
126-13のhang scriptはSINGLE-059と同じもので、同じ観測関数を使う。

126-15では次の読みを固定する。

- 環境変数値（名前に`TOKEN`を含む）は値全体を置換する
- `Authorization:`と、行値規則の`password=`は区切り記号を残し、その直後から行末までを置換する
- `Bearer `は語と空白を残し、続く非空白tokenを置換する
- PEMは`-----BEGIN ... PRIVATE KEY-----`から`-----END ... PRIVATE KEY-----`までを1つの`[REDACTED]`へ置換し、
  直後の改行は残す

区切り記号の後の空白をどう扱うかという曖昧さを避けるため、入力には区切り記号の直後に空白を置かない。
auditは全文を一括処理する参照変換で期待抜粋を再計算し、scriptの分割出力に依存しない期待値とする。

126-14〜16では、実行環境にredaction対象名の環境変数があり、その値が期待出力に現れる場合は
抜粋が環境へ依存するため、auditを失敗させる。

回帰試験では、違反keyの改変、`workspace.id`の確定、code改変、二重診断、終了コード改変、空引数の削除、
blocked targetへのbinding参照やDiagnostic複製、status改変、`PWD`上書きの除去、cwd相対展開の破壊、
timeoutのsignal化、後続binding結果の削除、CR残存、secret生値の残存、secret環境の除去、truncated flagの改変を
いずれも拒否する。期待と異なる挙動のscript（常に成功するscript、setsidを使わないscript、ESCを出さないscript）も
直接観測で拒否する。Core、process runner、redaction実装は作らない。実際の挙動はGate Bで受け入れる。

## 保留するfixture

- **SINGLE-126-06（argv templateのbyte総和が1 MiB超過）**: `bitz.yaml`自体が64 KiB上限であり、YAMLにはanchorも
  展開もないため、1 MiBを超えるtemplateを持つ設定は先に`SPEC-INPUT-LIMIT-001`で拒否される。
  現行仕様では`SPEC-CONFIG-SCHEMA-001`に到達できず、matrixと仕様の整合を裁定する必要がある。
- **SINGLE-126-08（`{tests}`展開後argvの上限超過）**: 到達は可能だが、要素32 KiBはpath長上限のため超過できず、
  10,000要素は約1万file、1 MiBは約4,000 byteのpathを約260件（Frontmatter 32 KiB上限のためTECH約38文書）必要とする。
  fixtureは数MiBになるため、作成方針を確認してから追加する。
