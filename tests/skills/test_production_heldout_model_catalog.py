"""公開catalogの差替え、対象/テンプレート不整合、読取り時の形状変化を拒否する。"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'evals/skills/routing'))
import production_heldout_model_catalog as catalog


class HeldoutModelCatalogTests(unittest.TestCase):
    def setUp(self):
        self.target = dict(slug=catalog.MODEL,
            model_messages=dict(collaboration_modes=dict(default='PUBLIC_SYNTHETIC_TEMPLATE')))
        self.value = dict(models=[self.target, *[dict(slug='public-other-'+str(n)) for n in range(10)]])

    def selected(self, value, *, selected_hash=None, template_hash=None):
        raw = catalog.io.encoded(value)
        with patch.multiple(catalog, LENGTH=len(raw), SEGMENT_SHA256=catalog.io.sha(raw),
            SELECTED_SHA256=selected_hash or catalog.io.sha(catalog.io.encoded(dict(models=[self.target]))),
            SELECTED_BYTES=len(catalog.io.encoded(dict(models=[self.target]))),
            DEFAULT_TEMPLATE_SHA256=template_hash or catalog.io.sha(b'PUBLIC_SYNTHETIC_TEMPLATE')):
            return catalog.select(raw)

    def test_only_the_fixed_target_is_returned(self):
        self.assertEqual(json.loads(self.selected(self.value)), dict(models=[self.target]))

    def test_segment_byte_drift_and_wrong_type_are_rejected(self):
        for raw in [b'{}', b'', 'PUBLIC', None]:
            with self.subTest(kind=type(raw).__name__), self.assertRaises(ValueError):
                catalog.select(raw)

    def test_target_missing_duplicate_and_wrong_inventory_are_rejected(self):
        for value in [dict(models=self.value['models'][1:]),
            dict(models=[self.target, self.target, *self.value['models'][2:]]),
            dict(models=self.value['models'], extra=True), dict(models={})]:
            with self.subTest(keys=list(value)), self.assertRaises(ValueError):
                self.selected(value)

    def test_template_and_selected_catalog_hashes_are_independent_pins(self):
        for kwargs in [dict(template_hash='0'*64), dict(selected_hash='0'*64)]:
            with self.subTest(pin=list(kwargs)), self.assertRaises(ValueError):
                self.selected(self.value, **kwargs)

    def test_missing_and_null_template_do_not_select_a_fallback(self):
        for modes in [None, {}, dict(default=None), dict(default='DIFFERENT_PUBLIC_TEMPLATE')]:
            target=dict(self.target, model_messages=dict(collaboration_modes=modes))
            with self.subTest(modes=modes), self.assertRaises(ValueError):
                self.selected(dict(models=[target, *self.value['models'][1:]]))

    def test_fixed_file_shape_and_mid_read_change_are_rejected(self):
        good=dict(st_dev=1, st_ino=2, st_size=catalog.BINARY_BYTES, st_mtime_ns=3,
            st_ctime_ns=4, st_mode=0o100644)
        for before, after in [(dict(good, st_size=1), good),
            (dict(good, st_mode=0o040755), good), (good, dict(good, st_mtime_ns=5))]:
            with self.subTest(before=before,after=after), patch.object(catalog.os, 'open', return_value=9), \
                patch.object(catalog.os, 'fstat', side_effect=[SimpleNamespace(**before), SimpleNamespace(**after)]), \
                patch.object(catalog.os, 'pread', return_value=b'PUBLIC'), \
                patch.object(catalog.os, 'close') as close, self.assertRaises(ValueError):
                catalog.fixed_catalog()
            close.assert_called_once_with(9)

    def test_configuration_is_copied_and_rejects_override_or_relative_root(self):
        config={'public':True};result=catalog.configuration(Path('/public-stage'),config)
        self.assertEqual(config,{'public':True})
        self.assertEqual(result['model_catalog_json'],'/public-stage/public-model-catalog.json')
        for root,value in [(Path('relative'),config),(Path('/public/../other'),config),
            (Path('/public-stage'),{'model_catalog_json':'/untrusted'})]:
            with self.subTest(root=root),self.assertRaises(ValueError):catalog.configuration(root,value)

    def test_selected_bytes_are_pinned_even_without_the_binary(self):
        for raw in [b'{}',b'',None,'PUBLIC']:
            with self.subTest(kind=type(raw).__name__),self.assertRaises(ValueError):catalog.verify(raw)


if __name__ == '__main__':
    unittest.main()
