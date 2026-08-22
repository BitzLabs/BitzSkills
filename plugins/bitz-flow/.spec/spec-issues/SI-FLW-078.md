---
id: SI-FLW-078
raised_by: FLW-REV-021
target: FLW-NFR-013 の承認宣言不在状態と永続束縛契約
proposed_change_type: modify
status: accepted
github_issue: https://github.com/BitzLabs/BitzSkills/issues/257
---
- **目的**: `FLW-NFR-013` の「plan後の新規作成・削除・内容変更・inode置換は停止する」契約を、ローカルfilesystemで実証できる境界に明確化する。

- **発見した事実**:
  1. `FLW-REV-021` は、plan時とmutation直前の二点でともに`absent`を観測した場合、間に作成・削除された宣言を同一digestからは識別できないと確認した。
  2. 宣言の再照合完了後からGit mutation開始までの書換えを、現在のtarget guard（プロセス内のみ）は直列化も検出もできない。
  3. 非観測の中間変化まで検出するには、repo外の信頼根・監査可能な世代台帳・プロセス間coordinatorが必要となり、現行M2のローカルruntime契約を越える。

- **提案する修正**:
  - **案A（強化）**: repo外の信頼根を持つ永続coordinatorを導入し、宣言世代・lease・fencing tokenを全CLI processで照合する。検出不能・coordinator未到達時は`BLOCKED`にする。
  - **案B（推薦）**: `FLW-NFR-013` の停止対象を「plan作成時、apply承認後、各mutation直前の必須再照合点で観測した宣言状態またはdigestの変化」と明示する。観測不能な一時作成・削除は承認強度を変更しない限り検出対象にせず、再照合と副作用の境界は `FLW-NFR-007` のatomicity契約で扱う。
  - どちらを選ぶ場合も、capability envelopeのversion、digest必須化、旧形式拒否、parent componentの非追随走査、観測結果のreceipt記録を後続要件・設計へ追加する。

- **対象ファイル**: `plugins/bitz-flow/.spec/requirements/FLW-NFR-013.md`、`plugins/bitz-flow/.spec/design/FLW-DSN-017.md`、`worktree_runtime.py`、`worktree_capability.py`、runtime/capability test。

- **確認観点**: bound/absentの通常系、symlink・未追跡・権限不正の拒否、再照合点での内容変更・削除・置換の副作用0件、旧capability/digest欠落の拒否、複数process競合または非対応環境での安全な停止を確認する。

- **影響推定・ロールバック**: 承認・plan・capabilityの内部契約に触れる通常レーンの変更であり、Design Gateを要する。案Aはrepo外の運用依存を追加する。案Bは検証可能な観測境界へ契約を限定する。未公開M2だけが対象のため、失敗時は対応要件・設計・実装をrevertし、現行の`BLOCKED`既定は維持する。

- **依存**: `FLW-NFR-013`、`FLW-FR-006`、`FLW-NFR-007`、`FLW-DSN-016` §4、`FLW-DSN-017`、`FLW-REV-021:SYN-001/SYN-004/SYN-005/SYN-006`。

- **予備判定（推薦）**: **案Bでacceptを推薦**。案Aはより強い検出を目指せるが、信頼根の運用・可用性・プラットフォーム依存を新たに持ち込み、現行のローカルM2スコープを拡張する。案Bは実際に観測・検証できる強度低下をfail-closedで止める。

- **裁定**: 2026-08-22 userが案B（観測可能checkpoint契約）を採用。
