---
id: FLW-NFR-007
version: 1.0
status: draft
domain: tooling
priority: high
origin: FLW-DSN-013
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-007 永続file更新の原子性と完全性

- **説明**: 永続fileの更新を同一directory内の検証済みtempから原子的に置換し、競合または異常終了時も原本を保全する。
- **受入基準 (EARS)**:
  - WHEN 永続file更新をplanする THEN bitz-flowはcanonical repo境界と`lstat`によるdevice、inode、owner、mode、link count、digestを記録すること SHALL
  - WHEN 対象がsymlink、複数hardlink、repo境界外parent、または所有者不一致である THEN bitz-flowは原本を変更せず`BLOCKED`を返すこと SHALL
  - WHEN 更新内容を準備する THEN bitz-flowは対象と同一directoryへ排他的かつowner-onlyのtempを作成し、write、flush、file fsync、parse、digest検証を実行すること SHALL
  - WHEN tempを原本へ置換する THEN bitz-flowは直前に原本identityとdigestを再照会し、plan時と一致する場合だけplatformのatomic replaceを実行すること SHALL
  - WHEN atomic replaceが完了する THEN bitz-flowはparent directoryのdurability同期と最終fileのparse、digest検証を実行すること SHALL
  - WHEN 更新が成功する THEN bitz-flowは原本のmode、改行形式、末尾改行を保持すること SHALL
  - WHEN 任意の更新段階で失敗またはcrashする THEN bitz-flowは原本の有効な内容を保全し、temp pathまたは秘密本文を公開resultへ含めないこと SHALL
  - WHEN filesystemまたはplatformでatomicityとdurabilityを検証できない THEN bitz-flowは該当永続file writeを`UNSUPPORTED`にすること SHALL
- **検証手段**: Linux、macOS、Windowsのidentity競合、symlink、hardlink、各段階crash、replace、directory同期、mode・改行保持をunit testで検証し、原本破損0件とtemp path公開0件を確認する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-NFR-004から永続file更新の原子性と完全性を分離してdraft起票
