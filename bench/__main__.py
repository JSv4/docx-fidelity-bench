from __future__ import annotations
import argparse
import sys
from pathlib import Path
from . import metrics, pdf, runner
from .common import WORD_TRACKS, ROOT, digest, identity, read_json, validate_registry, write_json
from .environment import environment
from .build import docxodus


def main():
    parser = argparse.ArgumentParser(description='Independent DOCX rendering fidelity benchmark')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    build = sub.add_parser('build-docxodus')
    build.add_argument('--source', required=True)
    build.add_argument('--commit', required=True)
    ref = sub.add_parser('reference')
    refs = ref.add_subparsers(dest='operation', required=True)
    create = refs.add_parser('libreoffice')
    create.add_argument('--out', required=True)
    controls = refs.add_parser('equivalent-controls')
    controls.add_argument('--reference', required=True, help='Immutable direct LibreOffice bundle')
    controls.add_argument('--out', required=True)
    capture = refs.add_parser('import')
    capture.add_argument('--metadata', required=True)
    capture.add_argument('--pdf-dir', required=True)
    capture.add_argument('--out', required=True)
    run = sub.add_parser('run')
    run.add_argument('--reference', required=True)
    run.add_argument('--adapter', choices=['docxodus', 'libreoffice', 'libreoffice-reference'], required=True)
    run.add_argument('--candidate', required=True, help='Exact source commit for Docxodus; explicit identity for other adapters')
    run.add_argument('--out', required=True)
    run.add_argument('--gate', choices=['report', 'mandatory', 'close'], default='report')
    compare = sub.add_parser('compare')
    compare.add_argument('previous')
    compare.add_argument('current')
    compare.add_argument('--tolerance', type=float, required=True, help='Explicit calibrated tolerance, in the units of each metric')
    red = sub.add_parser('redline', help='Comparison (redline) track; see docs/REDLINE.md')
    reds = red.add_subparsers(dest='operation', required=True)
    reds.add_parser('validate')
    rbuild = reds.add_parser('build-docxodus')
    rbuild.add_argument('--source', required=True)
    rbuild.add_argument('--commit', required=True)
    rbuild.add_argument('--out', required=True)
    rvalidator = reds.add_parser('build-validator')
    rvalidator.add_argument('--out', required=True)
    rrun = reds.add_parser('run')
    rrun.add_argument('--adapter', choices=['docxodus', 'authored'], required=True)
    rrun.add_argument('--candidate', required=True, help='Exact source commit for Docxodus; explicit identity for the authored calibration')
    rrun.add_argument('--build', help='Directory written by `redline build-docxodus`')
    rrun.add_argument('--validator', help='Directory written by `redline build-validator`; without it the run is incomplete')
    rrun.add_argument('--case', action='append', help='Restrict to one case (diagnostic; never a complete run unless every case is listed)')
    rrun.add_argument('--out', required=True)
    rrun.add_argument('--gate', choices=['report', 'pass'], default='report')
    rcompare = reds.add_parser('compare')
    rcompare.add_argument('previous')
    rcompare.add_argument('current')
    record = sub.add_parser('record-propose')
    record.add_argument('result')
    record.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'redline':
        return redline_command(args)
    registry = validate_registry()
    if args.command == 'validate':
        print(f'Validated {len(registry["cases"])} authored cases in {registry["suite"]["id"]}')
    elif args.command == 'build-docxodus':
        docxodus(args.source, args.commit)
    elif args.command == 'reference' and args.operation == 'libreoffice':
        runner.reference_bundle(args.out)
    elif args.command == 'reference' and args.operation == 'equivalent-controls':
        runner.equivalent_reference_bundle(args.out, args.reference)
    elif args.command == 'reference':
        import_reference(registry, args)
    elif args.command == 'run':
        adapter = args.adapter if args.adapter != 'docxodus' else ['node', str(ROOT / 'adapters/docxodus.mjs')]
        result = runner.run(args.out, args.reference, adapter, args.candidate)
        print(result['summary'])
        if 'htmlSummary' in result:
            print('Delivered HTML:', result['htmlSummary'])
        html_summary = result.get('htmlSummary', {'complete': True, 'passed': 0, 'required': 0})
        if not result['summary']['complete'] or not html_summary['complete']:
            return 2
        if args.gate in {'mandatory', 'close'} and html_summary['passed'] != html_summary['required']:
            return 1
        if args.gate == 'mandatory' and result['summary']['mandatoryPassRate'] != 1:
            return 1
        if args.gate == 'close' and result['summary']['closeMatchRate'] != 1:
            return 1
    elif args.command == 'compare':
        findings = runner.compare(read_json(args.previous), read_json(args.current), args.tolerance)
        print('\n'.join(findings) or 'No regression')
        return int(bool(findings))
    else:
        result = read_json(args.result)
        runner.validate_result(result)
        if not result['summary']['complete'] or not result.get('htmlSummary', {'complete': True})['complete'] or result['contractDigest'] != identity(result['contract']):
            raise ValueError('Incomplete or corrupt runs cannot propose a record')
        if result['contract']['suiteDigest'] != identity(registry):
            raise ValueError('Stale fixture or suite cannot propose a record')
        target = Path(args.out)
        if target.exists():
            raise ValueError('Record proposal destination already exists')
        write_json(target, {'schema': 1, 'status': 'proposal-requires-evidence-review', 'result': result})
        print('Prepared a proposal; no existing record was changed')
    return 0


def redline_command(args):
    from . import redline, redline_build
    if args.operation == 'validate':
        registry = redline.validate_registry()
        print(f'Validated {len(registry["cases"])} authored redline cases in {registry["suite"]["id"]}')
    elif args.operation == 'build-docxodus':
        redline_build.build_docxodus(args.source, args.commit, args.out)
    elif args.operation == 'build-validator':
        redline_build.build_validator(args.out)
    elif args.operation == 'run':
        result = redline.run(args.out, args.adapter, args.candidate, args.build, args.validator, args.case)
        print(result['summary'])
        if not result['summary']['complete']:
            return 2
        if args.gate == 'pass' and result['summary']['passRate'] != 1:
            return 1
    else:
        findings = redline.compare(read_json(args.previous), read_json(args.current))
        print('\n'.join(findings) or 'No regression')
        return int(bool(findings))
    return 0


def import_reference(registry, args):
    import shutil
    metadata = read_json(args.metadata)
    if metadata.get('track') not in WORD_TRACKS or metadata.get('rightsApproved') is not True:
        raise ValueError('Explicit Word capture track and approved artifact rights are required')
    for key in ('capturedAt', 'provider', 'method', 'reportedBuild', 'platform', 'profile', 'fontContract', 'cases'):
        if key not in metadata:
            raise ValueError('Missing capture metadata: ' + key)
    env = environment([f for c in registry['cases'] for f in c['fonts']])
    if metadata['fontContract'] != env['contract']['fonts'] or metadata['profile'] != {'review': 'final', 'comments': 'hidden'}:
        raise ValueError('Capture font or view contract is unverified or mismatched')
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=False)
    bundle = {'schema': 1, 'track': metadata['track'], 'suiteDigest': identity(registry), 'environment': env['contract'], 'capture': metadata, 'cases': {}}
    for case in registry['cases']:
        record = metadata['cases'].get(case['id'])
        if not record:
            continue
        if record['inputSha256'] != case['sha256']:
            raise ValueError('Capture source mismatch: ' + case['id'])
        source = Path(args.pdf_dir) / (case['id'] + '.pdf')
        if digest(source) != record['pdfSha256']:
            raise ValueError('Capture PDF mismatch: ' + case['id'])
        target = output / (case['id'] + '.pdf')
        shutil.copyfile(source, target)
        info = pdf.inspect_pdf(target)
        failures = pdf.reference_failures(case, info, metadata['track'])
        bundle['cases'][case['id']] = {'inputSha256': case['sha256'], 'pdf': target.name, 'pdfSha256': digest(target), 'eligible': not failures, 'ineligibleChecks': failures, 'inspection': info}
    write_json(output / 'bundle.json', bundle)
    print(f'Registered {len(bundle["cases"])} Word captures; absent cases remain pending')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'Benchmark error: {type(error).__name__}: {error}', file=sys.stderr)
        sys.exit(2)
