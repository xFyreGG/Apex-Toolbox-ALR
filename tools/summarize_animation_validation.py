"""Produce a readable local coverage report after the optional real-export tests."""
import argparse
from collections import Counter
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--playback', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding='utf-8'))['libraries']
    playback_report = json.loads(args.playback.read_text(encoding='utf-8'))
    playback = {item['export']: item for item in playback_report['libraries']}
    counts = Counter(item['status'] for item in playback.values())
    samples = sum(len(item['samples']) for item in playback.values())
    lines = ['# Apex Toolbox %s — Experimental animation name validation' % playback_report['version'], '',
             'English names are supplied by the plugin when linking or refreshing a rig. '
             'The playback test never imports a language file or item settings.', '',
             '- Export folders audited: **%d**' % len(audit),
             '- Animation clips indexed: **%s**' % format(sum(len(item['clips']) for item in audit), ','),
             '- Exact named clips: **%s**' % format(sum(item['named'] for item in audit), ','),
             '- Conflicting/unresolved name matches: **%d** (export names retained)' % sum(item['ambiguous'] for item in audit),
             '- Rig libraries with successful sample playback: **%d**' % counts['passed'],
             '- Successful load → rest pose → cached reload samples: **%d**' % samples,
             '- Playback failures: **%d**' % counts['failed'], '',
             'Coverage is limited to the supplied exports. Names were checked for every indexed clip; '
             'playback sampled one named clip per available category (ground emote, skydive, banner and finisher). '
             'A passing sample does not verify every animation in that library.', '',
             '| Export folder | Clips | Named | Playback samples | Result |',
             '| --- | ---: | ---: | ---: | --- |']
    status = {'passed': 'Passed', 'index_only': 'Index only; no named cosmetic clips',
              'unavailable': 'Incomplete export; playback untested', 'failed': 'Failed'}
    notes = []
    for source in audit:
        name = Path(source['folder']).name
        result = playback.get(name)
        verdict = status[result['status']] if result else 'Not tested'
        lines.append('| %s | %d | %d | %d | %s |' % (
            name, len(source['clips']), source['named'], len(result['samples']) if result else 0, verdict))
        for note in [*source['warnings'], *(result['notes'] if result else [])]:
            notes.append('- **%s:** %s' % (name, note))
    lines += ['', '## Incomplete exports and notes', '', *notes, '',
              'The source exports and the user’s working Blender scene were not modified. '
              'Tests ran in separate factory-startup Blender 4.2.2 processes.', '']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(dict(statuses=dict(counts), samples=samples), indent=2))


if __name__ == '__main__':
    main()
