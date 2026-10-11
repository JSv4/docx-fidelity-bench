"""Build the separately provisioned renderer and bind its artifacts to source."""
from pathlib import Path
import re
import subprocess
from .common import digest, execute, write_json


def docxodus(source, commit):
    source = Path(source).resolve()
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Candidate must be a full commit SHA')
    actual = execute(['git', '-C', source, 'rev-parse', 'HEAD']).strip()
    if actual != commit or execute(['git', '-C', source, 'status', '--porcelain', '--untracked-files=no']).strip():
        raise ValueError('Renderer source must be clean at the requested commit')
    commands = [['npm', '--prefix', str(source / 'npm'), 'ci'], ['npm', '--prefix', str(source / 'npm'), 'run', 'build:wasm']]
    commands += [['npm', '--prefix', str(source / 'npm'), 'run', name] for name in ('build:ts', 'build:pagination-bundle', 'build:worker-bundle', 'build:export-browser', 'build:export-assets')]
    commands += [['npm', '--prefix', str(source / 'npm-export'), 'ci'], ['npm', '--prefix', str(source / 'npm-export'), 'run', 'build']]
    record_path = source / '.docx-bench-build.json'
    record_path.unlink(missing_ok=True)
    for command in commands:
        print('Building: ' + ' '.join(command), flush=True)
        subprocess.run(command, check=True, timeout=1800)
    files = ['npm/package-lock.json', 'npm-export/package-lock.json', 'npm/dist/export-assets.json', 'npm-export/dist/index.js']
    files += [str(path.relative_to(source)) for path in sorted((source / 'npm-export/dist').rglob('*.js')) if str(path.relative_to(source)) not in files]
    write_json(record_path, {'schema': 1, 'commit': commit, 'tree': execute(['git', '-C', source, 'rev-parse', 'HEAD^{tree}']).strip(), 'recipeSha256': digest(Path(__file__)), 'node': execute(['node', '--version']).strip(), 'commands': commands, 'files': {name: digest(source / name) for name in files}})
    print('Recorded source-bound build identity: ' + str(record_path), flush=True)
