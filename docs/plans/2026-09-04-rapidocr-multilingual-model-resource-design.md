# RapidOCR Multilingual Model Resource Design

## Decision

Use the explicitly installed `rapidocr.ppocr-v6-multilingual-small` recognition
model for OCR profiles that must read Traditional Chinese. It is the
`PP-OCRv6_rec_small.onnx` asset from the RapidOCR v3.9.2 catalog.

The project does **not** make it the import-time default, bundle its ONNX binary
in Git, or add it to the base runtime. A model is an optional provider resource:
an application chooses it during composition, then gives the verified
`engine_options` to the existing `RapidOcrProvider`.

## Why this model

The previous bundled recognition asset is the Chinese PP-OCRv4 model. Its
character list omits `異`, which caused the generated phrase `進入異界地圖` to be
read incorrectly. The chosen multilingual small model has a larger character
set, includes `異`, and correctly read both generated Traditional Chinese lines
in the project virtual environment:

```text
開始儀式
進入異界地圖
```

The test also asserts location boxes, so it covers the needed contract—text and
geometry—not merely a text string. On the current Windows machine the complete
two-line test took about 1.6 seconds including backend setup; normal callers
reuse one provider instance and therefore do not pay model construction for
every frame. Configure an ROI in each OCR algorithm instance when a scene has a
stable text region.

## Resource boundary

```text
named model ID + source URL + SHA-256
  -> explicit installer downloads to a local ignored directory
  -> resolver checks the same SHA-256 and returns copied engine options
  -> RapidOcrProvider(engine_options=...)
  -> OcrSpan(text, original-frame bbox, confidence)
  -> ProviderBackedOcrDetector text predicate
  -> TargetDetection
```

`core/perception/providers/rapidocr_models.py` owns the first two runtime-safe
steps only. It contains no game terms, profile matching policy, screen capture,
coordinate mapping, click, or workflow behavior. `RapidOcrProvider` remains
responsible only for lazy local inference and geometry normalization.

## Installation

The model directory is intentionally ignored by Git. From the project virtual
environment, install the model explicitly:

```powershell
D:\ACloud\.venv\Scripts\python.exe utils\install_perception_ocr_model.py `
  --model rapidocr.ppocr-v6-multilingual-small `
  --destination assets\perception_models
```

The installer writes to a temporary file in the target directory, validates its
SHA-256, and only then atomically replaces the final file. A failed network
request or checksum failure never overwrites an existing model file. Re-running
the command returns immediately when the existing asset already verifies.

The manifest source URL and SHA-256 are public, versioned metadata:

```text
URL: https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv6/rec/PP-OCRv6_rec_small.onnx
SHA-256: 6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884
```

## Application composition

The model is selected once by the host/application composition layer, not by an
OCR profile's per-frame `language` field. `language` is only an optional label
on emitted results and never loads or switches a model.

```python
from core.perception.builtins import create_ocr_detector
from core.perception.engine import PerceptionEngine
from core.perception.providers import (
    RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
    RapidOcrProvider,
    resolve_rapidocr_engine_options,
)

engine_options = resolve_rapidocr_engine_options(
    RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
    "assets/perception_models",
    overrides={"intra_op_num_threads": 4, "inter_op_num_threads": 1},
)
ocr_provider = RapidOcrProvider(engine_options=engine_options)
engine = PerceptionEngine(
    algorithm_factories={
        "ocr": lambda parameters: create_ocr_detector(parameters, ocr_provider=ocr_provider),
    }
)
```

`rec_model_path` cannot be overridden through the resolver: overriding it would
evade the selected manifest's integrity check. Other RapidOCR construction
options may be copied into `overrides`, so the host can tune its own hardware
without changing the generic detection or workflow architecture.

## Validation

- Offline tests cover unknown model IDs, absent/corrupt assets, copied thread
  overrides, protected recognition paths, atomic replacement, failed download
  preservation, and direct execution of the installer script.
- An optional integration test runs only when RapidOCR, the locally installed
  model, and the Windows Traditional Chinese font are present. It renders the
  two phrases above and checks exact recognition plus plausible full-frame
  bounding-box locations.
- The optional dependency remains in `requirements-ocr.txt`; importing
  `core.perception` never downloads or initializes this model.
