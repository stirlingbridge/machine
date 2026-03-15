---
name: E2E test CI trigger decision
description: E2E tests currently run nightly + manual only; revisiting PR/merge triggers later based on cost/runtime
type: project
---

E2E tests (`.github/workflows/e2e-test.yml`) are deliberately limited to nightly schedule and manual `workflow_dispatch` triggers.

**Why:** Runtime and cost of creating real DigitalOcean droplets is not yet understood. Running on every PR/merge could be expensive.

**How to apply:** If the user asks about adding PR or push triggers to the e2e workflow, remind them of this decision and check whether they've gathered enough data to revisit.
