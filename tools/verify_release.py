"""Check that the installable ZIP is an exact, clean copy of the add-on tree."""
import hashlib
from pathlib import Path
import zipfile

from build_release import ADDON, ROOT, release_version


version = '.'.join(map(str, release_version()))
archive_path = ROOT / 'dist' / ('Apex-Toolbox-ALR-%s.zip' % version)
expected = {
    path.relative_to(ROOT).as_posix(): path
    for path in ADDON.rglob('*')
    if path.is_file()
    and not any(part in {'__pycache__', 'tests'} for part in path.parts)
    and path.suffix not in {'.pyc', '.pyo', '.blend1', '.blend2'}
}
with zipfile.ZipFile(archive_path) as archive:
    names = archive.namelist()
    assert len(names) == len(set(names)), 'Duplicate ZIP entries'
    assert set(names) == set(expected), 'ZIP manifest differs from add-on tree'
    assert archive.testzip() is None, 'Corrupt ZIP entry'
    for name, source in expected.items():
        assert archive.read(name) == source.read_bytes(), 'Stale ZIP entry: ' + name
    assert not any(name.endswith(('.cast', '.locl', '.rseq')) for name in names)
    assert not any('artifacts/' in name or '/.git/' in name for name in names)

digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
print('VERIFIED:', archive_path.name, archive_path.stat().st_size,
      'bytes,', len(expected), 'files, SHA-256', digest)
