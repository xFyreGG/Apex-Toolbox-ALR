"""Optional on-disk CAST metadata index, independent of Blender and user state.

The caller discovers files and validates the exported rig as usual. For every
file, call lookup before parsing, record a cache miss, then finish only when the
whole scan succeeds. A force scan still records new metadata but reuses none.
"""
from dataclasses import asdict, is_dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile


SCHEMA = 1
# Change this when the CAST reader or clip metadata interpretation changes.
READER_VERSION = 1
MAX_CACHE_BYTES = 64 * 1024 * 1024
MAX_FILES = 250000
MAX_CLIPS_PER_FILE = 200000
MAX_WARNINGS_PER_FILE = 4096


def _key(path):
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def _fingerprint(path):
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Animation cache expects a regular file.')
    return [info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_dev, info.st_ino]


def file_fingerprint(path):
    """A cheap identity check before parsing and before committing a scan."""
    try:
        return _fingerprint(path)
    except (OSError, ValueError):
        return None


def _entries(values):
    """Validate saved offsets and metadata without trusting saved source paths."""
    if not isinstance(values, (list, tuple)) or len(values) > MAX_CLIPS_PER_FILE:
        raise ValueError('Invalid cached animation list.')
    result = []
    for value in values:
        if is_dataclass(value):
            value = asdict(value)
        if not isinstance(value, dict):
            raise ValueError('Invalid cached animation.')
        offset = value.get('offset')
        name = value.get('name')
        fps = value.get('fps')
        additive = value.get('additive')
        guid = value.get('guid', '')
        sequence_hash = value.get('sequence_hash', '')
        external = value.get('external', False)
        if (type(offset) is not int or offset < 16
                or not isinstance(name, str) or not name or len(name) > 65536
                or type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0
                or type(additive) is not bool or type(external) is not bool
                or not isinstance(guid, str) or len(guid) > 16
                or not isinstance(sequence_hash, str) or len(sequence_hash) > 16
                or any(char not in '0123456789abcdefABCDEF' for char in guid + sequence_hash)):
            raise ValueError('Invalid cached animation metadata.')
        result.append({'offset': offset, 'name': name, 'fps': fps,
                       'additive': additive, 'guid': guid,
                       'sequence_hash': sequence_hash, 'external': external})
    return result


def _warnings(values):
    if (not isinstance(values, (list, tuple)) or len(values) > MAX_WARNINGS_PER_FILE
            or any(not isinstance(item, str) or len(item) > 131072 for item in values)):
        raise ValueError('Invalid cached warnings.')
    return list(values)


class Index:
    """Reuse unchanged files and atomically replace one rig's completed index.

    ``cache_root`` is supplied by Blender's user data directory. Passing None
    disables caching. lookup returns (clip dictionaries, warning strings), or
    None. record accepts Clip dataclasses or dictionaries and returns success.
    Read/write errors disable persistence without affecting animation imports.
    """
    def __init__(self, rig_path, cache_root, force=False):
        self.hits = 0
        self.misses = 0
        self._known = {}
        self._next = {}
        self._fingerprints = {}
        self.path = None
        self._rig_key = ''
        self._rig_fingerprint = None
        try:
            self._rig_key = _key(rig_path)
            self._rig_fingerprint = _fingerprint(self._rig_key)
            if cache_root is None:
                return
            name = hashlib.sha256(self._rig_key.encode('utf-8')).hexdigest() + '.json'
            self.path = Path(cache_root) / name
            if force:
                return
            with self.path.open('rb') as source:
                data = source.read(MAX_CACHE_BYTES + 1)
            if len(data) > MAX_CACHE_BYTES:
                return
            saved = json.loads(data)
            if (not isinstance(saved, dict) or saved.get('schema') != SCHEMA
                    or saved.get('reader') != READER_VERSION
                    or saved.get('rig') != self._rig_key
                    or saved.get('fingerprint') != self._rig_fingerprint):
                return
            files = saved.get('files')
            if isinstance(files, dict) and len(files) <= MAX_FILES:
                self._known = files
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            # A missing, corrupt, or unwritable cache must never block a scan.
            pass

    def lookup(self, path):
        try:
            key = _key(path)
            fingerprint = _fingerprint(path)
            self._fingerprints[key] = fingerprint
            saved = self._known.get(key)
            if isinstance(saved, dict) and saved.get('fingerprint') == fingerprint:
                entries = _entries(saved.get('entries'))
                if any(item['offset'] >= fingerprint[0] for item in entries):
                    raise ValueError('Cached animation offset is outside the source file.')
                warnings = _warnings(saved.get('warnings', []))
                self._next[key] = {'fingerprint': fingerprint,
                                   'entries': entries, 'warnings': warnings}
                self.hits += 1
                return ([dict(item, filepath=str(path)) for item in entries], list(warnings))
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            pass
        self.misses += 1
        return None

    def record(self, path, entries, warnings=()):
        try:
            key = _key(path)
            fingerprint = _fingerprint(path)
            # Do not save offsets if an export changed while it was parsed.
            if fingerprint != self._fingerprints.get(key, fingerprint):
                self._next.pop(key, None)
                return False
            values = _entries(entries)
            if any(item['offset'] >= fingerprint[0] for item in values):
                return False
            self._next[key] = {'fingerprint': fingerprint, 'entries': values,
                               'warnings': _warnings(warnings)}
            return True
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            return False

    def finish(self):
        """Save only files visited by this completed scan, pruning deleted files."""
        temporary = None
        try:
            if (self.path is None or len(self._next) > MAX_FILES
                    or _fingerprint(self._rig_key) != self._rig_fingerprint):
                return False
            saved = {'schema': SCHEMA, 'reader': READER_VERSION,
                     'rig': self._rig_key, 'fingerprint': self._rig_fingerprint,
                     'files': self._next}
            data = json.dumps(saved, ensure_ascii=True, separators=(',', ':'),
                              allow_nan=False).encode('utf-8')
            if len(data) > MAX_CACHE_BYTES:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=self.path.stem + '.',
                                             suffix='.tmp', delete=False) as target:
                temporary = target.name
                target.write(data)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.path)
            temporary = None
            return True
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            return False
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
