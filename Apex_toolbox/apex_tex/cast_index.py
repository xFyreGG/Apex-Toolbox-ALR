"""Bounded CAST metadata reader; skips mesh/key buffers instead of decoding them.

Layout follows dtzxporter/cast's public file format. This is only an index and
preflight validator; the user's installed CAST add-on still imports the data.
"""
from dataclasses import dataclass, field
import os
import mmap
from pathlib import Path
import struct
import stat


@dataclass
class Node:
    kind: bytes
    offset: int
    properties: dict
    children: list = field(default_factory=list)
    byte_size: int = 0
    guid: int = 0

    def descendants(self, kind):
        for child in self.children:
            if child.kind == kind:
                yield child
            yield from child.descendants(kind)


def read_cast(path):
    """Synchronous preflight used before importing a model or clip."""
    for result in iter_cast(path):
        pass
    return result


def iter_cast(path):
    """Validate lengths, counts and strings before handing a file to CAST.

    The upstream decoder reads strings until NUL, so truncated strings must
    be rejected here. Limits also keep a bad export from exhausting memory.
    """
    size = os.path.getsize(path)
    budget = [200000]
    if size < 16:
        raise ValueError('Truncated CAST header. Re-export this file from RSX.')
    with open(path, 'rb') as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as stream:
        def read(count, end):
            if count < 0 or stream.tell() + count > end:
                raise ValueError('Truncated CAST data. Re-export this file from RSX.')
            data = stream.read(count)
            if len(data) != count:
                raise ValueError('Incomplete CAST file.')
            return data

        def node(end, depth=0):
            budget[0] -= 1
            if budget[0] < 0 or depth > 64:
                raise ValueError('CAST file exceeds the metadata limits.')
            offset = stream.tell()
            kind, length, guid, prop_count, child_count = struct.unpack('<4sIQII', read(24, end))
            node_end = offset + length
            if length < 24 or node_end > end or prop_count > 4096 or child_count > budget[0]:
                raise ValueError('Invalid CAST node size or count.')
            props = {}
            for _ in range(prop_count):
                value_type, name_size, count = struct.unpack('<2sHI', read(8, node_end))
                name = read(name_size, node_end).decode('utf-8')
                value_type = value_type.rstrip(b'\0')
                value = None
                if value_type == b's':
                    if count != 1:
                        raise ValueError('Invalid CAST string count.')
                    # Search the mapped bytes without repeatedly reading ahead
                    # and seeking backwards through every curve's key buffers.
                    start = stream.tell()
                    terminator = stream.find(b'\0', start, min(start + 65536, node_end))
                    if terminator < 0:
                        raise ValueError('Unterminated or oversized CAST string.')
                    value = stream[start:terminator].decode('utf-8')
                    stream.seek(terminator + 1)
                else:
                    widths = {b'b': 1, b'h': 2, b'i': 4, b'l': 8, b'f': 4,
                              b'd': 8, b'2v': 8, b'3v': 12, b'4v': 16}
                    if value_type not in widths:
                        raise ValueError('Unsupported CAST property type.')
                    length = widths[value_type] * count
                    if stream.tell() + length > node_end:
                        raise ValueError('Truncated CAST property buffer.')
                    if count == 1 and value_type in (b'f', b'b', b'i'):
                        value = struct.unpack({b'f': '<f', b'b': '<B', b'i': '<I'}[value_type],
                                              read(length, node_end))[0]
                    else:
                        stream.seek(length, 1)
                # Only metadata used by the browser is retained.
                if name in {'n', 'nn', 'kp', 'm', 'fr', 'lo'}:
                    props[name] = value
                yield None  # Allow the UI to yield even inside a large node.
            children = []
            for _ in range(child_count):
                children.append((yield from node(node_end, depth + 1)))
            if stream.tell() != node_end:
                raise ValueError('CAST node length does not match its contents.')
            yield None
            return Node(kind, offset, props, children, node_end - offset, guid)

        magic, version, roots, _ = struct.unpack('<4sIII', read(16, size))
        if magic != b'cast' or version != 1 or roots > 4096:
            raise ValueError('Select a CAST export from RSX (version 1).')
        result = []
        for _ in range(roots):
            result.append((yield from node(size)))
        if stream.tell() != size:
            raise ValueError('Unexpected data after the CAST file.')
        yield result


def nodes_of(roots, kind):
    return [node for root in roots for node in root.descendants(kind)]


def animation_files(folder):
    """Discover all CAST files; the UI uses the incremental variant below."""
    files, warnings = [], []
    for entry in iter_animation_files(folder):
        if isinstance(entry, Path):
            files.append(entry)
        elif isinstance(entry, str):
            warnings.append(entry)
    return sorted(files), warnings


def iter_animation_files(folder):
    """Yield paths, warnings and checkpoints without file-count/depth cutoffs.

    Symlinks and junctions are skipped to keep discovery inside the export.
    Real-path deduplication also prevents cycles on older Python versions.
    """
    pending = [Path(folder)]
    visited = set()
    while pending:
        directory = pending.pop()
        try:
            real = os.path.normcase(os.path.realpath(directory))
            if real in visited:
                continue
            visited.add(real)
            with os.scandir(directory) as scan:
                for entry in scan:
                    try:
                        reparse = (os.name == 'nt' and getattr(entry.stat(follow_symlinks=False),
                                   'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
                        if entry.is_symlink() or reparse:
                            yield 'Linked folder or file skipped: %s' % entry.path
                        elif entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                        elif entry.name.lower().endswith('.cast') and entry.is_file(follow_symlinks=False):
                            yield Path(entry.path)
                    except OSError as error:
                        yield '%s: %s' % (entry.path, error)
                    yield None
        except OSError as error:
            yield str(error)
