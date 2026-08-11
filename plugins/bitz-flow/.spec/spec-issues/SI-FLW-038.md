---
id: SI-FLW-038
raised_by: M0全14ラウンド振り返り（platform固有失敗による再実測コスト）
target: FLW-DSN-014・score.py・run manifest・M1以降の検証プロトコル
proposed_change_type: modify
status: open
---
- **目的**: M0ではplatform固有のレート制限・quota・sandbox・ホーム書込み制限により、正常だった
  platformまで再実測する判断が繰り返された。第14ラウンドではplatform別123件を独立実行して最後に
  369件を合成できたが、「どの入力が不変なら既存platform証跡を再利用できるか」が契約化されていない。
  都合のよい結果選択を防ぎつつ、影響のないplatformの再実測を省く。
- **提案する修正**:
  1. platform runを独立した不変証跡とし、合成manifestが参照する構造へする。
  2. 再利用keyを、scoring rule完全hash、runner共通部hash、platform adapter hash、fixture / prompt /
     skill / schema hash、trial割付・母数、model / CLI metadata、qualification result、raw log digestで構成する。
  3. 共通採点規則・fixture・prompt・schema・runner共通部が変われば全platformをinvalidateする。
     platform固有adapterまたは環境だけが変われば当該platformだけをinvalidateする。
  4. 合成時は各platformのkey一致、所要母数、raw log参照、時刻・環境差の許容範囲を検査し、
     不一致を`unknown`または`blocked`としてGateへ採用しない。
  5. 同じkeyに複数candidateがある場合の選択規則を事前固定し、結果を見て有利なrunを選べないようにする。
- **対象ファイル**: `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`、`evals/flow-core/m0-eval/score.py`、
  run manifest schema / runner、M1以降の検証プロトコル。bitz-sdd V4テーマ13-Aのverification historyへ
  platform evidence / composite evidence関係として接続する。
- **確認観点**:
  - platform adapterだけを変更すると当該platformだけ再実測要求になり、他platformは再利用されること。
  - scoring rule / fixture / schema変更では全platformがinvalidateされること。
  - raw log欠落、母数不足、qualification不一致、複数candidate曖昧時はGateがblockedになること。
  - 合成結果から全入力digestと各platform原証跡へ双方向に追跡できること。
  - 過去のFAILを除外してPASSだけ選ぶ操作を機械的に拒否すること。
- **影響推定・ロールバック**: 検証証跡schema・採点対象選択・Gate判定に触れるため軽量レーン不適、
  Design Gateが必要。既存の単一JSONL採点は移行期間のread-only互換入口として残し、新しい合成契約を
  無効化すれば現行方式へ戻せる。既存run manifestは書き換えずlegacy evidenceとして保持する。
- **依存**: `FLW-NFR-009`の採点規則入力hash・result履歴、`FLW-NFR-010`のraw log永続性、
  `SI-FLW-037`のqualification result、bitz-sdd V4 ROADMAPテーマ13-A。**推薦: accept**。
  テーマ13-Aを重複起票せず、platform証跡の合成・invalidate境界だけを具体化する補強とする。
