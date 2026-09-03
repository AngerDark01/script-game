# RapidOCR Text-Location Provider Design

## Goal

Provide a fast, local OCR implementation for the generic perception architecture. Given a full game frame or an optional rectangular region, it must recognize visible text and return the text's position in the original frame. The provider adds no game target rules, coordinate mapping, clicking, GUI dependency, or workflow action.

## Why RapidOCR

RapidOCR ONNX Runtime is the first concrete backend because it runs locally on CPU, is available for the project Python/Windows environment, returns both text and quadrilateral geometry, and can keep one ONNX model instance in memory between frames. This avoids spawning a Tesseract process for every frame while keeping the core independent of PaddleOCR or a mandatory ML stack.

The backend is optional. `requirements.txt` remains unchanged; users that need OCR install `requirements-ocr.txt` in the project virtual environment.

## Runtime Composition

```text
FrameContext(image, coordinate_space)
  -> RapidOcrProvider.recognize(frame, provider_parameters)
       -> optional ROI crop
       -> cached RapidOCR ONNX inference
       -> text polygon + confidence
       -> offset local polygon back to full-frame coordinates
       -> OcrSpan(text, BoundingBox, coordinate_space, confidence)
  -> ProviderBackedOcrDetector text predicate
  -> TargetDetection
  -> existing runner / fusion / confirmation / selection
```

The application owns one `RapidOcrProvider` instance and injects it into the existing OCR factory seam. Profiles still contain only serializable data; they never contain an OCR engine object.

```python
from core.perception.builtins import create_ocr_detector
from core.perception.engine import PerceptionEngine
from core.perception.providers import RapidOcrProvider

ocr_provider = RapidOcrProvider()
engine = PerceptionEngine(
    algorithm_factories={
        "ocr": lambda parameters: create_ocr_detector(parameters, ocr_provider=ocr_provider),
    }
)
```

## Provider Parameters

These values live inside an OCR algorithm instance's existing `provider_parameters` mapping:

```json
{
  "text_query": "Enter Map",
  "match_mode": "contains",
  "min_ocr_confidence": 0.80,
  "provider_parameters": {
    "roi": {"left": 380, "top": 240, "width": 880, "height": 320},
    "language": "en",
    "backend_options": {"use_cls": false, "text_score": 0.70}
  }
}
```

- `roi` is optional. It accepts a `BoundingBox`, a JSON four-item array, or a JSON object with `left`, `top`, `width`, and `height`. It is clipped to the source image before inference; all emitted boxes are translated back to the source coordinate space.
- `language` is an optional result label. Model/language initialization is a composition-time decision through `RapidOcrProvider(engine_options=...)`; this label does not silently swap models per frame.
- `backend_options` is a copied mapping passed to RapidOCR's documented call options such as `use_det`, `use_cls`, `use_rec`, `box_thresh`, `unclip_ratio`, `text_score`, and `return_word_box`.

Unknown provider parameters, malformed polygons, invalid numeric timings/confidences, empty text, non-intersecting ROI values, and an unavailable backend raise explicit provider errors. `DetectorRunner` already isolates such an algorithm-instance error from other configured detectors.

## Performance and Threading Rules

- The optional package is imported only when the first frame is recognized.
- The `RapidOCR` object is constructed once and cached per `RapidOcrProvider`; no model or process startup happens in subsequent frames.
- RapidOCR mutates a small amount of backend threshold state when call options are supplied, so initialization and one backend invocation are protected by a provider-local re-entrant lock. Parsing and `OcrSpan` construction happen after the lock is released.
- Use ROI for fixed text zones such as a portal label or objective header. Use the full frame when a scene first needs broad discovery. Both paths return the same full-frame `BoundingBox` contract.
- Thread settings remain a composition-time knob rather than a hard-coded machine assumption. On the current Windows CPU, the generated 900×260 `ENTER MAP` smoke image measured about 3.09 s warm with the library default and 0.72 s warm with `engine_options={"intra_op_num_threads": 4, "inter_op_num_threads": 1}`. This is an environment-specific baseline, not a cross-machine SLA; record real-game timings before choosing a profile default.

## Verification

`tests/test_perception_rapidocr_provider.py` covers lazy backend construction, lazy engine-option application, standard polygon-to-box conversion, ROI crop/coordinate restoration, provider parameter isolation, malformed backend output, missing optional dependency behavior, and the full provider-to-adapter-to-detection chain. It also runs a real RapidOCR smoke test on a generated image containing `ENTER MAP` whenever the optional package is installed.

The real smoke test verifies both text content and a plausible image-space box; it does not use desktop capture or a game client.
