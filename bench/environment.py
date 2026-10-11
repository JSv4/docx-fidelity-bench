from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from .common import digest, execute, identity


def environment(families):
    tools = {}
    for name, argument in [('qpdf', '--version'), ('pdftoppm', '-v'), ('pdftotext', '-v'), ('pdffonts', '-v')]:
        path = shutil.which(name)
        if not path:
            raise RuntimeError('Required external executable is missing: ' + name)
        result = subprocess.run([path, argument], capture_output=True, text=True, timeout=15, check=True)
        tools[name] = {'version': (result.stdout + result.stderr).splitlines()[0], 'sha256': digest(path)}
    files, directories = {}, set()
    for family in sorted(set(families)):
        for style in ('Regular', 'Bold', 'Italic', 'Bold Italic'):
            match = execute(['fc-match', '-f', '%{family}|%{file}', family + ':style=' + style])
            actual, filename = match.split('|', 1)
            if family not in actual.split(','):
                raise RuntimeError('Font substitution is ineligible: ' + family + ' -> ' + actual)
            path = Path(filename)
            files[path.name] = {'family': family, 'sha256': digest(path)}
            directories.add(str(path.parent))
    contract = {'tools': tools, 'fonts': files}
    return {'contract': contract, 'fingerprint': identity(contract), 'fontDirectories': sorted(directories)}
