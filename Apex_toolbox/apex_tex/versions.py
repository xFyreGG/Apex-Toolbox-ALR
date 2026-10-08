"""Numeric version comparisons for release notices; no network dependency."""
import re


def version_key(value):
    match = re.fullmatch(r'[vV]?\.?\s*(\d+(?:\.\d+)*)(.*)', str(value).strip())
    if not match:
        return None
    parts = tuple(int(part) for part in match.group(1).split('.'))
    parts += (0,) * max(0, 3 - len(parts))
    suffix = match.group(2).lower().strip(' -_.')
    if not suffix:
        return parts, 4, 0
    prerelease = re.fullmatch(r'(dev|alpha|a|beta|b|rc)[ ._-]*(\d*)', suffix)
    if prerelease is None:
        return None
    stage = {'dev': 0, 'alpha': 1, 'a': 1, 'beta': 2, 'b': 2, 'rc': 3}[prerelease.group(1)]
    return parts, stage, int(prerelease.group(2) or 0)


def newer_version(candidate, current):
    latest, installed = version_key(candidate), version_key(current)
    return latest is not None and installed is not None and latest > installed
