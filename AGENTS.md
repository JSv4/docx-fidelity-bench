# Repository Guidelines

## Project Structure & Module Organization

`bench/` contains the Python CLI, deterministic DOCX generators, PDF/HTML measurements, redline checks, and report generation. `adapters/` bridges external Docxodus builds through JavaScript and C#; `tools/ooxml-validator/` provides the optional Open XML validator. `fixtures/` holds generated documents and manifests, with comparison inputs under `fixtures/redline/`. Tests live in `tests/`; contracts and capture instructions live in `docs/`. CI workflows are under `.github/workflows/`.

## Build, Test, and Development Commands

Use Python 3.11+; the harness has no Python package dependencies. Rendering additionally requires LibreOffice, Poppler, qpdf, fontconfig, and Liberation Serif. Docxodus builds require Node.js 22.13+, .NET 10, and `wasm-tools`; see `README.md` for provisioning.

- `python3 -m bench validate`: validate the PDF-track manifest and inputs.
- `python3 -m bench redline validate`: validate the comparison corpus.
- `python3 -m unittest discover -s tests -v`: run Python contract tests.
- `node --test tests/test-adapter.mjs`: test the JSON adapter protocol.
- `python3 -m bench.audit`: regenerate fixtures temporarily and check byte identity, rights, and provenance inventory.
- `python3 -m bench build-docxodus --source /path/to/Docxodus --commit FULL_SHA`: build an exact external renderer revision.

Keep generated runs, references, and renderer checkouts in ignored `runs/`, `references/`, and `renderer/` directories.

## Coding Style & Naming Conventions

Follow surrounding code: four-space indentation for Python/C#, two spaces for JavaScript, and ES modules in `.mjs` files. Use `snake_case` for Python functions and descriptive hyphenated fixture IDs, such as `html-css-child-selector`. No dedicated formatter or linter is configured. Keep adapters faithful to the versioned protocol in `docs/ADAPTERS.md`.

## Testing Guidelines

Use Python `unittest` in `tests/test_*.py` with `test_*` methods, and Node's built-in test runner. Add positive and negative examples for new assertions. Coverage centers on scoring, failure contracts, and deterministic regeneration; no numeric coverage threshold is configured. Case changes require a suite-version increment, complete token inventories, rights records, and updated provenance hashes.

## Commit & Pull Request Guidelines

Prefer the history's scoped subjects, such as `bench(html): cover comment return links` or `test(pdf): add border control`. PRs should explain the trigger, reproducer/control pair, linked issue, and validation results. **Agents must attach screenshots of every new case to the PR for review**, showing the relevant rendered behavior and labeling each case and renderer. Include evidence links and clearly identify pending references or scoring. Review `RIGHTS.md` before adding assets and update `PROVENANCE.json` for added or changed files.
