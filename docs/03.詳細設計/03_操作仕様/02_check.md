# `bitz check`仕様 1.0

## 1. 目的

EARS-AI、SPEC Schema、ID、関係、状態、path、trace、Git差分を検査する。`--report`なしではfile system上も
読取り専用とし、明示時だけ結果reportを書き出す。

## 2. 公開操作

```text
bitz check [<spec-or-statement-id-or-spec-path>...]
  [--full]
  [--base <git-revision>]
  [--workspace <workspace-id>]
  [--format text|json]
  [--report]
bitz check --all-workspaces
  [--base <git-revision>]
  [--format text|json]
  [--report]
```

明示対象はREQ、TECH、ADR、TASKの文書ID、statement ID、SPEC Markdown pathとする。statement IDとpathは
所有文書IDへ正規化する。連合ではactive／`--workspace`で選択したworkspaceの非修飾IDとpath、または修飾IDを
受け付け、1回の単独操作の対象workspaceを1つに限定する。code path、test path、directory、不正ID/path、
異なるworkspaceを所有する対象の混在は引数不正で終了コード4とする。

`--full`と明示対象は排他的である。引数なしはGit変更集合を起点にする。
`--all-workspaces`は同じGit rootとfederation rootを探索起点から一意に発見できる場合だけ許可し、current directoryの
root一致は要求しない。明示対象、`--full`、`--workspace`と排他的である。
全体操作は`--full`を含意し、catalog、全workspace、横断関係、所有境界を検査する。

## 3. 共通索引と完全検査

どのscopeでも単一workspaceまたは連合catalog全体の軽量Frontmatter索引を構築する。EARS-AI ASTと本文の
完全検査対象は次とする。

- 明示対象: 対象文書、強い依存閉包、直接逆参照
- 引数なし: Git変更から選んだ所有文書、強い依存閉包、直接逆参照
- `--full`: 全SPEC
- `--all-workspaces`: catalog内の全SPEC

軽量索引の構築と対象文書の完全解析を混同しない。
`--all-workspaces`は共通preflightでbase/currentのGit既知`.spec/bitz.yaml`を、連合を宣言している各snapshot自身の
catalogと比較する。初回連合化前の単一workspace baseへ全体列挙を適用しない。catalog、ID、path、Git境界、
未対応major、resource上限が非成功ならworkspace別検査を開始しない。

## 4. 検査順序

1. `bitz.yaml` Schema、連合catalog、互換性
2. file名、Frontmatter、ID一意性
3. EARS-AI構文と文書ID整合
4. relationのID、型、状態、循環
5. `implements`、test対応、command解決
6. H1、REQ必須section、規範文配置
7. 状態遷移と管理済みSPEC削除
8. 承認済みREQ保護
9. 明示TASKの`changes`境界
10. changed strong dependencyの直接逆参照による影響候補

global preflight非成功ならworkspace別検査を開始しない。preflight通過後に後段へ進めないerrorがあっても、
独立fileのDiagnosticは可能な範囲で返す。継続単位は文書と、その文書をsourceとするedgeであり、別workspaceの
非成功だけを理由に無関係な文書検査を省略しない。strong targetを解釈できないsourceは具体的なrelation Diagnosticを
持つ非成功とし、その依存閉包だけを完全Contextとして扱わない。

## 5. Git基準版と変更集合

`--base`指定時は解決済みcommit、未指定時は`HEAD`を基準版とする。変更集合は次の和集合である。

- 基準版からindex
- indexからworking tree
- 未追跡かつ非ignore path
- 削除とrename

同じ基準版を対象選択、状態遷移、削除検出、REQ保護、TASK境界へ使用し、結果`revision.base`へfull commit IDを
記録する。revisionを解決できなければ終了コード4とする。

基準版と現在版はdocument IDで対応付け、pathだけの変更はrenameとする。基準版IDが現在版にない場合は
管理済みSPEC削除としてfailedとする。

`--all-workspaces`ではrepository全体で1つの基準commitを使い、基準版と現在版の両catalogからworkspace修飾IDで
文書を対応付ける。member削除または移動時の扱いは
[モノレポSPEC連合仕様](../02_SPECモデル/05_モノレポSPEC連合仕様.md)に従う。

初回連合化では、baseのrepository root設定が`monorepo`と明示`workspace.id`を持たない場合だけ、実効ID `root`を
currentのfederation root IDへ比較上で写像する。連合化後のID renameは推定せず、member pathだけの移動は同じIDで
対応付ける。catalogから消えたmemberの管理済みSPECは削除検査の対象から外さない。

## 6. 引数なし対象選択

| changed path | 所有文書への正規化 |
|---|---|
| SPEC path | Frontmatter ID |
| code path | `implements`逆索引のREQ/TECH |
| test path | `tests[].path`逆索引のREQ/TECH |

どの逆索引にも該当しないcode/test pathは対象外とし、Diagnosticを出さず件数だけを結果へ残す。
rejected REQ/TECHは所有逆索引へ含めない。

連合のworkspace単独操作では、選択workspaceが所有するchanged pathだけを起点にする。横断する強い依存閉包と
直接逆参照は通常どおり辿るが、別workspaceの無関係な変更を対象へ混ぜない。

対象文書が0件で、設定、索引、Git縮退を含む他Diagnosticがなければpassedとする。設定検査と索引構築は省略しない。

## 7. TASK境界

TASK IDまたはTASK pathを明示した場合だけ、同じGit基準版からの変更pathを`changes`と比較する。境界外変更は
`SPEC-TASK-BOUNDARY-001`／failedとする。TASK自身のfileと明示生成reportは比較対象から除く。

`changes`のfileは正規化した字句Git pathの完全一致、末尾`/`のdirectory prefixはpath segment単位の子孫一致で
変更を許可する。symlink解決先の別の字句pathへ許可を拡張しない。宣言pathと変更pathには所有境界検査を先に適用し、
追加はcurrent、削除はbase、変更とsymlink変更はbase/current双方、renameはsourceとdestinationの2 pathを検査する。
所有境界不適合と`SPEC-TASK-BOUNDARY-001`を同じpathへ重複して返さない。

引数なし、`--full`でTASKが選ばれても文書検査だけを行い、境界未実施をwarningにしない。Git不在では
`SPEC-TASK-BOUNDARY-002`／blockedとする。

## 8. 影響候補

changed REQ/TECHへ強く依存するapproved文書を`SPEC-IMPACT-OUTDATED-001`／warningとして示す。
Coreは意味的影響を断定せず、statusを自動変更しない。`related`、code、test変更を影響候補の起点にしない。

## 9. 結果

```json
{
  "schemaVersion": "1.0",
  "operation": "check",
  "status": "passed",
  "scope": "changed",
  "workspace": {"id": "root", "path": "."},
  "revision": {"base": "89abcdef0123456789abcdef0123456789abcdef", "commit": "0123456789abcdef0123456789abcdef01234567", "dirty": true},
  "selection": {
    "changedPathCount": 3,
    "targetDocumentCount": 1,
    "excludedCodeTestPathCount": 2
  },
  "durationMs": 184,
  "diagnostics": []
}
```

`scope: changed`では`selection`を必須とする。text出力も同じ3件数を使う。
`--all-workspaces`では`scope: all-workspaces`と共通の`federation`、`workspaces`外形を使用し、各memberの
`checkedDocumentCount`、`checkedStatementCount`とDiagnosticをmember結果へ保持する。両件数は非負integerで必須とし、
全SPECを完全検査した文書数と規範文数を表す。repository共通の`revision`はtop-levelに1件だけ置き、member結果へ
複製しない。完全JSON例は[共通結果契約](../00_共通契約/01_結果・Diagnostic・終了コード.md#21-check全体結果)を正とする。

## 10. Git不在

単一workspaceの引数なしcheckは全体checkへ縮退する。REQ保護、遷移、削除検出の失われる保証をwarningで示す。
明示TASK境界だけはblockedとする。詳細は[安全な入出力](../00_共通契約/02_安全な入出力・互換性.md)に従う。

## 11. Diagnostic

| code | result | 条件 |
|---|---|---|
| `SPEC-CONFIG-SCHEMA-001` | error／blocked | 設定不正／未知major |
| `SPEC-INPUT-READ-001` | failed／error | UTF-8不正／I/O障害 |
| `SPEC-FILE-NAME-001` | failed | file名ID不一致 |
| `SPEC-FM-REQUIRED-001` | failed | Frontmatter必須field不足 |
| `SPEC-REQ-STATEMENT-001` | failed | approved REQに妥当statementなし |
| `SPEC-ID-DUPLICATE-001` | failed | ID重複 |
| `SPEC-RELATION-LEGACY-001` | failed | 旧`refs`使用 |
| `SPEC-RELATION-MISSING-001` | failed | strong target不在 |
| `CTX-RELATION-TYPE-001` | failed | 存在するsource／targetの型不適合 |
| `SPEC-PATH-INVALID-001` | failed／warning | path不正。draft予定だけwarning |
| `SPEC-TEST-COVERAGE-001` | failed | `covers`不正 |
| `SPEC-SAFETY-APPROVED-001` | failed | approvedを戻さず意味変更 |
| `SPEC-STATE-TRANSITION-001` | failed | 禁止遷移または管理済みSPEC削除 |
| `SPEC-TASK-BOUNDARY-001` | failed | 明示TASK境界外変更 |
| `SPEC-TASK-BOUNDARY-002` | blocked | Git不在でTASK境界不能 |
| `SPEC-IMPACT-OUTDATED-001` | passed_with_warnings | strong dependency変更 |
| `SPEC-STYLE-H1-001` | failed | H1不正 |
| `SPEC-STYLE-SECTION-001` | failed | REQ必須section不在・空 |
| `SPEC-STYLE-PLACEMENT-001` | failed | 規範文が文書種別ごとの許可位置外 |

Core 1.0は`idCollisions`、`SPEC-BASE-AMBIGUOUS-001`、H2順序・空節・疑似節Diagnosticを返さない。
連合固有Diagnosticは[モノレポSPEC連合仕様](../02_SPECモデル/05_モノレポSPEC連合仕様.md)が所有する。
