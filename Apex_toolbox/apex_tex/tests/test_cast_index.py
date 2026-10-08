"""Malformed exports must fail before entering the external CAST decoder."""
from pathlib import Path
import struct
import tempfile
import unittest

from apex_tex.cast_index import animation_files, iter_cast, nodes_of, read_cast


def node(kind, properties=b'', prop_count=0, children=()):
    payload = properties + b''.join(children)
    return struct.pack('<4sIQII', kind, 24 + len(payload), 123, prop_count, len(children)) + payload


def prop(name, value):
    return struct.pack('<2sHI', b's', len(name), 1) + name + value + b'\0'


def document(*children):
    return struct.pack('<4sIII', b'cast', 1, 1, 0) + node(b'root', children=children)


class CastIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'test.cast'

    def parse(self, data):
        self.path.write_bytes(data)
        return read_cast(self.path)

    def test_offsets_and_names_in_multiclip_file(self):
        roots = self.parse(document(node(b'anim', prop(b'n', b'idle'), 1),
                                    node(b'anim', prop(b'n', b'walk'), 1)))
        clips = nodes_of(roots, b'anim')
        self.assertEqual([c.properties['n'] for c in clips], ['idle', 'walk'])
        self.assertEqual(clips[0].offset, 40)
        self.assertEqual(clips[0].guid, 123)
        with open(self.path, 'rb') as stream:
            stream.seek(clips[1].offset)
            self.assertEqual(stream.read(4), b'anim')

    def test_unterminated_string(self):
        data = struct.pack('<2sHI', b's', 1, 1) + b'n' + b'no terminator'
        with self.assertRaisesRegex(ValueError, 'Unterminated'):
            self.parse(document(node(b'anim', data, 1)))

    def test_truncated_buffers(self):
        data = struct.pack('<2sHI', b'4v', 2, 999999) + b'kv' + b'\0' * 4
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            self.parse(document(node(b'curv', data, 1)))

    def test_huge_child_count(self):
        with self.assertRaisesRegex(ValueError, 'count'):
            self.parse(struct.pack('<4sIII', b'cast', 1, 1, 0)
                       + struct.pack('<4sIQII', b'root', 24, 0, 0, 99999999))

    def test_node_length_mismatch(self):
        with self.assertRaises(ValueError):
            self.parse(document(node(b'anim') + b'padding'))

    def test_magic_and_version(self):
        for data in (b'not cast', struct.pack('<4sIII', b'cast', 99, 0, 0)):
            with self.assertRaises(ValueError):
                self.parse(data)

    def test_discovery_includes_deeply_nested_files(self):
        (self.folder / 'nested').mkdir()
        (self.folder / 'nested' / 'walk.CAST').touch()
        (self.folder / 'idle.cast').touch()
        (self.folder / 'readme.txt').touch()
        files, warnings = animation_files(self.folder)
        self.assertEqual({p.name for p in files}, {'idle.cast', 'walk.CAST'})
        self.assertFalse(warnings)
        nested = self.folder.joinpath(*['nested'] * 10)
        nested.mkdir(parents=True)
        (nested / 'deep.cast').touch()
        files, warnings = animation_files(self.folder)
        self.assertEqual(len(files), 3)
        self.assertFalse(warnings)

    def test_discovery_has_no_4096_file_cutoff(self):
        for i in range(4100):
            (self.folder / ('%04d.cast' % i)).touch()
        files, warnings = animation_files(self.folder)
        self.assertEqual(len(files), 4100)
        self.assertEqual(files, sorted(files))
        self.assertFalse(warnings)

    def test_incremental_reader_yields_inside_file_and_releases_it_on_cancel(self):
        self.path.write_bytes(document(*[node(b'anim', prop(b'n', b'idle'), 1)] * 1000))
        steps = iter_cast(self.path)
        for _ in range(100):
            self.assertIsNone(next(steps))
        steps.close()
        self.path.unlink()  # Windows cannot unlink a file with a live mapping.

    def test_invalid_utf8(self):
        with self.assertRaises(UnicodeError):
            self.parse(document(node(b'anim', prop(b'n', b'\xff'), 1)))
