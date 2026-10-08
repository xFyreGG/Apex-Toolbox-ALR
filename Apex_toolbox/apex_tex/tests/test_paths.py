"""Bounded searches must stay predictable across roots and filesystem order."""
import os
import tempfile
import unittest
from unittest.mock import patch

from apex_tex.paths import TextureIndex
from apex_tex import roots


class SearchLimitsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def file(self, name):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as handle:
            handle.write(b'texture')
        return path

    def test_file_limit_is_global_across_roots_and_images(self):
        for name in ['a/z_col.png', 'a/b_col.png', 'a/a_col.png', 'b/other_col.png']:
            self.file(name)
        index = TextureIndex()
        index.MAX_FILES = 2
        index.add_root(os.path.join(self.root, 'a'))
        index.add_root(os.path.join(self.root, 'b'))
        self.assertFalse(index.add_file(self.file('last.png')))
        self.assertFalse(index.add_image('image.png', 'missing.png'))
        self.assertEqual([f.name for f in index.files], ['a_col.png', 'b_col.png'])
        self.assertTrue(index.warnings)

    def test_directory_limit_bounds_trees_with_no_images(self):
        for i in range(10):
            os.mkdir(os.path.join(self.root, str(i)))
        index = TextureIndex()
        index.MAX_DIRECTORIES = 3
        index.add_root(self.root, recursive=True)
        self.assertEqual(index._directories, 3)
        self.assertTrue(index.warnings)

    def test_entry_limit_counts_non_image_files(self):
        for i in range(10):
            self.file('%d.txt' % i)
        index = TextureIndex()
        index.MAX_ENTRIES = 4
        index.add_root(self.root, recursive=True)
        self.assertEqual(index._entries, 4)
        self.assertEqual(len(index), 0)
        self.assertTrue(index.warnings)

    def test_depth_limit_warns_instead_of_silent_partial_search(self):
        self.file('one/two/body_col.png')
        index = TextureIndex()
        index.MAX_DEPTH = 1
        index.add_root(self.root, recursive=True)
        self.assertEqual(len(index), 0)
        self.assertTrue(any('Depth' in s for s in index.warnings))

    def test_unreadable_folder_is_reported(self):
        index = TextureIndex()
        with patch('os.scandir', side_effect=PermissionError('Denied')):
            index.add_root(self.root)
        self.assertTrue(any('Denied' in s for s in index.warnings))

    def test_disk_identity_reuses_image_without_losing_root_priority(self):
        path = self.file('body_col.png')
        image = object()
        index = TextureIndex()
        index.add_root(self.root, rank=1)
        index.add_image('user renamed image', path, rank=99, image_key=image)
        self.assertEqual(len(index), 1)
        self.assertEqual(index.files[0].root_rank, 1)
        self.assertIs(index.files[0].image_key, image)
        self.assertEqual(index.files[0].name, 'body_col.png')

    def test_recursive_override_upgrades_an_existing_material_root(self):
        result = roots.discover(material_dirs=[self.root], manual=self.root,
                                search_subfolders=True)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].recursive)
        self.assertEqual(result[0].rank, roots.RANK_MATERIAL_IMAGE)
