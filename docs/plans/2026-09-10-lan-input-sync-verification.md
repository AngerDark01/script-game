# LAN input sync — implementation and verification

## Delivered boundaries

- Independent `lan_input_sync` .NET library using LiteNetLib 2.1.4; no dependency on the workbench UI, keyboard capture or ViGEm driver.
- Existing VirtualGamepadHost owns the library and converts final per-controller reports. Only local output is exported; remote-owned slots bypass local mapping, suppression and state arbitration.
- Existing workbench/standalone controller page embeds a `设备同步` tab. Management uses independent, bounded local-pipe requests outside the Qt thread.
- Network start is explicit. Device identity and trusted peers persist; network mode and remote permissions do not automatically resume on process restart.

## Verification performed on this Windows machine

- Host regression suite: 49 passed, including input ownership, no physical suppression on remote slots, independent local slot, F7/F8 permission toggles, F9 reset, one consumption per output report, stale/malformed command fencing and machine-readable ownership rejection.
- Qt UI suite: 32 passed, including queued-start cancellation, serial stop scopes, stale result filtering, explicit pairing confirmation, applied-mode/readiness controls, shutdown compatibility and preservation of real stop failures.
- Focused workbench integration: 7 passed.
- Existing unified launcher suite: 4 passed.
- Network suite: 19 passed, using separate temporary identities and real TLS/TCP plus encrypted LiteNetLib UDP on loopback. It covers confirmation/pinning, short button transitions, independent slots, two receivers, slow-receiver isolation, watchdogs, fresh-session recovery and selected-peer cancellation while another connection is pending. The earlier 17-test suite also passed three consecutive repeat runs. See the module README and test source for details.
- Release host built to `virtual_gamepad/dist/lan-sync-staging` without overwriting or terminating the active elevated old host. The staging directory is generated/ignored, not source-controlled.
- A local offscreen render of the sync panel was visually inspected for Chinese text and horizontal clipping. This was a panel preview, not an active network/game screenshot.

## Review corrections

Spec review and subsequent quality review led to explicit active-reception state separate from permission, ownership error codes, stop-priority/ordering fixes, unavailable-service shutdown compatibility, independent configuration generations, network readiness, deferred socket cleanup, persistence isolated from network polling and per-peer cancellation fences. Final scoped and overall reviews passed after corrections.

## Still requires two actual computers

Loopback is not evidence of LAN/game acceptance. Validate Windows Firewall private-profile rules, device discovery/manual address fallback, focus in the target game, one-to-many simultaneous control, cable/Wi-Fi interruption, receiver sleep, and process exit on both ends. Measure sender-output to receiver-output latency separately from the displayed RTT. The design target of wired p95 additional latency at most 20 ms has **not** been measured or claimed achieved.

The existing Release host was active during this work. Close the workbench and any independently started host before replacing Release binaries; then restart through the existing unified workbench/launcher entry. No controller profile JSON, maps or unrelated action-module changes are part of this feature.
