# SheetNest

A local material-layout workbench for makers planning rectangular parts on sheet stock. Built with Python 3.11+ standard library, SQLite, vanilla JavaScript and SVG. This is a new, independently useful application prototype, developed with AI assistance. The bundled sample is fictional; no accounts, API keys or external services are required.

## What works today

- Edit stock dimensions, sheet count, kerf allowance and quantities in a cut list.
- Generate deterministic layouts, inspect utilization and see explicitly unplaced pieces.
- Select pieces by mouse or keyboard; adjust positions and rotate with backend bounds and spacing checks.
- Undo/redo manual moves, save projects in SQLite, reopen layouts and detect stale saves.
- Import/export project JSON, export a dimensioned SVG and print a plan.

## Run locally

```sh
python3 -m sheetnest
# Open http://127.0.0.1:7421
```

Start commands run from the repository root. The server binds to `127.0.0.1`; open that address rather than `localhost`, because host/origin checks are deliberate. This local server is not configured for public internet hosting.

Use `--port` to choose another port and `--data PATH` to choose the SQLite file. The default is `.local-data/sheetnest.sqlite3`.

## Verify

```sh
python3 -m unittest discover -s tests -v
# Browser checks: start a separate server with a disposable data path first.
npm ci
npx playwright install chromium
npm run test:ui
```

Browser tests create synthetic saved records. Point `BASE_URL` at the test server if needed. Chromium requires its normal OS libraries; consult Playwright installation guidance for your system. Set `UI_SCREENSHOTS` to an output directory to capture desktop and narrow-screen evidence. There is no hosted CI configured yet.

## Organization

`sheetnest/core.py` validates and packs rectangles; `store.py` persists revisions; `__main__.py` serves the local API. `web/` contains the interface, `tests/` contains Python and browser checks, and `examples/` contains a fictional project.

## Scope and limitations

Dimensions are integer millimetres. Limits are 200 pieces, 20 sheets and 100 saved projects. Packing uses a deterministic shelf heuristic, so it can leave pieces unplaced even when a better arrangement exists. Manual edits must account for every piece and retain configured spacing. Area utilization uses the area of sheets that contain pieces, including kerf in unused area.

This is a planning aid, not a CNC exporter, optimal nesting solver or cut-sequence/safety validator. Verify dimensions and cutting order independently before fabrication. Changing a cut-list input requires regenerating the layout. Undo covers manual layout changes, not every cut-list edit.

Local state, build output and browser downloads are excluded from Git. Back up your data file before experimenting with it. No telemetry or remote synchronization is implemented.

## Next steps

See [ROADMAP.md](ROADMAP.md) for concrete work with acceptance criteria and rough estimates, and [CONTRIBUTING.md](CONTRIBUTING.md) for development conventions.

## License

MIT. See [LICENSE](LICENSE).
