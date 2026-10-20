"""固定CLI内蔵の公開モデル情報だけを抽出する。起動・認証・私的入力の読取りなし。

保持評価の新条件へ接続するための部品。既存のcapture/config/台帳にはまだ接続しない。
"""
import os
import stat

import production_canary_runtime as runtime
import production_ledger as io
import production_trace as trace

MODEL = 'gpt-6.1-sol'
OFFSET = 238936729
LENGTH = 472511
BINARY_BYTES = 289166920
SEGMENT_SHA256 = '719c75b77ed02c783263f8fe62532ecd0abc1d1ccf2c34b12e5d221d509995a1'
SELECTED_SHA256 = '529c2b0d2e898ac64e6bfedf750818a94cc5cba7c0e3fac950c2c81211675db9'
DEFAULT_TEMPLATE_SHA256 = 'c1ed5ce0a3a49ba35b9eeba9774e0bd8ebd10eddec13b2dac564e7170513356c'
require = trace.require


def select(segment):
    """固定区間と抽出結果の両方のhashが一致した場合だけ返す。"""
    require(isinstance(segment, bytes) and len(segment) == LENGTH
        and io.sha(segment) == SEGMENT_SHA256, 'heldout fixed public catalog segment drift')
    value = trace.strict_json(segment)
    require(isinstance(value, dict) and set(value) == {'models'}
        and isinstance(value['models'], list) and len(value['models']) == 11,
        'heldout fixed public catalog inventory')
    selected = [m for m in value['models'] if isinstance(m, dict) and m.get('slug') == MODEL]
    require(len(selected) == 1, 'heldout fixed public model identity')
    modes = selected[0].get('model_messages', {}).get('collaboration_modes')
    require(isinstance(modes, dict) and isinstance(modes.get('default'), str)
        and io.sha(modes['default'].encode()) == DEFAULT_TEMPLATE_SHA256,
        'heldout fixed public mode template drift')
    raw = io.encoded(dict(models=selected))
    require(io.sha(raw) == SELECTED_SHA256, 'heldout selected public catalog drift')
    return raw


def fixed_catalog():
    """公開CLIの既知区間のみを有限に読む。全runtime検査は接続先でも必要。"""
    path = runtime.ROOT/runtime.VENDOR/'bin/codex'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size == BINARY_BYTES,
            'heldout fixed public CLI file shape')
        segment = os.pread(fd, LENGTH, OFFSET)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            'heldout public CLI changed during catalog read')
        return select(segment)
    finally:
        os.close(fd)
