# Auto Modules Workspace Implementation Plan

## Goal

Configure `D:\ACloud\auto_modules` as an isolated Codex workspace with a
small Skillshare assignment, a project-scoped Serena configuration, and a
local CodeGraph index.

## Architecture Overview

- Global Codex MCP registrations remain unchanged.
- `auto_modules` owns its `AGENTS.md`, `.serena/project.yml`, `.codegraph/`,
  and Skillshare project assignment.
- Skillshare only syncs the approved project whitelist to `.agents/skills`.
- Serena uses symbol-oriented tools; Codex keeps native file and shell tools.
- CodeGraph serves architecture and impact questions from its local index.

## Tech Stack

- Codex MCP: Serena 1.7.0 and CodeGraph 1.6.0
- Skillshare: dev-modified-20260712-r15
- Project: Python, PySide, OpenCV/OCR, virtual gamepad, and LAN input modules

## Task 1: Add Project Instructions And Ignore Generated State

Files:

- `D:\ACloud\auto_modules\AGENTS.md`
- `D:\ACloud\auto_modules\.gitignore`

Preflight:

```powershell
Test-Path D:\ACloud\auto_modules\AGENTS.md
# Expected: False
```

Create `AGENTS.md` with:

```markdown
# Auto Modules

Work only within `D:\ACloud\auto_modules` unless the task explicitly names a
different directory.

At the start of a Codex session, activate this project with Serena. Use
CodeGraph for architecture, call-path, blast-radius, and affected-test
questions. Use Serena for symbol navigation, references, diagnostics, and
symbol-aware refactors.

Before changing virtual gamepad, LAN input, OCR, or desktop-control behavior,
trace the affected path and run focused tests. Do not send real input or start
network synchronization unless the task explicitly requests it.

Project references:

- `README.md`
- `ARCHITECTURE_GUIDE.md`
- `CODEBASE.md`
- `ARCHITECTURE_ITERATION_LOG.md`
```

Append these local generated paths to `.gitignore`:

```gitignore

# Local Codex analysis and managed-skill state.
.codegraph/
.agents/
.serena/cache/
.serena/memories/
.serena/project.local.yml
```

Verify:

```powershell
Select-String -Path D:\ACloud\auto_modules\AGENTS.md -Pattern 'CodeGraph'
Select-String -Path D:\ACloud\auto_modules\.gitignore -Pattern '^\.codegraph/$'
# Expected: both matches are present
```

## Task 2: Create A Lean Serena Project

Files:

- `D:\ACloud\auto_modules\.serena\project.yml`

Preflight:

```powershell
Test-Path D:\ACloud\auto_modules\.serena\project.yml
# Expected: False
```

Generate the project configuration:

```powershell
serena project create D:\ACloud\auto_modules --name auto_modules --language python
```

Set the following project settings in the generated file:

```yaml
project_name: "auto_modules"
language_servers:
  - python
ignored_paths:
  - build/
  - dist/
  - logs/
  - map_data/
  - assets/perception_models/
fixed_tools:
  - activate_project
  - get_current_config
  - find_symbol
  - find_declaration
  - find_implementations
  - find_referencing_symbols
  - get_symbols_overview
  - get_diagnostics_for_file
  - replace_symbol_body
  - insert_after_symbol
  - insert_before_symbol
  - rename_symbol
  - safe_delete_symbol
```

Verify:

```powershell
serena project health-check D:\ACloud\auto_modules
# Expected: project configuration and Python language server are healthy
```

## Task 3: Build The CodeGraph Index

Files:

- `D:\ACloud\auto_modules\.codegraph\codegraph.db` (generated)

Preflight:

```powershell
codegraph status D:\ACloud\auto_modules
# Expected: Not initialized
```

Initialize:

```powershell
codegraph init D:\ACloud\auto_modules --yes
```

Verify:

```powershell
codegraph status D:\ACloud\auto_modules
codegraph explore "How does the application reach the virtual gamepad host?"
# Expected: initialized graph statistics and cross-file source context
```

## Task 4: Register And Assign The Skillshare Workspace

Files:

- Skillshare local project registry (generated outside the repository)
- `D:\ACloud\auto_modules\.agents\skills\` (generated local target)

Register the project:

```powershell
skillshare project add AutoModules D:\ACloud\auto_modules
skillshare project list
# Expected: print the generated AutoModules workspace id
```

Assign these skills using the generated workspace id:

```powershell
skillshare project assign <AutoModules-id> --target codex --skill brainstorming
skillshare project assign <AutoModules-id> --target codex --skill writing-plans
skillshare project assign <AutoModules-id> --target codex --skill systematic-debugging
skillshare project assign <AutoModules-id> --target codex --skill testing-generator
skillshare project assign <AutoModules-id> --target codex --skill requesting-code-review
skillshare project assign <AutoModules-id> --target codex --skill codebase-ontology
skillshare project assign <AutoModules-id> --target codex --skill tech-stack-scout
skillshare project assign <AutoModules-id> --target codex --skill associative-research
```

Preview before applying:

```powershell
skillshare project sync <AutoModules-id> --dry-run
# Expected: create only the eight assigned skills under .agents/skills
```

Apply only if the preview is safe and contains no global target changes:

```powershell
skillshare project sync <AutoModules-id>
```

Verify:

```powershell
skillshare codex status workspace <AutoModules-id> skills
Get-ChildItem D:\ACloud\auto_modules\.agents\skills -Directory
# Expected: only the approved project skills are effective
```

## Task 5: Final Workspace Validation

Files:

- `D:\ACloud\auto_modules\AGENTS.md`
- `D:\ACloud\auto_modules\.serena\project.yml`
- `D:\ACloud\auto_modules\.codegraph\` (generated and ignored)
- `D:\ACloud\auto_modules\.agents\` (generated and ignored)

Run:

```powershell
git -C D:\ACloud\auto_modules status --short
codegraph status D:\ACloud\auto_modules
serena project health-check D:\ACloud\auto_modules
skillshare project list
```

Expected:

- `AGENTS.md`, `.gitignore`, and the design documents are the only tracked
  working-tree changes.
- CodeGraph reports an initialized project.
- Serena reports a healthy Python project.
- Skillshare lists `AutoModules` as a registered local project.

No Git commit is included in this plan because the repository's commit policy
has not been requested.
