"""Build the redline-track adapter and validator, and bind each build to its sources.

The candidate adapter is compiled against a separately provisioned, clean Docxodus checkout at an
exact commit. Every build writes a record of its source identity and artifact digests; a run
re-verifies the record before each invocation.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .common import ROOT, contained, digest, execute, read_json, write_json

ADAPTER_SOURCES = ['adapters/docxodus-redline/DocxBenchRedline.csproj', 'adapters/docxodus-redline/Program.cs']
VALIDATOR_SOURCES = ['tools/ooxml-validator/OoxmlValidator.csproj', 'tools/ooxml-validator/Program.cs']


def dotnet():
    return shutil.which('dotnet') or str(Path.home() / '.dotnet' / 'dotnet')


def _clean(source, commit):
    """The checkout is at `commit` with no tracked change and no untracked file in the compiled project."""
    return (execute(['git', '-C', source, 'rev-parse', 'HEAD']).strip() == commit
            and not execute(['git', '-C', source, 'status', '--porcelain', '--untracked-files=no']).strip()
            and not execute(['git', '-C', source, 'status', '--porcelain', '--untracked-files=all', '--', 'Docxodus']).strip())


def _build(sources, out, project, properties):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Build output already exists: ' + str(out))
    src = out / 'src'
    src.mkdir(parents=True)
    for name in sources:
        shutil.copyfile(ROOT / name, src / Path(name).name)
    command = [dotnet(), 'build', str(src / project), '-c', 'Release', '-o', str(out / 'bin'), '-nologo', '-v', 'q'] + [f'-p:{k}={v}' for k, v in properties.items()]
    print('Building: ' + ' '.join(command), flush=True)
    subprocess.run(command, check=True, timeout=1800)
    files = {str(path.relative_to(out)): digest(path) for path in sorted((out / 'bin').glob('*.dll'))}
    return out, command, files


def build_docxodus(source, commit, out):
    source = Path(source).resolve()
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Candidate must be a full commit SHA')
    if not _clean(source, commit):
        raise ValueError('Docxodus source must be clean at the requested commit, with no untracked files in Docxodus/')
    out, command, files = _build(ADAPTER_SOURCES, out, 'DocxBenchRedline.csproj', {'DocxodusRoot': source})
    record = {'schema': 1, 'commit': commit, 'tree': execute(['git', '-C', source, 'rev-parse', 'HEAD^{tree}']).strip(),
              'source': str(source), 'adapterSources': {name: digest(ROOT / name) for name in ADAPTER_SOURCES},
              'recipeSha256': digest(Path(__file__)), 'dotnet': execute([dotnet(), '--version']).strip(), 'command': command, 'files': files}
    write_json(out / 'redline-build.json', record)
    print('Recorded source-bound redline adapter build: ' + str(out / 'redline-build.json'), flush=True)
    return record


def build_validator(out):
    out, command, files = _build(VALIDATOR_SOURCES, out, 'OoxmlValidator.csproj', {})
    record = {'schema': 1, 'sources': {name: digest(ROOT / name) for name in VALIDATOR_SOURCES}, 'package': 'DocumentFormat.OpenXml 3.5.1',
              'fileFormat': 'Microsoft365', 'dotnet': execute([dotnet(), '--version']).strip(), 'command': command, 'files': files}
    write_json(out / 'validator-build.json', record)
    print('Recorded validator build: ' + str(out / 'validator-build.json'), flush=True)
    return record


def _verify_files(folder, record):
    for name, value in record['files'].items():
        if digest(contained(folder, name)) != value:
            raise ValueError('Build artifact digest mismatch: ' + name)


def verify_validator(folder):
    folder = Path(folder).resolve()
    record = read_json(folder / 'validator-build.json')
    if record.get('schema') != 1 or record['sources'] != {name: digest(ROOT / name) for name in VALIDATOR_SOURCES}:
        raise ValueError('Validator build is stale; rebuild it')
    _verify_files(folder, record)
    return {'package': record['package'], 'fileFormat': record['fileFormat'], 'dotnet': record['dotnet'], 'files': record['files']}


def verify_docxodus(folder, candidate):
    folder = Path(folder).resolve()
    record = read_json(folder / 'redline-build.json')
    source = record['source']
    if record.get('schema') != 1 or record['commit'] != candidate:
        raise ValueError('Redline adapter build does not match the requested candidate')
    if not _clean(source, candidate):
        raise ValueError('Candidate source checkout moved or is dirty')
    if execute(['git', '-C', source, 'rev-parse', 'HEAD^{tree}']).strip() != record['tree']:
        raise ValueError('Candidate source tree changed')
    if record['adapterSources'] != {name: digest(ROOT / name) for name in ADAPTER_SOURCES} or record['recipeSha256'] != digest(Path(__file__)):
        raise ValueError('Redline adapter sources or build recipe changed; rebuild the adapter')
    _verify_files(folder, record)
    return record


def validate_packages(folder, paths):
    """Validator findings for each path. The validator only ever sees temporary copies, so it can
    never rewrite a fixture or a candidate output; a copy it changes still fails the run."""
    with tempfile.TemporaryDirectory() as temp:
        copies = {}
        for index, path in enumerate(paths):
            copy = Path(temp) / str(index) / Path(path).name
            copy.parent.mkdir()
            shutil.copyfile(path, copy)
            copies[str(copy)] = (str(path), digest(copy))
        output = execute([dotnet(), str(Path(folder).resolve() / 'bin' / 'OoxmlValidator.dll')] + list(copies), timeout=300)
        if any(digest(copy) != value for copy, (_, value) in copies.items()):
            raise ValueError('The validator modified a package it was given')
        documents = json.loads(output)['documents']
        return {original: documents[copy] for copy, (original, _) in copies.items()}
