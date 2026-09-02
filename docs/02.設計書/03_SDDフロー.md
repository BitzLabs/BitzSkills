# SDDフロー

## 1. 目的

SDDフローはCoreの公開操作を使って開発を進めるadapter／Skillの契約である。Coreはフロー状態、Human Review、
commitを保持せず、各段階で決定論的な検査結果を返す。

## 2. フロー選択

| 条件 | フロー |
|---|---|
| 通常のbug fix、局所機能、refactoring | Small Flow |
| 公開API、永続data、security、費用、法令、SLO、複数moduleへ影響 | Full Flow |
| 技術的不確実性が高く要求確定前の証拠が必要 | Spike |

## 3. Small Flow

```text
Intent -> Context -> Pre-check -> Implement -> Post-check -> Verify -> Human Review -> Done
```

1. **Intent**: `approved` REQ／TECH、その規範文、または`open` TASKを起点として特定する。
2. **Context**: `purpose=implement`の完全なBundleを取得し、通過statusであることを確認する。
3. **Pre-check**: `bitz check <起点ID>`が通過statusであることを確認する。
4. **Implement**: 最初の書込み直前にContext Digestを再照合し、境界内のcodeとtestを変更する。
5. **Post-check**: `bitz check`を再実行する。TASK起点では`bitz check <TASK-ID>`で`changes`を検査する。
6. **Verify**: `purpose=verify`を解決し、`bitz verify <ID>`が通過statusであることを確認する。
7. **Human Review**: 対応句、test結果、最終diff、未証明事項を人間が確認する。
8. **Done**: TASK起点なら`done`へ変更し、最終`bitz check <TASK-ID>`を通してGitへ記録する。

Context、check、verifyは`passed`または`passed_with_warnings`だけを通過statusとする。Contextはさらに
`resolution.complete: true`とContext Digestを必要とする。`failed`、`blocked`、`error`、引数不正では
次段階へ進まず、verify非成功時はHuman ReviewとDoneへ進まない。Core 1.0はwarningを昇格する`--strict`を
提供しない。

## 4. Full Flow

```text
Intent -> Interpret Context -> Requirement Review -> Approval
       -> Implement Context -> Design Review -> Pre-check
       -> Implement -> Post-check -> Verify -> Human Review -> Done
```

Full FlowはSmall Flowへ要求と設計の明示reviewを追加する。要求review前は`purpose=interpret`を使い、
`draft`をadvisoryとして読めるようにする。要求を承認した後に`purpose=implement`を解決する。検査command、
実装後の順序、Done条件はSmall Flowと同じものを使用し、別の実行engineを作らない。

- Requirement Reviewは目的、意味、受入条件、互換性を確認する。
- 新規または編集中のREQ／TECHはreview後に`approved`へ変更し、`bitz check <ID>`を通す。
- `approved` REQ／TECHを意味変更する場合は、変更と同じ作業で先に`draft`または`outdated`へ戻し、review後に
  `approved`へ変更して再checkする。
- Design Reviewは依存、変更境界、異常系、検証方法を確認する。
- review結果はCoreへ保存せず、Git／PRへ記録する。
- 要求、依存、設定を変更した場合は、Approval後のImplement Contextを再取得する。

## 5. Spike

Spikeは本番成果物と分離した実験である。

- 実験目的、時間、隔離範囲を定める。
- 結果、失敗、制約、採否をREQ、TECH、ADR、Issueのいずれかへ短く反映する。
- Spike成果物をそのまま本番へmergeしない。
- 採用実装はSmall FlowまたはFull Flowで作る。

Profileタグ、専用run状態、Gate engineはCore 1.0に追加しない。

## 6. プリフライト

実装開始には次を要求する。

- 起点IDが存在する。
- Contextが`passed`または`passed_with_warnings`で、`resolution.complete: true`である。
- 対象`MUST`句が列挙されている。
- 変更予定pathがadapterの作業計画に列挙されている。Coreによる境界強制が必要ならTASK `changes`へ記録する。
- test commandを解決できる。
- 既存の未commit変更と衝突しない。
- TASK起点では先行TASKがすべて`done`である。
- 高リスク変更ではFull Flowを選択している。

## 7. 失敗と戻り先

| 原因 | 戻り先 | 自動再試行 |
|---|---|---:|
| compile、lint、unit test、TASK境界 | Implement | 最大2回 |
| 一時的tool障害 | 同じ操作 | 冪等な1回 |
| Context stale、依存・設計不足 | Context | 0回 |
| 要求・受入条件の問題 | Intent | 0回 |
| 権限、security、費用、法令 | Escalate | 0回 |

`Escalate`は人間の判断を待つ停止点であり、Doneへの遷移ではない。解消後はIntent、Context、または中断した操作へ
戻り、そこからPre-check、Post-check、verify、Human Reviewを省略せず再実行する。解消しなければ取り止める。

最終Human Reviewの否決は自動再試行回数へ含めない。人間がIntent、Context、Implementのいずれかの戻り先、
または取り止めを選び、Doneへ直接進めない。

## 8. 取り止め

Done前は人間判断で取り止められる。`draft` REQ/TECHは`rejected`、`open` TASKは`cancelled`へ変更できる。
理由は任意の`Notes`、ADR、Issue、commitへ記録し、変更後の`bitz check <ID>`を通してGitへ記録する。

Coreは取り止めを推測せず、code/test差分を削除しない。既に`approved`のREQ/TECHは`rejected`へ戻さず、
必要なら`outdated`と後継判断で扱う。

## 9. モノレポ横断作業

共通要求が複数workspaceへ影響する場合、federation rootに共通REQまたはADRを置き、各memberのREQ／TECHが
修飾IDで具体化する。実装とtestは所有memberへ置き、作業TASKもmemberごとに分ける。

1. 共通要求の`purpose=interpret` Contextをreviewする。
2. memberごとに`purpose=implement` Context、Pre-check、実装、Post-check、verifyを行う。
3. 横断Contextの到達先と、各memberの所有境界をHuman Reviewで確認する。
4. 統合前にfederation rootで`check --all-workspaces --base <統合先先端>`と
   `verify --all-workspaces`を実行する。

独立した複数workspaceを1つのContext requestの複数起点にせず、memberごとにrequestを分ける。
全体操作はworkspace単独フローのHuman Reviewを代替しない。

## 10. 並行開発

Core 1.0は専用`Integrate`段階と自動改番支援を持たない。作業branchを統合先へmergeまたはrebaseした後、
次を実施する。

1. `bitz check --full --base <統合先先端>`を実行する。
2. 同じworkspace内に重複IDがあれば、人間が片方を当該workspaceの未使用IDへ改番し、Frontmatter、ファイル名、
   関係、`covers`、`addresses`を更新する。別workspaceの同名ローカルIDは改番しない。
3. 同じcheckを再実行する。
4. 通過後に通常のreviewとmergeを行う。

Coreは勝者、敗者、新IDを決めない。

## 11. 完了条件

- 対象規範文が特定されている。
- 書込み直前のContext Digestが一致している。
- Context、実装前後のcheck、verifyがすべて通過statusである。
- 未tested `MUST`が0件である。
- 必須testが実行され成功している。
- 省略・未証明事項が表示されている。
- 人間が最終diffを確認している。
- TASK起点では`done`への変更後に最終checkが通過している。
- 完了結果がGitへ記録されている。
- 連合横断作業では、全workspaceのcheckとverifyの集約結果が通過statusである。
