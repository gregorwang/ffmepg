# Decisions Log

This file records plan changes, abandoned approaches, unexpected issues,
and technical debt discovered during development. It is an engineering
journal for project maintainers, not for end users.

Each entry uses this format:

## [YYYY-MM-DD] Short Title

**Context**: What was being worked on
**Original Plan**: What was originally intended
**What Happened**: What actually occurred
**Decision Made**: What was done instead
**Future Impact**: How this affects subsequent work

---

(Entries below, newest first)

## [2026-04-11] Realign CLI Contracts With Task Document

**Context**: Auditing implementation against `docs/nextstep.md`
**Original Plan**: Keep the initially implemented CLI contracts centered on `*.atproj` handles and `TranscodeTaskSpec` JSON field names
**What Happened**: The audit showed that `transcript generate --project <project-dir>` and the documented `spec.json` shape (`input` / `output`) were not strictly matched
**Decision Made**: Extend `transcript generate` to resolve a project directory to a single `.atproj` file and change batch transcode spec parsing to the documented JSON field names
**Future Impact**: CLI behavior is now closer to the task document while still preserving compatibility with the repository's underlying `.atproj` project model

---

## [2026-04-11] Protocol Validation Relaxed To Preserve File Workflow

**Context**: Adding round-trip tests, Whisper transcript generation, and render-time edge-case coverage
**Original Plan**: Keep `TranscriptDocumentService` and `SelectionDocumentService` strict, rejecting empty documents and zero-duration segments at load/save time
**What Happened**: The task required round-trip preservation of edge-case protocol data and explicit handling of empty transcript/selection results in later workflow steps
**Decision Made**: Relax protocol validation so empty transcript/selection documents and zero-duration transcript segments can be serialized and loaded; keep business-rule failures at render/transcode stages with clear errors
**Future Impact**: File protocol stays compatible with external tools and partial pipeline outputs, but downstream workflows must continue validating operationally relevant constraints

---

## [2026-04-11] Keep CLI Project Handle As `.atproj`

**Context**: Implementing `transcript generate` and transcode CLI extensions on top of the current repository
**Original Plan**: Follow the task doc literally and treat `--project` as a project directory handle
**What Happened**: The current repository already models projects as `*.atproj` files plus a sibling `.artifacts` directory, and existing CLI/GUI workflows are built around that contract
**Decision Made**: Preserve `--project <path.atproj>` as the CLI surface and write generated `transcript.json` into the project's artifact directory instead of inventing a second project-root abstraction
**Future Impact**: CLI stays consistent with existing GUI/Core behavior, but future docs should describe the `.atproj` + `.artifacts` layout explicitly to avoid ambiguity

---
