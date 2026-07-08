"""Markdown catalog for ``harmonics explain <path>``.

Each entry is verbatim markdown. Keys are command-path tuples. The empty tuple,
``("harmonics",)`` (the command name), and ``("harmonics-cli",)`` (the dist
name) all resolve to the root entry.

Keep bodies self-contained: an agent reading one entry should get enough
context without chaining reads.

Naming: the command is ``harmonics`` (what you type); ``harmonics-cli`` is the
PyPI/dist name and identity. Runnable examples use ``harmonics``; the root page
title and the root topic token stay ``harmonics-cli`` (the product itself).
"""

from __future__ import annotations

_ROOT = """\
# harmonics-cli

A clonable template for AgentCulture mesh agents. It carries an agent-first CLI
(cited from the teken `python-cli` reference), a mesh identity (`culture.yaml` +
`CLAUDE.md`), the canonical guildmaster skill kit under `.claude/skills/`, and a
buildable/deployable package baseline. Clone it, rename the package, edit
`culture.yaml`, and you have a new agent.

Installed from PyPI as `harmonics-cli`; the command you run is `harmonics`.

## Verbs

- `harmonics whoami` — identity probe from `culture.yaml`.
- `harmonics learn` — structured self-teaching prompt.
- `harmonics explain <path>` — markdown docs for any noun/verb.
- `harmonics overview` — descriptive snapshot of the agent.
- `harmonics doctor` — check the agent-identity invariants.
- `harmonics cli overview` — describe the CLI surface.

## Exit-code policy

- `0` success
- `1` user-input error
- `2` environment / setup error
- `3+` reserved

## See also

- `harmonics explain whoami`
- `harmonics explain doctor`
"""

_WHOAMI = """\
# harmonics whoami

Reports the agent's identity from `culture.yaml`: nick (`suffix`), backend,
served model, and the package version. Read-only.

## Usage

    harmonics whoami
    harmonics whoami --json
"""

_LEARN = """\
# harmonics learn

Prints a structured self-teaching prompt covering purpose, command map,
exit-code policy, `--json` support, and the `explain` pointer.

## Usage

    harmonics learn
    harmonics learn --json
"""

_EXPLAIN = """\
# harmonics explain <path>

Prints markdown documentation for any noun/verb path. Unlike `--help` (terse,
positional), `explain` is global and addressable by path.

## Usage

    harmonics explain harmonics
    harmonics explain whoami
    harmonics explain --json <path>
"""

_OVERVIEW = """\
# harmonics overview

Read-only descriptive snapshot of the agent: identity (from `culture.yaml`), the
verb surface, and the sibling-pattern artifacts the template carries. Accepts an
ignored `target` so a stray path never hard-fails.

## Usage

    harmonics overview
    harmonics overview --json
"""

_DOCTOR = """\
# harmonics doctor

Checks the agent-identity invariants `steward doctor` verifies:
prompt-file-present and backend-consistency (`colleague` → `AGENTS.colleague.md`), plus a
skills-present check. Exits 1 when unhealthy.

## Usage

    harmonics doctor
    harmonics doctor --json
"""

_CLI = """\
# harmonics cli

Noun group for CLI-surface introspection. `cli overview` describes the CLI
itself (distinct from the global `overview`, which describes the agent).

## Usage

    harmonics cli overview
    harmonics cli overview --json
"""


ENTRIES: dict[tuple[str, ...], str] = {
    (): _ROOT,
    ("harmonics",): _ROOT,
    ("harmonics-cli",): _ROOT,
    ("whoami",): _WHOAMI,
    ("learn",): _LEARN,
    ("explain",): _EXPLAIN,
    ("overview",): _OVERVIEW,
    ("doctor",): _DOCTOR,
    ("cli",): _CLI,
    ("cli", "overview"): _CLI,
}
