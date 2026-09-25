# PoE2 Offline Localization Probe

This experiment diagnoses saved PoE2 minimap/terrain pairs without running the
game or changing the production localization runtime.

Run against the newest readable sample:

```powershell
& D:/ACloud/.venv/Scripts/python.exe D:/ACloud/auto_modules/tools/debug/poe2_live_terrain_localization_probe.py
```

Run against one explicit sample and override recognizer parameters:

```powershell
& D:/ACloud/.venv/Scripts/python.exe D:/ACloud/auto_modules/tools/debug/poe2_live_terrain_localization_probe.py `
  --sample D:/ACloud/auto_modules/data/poe2_live_terrain_test/samples/<sample> `
  --set player_clear_radius=26 `
  --set edge_weight=36
```

The probe writes `report.json`, stored/rebuilt/cleaned feature images, terrain
edges, individual candidate overlays, and a candidate sheet under
`data/poe2_live_terrain_test/probe_results/`. Green pixels are transformed
minimap evidence, blue pixels are terrain edges, yellow pixels overlap, and the
red cross is the candidate player position. `candidate_map.png` marks all
spatially distinct candidates on the full terrain.

The algorithm is intentionally experimental:

1. Replay the saved `HSVRecognizer` profile against `raw.png`.
2. Clear the configured player center and reject compact non-map components.
3. Recover the local walkable side from the player seed and closed screenshot
   boundary; require candidate player and visible walkable pixels to agree with
   the native terrain walkable mask.
4. Search 45-degree rotations, reflection, and scale on a coarse terrain grid.
5. Refine the strongest seeds at full terrain resolution with small angle and
   scale offsets.
6. Rank spatially distinct candidates using forward Chamfer coverage, mean
   edge distance, and reverse coverage.
7. Reject the result when the best template is too small, its score is below
   the configured threshold, or the top-two score margin is ambiguous.

Do not copy this file into the production runtime until several maps and
several positions per map demonstrate a stable winner and useful score margin.
