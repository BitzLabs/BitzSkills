# 振り返り記録 — M2 Local Safety Profile の設計評価と実装後評価の乖離

- **日付**: 2026-08-23
- **対象**: `FLW-DSN-017`、`FLW-FR-006`、`FLW-NFR-014`、`FLW-TSK-106`〜`114`
- **起点**: 実装後レビュー `FLW-REV-027`（FAIL 2.12）
- **追跡先**: `SI-FLW-084`〜`SI-FLW-091`
- **記録目的**: 今回の失敗を是正項目だけで終わらせず、次の設計で再利用できる判断規則にする
- **記録者**: codex（ユーザーの明示指示に基づく記録）

## 1. 結論

オーバースペックな機能を削り、契約と責任境界を単純化した設計方針そのものは維持する。
一方、設計レビューで高評価を得たことを、production入口から永続化・復旧・監査までの
実行可能性が証明されたことと同一視してはならなかった。

今回の主要な失敗は、**部品が設計どおり存在することを、利用者が通る垂直フローの完成と
判定したこと**である。局所的な契約、adapter、transaction、recovery、testは存在したが、
production CLIから同じ契約へ到達する接続、異常終了時の状態遷移、有限時間での終了、
実対象OSでの成立を一体として証明していなかった。

したがって次回以降は、設計・実装・テストの完了判定を「成果物がある」から
「production経路を、正常系と全異常境界の双方で実証した」へ変更する。

## 2. 事実

- `FLW-REV-027` は集計 **2.12 / FAIL**、risk **1.33** と判定した。
- findingは10件で、P0が2件、P1が5件、P2が3件だった。
- P0は、実環境platform evidenceがproduction CLIへ接続されていないことと、create/resume CLIが
  廃止済み承認契約・旧contextを参照していたことである。
- P1は、有限timeout欠落、durable確定間のcrash空隙、`QUARANTINED`の完了誤分類、
  marker適格性確認前のreconcile closure、verified・task done・予算の過大主張である。
- 過去9レビューの未解決P0/P1が機械台帳上88件あり、後続判定との照合も未完了だった。
- 公開とPromotion Gateは停止し、`SI-FLW-084`〜`SI-FLW-091`で是正を追跡している。

## 3. 以前からの指摘と、新たに判明した指摘

### 3.1 同系統の再発

次は、過去レビューで既に現れていた失敗類型の再発である。

| 失敗類型 | 過去の主な指摘 | 今回の現れ方 |
|---|---|---|
| 公開入口まで結線されない | `FLW-REV-015:SYN-001`、`FLW-REV-016:SYN-011` | platform evidenceがproduction CLIへ渡らない |
| 設計・schema・実装の語彙／契約がずれる | `FLW-REV-017:SYN-005`、`SYN-011` | 廃止済みsigned-capabilityと旧contextがproduction CLIに残る |
| 実platformで成立を証明しない | `FLW-REV-023:SYN-006`、`FLW-REV-024:SYN-009` | Windowsを含むproduction経路の実観測が無い |
| recovery・quarantineの状態意味が崩れる | `FLW-REV-018:SYN-006`、`FLW-REV-019:SYN-010`、`FLW-REV-024:SYN-004` | `QUARANTINED`を完了扱いし、closure順序も逆転できる |
| 証跡とstatusが実態を過大主張する | `FLW-REV-016:SYN-008`、`FLW-REV-018:SYN-011`〜`012`、`FLW-REV-019:SYN-014` | production未接続のままverified・task doneとした |

共通する原因は、**横方向の成果物整合を確認しても、利用者入口から最終状態までの縦方向の
到達可能性を確認していない**ことである。

### 3.2 今回初めて具体化した故障機構

次の具体的な故障機構は、過去の類型と同根だが今回の実装で初めて確定した。

- production呼出しから`platform_evidence`を渡す引数・生成経路が存在しない。
- 廃止済み`worktree_dir_guard_key`等の旧contextがproduction CLIに残存する。
- intentと緊急receiptという2回のdurable writeの間に、回収不能になり得るcrash点がある。
- `QUARANTINED`をconfirmed-completeと分類できる条件式がある。
- active markerの適格性確認より前にreconcile closureを不可逆追記できる。
- 全childを有限時間で収束させ、30秒以内にterminal resultを返す監督処理が無い。
- Windows実行をPOSIX前提のcomponentで代替し、同一経路の証明として扱っていた。

## 4. 足りなかったもの

### 4.1 設計

- **垂直接続図**: production入口、parser、approval、platform probe、transaction、Git child、
  receipt、recovery、audit、rendererまでを1本の経路として示す設計。
- **状態遷移の意味表**: `DONE`、`QUARANTINED`、`INDETERMINATE`、`BLOCKED`について、
  前提、永続証跡、許される後続処理、禁止される完了判定を定義すること。
- **crash-point表**: 各durable writeの直前・直後で停止した場合の観測状態、authority、
  再開処理、重複実行時の結果を列挙すること。
- **liveness budget**: child単位とoperation全体のdeadline、kill、回収、terminal resultの
  最大応答時間を設計値として定義すること。
- **platform reality表**: OSごとの実装component、identity、probe方法、未対応時の即時拒否を
  明記し、代替componentを同一証明として扱わないこと。
- **legacy exclusion表**: 廃止した入力・field・context・approval方式がproduction入口から
  到達不能であることを設計成果物へ含めること。

### 4.2 実装

- production dispatcherを唯一の統合入口として扱い、test fixtureや内部helperだけで成立する
  経路を完了根拠にしない。
- 各境界で同じ型・語彙・authorityを引き回し、adapterで暗黙の既定値や旧契約へ戻さない。
- durable writeは「何を書いたか」だけでなく、write間crashから確実に回復できる順序と
  冪等性を実装する。
- terminal stateを文字列一致でまとめず、完了・隔離・判定不能・失敗を別の後続処理へ分岐する。
- child processには必ずdeadline、停止処理、出力回収、親側の最終deadlineを持たせる。
- productionコードから旧field・旧parser・旧approvalを削除し、入力された場合は解析せず
  即時拒否する。

### 4.3 テスト

- production既定dispatcherを起点にしたblack-box E2Eを必須にする。
- 全durable boundaryの直前・直後へfault injectionし、再開後のauthorityと最終状態を検証する。
- hangするchild、終了しないchild、部分出力、kill失敗を含むliveness試験を行う。
- 対象3platformで同じproduction入口を実走し、各OS固有componentとidentityを証跡へ残す。
- 廃止入力と旧contextのnegative testをproduction入口に対して実行する。
- taskを`done`、要件を`verified`にする前に、要件→production test→machine evidenceの
  トレースが連続していることを検査する。

## 5. 次の設計で必須にする7観点

次の設計レビューでは、機能ごとに以下をすべて回答する。1つでも「未証明」ならDesign Gateの
PASS根拠にせず、未実装境界または検証計画として明示する。

1. **接続完全性** — production入口から最終の永続証跡・利用者出力まで到達するか。
2. **失敗原子性** — 全durable write境界で停止してもauthorityが一意に回復するか。
3. **有限収束性** — 外部processがhangしても定めた時間内にterminal resultへ収束するか。
4. **platform実在性** — 対象OS固有の実装を、そのOS上のproduction経路で証明したか。
5. **証跡妥当性** — machine evidenceが主張しているproduction経路そのものを実行したか。
6. **legacy排除** — 廃止契約がproduction入口・内部fallback・fixtureに残っていないか。
7. **状態意味保存** — 隔離・判定不能・失敗を成功や完了へ畳み込んでいないか。

## 6. 次回の完了判定

### Design Gate

- 垂直接続図、状態遷移表、crash-point表、liveness budget、platform reality表、
  legacy exclusion表が揃っている。
- 各表の行が、実装taskとproduction test IDへ追跡できる。
- fixtureや予定上の接続を「成立済み」と表記していない。

### 実装完了

- production入口に未接続の実装taskを`done`にしない。
- 異常境界と旧契約拒否を含むproduction E2EがPASSしている。
- 状態遷移・receipt・recoveryの機械証跡が同じoperation IDで追跡できる。

### Verification / Promotion Gate

- `SI-FLW-084`〜`SI-FLW-090`が実証を伴って解消されている。
- `SI-FLW-091`で過去P0/P1台帳を再照合し、未解決項目を欠落させていない。
- 同じ5観点の再レビューでPASSし、risk floorを満たす。
- その後に限り、本記録の汎用教訓を人間確認のうえ
  `docs/05_リリース・運用/教訓.md`へ昇格する。

## 7. 維持する判断

今回の結果は「単純化が誤りだった」ことを意味しない。次は維持する。

- 運用価値のないoperationやenumを増やさず、実態へ主張を合わせる。
- approvalをplan-digestへ一本化し、廃止契約を互換維持しない。
- `TargetTransaction`を変更authorityの単位とする。
- 公開前に停止できるgated運用を維持する。

改善すべきなのは機能量ではなく、**接続・異常境界・実platform・証跡の検証密度**である。
