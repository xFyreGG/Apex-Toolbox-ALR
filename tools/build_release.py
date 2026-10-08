"""Build the installable Lite ZIP from source, excluding caches and tests."""
import ast
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'Apex_toolbox'


def release_version():
    tree = ast.parse((ADDON / '__init__.py').read_text(encoding='utf-8'))
    info = next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'bl_info'
                        for target in node.targets))
    return tuple(info['version'])


def build_release():
    version = '.'.join(map(str, release_version()))
    output = ROOT / 'dist' / ('Apex-Toolbox-ALR-%s.zip' % version)
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ADDON.rglob('*')):
            if not path.is_file() or any(part in {'__pycache__', 'tests'} for part in path.parts):
                continue
            if path.suffix in {'.pyc', '.pyo', '.blend1', '.blend2'}:
                continue
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        required = ['Apex_toolbox/__init__.py', 'Apex_toolbox/ApexShader.blend',
                    'Apex_toolbox/LICENSE', 'Apex_toolbox/apex_tex/health.py',
                    'Apex_toolbox/apex_tex/cast_index.py', 'Apex_toolbox/apex_tex/workflows.py',
                    'Apex_toolbox/apex_tex/animations.py', 'Apex_toolbox/apex_tex/animation_names.py',
                    'Apex_toolbox/apex_tex/data/animation_names_en.json']
        for name in required:
            assert name in archive.namelist(), name
        assert archive.testzip() is None
    print(output)
    return output


if __name__ == '__main__':
    build_release()
