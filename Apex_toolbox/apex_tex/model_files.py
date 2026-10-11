"""Pick one model CAST from each RSX export folder."""

from pathlib import Path
import re


LOD_SUFFIX = re.compile(r"(?:[_-]lod)(\d+)$", re.IGNORECASE)
MAX_BATCH_MODELS = 50


LEGEND_NAMES = frozenset({
    'alter', 'ash', 'axle', 'ballistic', 'bangalore', 'bloodhound', 'catalyst', 'caustic',
    'conduit', 'crypto', 'fuse', 'gibraltar', 'horizon', 'lifeline', 'loba',
    'madmaggie', 'mirage', 'newcastle', 'octane', 'pathfinder', 'rampart',
    'revenant', 'seer', 'sparrow', 'valkyrie', 'vantage', 'wattson', 'wraith',
})
WEAPON_PREFIXES = frozenset({
    'alternator', 'bocek', 'car', 'charge', 'devotion', 'eva8', 'flatline', 'g7',
    'havoc', 'heirloom', 'hemlok', 'knife', 'kraber', 'longbow', 'lstar', 'm20',
    'mastiff', 'mozambique', 'nemesis', 'p2011', 'p2020', 'peacekeeper',
    'prowler', 'ptpov', 'r97', 'r99', 'r301', 'rampage', 're45', 'rspn101',
    'sentinel', 'spitfire', 'volt', 'w', 'wingman',
})
HELD_ITEM_WORDS = frozenset({'axe', 'grenade', 'heirloom', 'knife', 'kunai', 'sword'})
GUN_NAMES = WEAPON_PREFIXES - {'heirloom', 'knife', 'm20', 'ptpov', 'w'}
WEAPON_LABELS = {
    'car': 'CAR SMG', 'g7': 'G7 Scout', 'lstar': 'L-STAR', 'r99': 'R-99',
    'r301': 'R-301', 're45': 'RE-45',
}
LEGEND_EXPORT_ALIASES = {
    'dummie': 'dummy', 'holo': 'mirage', 'nova': 'horizon',
    'overdrive': 'axle', 'stim': 'octane',
}
LEGEND_LABELS = {'madmaggie': 'Mad Maggie'}


def _export_name(name):
    """Normalise export names and Blender's duplicate/LOD suffixes."""
    name = str(name).replace('\\', '/').rsplit('/', 1)[-1].casefold()
    name = re.sub(r'\.cast$', '', name)
    name = re.sub(r'\.\d{3,}$', '', name)
    name = LOD_SUFFIX.sub('', name)
    name = re.sub(r'[\s-]+', '_', name)
    return name.replace('mad_maggie', 'madmaggie')


def _canonical_legend(name):
    name = LEGEND_EXPORT_ALIASES.get(name, name)
    return name if name in LEGEND_NAMES else None


def _model_name_legend(name, object_name=False):
    name = _export_name(name)
    words = name.split('_')
    if model_folder_category(name) == 'LEGENDS':
        return model_folder_group(name)
    if object_name:
        # A renamed armature can supply the identity when the export has a
        # generic filename, but a legend's drone/heirloom is not its model.
        if len(words) == 1 or (len(words) == 2 and words[1] in {
                'armature', 'rig', 'skeleton'}):
            return _canonical_legend(words[0])
    return None


def model_legend(model_filepath, object_names=()):
    """Identify a legend model without treating its props as character rigs.

    The CAST filename, immediate model folder and imported object names must
    agree wherever they contain a recognised legend identity. Unknown generic
    filenames can use an armature renamed to the legend's name. A filename or
    folder explicitly describing a weapon or legend prop blocks auto linking.
    """
    path_parts = str(model_filepath or '').replace('\\', '/').rstrip('/').split('/')
    source_names = path_parts[-2:]
    legends = set()
    for source in source_names:
        name = _export_name(source)
        legend = _model_name_legend(name)
        if legend:
            legends.add(legend)
            continue
        words = name.split('_')
        if (model_folder_category(name) == 'WEAPONS'
                or (_canonical_legend(words[0]) and len(words) > 1)):
            return None
    for name in object_names:
        legend = _model_name_legend(name, object_name=True)
        if legend:
            legends.add(legend)
    return next(iter(legends)) if len(legends) == 1 else None


def choose_animation_rig(legend, candidates):
    """Return (CAST path, reason) for one safe matching legend animation rig.

    Candidates use the (folder name, CAST path) pairs from legend_animation_rigs.
    Prefer an unqualified pilot rig over its named variants. Duplicate paths do
    not count twice. Multiple equally suitable rigs are ambiguous, and special
    holo/nova prop rigs are never selected for a legend automatically.
    """
    legend = _canonical_legend(_export_name(legend))
    if legend is None:
        return None, 'unknown_legend'
    matches = {}
    bases = {}
    for name, filepath in candidates:
        name = _export_name(name)
        words = name.split('_')
        if (len(words) < 3 or words[0] != 'pilot'
                or _canonical_legend(words[2]) != legend):
            continue
        identity = str(filepath).replace('\\', '/').casefold()
        matches[identity] = str(filepath)
        if len(words) == 3:
            bases[identity] = str(filepath)
    preferred = bases or matches
    if len(preferred) == 1:
        return next(iter(preferred.values())), 'matched'
    return None, 'ambiguous' if preferred else 'no_match'


def model_folder_category(name):
    """Sort RSX folder names into three exhaustive, non-overlapping views."""
    words = name.casefold().split('_')
    first = words[0]
    if first in WEAPON_PREFIXES or any(word in HELD_ITEM_WORDS for word in words[1:]):
        return 'WEAPONS'
    if first == 'pilot':
        legend = LEGEND_EXPORT_ALIASES.get(words[2], words[2]) if len(words) > 2 else ''
        return 'LEGENDS' if legend in LEGEND_NAMES else 'MISC'
    if (first in LEGEND_NAMES or first in LEGEND_EXPORT_ALIASES) and len(words) > 1:
        skin = words[1]
        if (skin in {'base', 'lgnd', 'mythic'} or re.fullmatch(r'v\d+', skin)):
            return 'LEGENDS'
    return 'MISC'


def model_folder_group(name):
    """Return one useful subfolder choice inside the model's category."""
    words = name.casefold().split('_')
    category = model_folder_category(name)
    if category == 'LEGENDS':
        if words[0] == 'pilot' and len(words) > 2:
            return LEGEND_EXPORT_ALIASES.get(words[2], words[2])
        return LEGEND_EXPORT_ALIASES.get(words[0], words[0])
    if category == 'WEAPONS':
        gun = next((word for word in words if word in GUN_NAMES), None)
        if gun:
            return gun
        if 'heirloom' in words:
            return 'heirlooms'
        if words[0] in {'w', 'ptpov'} and len(words) > 1:
            return words[1]
        return next((word for word in words[1:] if word in HELD_ITEM_WORDS), words[0])
    if words[0] == 'district' and len(words) > 1:
        return 'district_' + words[1]
    return words[0]


def model_group_label(group, category):
    if category == 'WEAPONS':
        return WEAPON_LABELS.get(group, group.replace('_', ' ').title())
    if category == 'LEGENDS':
        return LEGEND_LABELS.get(group, group.replace('_', ' ').title())
    return group.replace('_', ' ').title()


def model_group_options(names, category):
    """Only offer groups that exist in the chosen RSX export folder."""
    counts = {}
    for name in names:
        if model_folder_category(name) == category:
            group = model_folder_group(name)
            counts[group] = counts.get(group, 0) + 1
    return [(group, model_group_label(group, category), counts[group])
            for group in sorted(counts)]


def folder_matches(name, search='', category='LEGENDS', group='NONE'):
    """Search inside one chosen legend, weapon or miscellaneous group."""
    if group == 'NONE':
        return False
    terms = search.casefold().split()
    return (model_folder_category(name) == category
            and model_folder_group(name) == group
            and all(term in name.casefold() for term in terms))


def model_root(folder):
    """Use the RSX mdl directory when a browser returns one of its children."""
    folder = Path(folder)
    return next((path for path in (folder, *folder.parents)
                 if path.name.casefold() == 'mdl'), folder)


def bookmarked_mdl(bookmarks_file):
    """Find an existing RSX mdl bookmark to open the model list immediately."""
    try:
        lines = Path(bookmarks_file).read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError, TypeError):
        return ''
    for line in lines:
        folder = Path(line.strip())
        if folder.name.casefold() == 'mdl' and folder.is_dir():
            return str(folder)
    return ''


def bookmarked_animrig(bookmarks_file):
    """Find an RSX animation-rig export from the user's Blender bookmarks."""
    try:
        lines = Path(bookmarks_file).read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError, TypeError):
        return ''
    for line in lines:
        folder = Path(line.strip())
        if folder.name.casefold() == 'animrig' and folder.is_dir():
            return str(folder)
        candidate = folder / 'animrig'
        if folder.name.casefold() == 'exported_files' and candidate.is_dir():
            return str(candidate)
        candidate = folder.parent / 'animrig'
        if folder.name.casefold() == 'mdl' and candidate.is_dir():
            return str(candidate)
    return ''


def legend_animation_rigs(parent):
    """Legend rig CASTs with their matching RSX sequence folder."""
    root = Path(parent)
    if not root.is_dir():
        return []
    rigs = []
    for folder in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        if not folder.is_dir() or not (folder.name.casefold().startswith('pilot_')
                                      or folder.name.casefold().startswith(('holo_', 'nova_'))):
            continue
        cast = folder / (folder.name + '.cast')
        sequences = folder / ('anims_' + folder.name)
        if cast.is_file() and sequences.is_dir():
            rigs.append((folder.name, str(cast)))
    return rigs


def animation_rig_legend(name):
    """Group a pilot rig under its legend, with unfamiliar rigs kept accessible."""
    words = name.casefold().split('_')
    if words[0] == 'pilot' and len(words) > 2:
        export_name = words[2]
    elif words[0] in {'holo', 'nova'}:
        export_name = words[0]
    else:
        return 'other'
    legend = LEGEND_EXPORT_ALIASES.get(export_name, export_name)
    return legend if legend in LEGEND_NAMES else 'other'


def animation_rig_legend_options(names):
    """Offer only legends with a usable rig in this animrig directory."""
    counts = {}
    for name in names:
        legend = animation_rig_legend(name)
        counts[legend] = counts.get(legend, 0) + 1
    return [(legend, 'Other rigs' if legend == 'other' else model_group_label(legend, 'LEGENDS'),
             counts[legend]) for legend in sorted(counts)]


def animation_rig_matches(name, legend, search=''):
    return (legend != 'NONE' and animation_rig_legend(name) == legend
            and all(term in name.casefold() for term in search.casefold().split()))


def model_cast(folder):
    """Return a folder's model CAST, preferring LOD0 over lower-detail exports."""
    folder = Path(folder)
    files = sorted((path for path in folder.iterdir()
                    if path.is_file() and path.suffix.lower() == '.cast'),
                   key=lambda path: path.name.casefold())
    if not files:
        return None
    lod0 = [path for path in files if (match := LOD_SUFFIX.search(path.stem))
            and int(match.group(1)) == 0]
    if len(lod0) == 1:
        return lod0[0]
    if len(files) == 1:
        return files[0]
    # Multiple model exports with no unique LOD0 are ambiguous. Do not guess.
    raise ValueError('%s has several CAST files and no unique LOD0.' % folder.name)


def batch_model_casts(folders, limit=MAX_BATCH_MODELS):
    """Accept model folders or one parent containing model folders."""
    paths = []
    seen = set()
    for selected in folders:
        folder = Path(selected)
        if not folder.is_dir():
            raise ValueError('Choose model folders, not files: %s' % folder.name)
        direct = model_cast(folder)
        candidates = [direct] if direct else [
            model_cast(child) for child in sorted(folder.iterdir(),
                                                  key=lambda path: path.name.casefold())
            if child.is_dir() and not child.name.lower().startswith('anims_')]
        for path in candidates:
            if path is None:
                continue
            identity = str(path.resolve()).casefold()
            if identity not in seen:
                paths.append(str(path))
                seen.add(identity)
            if len(paths) > limit:
                raise ValueError('More than %d models found. Choose a smaller folder or fewer folders.' % limit)
    if not paths:
        raise ValueError('No model CAST files found in the chosen folders.')
    return paths
