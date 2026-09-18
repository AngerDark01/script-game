# Wire protocol v1

## Control transport and pairing

TLS over TCP on the configured private IPv4 interface, default port 45873. TLS 1.2/1.3 with mutual X.509 certificates. Every message is a four-byte big-endian length followed by UTF-8 JSON, maximum 8192 bytes, JSON depth at most 8.

Discovery is an unauthenticated LiteNetLib broadcast containing protocol `automodules.lan-input/1`, deviceId, name and TCP port. It only suggests an address; it never authorizes an input source. Entries expire after six seconds; at most 64 are retained.

Pairing control sequence:

1. Receiver opens a five-minute one-use eight-digit code.
2. Sender connects with a temporary untrusted TLS certificate and sends `{type:"pair",name,code,nonce,port}`. nonce is 32 random bytes encoded as hex.
3. Receiver consumes the correct code and responds `{type:"pair-ready",name,nonce}` with its independent 32-byte nonce.
4. Both compute `SHA256(sortedFingerprint0 + ":" + sortedFingerprint1 + ":" + clientNonce + ":" + serverNonce)`; display the first 16 hexadecimal characters grouped into four groups.
5. Each local UI must explicitly confirm the same value. Each sends `{type:"confirm",fingerprint}` and waits for the other's matching confirmation before saving trust.

No input session exists during pairing. Pending confirmation expires after three minutes. TLS handshakes/initial messages have a ten-second deadline. Incoming TLS connections are capped at 16; pending pair requests at four. Unknown certificates are only provisionally accepted while pairing is open and cannot issue `start`.

Subsequent TLS is certificate-pinned. Sender sends `{type:"start",controllers:[1,2]}`; receiver must already have enabled local permission for each selected slot. Overlapping owners are rejected. Receiver creates a session and replies with `{type:"session",sessionId,token,senderKey,receiverKey,port,grants:[g1,g2]}`. Each key is independently random, 256 bits. Token is random, used to associate LiteNetLib's initial connection; input authorization always additionally requires valid AEAD payloads.

Event/position sharing uses the same paired TLS connection without owning a
controller. A data-only session is started with `{type:"start-data"}` after
both devices are configured for `share` mode and have enabled the corresponding
data permission. `sync.share.catalog` publishes a versioned event definition
catalog. The host exposes `sync.share.catalog_drain` as a catalog-only read
queue; it never consumes pending shared trigger events. `sync.share.drain`
continues to return trigger events (and retains its legacy catalog field for
older clients). This separation allows the workbench to refresh read-only
event definitions in the background without starting an event listener or
interfering with remote event execution.

Receiver sends `{type:"permissions",grants:[g1,g2]}` to change local slot permission. Zero denies; reauthorization creates a new random nonzero grant. Sender transmits a fresh reliable baseline for a changed nonzero grant. TCP closure invalidates the associated UDP session. Stop uses closure plus immediate local neutralization rather than waiting for a delivered stop message.

## UDP envelope

All integers below are little-endian. Maximum encoded packet is 554 bytes; no application fragmentation is used.

| Field | Bytes |
|---|---:|
| Version (1) | 1 |
| Lane | 1 |
| Session Guid (.NET byte layout) | 16 |
| Per-lane increasing packet sequence | 8 |
| AES-GCM encrypted payload | 0–512 |
| Authentication tag | 16 |

Header is authenticated additional data. AES-GCM nonce is `lane + three zero bytes + uint64 sequence`. Keys differ by direction; sessions always use fresh keys, so nonce/key pairs do not repeat. Sequence starts at one and must not wrap. Receiver authenticates before updating per-lane replay state. Channels have independent counters, preventing a newer snapshot from suppressing an older-but-required reliable button record.

Lane 0 uses LiteNetLib `Sequenced`. Payload: count byte followed by each selected slot: zero-based slot byte, uint32 grant, uint32 source epoch, uint32 button revision, enabled byte, pad report (uint16 buttons, uint8 LT/RT, int16 LX/LY/RX/RY).

Lane 1 uses `ReliableOrdered`. Payload: slot byte, grant, epoch, revision, enabled byte, uint16 buttons, baseline byte. Receiver snapshots never directly overwrite the ordered button output. A real backend report consumes at most one queued button bitmap; down/up cannot be collapsed in the same backend submission.

Lanes 2 and 3 use independent `Sequenced` channels for challenge and reply. A challenge is kind=0 plus uint64 challengeId. Response kind=1 includes echoed challengeId and two uint32 cumulative button revisions. Receipt kind=2 includes slot byte and uint32 revision. Cumulative receipts repair lost one-off acknowledgements. LiteNetLib `Unreliable` does not preserve a nonzero channel index and must not be substituted here without changing envelope validation.

## Freshness, limits and cancellation

Default report rate is 125Hz, optional 60Hz. Analog snapshots overwrite previous unsent snapshots. Each source slot holds at most 64 pending button changes; sender unacknowledged buttons cap at 64 per peer; receiver output queue caps at 32 per slot. No old button backlog is replayed after the 200ms budget.

Independent monotonic checks cover last valid state, source host report freshness, oldest queued receiver button, unresolved revision gap, oldest unacknowledged sender change and challenge turnaround. Probes run every 50ms. TCP liveliness or authenticated probes cannot substitute for fresh controller state. Output-side checks also run during `Consume`/status, so a stalled network worker cannot keep output alive.

Local F9/stop marks sessions inactive and resets outputs synchronously before scheduling socket disposal. Late control/UDP cannot reactivate them. Config listener generation is separate from session generation: an emergency stop cancels control authority without canceling the listener configuration. Reconnect creates a new session; both receiver permission and sender start must be explicitly requested again after loss/F9.

The limits bound normal application queues and authorization. OS thread scheduling is not real-time, and a whole-host crash is handled by the host/driver lifecycle rather than an in-process watchdog.
