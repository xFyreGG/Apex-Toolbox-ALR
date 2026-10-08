"""Exact menu-name lookup, with a compact bundled English catalogue.

RSX writes the sequence GUID on CAST animation nodes and a hash of the short
sequence name on their skeleton nodes. These match item-flavour references;
filenames are never used to guess a menu name. The catalogue contains only short
menu labels and matching identifiers; raw settings, language packs and clips
are not distributed. User RSX exports can override names for another language.
Format references: r-ex/rsx's Localization.md, settings.cpp, itemflav_window.cpp
and ExportSeqDescCast in src/core/mdl/modeldata.cpp.
"""
import json
import os
from pathlib import Path
import re
import stat
from functools import lru_cache


CATALOG_PATH = Path(__file__).with_name('data') / 'animation_names_en.json'


def string_guid(text):
    """RTech's case/slash-insensitive 64-bit string identifier."""
    data = text.replace('\\', '/').encode('utf-8') + bytes(4)
    mask = (1 << 64) - 1
    state = 0
    for offset in range(0, len(data), 4):
        word = int.from_bytes(data[offset:offset + 4], 'little')
        zero = ~word & (word - 0x01010101) & 0x80808080
        valid = (zero ^ (zero - 1)) & 0xffffffff
        product = (state * 0x633D5F1) & mask
        term = ((0xFB8C4D96501 * (word & valid & 0xDFDFDFDF)) & mask) >> 24
        if zero:
            length = offset + (valid.bit_length() - 1) // 8
            return (product + term - 0xAE502812AA7333 * length) & mask
        state = (product + term) & mask
        state ^= state >> 61


# Only character animation references, excluding lights, effects and victims.
ITEM_FIELDS = {
    'character_emote': {'anim3p': '', 'anim3pLoop': 'Loop'},
    'character_execution': {'attackerAnimSeq': '', 'attackerPreviewAnimSeq': 'Preview'},
    'gladiator_card_stance': {'stillAnimSeq': 'Still', 'movingAnimSeq': 'Animated'},
    'skydive_emote': {'animSequence': ''},
}
ITEM_FOLDERS = ('character_emote', 'character_execution', 'gcard_stance', 'skydive_emote')
QUOTED = r'"(?:[^"\\]|\\.)*"'
PAIR = re.compile(r'\s*("[0-9a-fA-F]{1,16}")\s+(' + QUOTED + r')\s*')


def read_settings(path):
    """RSX writes // offset comments in settings with mod-value overrides."""
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Oversized animation item settings: %s' % path.name)
    text = path.read_text(encoding='utf-8-sig')
    text = re.sub(QUOTED + r'|//[^\r\n]*',
                  lambda match: match[0] if match[0].startswith('"') else '', text)
    try:
        document = json.loads(text)
    except ValueError as error:
        raise ValueError('Invalid RSX item settings %s: %s' % (path.name, error)) from error
    if not isinstance(document, dict) or not isinstance(document.get('settings'), dict):
        raise ValueError('Invalid RSX item settings: %s' % path.name)
    return document['settings']


def iter_localization(path, strings):
    """Read RSX's flat KeyValues map incrementally, rejecting partial exports."""
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Language export exceeds 64 MB. Choose an RSX localization .locl file.')
    stage = 0
    with path.open(encoding='utf-8-sig') as stream:
        for number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            if len(line) > 1024 * 1024:
                raise ValueError('Language export contains an oversized entry.')
            if stage == 0 and re.fullmatch(QUOTED, line):
                stage = 1
            elif stage == 1 and line == '{':
                stage = 2
            elif stage == 2 and line == '}':
                stage = 3
            elif stage == 2 and (match := PAIR.fullmatch(line)):
                key = int(match[1][1:-1], 16)
                value = json.loads(match[2])
                if key in strings and strings[key] != value:
                    raise ValueError('Language export contains conflicting names for one identifier.')
                strings[key] = value
            else:
                raise ValueError('Invalid RSX language export at line %d.' % number)
            if number % 128 == 0:
                yield
    if stage != 3 or not strings:
        raise ValueError('The language export is empty or incomplete. Export it again with RSX.')


def itemflav_folder(localization, settings_folder=''):
    if settings_folder:
        base = Path(settings_folder)
        candidates = (base / 'settings' / 'itemflav', base / 'itemflav', base)
    else:
        # RSX's normal layout: exported_files/localization/*.locl with
        # exported_files/settings/itemflav/<type>/<legend>/*.json beside it.
        candidates = (localization.parent.parent / 'settings' / 'itemflav',
                      localization.parent / 'settings' / 'itemflav')
    for candidate in candidates:
        if any((candidate / name).is_dir() for name in ITEM_FOLDERS):
            return candidate
    raise ValueError('Item settings were not found. Export the animation item settings with RSX, '
                     'or choose their export folder in the file picker.')


def iter_settings(folder):
    """Walk only animation item folders. Linked/unreadable data fails the import.

    Skipping unreadable metadata could conceal a conflicting name, so callers
    must retain the previous complete name map if this scan fails.
    """
    pending = [folder / name for name in ITEM_FOLDERS if (folder / name).exists()]
    while pending:
        directory = pending.pop()
        info = directory.lstat()
        if directory.is_symlink() or (getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError('Use a local export folder without linked item folders.')
        with os.scandir(directory) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or (getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                    raise ValueError('Use a local export folder without linked item files or folders.')
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith('.json'):
                    yield Path(entry.path)
                yield None


class NameCatalog:
    def __init__(self):
        self.full = {}
        self.short = {}
        self.files = 0
        self.missing_text = 0
        self.status = 'Reading exported language text…'

    def read(self, localization, settings_folder=''):
        strings = {}
        yield from iter_localization(localization, strings)
        folder = itemflav_folder(localization, settings_folder)
        for path in iter_settings(folder):
            if path is not None:
                self.add_item(read_settings(path), strings)
                self.files += 1
                self.status = 'Reading animation item settings: %d files…' % self.files
            yield
        if not self.files:
            raise ValueError('No animation item settings JSON files were found.')

    def add_item(self, settings, strings):
        fields = ITEM_FIELDS.get(settings.get('itemType'), {})
        if not fields:
            return
        token = settings.get('localizationKey_NAME', '')
        name = strings.get(string_guid(token.lstrip('#'))) if isinstance(token, str) and token else None
        # Missing text is also a competing candidate: never pick another item's
        # name merely because that other item's localization happened to exist.
        if not name:
            self.missing_text += 1
        for field, role in fields.items():
            reference = settings.get(field)
            if not isinstance(reference, str) or not reference:
                continue
            full = reference.lower().replace('\\', '/').startswith('animseq/')
            mapping = self.full if full else self.short
            mapping.setdefault(string_guid(reference), set()).add((name, role))

    def match(self, guid, sequence_hash):
        candidates = self.full.get(guid, set()) | self.short.get(sequence_hash, set())
        if not candidates:
            return '', '', False
        names = {name for name, _ in candidates}
        if len(names) != 1 or None in names or '' in names:
            return '', '', True
        name = next(iter(names))
        roles = {role for _, role in candidates}
        return name, next(iter(roles)) if len(roles) == 1 else '', False

    def snapshot(self, **metadata):
        def compact(mapping):
            result = {}
            for guid, candidates in sorted(mapping.items()):
                names = {name for name, _ in candidates}
                if len(names) != 1 or None in names or '' in names:
                    result[format(guid, '016x')] = None
                else:
                    roles = {role for _, role in candidates}
                    result[format(guid, '016x')] = [next(iter(names)), next(iter(roles)) if len(roles) == 1 else '']
            return result
        return dict(schema=1, metadata=metadata, full=compact(self.full), short=compact(self.short))

    @classmethod
    def from_snapshot(cls, document):
        if not isinstance(document, dict) or document.get('schema') != 1:
            raise ValueError('Unsupported animation name catalogue.')
        catalog = cls()
        for field in ('full', 'short'):
            values = document.get(field)
            if not isinstance(values, dict) or len(values) > 20000:
                raise ValueError('Invalid animation name catalogue entries.')
            for key, value in values.items():
                if not isinstance(key, str) or not re.fullmatch('[0-9a-fA-F]{1,16}', key):
                    raise ValueError('Invalid animation name identifier.')
                if value is None:
                    candidate = (None, '')  # Retain known conflicts when combining hash namespaces.
                elif (isinstance(value, list) and len(value) == 2 and
                      isinstance(value[0], str) and 0 < len(value[0]) <= 256 and
                      isinstance(value[1], str) and
                      value[1] in {'', 'Loop', 'Preview', 'Still', 'Animated'}):
                    candidate = tuple(value)
                else:
                    raise ValueError('Invalid animation name label.')
                getattr(catalog, field)[int(key, 16)] = {candidate}
        return catalog


@lru_cache(maxsize=1)
def bundled_catalog():
    """Read on first use, never on add-on activation; no network or game access."""
    if CATALOG_PATH.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('The bundled animation name catalogue is oversized.')
    with CATALOG_PATH.open(encoding='utf-8') as stream:
        return NameCatalog.from_snapshot(json.load(stream))
