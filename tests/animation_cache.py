"""Pure Python tests: python tests/animation_cache.py (no Blender required)."""
import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'Apex_toolbox/apex_tex/animation_cache.py'
SPEC = importlib.util.spec_from_file_location('animation_cache', SOURCE)
cache = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cache)


@dataclasses.dataclass
class Clip:
    filepath: str
    offset: int = 16
    name: str = 'idle'
    fps: float = 30.0
    additive: bool = False
    guid: str = 'fedcab0123456789'
    sequence_hash: str = '123abc'
    external: bool = False


class AnimationCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rig = self.root / 'pilot_medium.cast'
        self.rig.write_bytes(b'rig' * 64)
        self.clip = self.root / 'anims_pilot_medium' / 'idle.cast'
        self.clip.parent.mkdir()
        self.clip.write_bytes(b'animation' * 64)
        self.cache_root = self.root / 'user-data' / 'animation-index'

    def index(self, **options):
        return cache.Index(self.rig, self.cache_root, **options)

    def saved_index(self, entries=None, warnings=()):
        index = self.index()
        self.assertIsNone(index.lookup(self.clip))
        self.assertTrue(index.record(self.clip, entries if entries is not None else [Clip(str(self.clip))], warnings))
        self.assertTrue(index.finish())
        return index

    def test_round_trip_dataclasses_and_warning_preservation(self):
        self.saved_index(warnings=['Unreadable curve was skipped.'])
        index = self.index()
        entries, warnings = index.lookup(self.clip)
        self.assertEqual(entries, [dataclasses.asdict(Clip(str(self.clip)))])
        self.assertEqual(warnings, ['Unreadable curve was skipped.'])
        self.assertEqual((index.hits, index.misses), (1, 0))
        self.assertTrue(index.finish())

    def test_cache_does_not_retain_user_state_or_trust_source_path(self):
        entry = dataclasses.asdict(Clip('another/file.cast'))
        entry.update(favourite=True, menu_name='Custom name', recent_order=1)
        self.saved_index(entries=[entry])
        restored, _ = self.index().lookup(self.clip)
        self.assertEqual(restored, [dataclasses.asdict(Clip(str(self.clip)))])

    def test_lookup_results_are_independent_copies(self):
        self.saved_index()
        index = self.index()
        entries, warnings = index.lookup(self.clip)
        entries[0]['name'] = 'mutated'
        warnings.append('mutated')
        self.assertTrue(index.finish())
        entries, warnings = self.index().lookup(self.clip)
        self.assertEqual(entries[0]['name'], 'idle')
        self.assertEqual(warnings, [])

    def test_changed_size_or_timestamp_requires_reparse(self):
        self.saved_index()
        self.clip.write_bytes(self.clip.read_bytes() + b'new')
        self.assertIsNone(self.index().lookup(self.clip))
        self.saved_index()
        info = self.clip.stat()
        os.utime(self.clip, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000000))
        self.assertIsNone(self.index().lookup(self.clip))

    def test_replaced_file_with_preserved_size_and_mtime_requires_reparse(self):
        self.saved_index()
        info = self.clip.stat()
        replacement = self.clip.with_suffix('.new')
        replacement.write_bytes(b'x' * info.st_size)
        os.utime(replacement, ns=(info.st_atime_ns, info.st_mtime_ns))
        os.replace(replacement, self.clip)
        self.assertIsNone(self.index().lookup(self.clip))

    def test_changed_rig_invalidates_all_files(self):
        self.saved_index()
        self.rig.write_bytes(b'new rig')
        self.assertIsNone(self.index().lookup(self.clip))

    def test_changed_file_does_not_invalidate_unchanged_files(self):
        second = self.clip.with_name('walk.cast')
        second.write_bytes(b'x' * 128)
        index = self.saved_index()
        index.lookup(second)
        index.record(second, [Clip(str(second), name='walk')])
        index.finish()
        second.write_bytes(b'x' * 256)
        index = self.index()
        self.assertIsNotNone(index.lookup(self.clip))
        self.assertIsNone(index.lookup(second))
        self.assertEqual((index.hits, index.misses), (1, 1))

    def test_force_scan_replaces_metadata_without_reuse(self):
        self.saved_index()
        index = self.index(force=True)
        self.assertIsNone(index.lookup(self.clip))
        self.assertTrue(index.record(self.clip, [Clip(str(self.clip), name='new_idle')]))
        self.assertTrue(index.finish())
        self.assertEqual(self.index().lookup(self.clip)[0][0]['name'], 'new_idle')

    def test_removed_files_are_pruned_on_completed_scan(self):
        second = self.clip.with_name('walk.cast')
        second.write_bytes(b'x' * 128)
        index = self.saved_index()
        index.lookup(second)
        index.record(second, [Clip(str(second), name='walk')])
        index.finish()
        second.unlink()
        index = self.index()
        self.assertIsNotNone(index.lookup(self.clip))
        self.assertTrue(index.finish())
        saved = json.loads(index.path.read_text())
        self.assertEqual(len(saved['files']), 1)

    def test_cancelled_scan_does_not_replace_previous_index(self):
        original = self.saved_index()
        before = original.path.read_bytes()
        index = self.index(force=True)
        index.lookup(self.clip)
        index.record(self.clip, [Clip(str(self.clip), name='unfinished')])
        # A cancelled caller deliberately does not call finish.
        self.assertEqual(original.path.read_bytes(), before)
        self.assertEqual(self.index().lookup(self.clip)[0][0]['name'], 'idle')

    def test_file_changed_during_parse_is_not_recorded(self):
        index = self.index()
        index.lookup(self.clip)
        self.clip.write_bytes(b'x' * 1024)
        self.assertFalse(index.record(self.clip, [Clip(str(self.clip))]))
        index.finish()
        self.assertIsNone(self.index().lookup(self.clip))

    def test_rig_changed_during_scan_is_not_saved(self):
        index = self.index()
        index.lookup(self.clip)
        index.record(self.clip, [Clip(str(self.clip))])
        self.rig.write_bytes(b'changed')
        self.assertFalse(index.finish())
        self.assertFalse(index.path.exists())

    def test_corrupt_wrong_schema_or_reader_cache_becomes_miss(self):
        index = self.saved_index()
        original = json.loads(index.path.read_text())
        for data in [b'{broken', b'[]', b'null', b'{"files":null}']:
            index.path.write_bytes(data)
            self.assertIsNone(self.index().lookup(self.clip))
        for field in ('schema', 'reader'):
            saved = dict(original, **{field: -1})
            index.path.write_text(json.dumps(saved))
            self.assertIsNone(self.index().lookup(self.clip))

    def test_invalid_cached_metadata_becomes_miss(self):
        index = self.saved_index()
        original = json.loads(index.path.read_text())
        key = next(iter(original['files']))
        for field, value in [('offset', -1), ('offset', True), ('offset', 1000000), ('name', None),
                             ('fps', float('nan')), ('additive', 1), ('guid', 'not_hex')]:
            saved = json.loads(json.dumps(original))
            saved['files'][key]['entries'][0][field] = value
            index.path.write_text(json.dumps(saved))
            self.assertIsNone(self.index().lookup(self.clip))

    def test_missing_files_disabled_cache_and_unwritable_paths_are_safe(self):
        index = cache.Index(self.rig, None)
        self.assertIsNone(index.lookup(self.clip))
        self.assertTrue(index.record(self.clip, [Clip(str(self.clip))]))
        self.assertFalse(index.finish())
        self.assertIsNone(index.lookup(self.clip.with_name('missing.cast')))
        cache_as_file = self.root / 'unwritable-root'
        cache_as_file.write_text('file instead of folder')
        index = cache.Index(self.rig, cache_as_file)
        index.lookup(self.clip)
        index.record(self.clip, [Clip(str(self.clip))])
        self.assertFalse(index.finish())

    def test_failed_atomic_replace_keeps_previous_index_and_cleans_temporary(self):
        original = self.saved_index()
        before = original.path.read_bytes()
        index = self.index(force=True)
        index.lookup(self.clip)
        index.record(self.clip, [Clip(str(self.clip), name='new')])
        with patch.object(cache.os, 'replace', side_effect=PermissionError('denied')):
            self.assertFalse(index.finish())
        self.assertEqual(original.path.read_bytes(), before)
        self.assertEqual(list(self.cache_root.glob('*.tmp')), [])

    def test_oversized_cache_is_ignored(self):
        index = self.saved_index()
        with patch.object(cache, 'MAX_CACHE_BYTES', 10):
            self.assertIsNone(self.index().lookup(self.clip))
            self.assertFalse(index.finish())

    def test_empty_entries_preserve_invalid_file_warnings(self):
        self.saved_index(entries=[], warnings=['Invalid CAST data.'])
        self.assertEqual(self.index().lookup(self.clip), ([], ['Invalid CAST data.']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
