"""Read every available legend export, including folders missing the rig CAST.

Reports remain local; source CAST files are never changed. This validates names
and indexing, not playback. Use tests/real_animation_libraries.py for playback.
"""
import argparse
import csv
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Apex_toolbox'))
from apex_tex import animation_names, cast_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    catalog = animation_names.bundled_catalog()
    report = {'libraries': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for folder in sorted(args.root.glob('pilot_*')):
        if not folder.is_dir():
            continue
        started = time.monotonic()
        entry = dict(folder=str(folder), rig_files=[str(p) for p in folder.glob('*.cast')],
                     clips=[], warnings=[])
        for sequences in sorted(folder.glob('anims_*')):
            files, warnings = cast_index.animation_files(sequences)
            entry['warnings'].extend(warnings)
            for path in files:
                try:
                    for node in cast_index.nodes_of(cast_index.read_cast(path), b'anim'):
                        sequence_hash = next((child.guid for child in node.children if child.kind == b'skel'), 0)
                        name, role, ambiguous = catalog.match(node.guid, sequence_hash)
                        entry['clips'].append(dict(file=str(path), offset=node.offset,
                            name=node.properties.get('n') or path.stem, guid=format(node.guid, 'x'),
                            sequence_hash=format(sequence_hash, 'x'), menu_name=name, menu_role=role,
                            ambiguous=ambiguous, fps=node.properties.get('fr') or 30.0,
                            additive=any(n.properties.get('m') == 'additive'
                                         for n in node.children if n.kind == b'curv')))
                except (OSError, UnicodeError, ValueError) as error:
                    entry['warnings'].append('%s: %s' % (path.name, error))
        entry['named'] = sum(bool(clip['menu_name']) for clip in entry['clips'])
        entry['ambiguous'] = sum(clip['ambiguous'] for clip in entry['clips'])
        entry['seconds'] = round(time.monotonic() - started, 2)
        report['libraries'].append(entry)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('%s: %d clips, %d named, %d ambiguous, %d warnings; %s (%.1fs)' % (
            folder.name, len(entry['clips']), entry['named'], entry['ambiguous'], len(entry['warnings']),
            'rig present' if entry['rig_files'] else 'RIG FILE MISSING', entry['seconds']), flush=True)
    with args.output.with_suffix('.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('Export', 'Rig present', 'Clips', 'Named', 'Ambiguous', 'Warnings'))
        for entry in report['libraries']:
            writer.writerow((Path(entry['folder']).name, bool(entry['rig_files']), len(entry['clips']),
                             entry['named'], entry['ambiguous'], len(entry['warnings'])))
    print('AUDIT COMPLETE', flush=True)


if __name__ == '__main__':
    main()
