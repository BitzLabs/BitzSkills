# `bitz verify`仕様 1.0

## 1. 目的

対象SPECのContextを再解決し、対象`MUST`にtest対応があることを確認して、`bitz.yaml`に定義されたcommandを
実行する。LLMを使わず、要求、test、実行結果を対応付ける。

## 2. 公開操作

```text
bitz verify [<req-tech-statement-task-or-spec-path>...]
  [--workspace <workspace-id>]
  [--timeout <seconds>]
  [--format text|json]
  [--report]
bitz verify --all-workspaces
  [--timeout <seconds>]
  [--format text|json]
  [--report]
```

明示対象はREQ ID、TECH ID、statement ID、TASK ID、REQ/TECH/TASK Markdown pathとする。pathはFrontmatter IDへ
正規化する。連合ではactive／`--workspace`で選択したworkspaceの非修飾IDとpath、または修飾IDを受け付け、
1回の単独操作の対象workspaceを1つに限定する。code/test path、directory、ADR、異なるworkspaceを所有する
対象の混在は引数不正で終了コード4とする。

`--all-workspaces`はfederation rootでだけ許可し、明示対象と`--workspace`に排他的である。各workspaceへ引数なし
verifyを適用し、結果を集約する。

## 3. 対象

| 起点 | target |
|---|---|
| REQ ID | 所有全statementとapplicable dependency/refinement |
| 規範文ありTECH ID | 所有全statementとapplicable dependency/refinement |
| statement ID | 指定句と直接applicable refinement。兄弟句はadjacent |
| 規範文なしTECH | 文書単位`tests` |
| open TASK | `addresses`句／TECHと`requires`閉包 |
| done TASK | 完了作業の再検証として同上 |
| cancelled TASK | `CTX-STATE-001`／blocked |

複数対象はIDへ正規化し、target statement集合を和集合にして重複排除する。

## 4. 処理

1. `purpose=verify` Contextを完全解決する。
2. 起点と強い依存の適用可能性、先行TASKのdoneを確認する。
3. target statementを確定し、全`MUST`へ1件以上のtest対応を要求する。
4. test pathとcommand名を解決する。
5. 同じ`(workspaceId, commandName)`に属するtest pathを所有workspace相対pathで重複排除し、辞書順に並べる。
6. workspace処理順、command名辞書順でbindingを逐次実行する。
7. Context Digest、対象句、実効timeout、終了理由、終了コード、所要時間を記録する。

異なるcommand名はargv/cwdが同じでも別bindingとして実行する。同じworkspaceの同じcommand名は1回だけ実行する。
workspaceが異なればcommand名と内容が同じでも別bindingとする。

## 5. command実行

- `{tests}`がある場合、重複排除したpathを1回だけargvへ展開する。
- `{tests}`がない場合、path数にかかわらずargvを1回実行する。
- testを所有するworkspaceが設定した`cwd`で実行し、未指定はそのworkspace rootとする。
- shellを介さない。
- 1件がfailed/errorでも解決済みの独立bindingを継続する。
- Core 1.0は並列実行とfail-fast optionを提供しない。

実効timeoutは`min(CLI cap, 設定timeout)`で、CLI未指定時は設定値を使う。Coreが停止を保証するのは直接起動した
processまでで、子孫processはcommand側の責務とする。

stdout/stderrは終了までdrainし、各末尾64 KiBだけを一時保持する。Coreは出力自然言語を合否へ使わない。

## 6. command結果

| termination | 条件 | status |
|---|---|---|
| `exit`、code 0 | 通常成功 | passed |
| `exit`、code非0 | test不合格 | failed |
| `spawn_error` | 起動不能 | error |
| `signal` | signal終了 | error |
| `timeout` | timeout | error |

coverage、command、環境不足はtestを開始せずblockedとする。

## 7. 引数なし実行

次を対象にする。

- approved REQ
- approved TECHのうち、statementを持つもの
- approved TECHのうち、statementを持たず`tests`を宣言するもの

対象ごとにContextを解決し、未tested MUSTを持つ対象だけblockedとして独立対象を継続する。同じcommand名の
test pathは全対象でまとめ、1回実行する。対象0件は`SPEC-VERIFY-BLOCKED-002`／blockedとし、空CIを成功にしない。

## 8. 結果

```json
{
  "schemaVersion": "1.0",
  "operation": "verify",
  "status": "passed",
  "scope": "selected",
  "workspace": {"id": "root", "path": "."},
  "targets": ["REQ-001"],
  "contextDigest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "statements": ["REQ-001:AC-01"],
  "revision": {"commit": "0123456789abcdef", "dirty": false},
  "commands": [
    {
      "name": "default",
      "status": "passed",
      "termination": "exit",
      "cwd": ".",
      "argv": ["pytest", "-q", "tests/auth/test_service.py"],
      "tests": ["tests/auth/test_service.py"],
      "covers": ["REQ-001:AC-01"],
      "exitCode": 0,
      "timeoutSeconds": 300,
      "durationMs": 817
    }
  ],
  "durationMs": 842,
  "diagnostics": []
}
```

`commands[]`はcommand名単位の実行実体である。`argv`は展開後、`tests`はworkspace相対宣言path、`cwd`は
workspace root相対で未指定時`.`とする。通常終了以外は`exitCode: null`とする。
連合内のworkspace単独結果では、command実体をその操作結果へ置き、`workspaceId`と
`bindingId: <workspace-id>::<command-name>`を追加する。対象と句のIDは修飾形式で返す。

`verified`は特定Context Digest、code、test、環境に対する実行時述語で、Frontmatter状態ではない。
Context Digestが変われば以前の成功を現在の根拠にしない。

## 9. Diagnostic

| code | result | 条件 |
|---|---|---|
| `SPEC-VERIFY-BLOCKED-001` | blocked | testまたはcommand不足 |
| `SPEC-VERIFY-BLOCKED-002` | blocked／passed_with_warnings | 単一・連合全体の対象0件／連合member単位の対象0件 |
| `SPEC-VERIFY-COMMAND-001` | error | 起動不能またはsignal |
| `SPEC-VERIFY-TIMEOUT-001` | error | timeout |
| `CTX-COVERAGE-TEST-001` | blocked | 対象MUSTが未tested |

report生成、秘密情報、result集約は共通契約に従う。

## 10. 全体実行

`verify --all-workspaces`はfederation rootを先頭、その後をworkspace ID辞書順に処理する。実行済みbinding集合は
連合全体で1つ保持し、横断refinementが参照する同じ`(workspaceId, commandName)`を二重実行しない。失敗した
workspaceがあっても、依存しない後続workspaceの解決済みbindingは継続する。

全workspaceの対象とContextを先に解決してbindingの和集合を作り、workspace処理順、command名辞書順で実行する。
command実体は所有workspaceのmember結果の`commands[]`へ1回だけ置く。各member結果は自身の対象が必要とする
`bindingRefs[]`へ`<workspace-id>::<command-name>`を列挙し、別memberが所有する実行結果を参照する。
member statusは自身のContext／coverage結果と全`bindingRefs`の実行statusの最悪値とする。commandを所有する
memberのstatusにも、そのcommandの実行statusを反映する。これにより横断testの失敗を依頼側と実行所有側の
どちらからも隠さず、command結果自体は複製しない。

workspace単位の引数なし対象が0件の場合、`SPEC-VERIFY-BLOCKED-002`をwarningとしてmember結果を
`passed_with_warnings`にする。連合全体の対象が0件の場合だけerror／`blocked`とする。結果は
[モノレポSPEC連合仕様](../02_SPECモデル/05_モノレポSPEC連合仕様.md)の集約外形を使う。
