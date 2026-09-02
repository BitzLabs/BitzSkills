# P0 verify証跡Schema検討

- 状態: Accepted / Reflected
- 実施日: 2026-09-02
- 基準commit: `b070c6e`
- 対象: `FED-VER-001`、`FED-CROSS-001`
- 前提: Core 1.0は仕様検討段階で未リリース
- 裁定: [ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)

## 1. 解決する問題

`verify`は、明示対象、引数なし実行、`--all-workspaces`で複数のContextを解決できる。一方、現在の結果Schemaは
top-levelに`contextDigest`を1つだけ持つため、次の対応を表せない。

```text
target -> Context Digest -> statement -> binding -> command result
```

Context Digestを任意の代表値にすると、他のtargetについて`verified`とstale判定が成立しない。Digestを連結した新しい
hashにすると、個々のContext Digestを再検証できず、「公開hashはContext Digestだけ」という既存方針から外れる。

## 2. 比較した案

| 案 | 内容 | 評価 |
|---|---|---|
| A | 全targetを1つのmulti-root ContextにしてDigestを1つにする | 不採用。引数なしと全workspaceは非成功targetを独立継続するため、結局複数Contextになる |
| B | `targetResults[]`ごとにContext Digestとbinding参照を持つ | 推奨。verifiedの単位と失敗継続の単位が一致する |
| C | `contexts[]`を別表にし、targetから`contextRef`で参照する | 不採用。Digest自体が一意な参照値であり、Core 1.0には正規化が過剰 |

## 3. 推奨する裁定

### 3.1 targetを証跡単位にする

明示対象、引数なし対象とも、正規化したtargetごとに`purpose=verify` Contextを1件解決する。複数targetを先に
1つのContextへ束ねない。強い関係は各Contextの完全閉包で解決するため、意味依存は失われない。

- 明示対象: ID／pathを正規target IDへ変換し、重複排除後の辞書順
- 引数なし: 対象REQ／TECHを正規IDへ変換し、辞書順
- 全workspace: workspace処理順の中で上記順序を使う
- TASK: TASK IDを1 targetとし、`addresses`と`requires`はそのContext内で解決する

target間でstatementやtestが重複してもよい。statementは各targetの証跡へ残し、command bindingだけを実行計画で
重複排除する。

### 3.2 `targetResults[]`を正本にする

top-levelの`targets[]`、`contextDigest`、`statements[]`を廃止し、次を置く。

| field | 型 | 必須 | 意味 |
|---|---|:--:|---|
| `target` | string | Yes | 正規target ID。連合では修飾形式 |
| `status` | enum | Yes | Context、coverage、参照binding結果の最悪値 |
| `contextDigest` | string/null | Yes | 完全ContextのDigest。Contextを構成できない場合だけnull |
| `statements` | string[] | Yes | このtargetが検証する規範文。重複なし辞書順 |
| `bindingRefs` | string[] | Yes | 必要なbinding ID。重複なし辞書順 |
| `diagnostics` | array | Yes | このtarget固有のDiagnostic |

規範文なしTECHは`statements: []`でも文書単位testの`bindingRefs`を持てる。Contextは完全だが未tested MUSTを持つ場合、
`contextDigest`は保持し、`status: blocked`、`bindingRefs: []`とする。

### 3.3 binding IDを全verify結果で統一する

単一workspaceを含め、binding IDを`<workspace-id>::<command-name>`へ統一する。workspace ID省略時の実効値は`root`である。
`commands[]`の各要素は`bindingId`と`workspaceId`を必須とし、`targetResults[].bindingRefs`から一意に参照できるようにする。

単一workspaceと連合でSchemaを分岐させず、連合時だけIDの修飾規則が変わるのはSPEC targetとstatementに限定する。

### 3.4 実行計画への採用条件

処理を次の2段階に分ける。

1. 全targetのContext、coverage、必要bindingを解決する
2. Contextとcoverageが通過statusのtargetから`bindingRefs`の和集合を作り、各bindingを1回だけ実行する

blocked／failed／error targetだけが要求するbindingは実行しない。別の通過targetも同じbindingを要求する場合は実行し、
その結果を通過targetへだけ反映する。非成功targetの元statusはcommand結果で上書きしない。

### 3.5 statusの計算

target statusは次の最悪値で計算する。

```text
Context解決status + coverage status + 全bindingRefsのcommand status
```

top-levelまたはworkspace statusは、全target status、所有するcommand実体のstatus、当該scopeのDiagnosticを集約する。
command失敗は参照targetのstatusへ反映し、連合ではcommand owner workspaceのstatusにも反映するが、command実体と
durationを複製しない。

### 3.6 `verified`述語

1つのtargetが現在の実行でverifiedである条件を次とする。

1. `targetResults[].status`が`passed`または`passed_with_warnings`
2. `contextDigest`がnullでない
3. 対象となる全`MUST`にtest対応がある
4. 全`bindingRefs`がちょうど1件の`commands[]`を参照する
5. 参照する全commandが`passed`である
6. top-level `revision`がこの実行時のcode／test状態を表す

結果全体の通過は全targetがverifiedであることに加え、targetを持たないowner commandやtop-level Diagnosticも
通過statusであることを要求する。

### 3.7 結果生成と保存を分離する

`targetResults[]`は標準出力または明示reportに含まれる実行時結果であり、SPECへ書き戻さない。`check`と`verify`は
成功・非成功を問わず`--report`指定時だけfileを保存する。`--report`がなければ既存reportを変更せず、新規作成もしない。

並行PR／worktreeの検査で生成reportが差分や残留fileになった既存事例を踏まえ、Git除外を自動保存の根拠にしない。
CIは標準出力と終了コードを既定とし、artifactが必要なjobだけ`--report`を明示する。

## 4. 推奨結果例

異なるContextを持つ2 targetが同じbindingを共有する最小例を示す。

```json
{
  "schemaVersion": "1.0",
  "operation": "verify",
  "status": "passed",
  "scope": "selected",
  "workspace": {"id": "root", "path": "."},
  "targetResults": [
    {
      "target": "REQ-001",
      "status": "passed",
      "contextDigest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "statements": ["REQ-001:AC-01"],
      "bindingRefs": ["root::default"],
      "diagnostics": []
    },
    {
      "target": "REQ-002",
      "status": "passed",
      "contextDigest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "statements": ["REQ-002:AC-01"],
      "bindingRefs": ["root::default"],
      "diagnostics": []
    }
  ],
  "revision": {"commit": "0123456789abcdef", "dirty": false},
  "commands": [
    {
      "bindingId": "root::default",
      "workspaceId": "root",
      "name": "default",
      "status": "passed",
      "termination": "exit",
      "cwd": ".",
      "argv": ["pytest", "-q", "tests/auth/test_service.py"],
      "tests": ["tests/auth/test_service.py"],
      "covers": ["REQ-001:AC-01", "REQ-002:AC-01"],
      "exitCode": 0,
      "timeoutSeconds": 300,
      "durationMs": 817
    }
  ],
  "durationMs": 842,
  "diagnostics": []
}
```

## 5. 不変条件

- `targetResults[].target`は結果内で一意
- 非null `contextDigest`は同じtargetのContext requestから得た値
- 全`bindingRefs`は結果内の`commands[].bindingId`を参照する。実行計画作成前に非成功となったtargetは空配列
- `commands[].bindingId`は結果内で一意
- `commands[].covers`は、当該bindingを参照する通過targetのstatement和集合
- 同じbindingを参照するtarget数にかかわらずcommand実体は1件
- top-level `status`は子要素より良いstatusにならない

## 6. 正本への反映範囲

| 文書 | 変更 |
|---|---|
| `03_verify.md` | target単位Context、結果Schema、binding採用条件、verified述語を置換 |
| `01_結果・Diagnostic・終了コード.md` | `targetResults[]`の集約と明示report保存を定義 |
| `05_モノレポSPEC連合仕様.md` | member結果と共有bindingの参照規則だけを同期 |
| `12_Core-1.0実装計画.md` | multi-context、共有binding、非成功混在fixtureを追加 |
| レビュー16・20、README | P0の裁定と反映状態を記録 |

公開hashの種類、command名binding、Context Digestの計算材料は変えない。report自動保存の既存裁定を変更するため、
理由をADR-041へ記録した。未リリースの初回1.0 Schemaなので、旧verify結果との移行fieldは設けない。

## 7. 裁定案

次を一括採用する。

1. targetごとにContextを解決する
2. `targetResults[]`をverified証跡の正本にする
3. top-level `targets[]`、`contextDigest`、`statements[]`を廃止する
4. binding IDを単一workspaceを含め`<workspace-id>::<command-name>`へ統一する
5. 非成功targetだけが要求するbindingは実行しない
6. target statusと全体statusを別々に集約する
7. `--report`なしではstatusにかかわらず結果fileを保存しない

7点をADR-041で採用し、FED-VER-001のP0と、同じ証跡対応に起因するFED-VER-002〜005を同時に閉じた。
