from __future__ import annotations
from html import escape
from pathlib import Path
from .common import write_json


def save(output, result):
    output = Path(output)
    write_json(output / 'result.json', result)
    summary = result['summary']
    score = f'{summary["score"]:.2f}' if summary['complete'] else 'Incomplete — no suite score'
    rows, sections = [], []
    for case in result['cases']:
        cid = escape(case['id'])
        display = f'{case["score"]:.2f}' if case['status'] == 'measured' else 'Unmeasured'
        rows.append(f'<tr><td><a href="#{cid}">{cid}</a></td><td>{escape(case["category"])}</td><td>{case["status"]}</td><td>{display}</td></tr>')
        failures = [escape(c['name'] + ': ' + str(c.get('error', 'failed'))) for c in case.get('checks', []) if not c['passed']]
        pages = []
        artifacts = ''.join(f'<a href="{cid}/{name}">{label}</a> ' for name, label in [('reference.pdf', 'Reference PDF'), ('direct-reference.pdf', 'Original direct reference PDF'), ('candidate.pdf', 'Candidate PDF'), ('production.json', 'Production report')] if (output / case['id'] / name).is_file())
        source = case.get('referenceSource')
        source_note = ('<p>Reference captured from equivalent control <code>' + escape(source['caseId']) +
                       '</code> using ' + escape(source['rule']) + '. The scored fixture remains <code>' + cid +
                       '</code>.</p>') if source and source['kind'] == 'equivalent-control' else ''
        for number, page in enumerate(case.get('pages', []), 1):
            if page.get('unmatched') or page.get('dimensionsMismatch'):
                pages.append(f'<p>Page {number}: {escape(str(page))}</p>')
                continue
            figures = ''.join(f'<figure><figcaption>{name.title()}</figcaption><a href="{cid}/{number}-{name}.png"><img loading="lazy" src="{cid}/{number}-{name}.png" alt="{name} page {number}"></a></figure>' for name in ('reference', 'candidate', 'overlay'))
            pages.append(f'<h3>Page {number}</h3><p>Score {page["score"]:.2f}; SSIM {page["ssim"]:.6f}; ink F1 {page["inkF1"]:.6f}; precision {page["precision"]:.6f}; recall {page["recall"]:.6f}</p><div class="pages">{figures}</div>')
        sections.append(f'<details id="{cid}"><summary>{cid} — {display}</summary>{source_note}<p>{escape(case.get("error", ""))}</p><p>{"; ".join(failures) or "Mandatory checks passed" if case["status"] == "measured" else "Comparison is unmeasured"}</p><p>{artifacts}<a href="{cid}/evidence.json">Case evidence</a></p>{"".join(pages)}</details>')
    category_rows = ''.join(f'<tr><td>{escape(category)}</td><td>{value:.2f}</td></tr>' for category, value in summary['categoryMeans'].items())
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>DOCX rendering fidelity</title>
    <style>body{{font:16px/1.5 system-ui;max-width:1400px;margin:2rem auto;padding:0 1rem;color:#1c2430}}table{{border-collapse:collapse}}th,td{{text-align:left;padding:.5rem 1rem;border-bottom:1px solid #ccd}}details{{margin:1rem 0;border:1px solid #ccd;padding:1rem}}summary{{cursor:pointer;font-weight:600}}.pages{{display:flex;gap:1rem;overflow:auto}}figure{{margin:0;min-width:280px;flex:1}}img{{width:100%;border:1px solid #bbb}}code{{overflow-wrap:anywhere}}</style>
    <h1>DOCX rendering fidelity</h1><p>Reference track: <strong>{escape(result['track'])}</strong>. Candidate: <code>{escape(result['candidate'])}</code>.</p>
    <p>Suite result: <strong>{score}</strong>. Coverage {summary['measured']}/{summary['required']}. Mandatory pass rate {summary['mandatoryPassRate']:.1%}; close match rate {summary['closeMatchRate']:.1%}.</p>
    <p>The score is a conservative layout similarity measure, not a percentage of document correctness. Rasters use 96 DPI without alignment, resizing, cropping of content, or masks. Page score is 100 times the smaller of SSIM and ink F1; case score uses the worst page and becomes zero on a mandatory failure. Suite score averages category means equally. Ink matching tolerates one pixel.</p>
    <p>Overlay: blue is reference-only ink; red is candidate-only ink; gray is shared ink. Close match requires every mandatory check, SSIM ≥ 0.98, and ink F1 ≥ 0.95 on every page. Word and LibreOffice tracks are separate.</p>
    <p><a href="result.json">Complete machine-readable results and environment</a></p><h2>Category means</h2><p>{'Complete coverage' if summary['complete'] else 'Partial diagnostic means; no suite score'}</p><table><thead><tr><th>Category</th><th>Mean</th></tr></thead><tbody>{category_rows}</tbody></table><h2>Cases</h2><table><thead><tr><th>Case</th><th>Category</th><th>Status</th><th>Score</th></tr></thead><tbody>{''.join(rows)}</tbody></table>{''.join(sections)}</html>'''
    (output / 'index.html').write_text(html)
