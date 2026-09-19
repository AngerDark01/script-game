# Portal Main-View Detector Assets

`blue_glow_detector_v1.json` stores the probe parameters verified against the live Torchlight: Infinite game window on 2026-05-22.

The detector is not YOLO-based. It captures the main game view, extracts cyan/blue/violet glowing pixels, groups contours, then accepts only candidates that are large, near-round, and sufficiently filled by glow. In the verified probe run, the real portal was the only strict accepted candidate; UI icons, blue machinery, and monster ice glow stayed as below-threshold diagnostic candidates.

Expected behavior:

- When the real portal entity is visible, it should be the only green/accepted candidate.
- When the portal entity is outside the view or blocked, zero accepted candidates is correct; orange/below-threshold boxes are diagnostic only.
- This detector should be used as a second-stage confirmation after the minimap icon detector has indicated that a portal event exists nearby.

Use with:

```powershell
D:\ACloud\.venv\Scripts\python.exe utils\portal_screen_probe.py --params assets\event_detectors\portal\main_view\blue_glow_detector_v1.json --output-dir debug\portal_screen_probe\run_params
```
