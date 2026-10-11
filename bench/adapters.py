from __future__ import annotations
import json
import shutil
import tempfile
import os
from pathlib import Path
from .common import digest, execute


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
    if adapter == 'libreoffice':
        return libreoffice(request['input'], request['output'])
    response = json.loads(execute(adapter, input=json.dumps(request), timeout=request['timeoutMs'] / 1000 + 15))
    if response.get('protocol') != 1 or response.get('status') not in {'ok', 'failed', 'unmeasured'}:
        raise ValueError('Invalid adapter response protocol')
    if response['status'] == 'ok' and digest(request['output']) != response.get('pdfSha256'):
        raise ValueError('Adapter PDF digest does not match output')
    return response
