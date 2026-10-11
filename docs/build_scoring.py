"""Create the scoring guide with this repository's original OOXML writer."""
from pathlib import Path
import sys
from zipfile import ZipFile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.fixtures import W, package, para, run, zip_write

ROOT = Path(__file__).resolve().parents[1]


def build():
    title = 'DOCX rendering fidelity scoring'
    body = para(title, '<w:pStyle w:val="Title"/>')
    manual = (ROOT / 'docs/SCORING.md').read_text()
    for paragraph in manual.split('\n\n')[1:]:
        if paragraph.startswith('## '):
            heading = paragraph[3:].strip()
            before = '<w:pageBreakBefore/>' if heading in ('Cases and suites', 'Gates and reproducibility') else ''
            body += para(heading, '<w:pStyle w:val="Heading1"/>' + before)
        else:
            text = paragraph.replace('`', '').replace('**', '').replace('\n', ' ')
            # Write formula symbols as ordinary readable prose in the guide.
            text = text.replace('100 × min(SSIM, ink F1)', '100 times the smaller of SSIM and ink F1')
            text = text.replace('2 × precision × recall / (precision + recall)', 'two times precision times recall, divided by their sum')
            body += para(text)
    output = ROOT / 'docs/SCORING.docx'
    package(output, body)
    with ZipFile(output) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    styles = parts['word/styles.xml'].decode().replace('</w:styles>', '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="000000"/></w:rPr></w:style></w:styles>')
    parts['word/styles.xml'] = styles
    zip_write(output, parts)
    print(output)


if __name__ == '__main__':
    build()
