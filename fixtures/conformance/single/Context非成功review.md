# Context非成功fixtureレビュー

2026-09-14。SINGLE-050、051、052-01〜02、053の5件について、Core実装前の固定入力・完全期待JSON・
read-only副作用期待値を作成する。これらはCoreが返した観測結果ではない。

## 入力と単一原因

| ID | 起点 / purpose | 入力 | 期待status / exit / Diagnostic |
|---|---|---|---|
| SINGLE-050 | TECH-999 / interpret | TECH-001だけが存在し、TECH-999は存在しない | failed / 1 / CTX-ROOT-MISSING-001 |
| SINGLE-051 | TASK-001 / implement | open TASK-001がopen TASK-002をrequiresする | blocked / 2 / CTX-TASK-DEPENDENCY-001 |
| SINGLE-052-01 | TECH-001 / implement | approved TECH-002がapproved TECH-001をsupersedesする | blocked / 2 / CTX-STATE-SUPERSEDED-001 |
| SINGLE-052-02 | TECH-003 / implement | 上記に加えapproved TECH-003が旧TECH-001をrequiresする | blocked / 2 / CTX-STATE-SUPERSEDED-001 |
| SINGLE-053 | TECH-001 / implement | approved TECH-002とTECH-003がともにTECH-001をsupersedesする | failed / 1 / CTX-STATE-SUPERSEDED-002 |

全件とも最小設定の単一workspaceで、Git initのみのunborn repositoryを使う。
contextは--baseを受け付けず、commitを必要としないためbaseCommitを作らない。明示purposeと--format jsonを使用する。
TECHは規範文・implements・tests・commandを持たず、TASKはaddressesとchangesを持たない。
これによりcoverage不足、path不在、command不在、REQ保護を原因へ混ぜない。

050ではID字句自体は妥当であり、引数エラーexit 4にせず操作結果を返す。存在するTECH-001へ起点を置換しない。
051のrequiresは存在するTASKへの型が正しい関係で、循環もない。単に先行TASKが未doneであることだけが遮断原因である。
052系は旧TECHのstatusをapprovedのまま保持する。後継の存在を逆索引で検出し、statusのdraft/outdatedとは区別する。
interpretで後継を提示する経路と混ぜないようimplementを明示する。052-02では起点TECH-003自体は置換されていない。
053は1つの旧文書に有効な後継が2件あるという単一原因であり、単一後継のblocked診断を重ねず、
後継重複のfailed診断を1件に固定する。最小IDの後継を選択しない。

## 完全期待値の選択

- rootsはinvocationに指定した1件をそのまま保持する。後継や既知起点への差替えを禁止する。
- workspaceはid=root、path=.。Git自体は利用可能だがunbornなのでrevision=nullとし、Git不在warningを加えない。
- ID・状態・強い関係の検査で完全解決に到達しないため、contextDigest=null、resolution.complete=false、
  documents=[]、constraintLedger.statements=[]、coverageのmust/should/may各5配列とadjacentを空にする。
- documentCount=0は完成した解決集合をまだ出力しないことを表す。unresolvedStrongRelations=0とする。
  050は明示起点の不在でありstrong edge不在ではなく、他4件は参照先がすべて存在する状態・後継検査の失敗である。
- projectionはdetail=standard、expanded=[]。durationMs=0で、既存normalizer以外の比較除外を追加しない。
- severityは全件error。050はinvocation sourceのargument=TECH-999、051はTASK-001のrelations.requiresをsourceとする。
  052・053は置換対象のTECH-001をfile sourceにする。逆索引で判定するため旧文書に存在しないsupersedes keyは付けない。
  line/column/evidence/suggestedActionは加えず、summaryは各expected/context.jsonの今回選択した文字列に固定する。

この空の非成功Bundle、Diagnostic位置・文言・件数は、既存の規範に沿って今回固定した受入期待値であり、
全非成功Contextに共通する本番処理をこのvalidatorへ実装したものではない。

根拠は[context仕様 §2〜§4・§10](../../../docs/03.詳細設計/03_操作仕様/01_context.md)、
[関係・トレースモデル §3〜§6](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md)、
[状態・適用可能性](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[共通結果契約](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[適合matrix §6.5](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証

context_failure_fixtures.pyは固定入力byte列、レビュー済みFrontmatter値のSchema、manifest、完全期待JSON、
read-only副作用期待値を照合する。起点・閉包の展開、状態適用可否、Digest計算などの製品処理は実装しない。
各2回の隔離setupで、Git repository・symbolic HEADの存在、HEAD未解決、ref/index空集合、worktree内容を確認する。
repository、Git status/index、HOME/cache/TMPDIRのsnapshotを固定値へ照合し、before=afterを要求する。
Core実行後の観測値ではなく、副作用ゼロの期待値である。

回帰試験では起点の差替え、非成功の成功化、誤ったDiagnostic、Digestの捏造、resolutionの成功化、
文書件数・coverageの部分出力、後継重複診断の降格・二重化、purposeの変更、Git snapshotの消去を拒否する。
入力については先行TASKのdone化、supersedes/requiresの弱い関係化、後継のdraft化、起点IDの追加を検出する。
実repositoryへのstageや初回commitも、unborn照合で拒否する。
実際のCoreの結果と副作用はGate Bで受け入れる。

準備済み65/311件、残246件。成功Contextと独立したgolden Digest等、fresh checkoutからの全Gate A検証は未完了であり、
Gate AはBlockedを維持する。
