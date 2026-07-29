---
id: FLW-NFR-007
version: 1.2
status: draft
domain: tooling
priority: high
origin: 2026-07-29 ユーザー指示（draft要件をFLW-NFR-003から順番に解決）
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-007 永続file更新の原子性と完全性

- **説明**: 永続fileを同一directory内の検証済みtempから原子的に置換し、異常終了時も完全な旧版または完全な新版のいずれかへ収束させる。
- **受入基準 (EARS)**:
  - WHEN 永続file更新をplanする THEN bitz-flowはcanonical repo境界と`lstat`によるdevice、inode、owner、mode、link count、digestを記録すること SHALL
  - WHEN 対象がsymlink、複数hardlink、repo境界外parent、または所有者不一致である THEN bitz-flowは原本を変更せず`BLOCKED`を返すこと SHALL
  - WHEN 更新内容を準備する THEN bitz-flowは対象と同一directoryへ排他的かつowner-onlyのtempを作成し、write、flush、file fsync、parse、digest検証を実行すること SHALL
  - WHEN tempを原本へ置換する THEN bitz-flowは直前に原本identityとdigestを再照会し、plan時と一致する場合だけplatformのatomic replaceを実行すること SHALL
  - WHEN atomic replaceが完了する THEN bitz-flowはparent directoryのdurability同期と最終fileのparse、digest検証を実行し、その完了をdurability commit pointとすること SHALL
  - WHEN 更新が成功する THEN bitz-flowは原本のmode、改行形式、末尾改行を保持すること SHALL
  - WHEN durability commit point前に失敗またはcrashする THEN bitz-flowは公開pathをplan時digestの完全な旧版またはexpected digestの完全な新版のいずれかに保ち、部分内容を残さないこと SHALL
  - WHEN durability commit point後にcrashする THEN bitz-flowは公開pathをexpected digestの完全な新版に保つこと SHALL
  - WHEN crash後の永続fileをreconcileする THEN bitz-flowはexpected digestなら`DONE`、plan時digestなら`STALE`として再plan、どちらでもなければ`INDETERMINATE`として後続mutationを停止すること SHALL
  - WHEN file更新のresultを返す THEN bitz-flowはtemp pathまたは秘密本文を含めないこと SHALL
  - WHEN filesystemまたはplatformでatomicityとdurabilityを検証できない THEN bitz-flowは該当永続file writeを`UNSUPPORTED`にすること SHALL
- **検証手段**: Linux、macOS、Windowsのidentity競合、symlink、hardlink、各段階crash、replace、directory同期、mode・改行保持をunit testで検証し、原本破損0件とtemp path公開0件を確認する。
- **Revision History**:
  - 1.2 (2026-07-29) durability commit pointをdirectory同期・最終検証後へ修正
  - 1.1 (2026-07-29) atomic replaceをcommit pointとし、crash後の旧版/新版/reconcile契約を実現可能化
  - 1.0 (2026-07-29) FLW-NFR-004から永続file更新の原子性と完全性を分離してdraft起票
