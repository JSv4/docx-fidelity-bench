"""Run exact public Project/ProjectAnchor diagnostics against a source-bound native build."""
import argparse
import json
import re
from pathlib import Path
from .common import ROOT, digest, execute, read_json, write_json
from .projection_fixtures import validate
from .redline_build import _build, _clean, _verify_files, dotnet

SOURCES = ['adapters/docxodus-projection/DocxBenchProjection.csproj', 'adapters/docxodus-projection/Program.cs']


def normalize(markdown):
    return ' '.join(re.sub(r'\{#[^}\n]+\}', '', markdown).split())


def checks(case, observation):
    return {'schema': observation['errors'] == [],
            'completeText': normalize(observation['markdown']) == case['expected'],
            'paragraphAnchors': all(any(p['text'] == text and normalize(p['markdown']) == text
                                       for p in observation['paragraphs']) for text in case['anchored'])}


def build(source, commit, out):
    source = Path(source).resolve()
    if not re.fullmatch('[0-9a-f]{40}', commit) or not _clean(source, commit):
        raise ValueError('Source must be clean at the full requested commit')
    out, command, files = _build(SOURCES, out, 'DocxBenchProjection.csproj', {'DocxodusRoot': source})
    record = {'schema': 1, 'source': str(source), 'commit': commit,
              'tree': execute(['git', '-C', source, 'rev-parse', 'HEAD^{tree}']).strip(),
              'adapterSources': {p: digest(ROOT / p) for p in SOURCES},
              'recipeSha256': digest(Path(__file__)), 'dotnet': execute([dotnet(), '--version']).strip(),
              'command': command, 'files': files}
    write_json(out / 'projection-build.json', record)


def run(build_dir, output):
    folder = Path(build_dir).resolve()
    record = read_json(folder / 'projection-build.json')
    if (record['schema'] != 1 or not _clean(Path(record['source']), record['commit'])
            or record['adapterSources'] != {p: digest(ROOT / p) for p in SOURCES}
            or record['recipeSha256'] != digest(Path(__file__))):
        raise ValueError('Projection build identity changed')
    _verify_files(folder, record)
    manifest = validate()
    observations = json.loads(execute([dotnet(), folder / 'bin/DocxBenchProjection.dll'] +
                                     [ROOT / c['input'] for c in manifest['cases']], timeout=300))
    if len(observations) != len(manifest['cases']):
        raise ValueError('Missing projection observations')
    results = []
    for case, observed in zip(manifest['cases'], observations):
        if Path(observed['path']).resolve() != (ROOT / case['input']).resolve():
            raise ValueError('Observation input identity mismatch')
        results.append({'id': case['id'], 'inputSha256': case['sha256'], 'checks': checks(case, observed),
                        'observation': observed})
    result = {'suite': manifest['suite'], 'scope': 'Unweighted exact Markdown and anchor checks; no PDF/redline score',
              'build': record, 'manifestSha256': digest(ROOT / 'fixtures/projection/manifest.json'), 'cases': results}
    write_json(Path(output), result)
    print(str(sum(all(r['checks'].values()) for r in results)) + '/' + str(len(results)) + ' cases pass')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    builder = commands.add_parser('build')
    builder.add_argument('--source', required=True)
    builder.add_argument('--commit', required=True)
    builder.add_argument('--out', required=True)
    runner = commands.add_parser('run')
    runner.add_argument('--build', required=True)
    runner.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'build':
        build(args.source, args.commit, args.out)
    else:
        result = run(args.build, args.output)
        raise SystemExit(0 if all(all(r['checks'].values()) for r in result['cases']) else 1)


if __name__ == '__main__':
    main()
