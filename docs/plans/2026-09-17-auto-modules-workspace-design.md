# Auto Modules Codex Workspace Design

## Goal

Make `D:\ACloud\auto_modules` an isolated Codex workspace with project-scoped
instructions, skills, Serena configuration, and a CodeGraph index. Avoid
loading the unrelated contents of `D:\ACloud` into the coding session.

## Scope

- Keep existing global Codex configuration in place during the migration.
- Do not delete or overwrite existing global skills.
- Register and manage `auto_modules` as a dedicated Skillshare project.
- Keep project-specific configuration inside the repository.

## Skills

The project skill whitelist is:

- `brainstorming`
- `writing-plans`
- `systematic-debugging`
- `testing-generator`
- `requesting-code-review`
- `codebase-ontology`
- `tech-stack-scout`
- `associative-research`

The global skills migration is deferred until the existing conflicts are
reviewed through Skillshare's collect, preview, and apply workflow.

## MCP Roles

CodeGraph is indexed only at `D:\ACloud\auto_modules` and is used for
architecture, call-path, impact, and affected-test questions.

Serena is activated only for `D:\ACloud\auto_modules`. Its project
configuration exposes a small symbol-oriented tool set and leaves file, shell,
and generic text operations to Codex's built-in tools.

## Project Instructions

The project-level `AGENTS.md` documents the workspace boundary, the required
Serena activation, CodeGraph use, the test command, and safety constraints for
virtual gamepad and network-input work. It points to existing architecture
documents rather than duplicating them.

## Safety

All Skillshare changes use the exact-plan preview and apply flow. No existing
global skill or agent is removed as part of this rollout.
