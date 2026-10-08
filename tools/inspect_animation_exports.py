"""Read-only CAST metadata inspection; writes a report, never changes exports."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Apex_toolbox'))
from apex_tex import animation_names, cast_index

parser = argparse.ArgumentParser()
parser.add_argument('--rig', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--names', type=Path, help='Optional RSX localization export beside settings/itemflav')
args = parser.parse_args()
started = time.monotonic()
roots = cast_index.read_cast(args.rig)
bones = cast_index.nodes_of(roots, b'bone')
files, warnings = cast_index.animation_files(args.rig.parent / ('anims_' + args.rig.stem))
catalog = animation_names.NameCatalog()
if args.names:
    for _ in catalog.read(args.names):
        pass
clips = []
for path in files:
    try:
        for clip in cast_index.nodes_of(cast_index.read_cast(path), b'anim'):
            sequence_hash = next((node.guid for node in clip.children if node.kind == b'skel'), 0)
            name, role, ambiguous = catalog.match(clip.guid, sequence_hash)
            clips.append({'file': path.name, 'name': clip.properties.get('n'),
                          'offset': clip.offset, 'fps': clip.properties.get('fr'),
                          'bytes': clip.byte_size, 'menu_name': name, 'menu_role': role,
                          'ambiguous_name': ambiguous})
    except (OSError, ValueError, UnicodeError) as error:
        warnings.append('%s: %s' % (path.name, error))
report = {'rig': str(args.rig), 'bones': len(bones), 'files': len(files),
          'clips': len(clips), 'seconds': round(time.monotonic() - started, 3),
          'warnings': warnings, 'named_clips': sum(bool(clip['menu_name']) for clip in clips),
          'animations': clips}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'animations'}, indent=2))
for word in ('gladcard', 'ground_emote', 'freefall_emote', 'lobby', 'execution'):
    matching = [clip for clip in clips if word in (clip['name'] or clip['file']).casefold()]
    print(word, len(matching), json.dumps(matching[:3]))
