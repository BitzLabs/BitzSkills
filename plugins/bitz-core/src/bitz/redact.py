"""プロセスの出力の、公開する抜粋（安全な入出力・互換性 §9）。

§9のストリームの処理の要件（プロセスの生成の時点からの逐次的なUTF-8のデコード、伏せ字化の状態をチャンクの境界を
またいで維持、公開するバッファーは末尾64 KiBだけを保持）を満たすため、``StreamRedactor``は全出力を溜め込まず、
必要な最小限の保留分だけを保持して逐次処理する。適用順は§9の列挙順（1 環境変数の値 → 2
Authorization/Bearer → 3 キーと値の行 → 4 PEM）に従う。
"""

from __future__ import annotations

import codecs

REDACTED = "[REDACTED]"
_ENV_NAME_WORDS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "PRIVATE_KEY",
    "CREDENTIAL",
    "AUTH",
)
_KV_KEYWORDS = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "private_key",
    "credential",
    "auth",
)

_TAIL_LIMIT_BYTES = 65536
# 末尾バッファーの間引きの閾値。コードポイント1個は最大4バイトなので、64 KiBの数倍を確保しておけば
# 間引きの前後で境界を見失わない。ストリーム全体の長さに関わらず、この定数だけで頭打ちにする。
_TAIL_TRIM_THRESHOLD_CHARS = _TAIL_LIMIT_BYTES * 4

_AUTH_LITERAL = "authorization:"
_BEARER_LITERAL = "bearer"
_TRIGGER_MAX_LEN = len(_AUTH_LITERAL)

_PEM_BEGIN = "-----begin"
_PEM_MARKER = "private key-----"
_PEM_END = "-----end"
# BEGIN/END直後からPRIVATE KEY-----までの走査の上限。無制限に保留しないための防御的な上限。
_PEM_HEADER_SCAN_LIMIT = 256


def _is_control_keep(code: int) -> bool:
    return code in (0x09, 0x0A)


def _convert_controls(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if _is_control_keep(code):
            out.append(ch)
        elif code <= 0x1F or code == 0x7F or 0x80 <= code <= 0x9F:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    return "".join(out)


class _ControlNormalizer:
    """逐次的なUTF-8のデコード、CRLF/CR→LF、C0/DEL/C1→``\\uNNNN``。

    チャンクの末尾の単独のCRは、次のチャンクの先頭がLFかどうかで判定が変わるため、確定するまで保留する。
    """

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending_cr = False

    def feed(self, chunk: bytes) -> str:
        return self._normalize(self._decoder.decode(chunk, False))

    def close(self) -> str:
        out = self._normalize(self._decoder.decode(b"", True))
        if self._pending_cr:
            out += "\n"
            self._pending_cr = False
        return out

    def _normalize(self, text: str) -> str:
        if self._pending_cr:
            self._pending_cr = False
            if not text.startswith("\n"):
                # 前のチャンクの末尾のCRは単独だった: 先頭へ戻し、後段のCR→LFの変換に委ねる。
                text = "\r" + text
            # text.startswith("\n")の場合はCRLFがLFへ収束するので、先頭の"\n"をそのまま残す
            # （以前は`text[1:]`で捨てており、CRLFがまるごと消えて、伏せ字化の照合の対象の改行が
            # 失われるという、チャンクの分割に依存した漏えいを起こしていた）。
        if text.endswith("\r"):
            self._pending_cr = True
            text = text[:-1]
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return _convert_controls(text)


class _EnvValueFilter:
    """§9-1: 伏せ字化の対象の名前を持つ環境変数の、空でない値を置換する（ストリーム・チャンクの境界に対して安全）。

    保留は「候補値の最大長-1」文字だけ保持すればよく、ストリームの長さに依存しない。
    """

    def __init__(self, env: dict[str, str]) -> None:
        candidates: list[tuple[str, str]] = []
        for name, value in env.items():
            if not value:
                continue
            upper = name.upper()
            if any(word in upper for word in _ENV_NAME_WORDS):
                # §9「環境変数の値は、制御文字を処理した後の値に揃え」: 照合は伏せ字化の後と同じ正規化を適用する。
                normalized = _convert_controls(value.replace("\r\n", "\n").replace("\r", "\n"))
                if normalized:
                    candidates.append((name, normalized))
        # バイト長の降順、同じ長さは変数名のコードポイント辞書順（§9-1の末尾）。
        candidates.sort(key=lambda item: (-len(item[1].encode("utf-8")), item[0]))
        seen: set[str] = set()
        values: list[str] = []
        for _name, value in candidates:
            if value not in seen:
                seen.add(value)
                values.append(value)
        self._values = values
        self._holdback_len = max((len(v) for v in values), default=0)
        self._buffer = ""

    def feed(self, text: str) -> str:
        self._buffer += text
        return self._drain(final=False)

    def close(self) -> str:
        out = self._drain(final=True)
        self._buffer = ""
        return out

    def _drain(self, *, final: bool) -> str:
        out: list[str] = []
        while self._values:
            match = self._find_earliest()
            if match is None:
                break
            start, matched_value = match
            out.append(self._buffer[:start])
            out.append(REDACTED)
            self._buffer = self._buffer[start + len(matched_value) :]
        if final or not self._values:
            out.append(self._buffer)
            self._buffer = ""
        else:
            safe_len = max(0, len(self._buffer) - (self._holdback_len - 1))
            out.append(self._buffer[:safe_len])
            self._buffer = self._buffer[safe_len:]
        return "".join(out)

    def _find_earliest(self) -> tuple[int, str] | None:
        best: tuple[int, str] | None = None
        for value in self._values:
            idx = self._buffer.find(value)
            if idx == -1:
                continue
            if best is None or idx < best[0]:
                best = (idx, value)
        return best


class _AuthBearerKvFilter:
    """§9-2・§9-3: Authorization/Bearer/キーと値の行の値を置換する（ストリーム・チャンクの境界に対して安全）。

    トリガーの検出に必要な保留は直近``_TRIGGER_MAX_LEN``文字だけで、ストリームの長さに依存しない。
    キーワードの直後の``:``/``=``はASCIIの大文字と小文字を区別せずに判定し、単語境界を要求しない
    （`MY_TOKEN=`・`GITHUB_TOKEN=`のような接頭辞付きでも一致させる。過剰なマスクは安全側）。
    """

    def __init__(self) -> None:
        self._rolling = ""
        self._mode = "normal"  # normal | bearer_ws | redact_line | redact_token

    def feed(self, text: str) -> str:
        out: list[str] = []
        for ch in text:
            self._step(ch, out)
        return "".join(out)

    def close(self) -> str:
        return ""

    def _step(self, ch: str, out: list[str]) -> None:
        if self._mode == "redact_line":
            if ch == "\n":
                out.append(ch)
                self._mode = "normal"
                self._rolling = ""
            return
        if self._mode == "redact_token":
            if ch.isspace():
                out.append(ch)
                self._mode = "normal"
                self._rolling = ""
            return
        if self._mode == "bearer_ws":
            if ch.isspace():
                out.append(ch)
                return
            out.append(REDACTED)
            self._mode = "redact_token"
            self._rolling = ""
            return

        out.append(ch)
        self._rolling = (self._rolling + ch.lower())[-_TRIGGER_MAX_LEN:]
        if self._rolling.endswith(_AUTH_LITERAL):
            out.append(REDACTED)
            self._mode = "redact_line"
            self._rolling = ""
            return
        if ch.isspace() and self._rolling[:-1].endswith(_BEARER_LITERAL):
            self._mode = "bearer_ws"
            self._rolling = ""
            return
        if ch in (":", "="):
            for kw in _KV_KEYWORDS:
                if self._rolling.endswith(kw + ch):
                    out.append(REDACTED)
                    self._mode = "redact_line"
                    self._rolling = ""
                    return


class _PemFilter:
    """§9-4: PEMの`PRIVATE KEY`のブロックを置換する（ストリーム・チャンクの境界に対して安全、未終端も末尾まで維持）。"""

    def __init__(self) -> None:
        self._buffer = ""
        self._mode = "normal"  # normal | in_pem

    def feed(self, text: str) -> str:
        self._buffer += text
        return self._drain(final=False)

    def close(self) -> str:
        out = self._drain(final=True)
        self._buffer = ""
        return out

    def _drain(self, *, final: bool) -> str:
        out: list[str] = []
        while True:
            if self._mode == "in_pem":
                if not self._drain_in_pem(out, final):
                    return "".join(out)
                continue
            if not self._drain_normal(out, final):
                return "".join(out)

    def _drain_in_pem(self, out: list[str], final: bool) -> bool:
        low = self._buffer.lower()
        idx = low.find(_PEM_END)
        if idx == -1:
            if final:
                # §9「開始を検出した時点から終端まで伏せ字化の状態を保ち」。未終端のPEMも末尾までマスクする。
                self._buffer = ""
                return False
            # ENDが来る可能性が残る間は本体を溜め続けない。走査の上限の分だけ保持すれば十分。
            self._buffer = self._buffer[-_PEM_HEADER_SCAN_LIMIT:]
            return False
        after = self._buffer[idx : idx + _PEM_HEADER_SCAN_LIMIT]
        marker_idx = after.lower().find(_PEM_MARKER)
        if marker_idx == -1:
            if len(after) >= _PEM_HEADER_SCAN_LIMIT or final:
                # 確定できないEND候補は通常の文字列として読み飛ばし、次のENDを探す。
                self._buffer = self._buffer[idx + len(_PEM_END) :]
                return True
            return False
        self._buffer = self._buffer[idx + marker_idx + len(_PEM_MARKER) :]
        self._mode = "normal"
        return True

    def _drain_normal(self, out: list[str], final: bool) -> bool:
        low = self._buffer.lower()
        begin_idx = low.find(_PEM_BEGIN)
        if begin_idx == -1:
            if final:
                out.append(self._buffer)
                self._buffer = ""
            else:
                safe_len = max(0, len(self._buffer) - (len(_PEM_BEGIN) - 1))
                out.append(self._buffer[:safe_len])
                self._buffer = self._buffer[safe_len:]
            return False
        # 確定の前に、begin_idxより前を確定済みとして吐き出し、バッファーをbeginの位置を基準に詰める。
        # そうしないと、未確定のまま複数回汲み出されたとき、同じ接頭辞を重複して出力してしまう。
        out.append(self._buffer[:begin_idx])
        self._buffer = self._buffer[begin_idx:]
        candidate = self._buffer[:_PEM_HEADER_SCAN_LIMIT]
        candidate_low = candidate.lower()
        marker_idx = candidate_low.find(_PEM_MARKER)
        newline_idx = candidate.find("\n")
        if marker_idx != -1 and (newline_idx == -1 or marker_idx < newline_idx):
            out.append(REDACTED)
            self._buffer = self._buffer[marker_idx + len(_PEM_MARKER) :]
            self._mode = "in_pem"
            return True
        if newline_idx != -1 and (marker_idx == -1 or newline_idx < marker_idx):
            out.append(self._buffer[: len(_PEM_BEGIN)])
            self._buffer = self._buffer[len(_PEM_BEGIN) :]
            return True
        if len(candidate) >= _PEM_HEADER_SCAN_LIMIT:
            out.append(self._buffer[: len(_PEM_BEGIN)])
            self._buffer = self._buffer[len(_PEM_BEGIN) :]
            return True
        if final:
            # ストリームが終わるまでPRIVATE KEY-----が確定しなかった: 安全側でBEGIN以降を末尾までマスクする。
            out.append(REDACTED)
            self._buffer = ""
            return False
        return False


class StreamRedactor:
    """プロセスの出力を§9のストリームの処理で伏せ字にし、末尾64 KiBの公開する抜粋を保持する。

    ``feed()``をチャンクごとに呼び、最後に``close()``で``(excerpt, truncated)``を得る。
    保持するメモリは64 KiB＋各フィルターの有界の保留分に収まり、元のストリームの総量へ依存しない。
    """

    def __init__(self, env: dict[str, str]) -> None:
        self._control = _ControlNormalizer()
        self._env_filter = _EnvValueFilter(env)
        self._auth_kv_filter = _AuthBearerKvFilter()
        self._pem_filter = _PemFilter()
        self._tail = ""
        self._raw_len = 0
        self._closed = False

    def feed(self, chunk: bytes) -> None:
        if not chunk:
            return
        self._raw_len += len(chunk)
        self._advance(self._control.feed(chunk))

    def close(self) -> tuple[str, bool]:
        if not self._closed:
            self._advance(self._control.close())
            text = self._env_filter.close()
            text = self._auth_kv_filter.feed(text) + self._auth_kv_filter.close()
            text = self._pem_filter.feed(text) + self._pem_filter.close()
            self._append_tail(text)
            self._closed = True
        truncated = self._raw_len > _TAIL_LIMIT_BYTES
        excerpt = self._trim_to_limit(self._tail)
        return excerpt, truncated

    def _advance(self, text: str) -> None:
        if not text:
            return
        text = self._env_filter.feed(text)
        text = self._auth_kv_filter.feed(text)
        text = self._pem_filter.feed(text)
        self._append_tail(text)

    def _append_tail(self, text: str) -> None:
        if not text:
            return
        self._tail += text
        if len(self._tail) > _TAIL_TRIM_THRESHOLD_CHARS:
            self._tail = self._trim_to_limit(self._tail)

    @staticmethod
    def _trim_to_limit(text: str) -> str:
        encoded = text.encode("utf-8")
        if len(encoded) <= _TAIL_LIMIT_BYTES:
            return text
        tail = encoded[-_TAIL_LIMIT_BYTES:]
        i = 0
        while i < len(tail) and (tail[i] & 0xC0) == 0x80:
            i += 1
        return tail[i:].decode("utf-8", errors="ignore")


def redact_output(raw: bytes, env: dict[str, str]) -> tuple[str, bool]:
    """一括のバイト列を1回で処理する互換用の関数（小さな入力・試験向け）。"""

    redactor = StreamRedactor(env)
    redactor.feed(raw)
    return redactor.close()
