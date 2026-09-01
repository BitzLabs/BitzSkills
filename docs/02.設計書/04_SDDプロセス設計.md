# SDDプロセス設計

## 1. 基本方針

個人から数人の開発では、段階管理そのものを目的にしない。EARS-AIで変更意図を短く固定し、
実装後に実行可能な証拠を対応付けることを最小サイクルとする。

フローは専用branchまたはworktreeで開始し、開始時のHEADを復帰基点とする。変更を伴うIntent、Requirement Review、
Design Review、Implement、Integrate、DoneまたはStoppedは、必要なcheckと人間確認を通過した時点で、他フェーズの変更を
混ぜずにGit commitへ記録する。Context、Pre-check、Post-check、Verify、Human Reviewのように正本の変更を
伴わない段階は、その時点のHEADをcheckpointとし、空commitを作らない。commitはsquashせず、取り消す場合は
共有済み履歴を書き換えず新しい順に`git revert`する。Coreはbranch、commit、revert、pushを実行しない。

`Integrate`では、統合先先端の合流と改番を別のcommitへ記録し、1つのcommitへまとめない。合流を記録する前に
改番すると旧IDが基準版にだけ残り、SPEC削除として拒否される。合流と改番を同一commitへまとめると、
基準版の敗者と現在版の勝者を同一文書として誤対応する。いずれもCoreは入力から判別できないため、
commit単位の規約として分離する。

## 2. Small Flow（既定）

```text
Intent -> Context -> Pre-check -> Implement -> Post-check -> Verify -> Human Review -> Integrate -> Done
                                      ^            |            |              |            |
                                      +------------+------------+--------------+------------+
```

1. **Intent**: 変更対象のREQ、TECH、1件以上のEARS-AI規範文、または`open` TASKを特定する。
2. **Context**: `bitz context --purpose implement`で強い依存、全`MUST`、変更境界を取得する。
3. **Pre-check**: 実装前に`bitz check`で構文、関係、状態遷移、既存作業ツリーの不適合を確認する。
4. **Implement**: Digestを再照合してからコードとテストを変更する。
5. **Post-check**: 実装後に`bitz check`で変更集合を検査する。TASK起点では`bitz check <TASK-ID>`を実行し、
   `changes`境界を強制する。
6. **Verify**: `purpose=verify`を再解決し、句単位の網羅を確認して対象テストを実行する。
7. **Human Review**: 対応した規範文IDと最終diffを人間が確認する。
8. **Integrate**: 統合先branchの先端を作業branchへ合流させてGitへ記録し、合流後の木に対し
   `bitz check --full --base <統合先先端>`を実行する。`idCollisions`があればUC-13の改番を適用し、
   再実行する。合流を記録する前に改番しない。Coreはbranch、merge、rebase、commit、pushを実行しない。
   `Integrate`は再検査の通過をもって完了とし、統合先branchへのmergeを含まない。mergeは`Done`を記録した
   後に[運用設計](06_運用設計.md)の手順で行う。
9. **Done**: TASK起点では、Human Review後に起点TASKを`done`へ変更してRevision Historyを更新し、
   変更後の入力へ`bitz check <TASK-ID>`を実行してから、完了結果をGitへ記録する。

Human Reviewで否決された場合は、理由に応じて次の段階へ戻す。

| 否決理由 | 戻り先 | 再実行する段階 |
|---|---|---|
| 要求、目的、受入条件 | Intent | ContextからHuman Reviewまで |
| 依存、設計、Context不足・陳腐化 | Context | Pre-checkからHuman Reviewまで |
| コード、テスト、最終diff | Implement | Post-checkからHuman Reviewまで |

`Integrate`の`failed`は再作業ではなく改番の適用であり、否決分類へ含めない。

戻った地点より後のcheck、Verify、Human Reviewを省略してDoneへ進まない。REQ、TECH、TASK、設定を変更した場合は
Contextを再取得し、書込み前にDigestを再照合する。Human Review否決は人間が指示する再作業であり、§6の
自動リトライ回数へ含めない。再作業しない場合は§2.1の`Stopped`を選ぶ。

`Pre-check`と`Post-check`は同じ`bitz check`であり、実行位置と対象選択だけが異なる。実装後に静的検査を
経ずに`Done`へ到達する経路は作らない。フロー配置と必須呼出しの根拠は
[ADR-028](10_決定記録/ADR-028_開発フローの実装後検査とTASK境界の接続.md)を正とする。

`Integrate`が`Pre-check`・`Post-check`と異なるのは、基準版に統合先branchの先端を用いる点だけである。
ID衝突は自branchの現在集合だけでは観測できず、統合先と合流した木の上でしか勝敗が決まらないため、
実装後検査とは別の段階として置く。`Integrate`でCoreが実行するのは`bitz check`だけとする。

合流の記録を改番より先に行うのは、基準版へ勝者と敗者の双方を含めるためである。合流前に改番すると
旧IDが基準版にだけ残り、SPEC削除として拒否される。`Integrate`の`check`は`--base <統合先先端>`を明示する。
未指定の結果を勝敗の根拠にしない（[UC-13](09_ユースケース設計.md)）。

Pre-check、Post-check、TASK起点のDone内で行う最終checkは、statusが`passed`または
`passed_with_warnings`の場合に通過する。`failed`、`blocked`、`error`、引数不正では次段階へ進まない。
warningは表示したまま継続し、Core 1.0は`--strict`で昇格しない
（[ADR-035](10_決定記録/ADR-035_check空対象とフロー通過statusの確定.md)）。

TASK起点の`Done`内で行うcheckは、`open -> done`、Revision History、文書構造、関係、`changes`境界を
変更後の入力で検査する。TASK自身のファイルは境界比較から除くが、状態遷移と文書検査からは除外しない。
checkがフローの通過条件を満たすまでGitへ記録せず、後続TASKのフローは完了結果を記録した後に開始する。
CoreはTASKのstatusを自動変更せず、Git commitも実行しない
（[ADR-034](10_決定記録/ADR-034_TASK完了終端とdone起点操作の確定.md)）。

Intentの機械起点はREQ、TECH、規範文、`open` TASKのいずれかに限る。`bitz context`は生の意図文字列を
起点にせず、SPEC IDまたは規範文IDを要求する。TASK起点では`addresses`と`requires`から適用要求を解決する
（[Context Resolution仕様](../03.詳細設計/02_SPECファイル規定/10_Context%20Resolution仕様.md) §5）。
生の意図しかない場合は、実装前にREQ、TECH、TASKのいずれかへ記録する。

SPECを作らずに行う変更は、Small Flowの外側にあるCore保証外の作業とする。`bitz check`の構文・関係検査は
受けられるが、句単位coverage、TASK変更境界、Context Digestの再照合は保証されない。この区別のために
専用のフローや公開操作を追加しない。

通常のバグ修正、局所的な機能追加、リファクタリングはSmall Flowを使う。専用Gate承認や永続runを要求しない。

### 2.1 取り止め終端

Small FlowとFull Flowは、`Done`へ到達する前のどの段階でも、人間の明示判断により`Stopped`へ終了できる。
`Stopped`は再作業のための一時停止やCoreの操作statusではなく、そのフローを完了させない終端である。
レビュー否決は再作業へ戻すことも、理由を記録して`Stopped`へ進むこともできる。Coreは停滞や否決から
取り止めを推測せず、文書の状態、ファイル、Gitを自動変更しない。

取り止める提案または設計が`draft`のREQ／TECHであれば`rejected`へ変更し、本文の
`Rejection Rationale`へ不採用理由、根拠またはトレードオフ、再検討条件を記録する。既に`approved`として
適用したREQ／TECHは`rejected`へ変更せず、必要に応じて`outdated`として別の廃止判断へ接続する。
起点が`open` TASKなら`cancelled`へ変更し、`Cancellation Rationale`へ取り止め理由、得た知見、再計画条件を
記録する。該当する文書のRevision Historyを更新し、変更後の`bitz check <ID>`が`passed`または
`passed_with_warnings`であることを確認してから、取り止め結果をGitへ記録する。

`Integrate`の段階でも取り止められる。合流commitと改番commitは自branchの履歴に残り、統合先へは
mergeしないため、統合先の内容へ影響しない。取り止め時にこれらのcommitをrevertすることは要求しない。
起点文書の`Rejection Rationale`または`Cancellation Rationale`へ、改番済みIDと取り止め理由を記録する。

取り止める文書IDは人間が明示し、CoreとSkillは関連文書から対象を推測しない。Implement開始後に取り止める場合、
Skillは残っているコード・テスト差分を提示し、人間が破棄、作業ツリーへ保持、別TASKへの引継ぎ、またはSpikeへの
隔離を選ぶ。CoreとSkillは途中成果物を自動削除しない。Stoppedのcommitは原則として状態、理由、Revision History
だけを含め、保持する途中成果物は新しいTASKまたはSpikeの別commitへ分離する。選択理由と引継ぎ先は既存の
`Rejection Rationale`または`Cancellation Rationale`へ記録し、新しいFrontmatter項目やCore statusを追加しない。

`Stopped`ではDoneの完了条件、検証成功、TASKの`done`化を要求しない。`cancelled` TASKを必要とする後続TASKは
依存未充足のままであり、依存の除去または代替TASKへの更新を人間が判断する。REQ／TECH／TASKがまだ存在しない
段階での取り止めはCore保証外の作業記録とする
（[ADR-036](10_決定記録/ADR-036_フロー取り止めと不採用履歴の保持.md)）。

## 3. Full Flow（条件付き）

次のいずれかに該当する場合だけ、要求と設計の明示レビューを追加する。

- 公開API、永続データ、互換性を変更する
- セキュリティ、費用、法令、本番SLOへ影響する
- 複数モジュールまたは複数人の作業境界を越える
- モノレポの複数workspaceへ変更または検証が波及する
- 承認済みREQの意味を変更する

```text
Intent -> Context -> Requirement Review -> Design Review -> Pre-check
   ^          ^              |                  |
   |          +--------------+                  |
   +--------------------------------------------+

Pre-check -> Implement -> Post-check -> Verify -> Human Review -> Integrate -> Done
                ^             |           |             |            |
                +-------------+-----------+-------------+------------+
```

- Requirement Review否決はIntentまたはREQ改訂へ戻す。
- Design Review否決はContext再取得または設計改訂へ戻す。
- 要求または設定を変更した場合はContext Digestを再照合する。
- `Post-check`とVerifyの失敗は§6の分類済みリトライ規則へ従う。
- Human Review否決はSmall Flowと同じ理由分類、戻り先、再実行範囲を使う。
- `Integrate`の配置と内容はSmall Flowと同一とし、Full Flow専用の統合手順を作らない。

品質検査コマンドはSmall Flowと同じものを使い、`Pre-check`と`Post-check`の配置もSmall Flowと同一とする。
TASK起点の`Done`もSmall Flowと同じ終端手順を使い、Full Flow専用の別エンジンを作らない。

レビューの承認と否決は人間とAI CLIの進行契約であり、Coreの機械契約ではない。Coreはレビュー状態も否決も
保持せず、Gate状態機械を持たない（[ADR-009](10_決定記録/ADR-009_小規模チーム向け軽量コアとEARS-AI中核化.md)）。
戻り先の合流点でCoreが行うのは、再取得したContextの完全解決とDigest照合だけである。

## 4. Spike

技術的不確実性が高い場合は、仕様を確定させる前に隔離領域で実験してよい。

- Spike成果物をそのまま本番へマージしない。
- 学びをREQ、TECH、ADRのいずれかへ短く反映する。
- 採用する実装はSmall FlowまたはFull Flowで作り直す。

## 5. プリフライト

実装前に必要なのは次だけとする。

- 対象REQ、TECH、規範文、または`open` TASKが特定されている
- Context Bundleが完全に解決され、`blocked`がない
- 対象となる全`MUST`規範文が列挙されている
- 変更予定パスが明示されている
- テストコマンドが解決できる
- 既存の未コミット変更と衝突しない
- TASK起点では、`requires`が指す先行TASKがすべて`done`である
- 高リスク変更ならFull Flowが選ばれている

前提不足は`blocked`とし、コード編集へ進まない。

## 6. リトライ

| 種別 | 既定上限 | 自動修正範囲 |
|---|---:|---|
| コンパイル・Lint・単体テスト | 2 | 変更境界内のコードとテスト |
| 一時的なツール障害 | 1 | 冪等な再実行のみ |
| 仕様矛盾、権限不足 | 0 | 人間へ確認 |

各試行で同じ変更を反復しない。上限到達時は進行を停止し、最後の失敗とdiffを提示する。この停止は
自動的な`Stopped`確定ではなく、人間が再作業または取り止めを選ぶ判断点である。

Human Review否決による再作業は自動修正ではないため、この表の回数へ含めない。Coreは否決回数を数えず、
同じ理由が繰り返された場合も、人間が再作業または`Stopped`を選ぶ。

戻り先は失敗種別で決める。コンパイル、Lint、単体テスト、TASK境界外変更は`Implement`へ戻す。仕様矛盾、
要求の意味変更、権限不足は自動修復せず人間確認へ戻す。一時的なツール障害は、同じ副作用を増やさない
冪等な再実行だけを許可する。

## 7. 自動修復境界

自動修復してよいもの:

- 構文、型、Lintエラー
- 承認済み仕様に対する局所的な実装不足
- 明示された受入条件に対するテスト不足

人間判断が必要なもの:

- REQまたは受入条件の意味変更
- 公開契約、データ互換性、依存、アーキテクチャの変更
- セキュリティ、費用、法令、本番運用への影響
- コードを正として仕様を変更する提案

## 8. 完了条件

- 対象EARS-AI規範文が特定されている。
- 実装直前にContext Digestが一致している。
- 実装前の`bitz check`が`passed`または`passed_with_warnings`である。
- 実装後の`bitz check`が`passed`または`passed_with_warnings`である。TASK起点では
  `bitz check <TASK-ID>`で`changes`境界を検査している。
- 対象`MUST`の未testedが0件である。
- 必須テストが実際に実行され成功している。
- 省略した検証があれば表示されている。
- 人間が最終diffを確認できる。
- TASK起点では、起点TASKが`done`へ遷移し、変更後の入力に対する`bitz check <TASK-ID>`が`passed`または
  `passed_with_warnings`である。
- 完了結果がGitへ記録されている。
