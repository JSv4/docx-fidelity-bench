from __future__ import annotations
import json
import shutil
import tempfile
import os
import time
from pathlib import Path
from .common import ROOT, contained, digest, execute


def libreoffice(input, output):
    output = Path(output)
    executable = os.environ.get('BENCH_LIBREOFFICE', 'libreoffice')
    with tempfile.TemporaryDirectory(prefix='docx-bench-', dir=output.parent) as temporary:
        temp = Path(temporary)
        execute([executable, '-env:UserInstallation=' + (temp / 'profile').as_uri(), '--headless', '--convert-to', 'pdf:writer_pdf_Export', '--outdir', temp, input], timeout=120)
        generated = temp / (Path(input).stem + '.pdf')
        if not generated.is_file():
            raise RuntimeError('LibreOffice did not produce a PDF')
        shutil.copyfile(generated, output)
    return {'status': 'ok', 'pdfSha256': digest(output), 'renderer': {'name': 'libreoffice', 'version': execute([executable, '--version']).strip()}}


def render(adapter, request):
    preparation = request.get('preparation')
    if preparation and adapter != 'libreoffice-reference':
        from .revisions import Package, style_id_findings
        from .redline import run_candidate
        from .redline_build import verify_docxodus
        build = os.environ.get('DOCXODUS_OPERATION_BUILD')
        if adapter != ['node', str(ROOT / 'adapters/docxodus.mjs')] or not build:
            return {'status': 'unmeasured', 'error': 'This case requires a source-bound document-operation build'}
        started = time.monotonic()
        identity = verify_docxodus(build, request['candidate'])
        output = Path(request['output']).with_suffix('.docx')
        response = run_candidate('docxodus', build, preparation, output, request['candidate'],
                                 timeout=request['timeoutMs'] / 1000)
        for source in preparation['inputs']:
            if digest(contained(ROOT, source['path'])) != source['sha256']:
                raise ValueError('Document preparation modified its input')
        if response['status'] != 'ok':
            return response
        findings = style_id_findings(Package(output))
        if findings:
            return {'status': 'failed', 'error': {'phase': 'preparation', 'check': 'style-ids-unique', 'findings': findings},
                    'preparation': {'build': identity, 'result': response}}
        remaining = request['timeoutMs'] - int((time.monotonic() - started) * 1000)
        if remaining <= 0:
            return {'status': 'failed', 'error': 'Document preparation exhausted the conversion deadline'}
        rendered = render(adapter, {key: value for key, value in request.items() if key != 'preparation'} |
                          {'input': str(output), 'inputSha256': response['outputSha256'], 'timeoutMs': remaining})
        rendered['preparation'] = {'build': identity, 'result': response}
        if digest(output) != response['outputSha256']:
            raise ValueError('Renderer modified the prepared document')
        return rendered
    if adapter in ('libreoffice', 'libreoffice-reference'):
        return libreoffice(request['input'], request['output'])
    response = json.loads(execute(adapter, input=json.dumps(request), timeout=request['timeoutMs'] / 1000 + 15))
    if response.get('protocol') != 1 or response.get('status') not in {'ok', 'failed', 'unmeasured'}:
        raise ValueError('Invalid adapter response protocol')
    if response['status'] == 'ok' and digest(request['output']) != response.get('pdfSha256'):
        raise ValueError('Adapter PDF digest does not match output')
    return response
