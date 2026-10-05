# Command-assisted role localization during marker occlusion

Approved 2026-10-04. Scope: PoE2 live-role follow in the data-collection
experiment. Do not change single-player center localization, dual first-frame
registration, or the click-target experiment. No real gamepad input in automated
verification.

## Boundary and invariant

The wall tracker estimates the minimap-to-native transform, not either actor's
motion. A visible, identity-validated marker is a measurement. A successful
program-output write is an input, not a measurement. A manual leader has no
known input and may only retain the last measured target for a bounded recovery
period. Every role owns its own estimator, output history and map identity.

## Prediction and correction

For a program-controlled role, retain successful output intervals
`[accepted_at, accepted_at + ttl]` with the effective stick direction after
basis, normalization and slew limiting. A newer write truncates the older
interval. Replay only elapsed, non-overlapping intervals from the last real
visual anchor, never the full intended command duration:

`p-(t) = p_anchor + sum(B_role * u_effective * dt)`

`P-(t) = P_anchor + sum(Q_motion(dt, calibration_quality, wall_context))`

The PoE2 composition converts an actual output axis vector back to canonical
native movement direction. Until an empirically calibrated matrix is usable,
use the measured role speed gain with the native direction and conservatively
large process noise. Predicted samples have their own source and cannot update
velocity calibration, contact evidence, no-progress counters, or visual TTL.

A new identity-validated visual marker is mapped through the same-frame wall
registration. At its capture time, compare it with the replayed prediction:

`innovation = z - p-`, `S = P- + R_marker + R_registration`,
`d2 = innovation.T * inverse(S) * innovation`.

Reject impossible identity/geometry jumps; otherwise apply the existing gated
position estimator's correction. Retain later command intervals and replay to
the control time. Do not label a predicted arrival as a confirmed arrival.

## Recovery states

`TRACKED -> PREDICTED -> ACTIVE_RECOVERY -> REANCHOR -> TRACKED`. The transition
depends on evidence and uncertainty, not a fixed marker-missing timer. With
fresh trusted wall registration, a hidden program role continues with short
collision-checked pulses along the existing route. The local candidate
controller evaluates progress, raw-wall walkability, clearance, reversal and
uncertainty; it does not dilate the full map. A hidden manual leader retains the
last trustworthy target without pretending to know new motion. Its marker
reappearance or a same-instance remote coordinate replaces that target.

Only real visual progress can prove a stall/contact. Missing visual feedback
cannot itself increment wall-contact evidence. High covariance, possible
arrival, lost wall registration, changed map/identity, repeated rejected marker
observations, or exhausted safe candidates request the existing one-shot
memory/visual re-anchor. Preserve the target and resume from a newly validated
same-instance state. When no source can bound position, release input rather
than continuing indefinitely in an unknown direction.

## Validation

First replay synthetic and archived marker dropouts with fake output, including
overlapping writes, TTL expiry, delayed visual frames, independent P1/P2 loss,
manual leader loss, no false collision/arrival, map change, and re-anchor
deduplication. Then shadow-compute against live frames without sending input.
Only a user-started later gamepad experiment can establish real movement.
Log source, anchor/frame age, output interval, effective axes, predicted point,
covariance/uncertainty, observation gate and recovery decision per role.
