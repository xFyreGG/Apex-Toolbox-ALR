"""Pick one model CAST from each RSX export folder."""

from pathlib import Path
import re


LOD_SUFFIX = re.compile(r"(?:[_-]lod)(\d+)$", re.IGNORECASE)
MAX_BATCH_MODELS = 50


def model_root(folder):
    """Use the RSX mdl directory when a browser returns one of its children."""
    folder = Path(folder)
    return next((path for path in (folder, *folder.parents)
                 if path.name.casefold() == 'mdl'), folder)


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
