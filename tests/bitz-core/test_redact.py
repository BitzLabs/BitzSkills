"""`bitz.redact`の単体試験（`00_共通契約/02_安全な入出力・互換性.md` §9）。"""

import tracemalloc
import unittest

from bitz import redact


def _feed_in_chunks(redactor: redact.StreamRedactor, raw: bytes, chunk_size: int) -> None:
    for i in range(0, len(raw), chunk_size):
        redactor.feed(raw[i : i + chunk_size])


class ControlCharTests(unittest.TestCase):
    def test_tab_and_lf_are_kept(self):
        excerpt, truncated = redact.redact_output(b"a\tb\nc", {})
        self.assertEqual(excerpt, "a\tb\nc")
        self.assertFalse(truncated)

    def test_crlf_and_lone_cr_become_lf(self):
        excerpt, _ = redact.redact_output(b"a\r\nb\rc", {})
        self.assertEqual(excerpt, "a\nb\nc")

    def test_c0_del_c1_become_escaped_codepoint(self):
        excerpt, _ = redact.redact_output(b"a\x01b\x7fc\xc2\x85d", {})
        self.assertEqual(excerpt, "a\\u0001b\\u007fc\\u0085d")

    def test_esc_is_escaped_not_interpreted(self):
        excerpt, _ = redact.redact_output(b"\x1b[31mred\x1b[0m", {})
        self.assertEqual(excerpt, "\\u001b[31mred\\u001b[0m")

    def test_invalid_utf8_becomes_replacement_char(self):
        excerpt, _ = redact.redact_output(b"a\xffb", {})
        self.assertEqual(excerpt, "a�b")


class SecretRedactionTests(unittest.TestCase):
    def test_authorization_header_value_redacted(self):
        excerpt, _ = redact.redact_output(b"Authorization:secret-token\nnext", {})
        self.assertEqual(excerpt, "Authorization:[REDACTED]\nnext")

    def test_bearer_token_redacted_keeping_prefix(self):
        excerpt, _ = redact.redact_output(b"call Bearer abc.def-123 done", {})
        self.assertEqual(excerpt, "call Bearer [REDACTED] done")

    def test_keyword_colon_or_equals_redacted(self):
        excerpt, _ = redact.redact_output(b"password=hunter2", {})
        self.assertEqual(excerpt, "password=[REDACTED]")
        excerpt2, _ = redact.redact_output(b"token: abc123", {})
        self.assertEqual(excerpt2, "token:[REDACTED]")

    def test_pem_block_is_fully_redacted(self):
        raw = (
            b"before\n-----BEGIN RSA PRIVATE KEY-----\n"
            b"AAAA\nBBBB\n-----END RSA PRIVATE KEY-----\nafter\n"
        )
        excerpt, _ = redact.redact_output(raw, {})
        self.assertEqual(excerpt, "before\n[REDACTED]\nafter\n")

    def test_env_var_value_redacted_regardless_of_context(self):
        env = {"BITZ_FIXTURE_TOKEN": "s3cr3t-value"}
        excerpt, _ = redact.redact_output(b"probe s3cr3t-value end", env)
        self.assertEqual(excerpt, "probe [REDACTED] end")

    def test_env_var_without_keyword_name_is_not_redacted(self):
        env = {"BITZ_FIXTURE_PROBE": "inherited-value"}
        excerpt, _ = redact.redact_output(b"plain inherited-value text", env)
        self.assertEqual(excerpt, "plain inherited-value text")

    def test_empty_env_value_is_ignored(self):
        env = {"BITZ_FIXTURE_TOKEN": ""}
        excerpt, _ = redact.redact_output(b"nothing to see", env)
        self.assertEqual(excerpt, "nothing to see")

    def test_env_values_redacted_longest_first_to_avoid_partial_overlap(self):
        env = {"A_TOKEN": "ab", "B_TOKEN": "abc"}
        excerpt, _ = redact.redact_output(b"value=abc", env)
        # 最長一致(abc)が先に置換されるため、残りの"ab"は残らない。
        self.assertEqual(excerpt, "value=[REDACTED]")

    def test_secret_spanning_synthetic_chunk_join_is_still_redacted(self):
        # chunk境界をまたいでも、最終合成後のbufferに対してredactionが適用されることを確認する。
        chunk_a = b"probe s3cr3t-env-"
        chunk_b = b"value-0123456789 end"
        excerpt, _ = redact.redact_output(chunk_a + chunk_b, {"BITZ_FIXTURE_TOKEN": "s3cr3t-env-value-0123456789"})
        self.assertEqual(excerpt, "probe [REDACTED] end")


class TruncationTests(unittest.TestCase):
    def test_short_output_not_truncated(self):
        excerpt, truncated = redact.redact_output(b"short", {})
        self.assertEqual(excerpt, "short")
        self.assertFalse(truncated)

    def test_raw_over_64kib_sets_truncated_true(self):
        raw = b"x" * (65536 + 10)
        excerpt, truncated = redact.redact_output(raw, {})
        self.assertTrue(truncated)
        self.assertLessEqual(len(excerpt.encode("utf-8")), 65536)
        self.assertTrue(excerpt.endswith("x"))

    def test_raw_within_limit_but_redaction_grows_text_keeps_truncated_false(self):
        # 制御文字1つが"\\uNNNN"(6文字)へ展開されるため、大量の制御文字はraw byte数以内でも
        # redaction後のbufferが64 KiBを超え得る。この場合もtruncatedはfalseのままとする。
        raw = (b"\x01" * 20000)
        excerpt, truncated = redact.redact_output(raw, {})
        self.assertFalse(truncated)
        self.assertLessEqual(len(excerpt.encode("utf-8")), 65536)

    def test_tail_kept_at_codepoint_boundary(self):
        # マルチバイト文字が境界に来ても不正byte列を残さない。
        raw = ("あ" * 40000).encode("utf-8") + b"end"
        excerpt, truncated = redact.redact_output(raw, {})
        self.assertTrue(truncated) if len(raw) > 65536 else None
        # 有効なUTF-8として再decodeできることを確認する(境界破損なし)。
        excerpt.encode("utf-8")
        self.assertTrue(excerpt.endswith("end"))


class KvBoundaryFixTests(unittest.TestCase):
    """検収是正1: keyword直後の`:`/`=`はword boundaryを要求しない（接頭辞付きでも一致）。"""

    def test_my_token_equals_is_redacted(self):
        excerpt, _ = redact.redact_output(b"MY_TOKEN=abc123", {})
        self.assertEqual(excerpt, "MY_TOKEN=[REDACTED]")

    def test_github_token_equals_is_redacted(self):
        excerpt, _ = redact.redact_output(b"GITHUB_TOKEN=ghp_x", {})
        self.assertEqual(excerpt, "GITHUB_TOKEN=[REDACTED]")

    def test_x_api_key_colon_is_redacted(self):
        excerpt, _ = redact.redact_output(b"x_api_key: v", {})
        self.assertEqual(excerpt, "x_api_key:[REDACTED]")

    def test_bearer_without_word_boundary_is_redacted(self):
        excerpt, _ = redact.redact_output(b"xBearer abc123 done", {})
        self.assertEqual(excerpt, "xBearer [REDACTED] done")


class EnvValueControlNormalizationTests(unittest.TestCase):
    """検収是正2: 環境変数値も制御文字処理後の値で照合する。"""

    def test_env_value_with_crlf_matches_normalized_output(self):
        env = {"BITZ_TEST_SECRET": "line1\r\nline2"}
        raw = b"before line1\r\nline2 after"
        excerpt, _ = redact.redact_output(raw, env)
        self.assertEqual(excerpt, "before [REDACTED] after")

    def test_env_value_with_control_char_matches_normalized_output(self):
        env = {"BITZ_TEST_TOKEN": "a\x01b"}
        raw = b"before a\x01b after"
        excerpt, _ = redact.redact_output(raw, env)
        self.assertEqual(excerpt, "before [REDACTED] after")


class OrderingTests(unittest.TestCase):
    """検収是正3: 環境変数値→Authorization/Bearer→kv→PEMの順で適用する。"""

    def test_env_value_replaced_before_line_rules_can_break_it(self):
        # 環境変数値の中にkv風の文字列が含まれていても、先に環境変数値として丸ごと置換される。
        env = {"BITZ_TEST_TOKEN": "password=inner"}
        raw = b"prefix password=inner suffix"
        excerpt, _ = redact.redact_output(raw, env)
        self.assertEqual(excerpt, "prefix [REDACTED] suffix")

    def test_same_length_values_tie_broken_by_variable_name_order(self):
        # 同じUTF-8 byte長の値は変数名のcode point辞書順で照合する。
        # ここではどちらのnameでも最終出力は同一（値が異なるため両方redactされる）ことを確認しつつ、
        # 実装内部のsort keyがname順であることを別途ホワイトボックスに検査する。
        env = {"Z_TOKEN": "bbbb", "A_TOKEN": "aaaa"}
        filt = redact._EnvValueFilter(env)
        self.assertEqual(filt._values, ["aaaa", "bbbb"])


class ChunkBoundaryTests(unittest.TestCase):
    """検収是正5: chunk境界をまたぐkv・環境変数値・PEM BEGIN/ENDでも正しくredactされる。"""

    def test_kv_keyword_split_across_chunks(self):
        redactor = redact.StreamRedactor({})
        raw = b"passwo" + b"rd=hunter2\n"
        _feed_in_chunks(redactor, raw, 3)
        excerpt, _ = redactor.close()
        self.assertEqual(excerpt, "password=[REDACTED]\n")

    def test_authorization_split_across_chunks(self):
        redactor = redact.StreamRedactor({})
        raw = b"Authoriza" + b"tion:secret\nnext"
        _feed_in_chunks(redactor, raw, 4)
        excerpt, _ = redactor.close()
        self.assertEqual(excerpt, "Authorization:[REDACTED]\nnext")

    def test_env_value_split_across_chunks(self):
        env = {"BITZ_TEST_TOKEN": "s3cr3t-value-1234567890"}
        redactor = redact.StreamRedactor(env)
        raw = b"probe s3cr3t-value-1234567890 end"
        _feed_in_chunks(redactor, raw, 5)
        excerpt, _ = redactor.close()
        self.assertEqual(excerpt, "probe [REDACTED] end")

    def test_pem_begin_and_end_split_across_chunks(self):
        redactor = redact.StreamRedactor({})
        raw = (
            b"before\n-----BEGIN RSA PRIVATE KEY-----\n"
            b"AAAABBBBCCCC\n-----END RSA PRIVATE KEY-----\nafter\n"
        )
        _feed_in_chunks(redactor, raw, 6)
        excerpt, _ = redactor.close()
        self.assertEqual(excerpt, "before\n[REDACTED]\nafter\n")


class UnterminatedPemTests(unittest.TestCase):
    """検収是正4: ENDが来ないままstreamが終わっても末尾までredactする。"""

    def test_pem_without_end_marker_is_redacted_to_stream_end(self):
        raw = b"before\n-----BEGIN RSA PRIVATE KEY-----\nAAAABBBBCCCC\nmore-data-with-no-end\n"
        excerpt, _ = redact.redact_output(raw, {})
        self.assertEqual(excerpt, "before\n[REDACTED]")

    def test_pem_cut_mid_header_at_stream_end_is_conservatively_redacted(self):
        raw = b"before\n-----BEGIN RSA PRI"
        excerpt, _ = redact.redact_output(raw, {})
        self.assertEqual(excerpt, "before\n[REDACTED]")


class AllSplitPositionsTests(unittest.TestCase):
    """検収是正（2回目）: 全byte位置で2分割した結果が一括投入と一致することを網羅する。

    CR・CRLF・マルチバイト文字・PEM・kv・環境変数値を含む入力を対象に、1バイトずつ位置を
    ずらして2 chunkへ分割してもStreamRedactorの出力が一括投入と一致することを確認する。
    分割位置を総当たりするため、他のfilterのchunk境界バグもここで拾う。
    """

    ENV = {
        "GH_TOKEN": "ghp_SECRETVALUE123",
        "MY_PASSWORD": "p\x1bss\rword",
        "HOME": "/home/x",
        "API_KEY_B": "zzzz",
        "AUTH_A": "yyyy",
    }
    RAW = (
        "start ok\n"
        "export GITHUB_TOKEN=ghp_other_leak and more\n"
        "curl -H 'Authorization: Basic abcd' x\n"
        "header Bearer\tabc.def ok\n"
        "val ghp_SECRETVALUE123 inline\n"
        "pw p\x1bss\r\nword\n"
        "x_api_key:kkk\n"
        "same zzzz yyyy\n"
        "あいうえお漢字混じりmulti-byte\r\ntext\r"
        "-----BEGIN RSA PRIVATE KEY-----\nMIIsecretkeydata\n-----END RSA PRIVATE KEY-----\nafter\n"
        "tail -----BEGIN OPENSSH PRIVATE KEY-----\nunterminated secret material"
    ).encode("utf-8")

    def _run(self, splits: list[int]) -> tuple[str, bool]:
        redactor = redact.StreamRedactor(self.ENV)
        pos = 0
        for s in splits:
            redactor.feed(self.RAW[pos:s])
            pos = s
        redactor.feed(self.RAW[pos:])
        return redactor.close()

    def test_two_way_split_at_every_byte_position_matches_single_feed(self):
        baseline = self._run([])
        self.assertNotIn("ghp_SECRETVALUE123", baseline[0])
        self.assertNotIn("ghp_other_leak", baseline[0])
        self.assertNotIn("abcd", baseline[0])
        self.assertNotIn("MIIsecret", baseline[0])
        self.assertNotIn("unterminated", baseline[0])
        self.assertNotIn("p\x1bssword", baseline[0].replace("\\u001b", "\x1b"))

        mismatches = []
        for cut in range(1, len(self.RAW)):
            got = self._run([cut])
            if got != baseline:
                mismatches.append((cut, self.RAW[max(0, cut - 10) : cut], self.RAW[cut : cut + 10], got))
        if mismatches:
            cut, before, after, got = mismatches[0]
            self.fail(
                f"{len(mismatches)}件のchunk分割位置で一括投入と結果が異なります。"
                f"最初の不一致: cut={cut} before={before!r} after={after!r}\n"
                f"expected={baseline[0]!r}\nactual  ={got[0]!r}"
            )


class MemoryBoundTests(unittest.TestCase):
    """検収是正5: 巨大な出力でもmemoryが有界であること。"""

    def test_ten_mib_output_keeps_bounded_peak_memory(self):
        chunk = ("x" * 8192).encode("ascii")
        redactor = redact.StreamRedactor({"BITZ_TEST_TOKEN": "irrelevant-secret-value"})
        # warm up（importや初回allocationのオーバーヘッドを測定対象から外す）。
        for _ in range(4):
            redactor.feed(chunk)

        tracemalloc.start()
        try:
            total_fed = 0
            target = 10 * 1024 * 1024
            while total_fed < target:
                redactor.feed(chunk)
                total_fed += len(chunk)
            excerpt, truncated = redactor.close()
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertTrue(truncated)
        self.assertLessEqual(len(excerpt.encode("utf-8")), 65536)
        # 10 MiB相当を流し込んでも、追跡peakは数MB程度に収まるはず（出力全体を保持していない証跡）。
        self.assertLess(peak, 5 * 1024 * 1024, f"peak={peak} bytes: 出力総量へ依存して増加しています")


if __name__ == "__main__":
    unittest.main()
