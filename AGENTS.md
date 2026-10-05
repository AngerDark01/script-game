# Auto Modules

Work only within `D:\ACloud\auto_modules` unless the task explicitly names a
different directory.

At the start of a Codex session, activate `D:\ACloud\auto_modules` as the
Serena project. Use CodeGraph for architecture, call-path, blast-radius, and
affected-test questions. Use Serena for symbol navigation, references,
diagnostics, and symbol-aware refactors.

Before changing virtual gamepad, LAN input, OCR, or desktop-control behavior,
trace the affected path and run focused tests. Do not send real input or start
network synchronization unless the task explicitly requests it.

## Mandatory Checkpoint Discipline

Every task must have a durable checkpoint document before implementation or
diagnosis begins. Use the task's existing checkpoint when one exists; otherwise
create one under `docs/` with a clear task name. Update it immediately after
each material finding, root-cause conclusion, implementation boundary,
verification result, unresolved risk, or user decision. Keep the checkpoint
concise but concrete: record the evidence, affected call chain, files and
symbols, current status, and the exact next action. Also append a short entry
to `ITERATION_LOG.md` for repository-level traceability. After context
compaction, the first action is to read the checkpoint and iteration entry
before inspecting code or repeating experiments. Never rely on chat history as
the only record of a decision or failed experiment.

## Architecture Design Philosophy: Generalize From the Bottom Up

Every layer must achieve the maximum **practical** generality within its own
stable responsibility. Build reusable capabilities at lower layers; assemble
those capabilities in higher layers. Do not put a concrete business rule into
a shared module merely because one feature needs it. "Practical" excludes
speculative frameworks: generalize only a capability with stable semantics and
real or clearly imminent reuse.

Use this dependency direction:

```text
Foundation capabilities
  recognition, coordinate transforms, maps, path planning, state machines,
  scheduling, controller-state output, and transport/device protocols
        ->
Generic domain runtimes
  localization, navigation tasks, event lifecycle, state merging, recovery
        ->
Composition and adapters
  GUI, OCR provider, Host, device, configuration, and event integration
        ->
Business features
  portal, follow strategy, skill workflow, and game-specific rules
```

- Lower layers must not import, branch on, or otherwise know business-feature
  concepts such as a particular event, game object, skill, role, or screen.
  Dependencies flow downward only; business layers must not become a dependency
  of generic capabilities.
- A business feature must compose existing capabilities through explicit
  interfaces, typed data, intents, commands, configuration, strategies, hooks,
  or adapters. It must not duplicate recognition, localization, path planning,
  scheduling, controller output, or transport logic.
- Generic planning and event modules produce domain-neutral observations,
  tasks, intents, actions, or commands. Only dedicated execution adapters may
  produce real mouse, keyboard, virtual-gamepad, Host, or network side effects.
- Keep state explicitly owned and scoped. Separate controllers, devices,
  sources, and feature instances must not overwrite each other's mutable state
  through globals or feature-specific shortcuts in shared modules.
- Promote a behavior from a business feature into a lower common module only
  when its contract is independent of the original feature and it can be reused
  without carrying that feature's terminology or policy with it. Otherwise keep
  it as a business strategy or adapter.
- A new feature is not complete if it requires special-case edits across
  unrelated existing features. Prefer adding a definition, policy, configuration,
  or adapter at the appropriate upper layer. Change a common module only to add
  a genuinely general capability with a narrow, explicit interface.
- Verify each boundary at the lowest practical level: test pure common modules
  independently, test interface contracts at adapters, then run focused
  integration tests for the business composition. Real input and network tests
  remain opt-in under the safety rule above.

Example: a portal feature defines target evidence, approach/interaction policy,
and completion conditions. It composes recognition, localization, navigation,
movement planning, controller output, and result observation; it does not own
or reimplement any of those capabilities.

Project references:

- `README.md`
- `ARCHITECTURE_GUIDE.md`
- `CODEBASE.md`
- `ARCHITECTURE_ITERATION_LOG.md`
