# SheetNest roadmap

These are planned enhancements, not implemented features. Estimates are provisional engineering effort, including tests and documentation; they are not a claim of hours already worked. Priorities can change after practical use.

## Interactive placement, 12–16 hours

Add pointer dragging with snap guides and a keyboard nudge mode. Invalid placements must show a reason and never replace the last valid layout.

## Packing alternatives, 10–14 hours

Add a second deterministic packing strategy and compare utilization on documented fixtures. Keep oversized and grain-constrained parts explicit.

## Offcut library, 8–12 hours

Support individually sized offcuts and grain direction, with schema migration and import compatibility tests.

## Workflow and accessibility, 8–12 hours

Add project duplication/deletion, safer destructive-action recovery, keyboard navigation across sheets and a clearer mobile editor.

## Printable workshop sheets, 6–10 hours

Generate labelled piece lists and scale-aware print layouts with pagination and browser regression coverage.

## Reviewable implementation work

Each milestone can become a focused issue with reproducible input, observable UI behavior and automated checks. Review visual hierarchy, interaction clarity, keyboard behavior, data correctness, regression coverage and maintainability together. The application itself does not run or benchmark AI models.
