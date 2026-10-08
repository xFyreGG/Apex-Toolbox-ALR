"""Maintainer-only: build the compact name catalogue from local RSX exports.

Only short cosmetic labels, clip identifiers and roles are retained. No raw game
exports or machine-specific paths are included in the distributable catalogue.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Apex_toolbox'))
from apex_tex.animation_names import NameCatalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--localization', required=True, type=Path)
    parser.add_argument('--settings', required=True, type=Path)
    parser.add_argument('--game-build', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'Apex_toolbox/apex_tex/data/animation_names_en.json')
    args = parser.parse_args()
    catalog = NameCatalog()
    for _ in catalog.read(args.localization, str(args.settings)):
        pass
    snapshot = catalog.snapshot(language='English', generated=str(date.today()),
                                game_build=args.game_build, item_settings=catalog.files,
                                description='Cosmetic animation menu labels matched by RSX sequence identifiers')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    counts = {key: {'named': sum(value is not None for value in snapshot[key].values()),
                    'unresolved': sum(value is None for value in snapshot[key].values())}
              for key in ('full', 'short')}
    print(json.dumps(dict(files=catalog.files, bytes=args.output.stat().st_size, entries=counts), indent=2))


if __name__ == '__main__':
    main()
