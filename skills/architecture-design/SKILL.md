---
name: architecture-design
description: >
  The design pipeline behind the architecture-design workflow: drivers baseline → current-state
  C4 → three lens proposals → judge panel with an adversarial refutation → threat model → data
  and migration review → ADRs → spec for writing-plans. Load when running or extending that
  workflow, or when a single stage is requested by hand ("document the current architecture",
  "write an ADR for …", "threat-model this design").
---

# Architecture Design

Stage reference → which file under `references/` an agent reads (resolve under the plugin root named in the injected rules block; never search the filesystem).

| Stage | Agent | Reads | Writes (under the work directory) |
|---|---|---|---|
| 0 Drivers | default workflow agent | `baseline-builder.md`, `nfr-capture.md` | `00-drivers.md` — driver register with ids `DR1…` |
| 1 Context | default agent per project, then a merge agent | `current-architecture.md`, `c4-model.md`, `sketch-conventions.md` | `01-context-<project>.md`, merged `01-current-c4.md` |
| 2 Proposals | `design-simplicity`, `design-scalability`, `design-boundaries` | `proposal-builder.md`, `sketch-conventions.md` | `02-proposal-<lens>.md` |
| 3 Judge | `design-judge` × N, one refuter, one synthesiser | `review-rubric.md`, `scenario-compare.md`, `sketch-conventions.md` | `03-decision.md` — scores, winner, runner-up, decision table |
| 4 Threats | `security-auditor` (audit mode) | `stride-threat-model`, `threat-mitigation-mapping` skills | `04-threat-model.md` |
| 5 Data | `migration-reviewer` | `postgres-migration`, `ssdt-reviewer` skills | — (returns JSON; the spec stage embeds it) |
| — Critic | default agent | all of the above | `06-completeness.md` — drivers without an answer |
| 6 ADR (after approval) | default agent | `decision-recorder.md`, `adr-madr.md`, `adr-process.md` | `<adrDir>/NNNN-<slug>.md` per decision |
| 7 Spec (after approval) | default agent | `migration-planner.md`, `diagram-builder.md`, `sketch-conventions.md` | `<specsDir>/<date>-<slug>-design.md` |

`references/c4-model.md` and `references/adr-process.md` were vendored as single files — use them for their templates and top-level guidance only; ignore their pointers to companion files (`mode-*.md`, `supporting-diagrams.md`, `shared-patterns.md`, …) and to tooling this plugin does not ship (`qmd`, `cgg`, `/sdd:*`, `TeamCreate`).

## Sketches

Design is drawn, not only described: every artifact in the table embeds its views as ```mermaid fences following `references/sketch-conventions.md` (flowchart with subgraphs for context/container/component, sequenceDiagram for the critical flow and its failure path, erDiagram for data, `:::target` marks for what changes). Sketches live with the other artifacts under the work directory (`<plansDir>/architecture/<slug>/`), never in a project's tracked tree, and the same text can be imported into FigJam later. No ASCII art, no image files, no Mermaid C4 syntax.

## Shared shapes

**Driver:** `{ id: "DR3", theme: "performance", statement: "p95 < 300 ms for catalog reads", criticality: "must|should|could", evidence: "measured|stated|assumed" }`.

**Proposal** (`02-proposal-<lens>.md` and JSON): `{ id: "P-simplicity", lens, title, summary, decisions: [{ id: "D1", topic, choice, alternatives: [], reopenTrigger }], driversAddressed: ["DR1"], driversUnaddressed: [], risks: [{ id, description, mitigation }], estimate: { effortDays, blastRadius: "low|medium|high", newInfrastructure: [] }, artifact }`.

**Score:** per proposal, six criteria 1–5: `fit` (drivers), `simplicity`, `blastRadius` (5 = smallest), `dataSafety`, `opsCost` (5 = cheapest), `conformance` (to the conventions and the existing service shape). Total is the sum; ties go to the higher `simplicity`.

## Spec format (stage 7)

The spec file must be what `superpowers:writing-plans` expects as input: a title, `## Goal`, `## Context` (current C4 summary), `## Design` (the winner: components, contracts, data model, failure behaviour, with the approved proposal's mermaid views verbatim), `## Decisions` (table: id, choice, ADR path), `## Threats and mitigations`, `## Data migration` (sequence and rollback), `## Out of scope`, `## Open questions` (empty or the list). No placeholders.
