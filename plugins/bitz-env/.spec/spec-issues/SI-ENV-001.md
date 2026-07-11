---
id: SI-ENV-001
raised_by: sdd-review REV-001（risk RSK-201/RSK-202, business BIZ-301）
target: plugins/bitz-env/.spec/design/ENV-DSN-001.md + ENV-CON-001.md（+ README / rules）
proposed_change_type: bump
status: proposed
---
- **矛盾/曖昧の内容**: ガードレールの防御思想に2つの暗黙前提がある。
  (1) 設計は「フック（即効層）＋permissions（恒久層）の二重の守り」を謳うが、
  プラグインを入れただけで env-init を未実行の環境には permissions 層が無く、
  fail-open 設計のフックが二重化の前提を欠いた単独防御になる。故障・タイムアウト時に
  破壊的操作が素通しする。
  (2) env_guard.py の正規表現ガード（`\bsudo\b` 等）は $(printf sudo)・base64 実行・
  環境変数展開などで回避可能であり、「誤操作の抑止」であって「悪意ある回避の防止
  （セキュリティ境界）」ではない。この位置づけが文書化されておらず過信を招く恐れ。
- **提案する修正**:
  (a) ENV-DSN-001 に fail-open 選択の ADR（選択肢・却下理由・permissions 層との関係）を明記。
  (b) 「本ガードは誤操作抑止でありセキュリティ境界ではない」を ENV-CON-001 の脚注か
      新 CON として要件化（plugin-agents の『tools 制限にセキュリティを依存させない』と同思想）。
  (c) env-init 未実行（permissions 層の不在）を env-doctor が WARN として検出する要件を追加。
- **影響推定**: ENV-DSN-001・ENV-CON-001 の記述追加、env-doctor 診断項目1件追加、
  README の注意事項補強。env_guard.py の挙動自体は変えない（文書・要件・診断の追加）。
