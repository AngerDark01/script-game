# Third-party components in AutoModules offline distribution

This package contains unmodified upstream runtime libraries. Their licenses remain
applicable independently of the AutoModules application. Wheel metadata, RECORDs
and bundled notices are retained under `python/Lib/site-packages`.

## Python and Python dependencies

CPython 3.12.10: https://www.python.org/downloads/release/python-31210/
License: `python/LICENSE.txt` (PSF and incorporated software notices).
Exact dependency versions and file hashes: `release-manifest.json`.

PySide6 Essentials and shiboken6 6.10.1, Qt 6.10.1:
LGPL-3.0 option; see `LGPL-3.0.txt` and `GPL-3.0.txt` (incorporated terms).
Source and build instructions:
https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.1-src/
https://download.qt.io/official_releases/qt/6.10/6.10.1/submodules/
https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.10.1
https://doc.qt.io/qtforpython-6/gettingstarted/index.html
Libraries are dynamically linked and separately replaceable. Users may modify or
replace LGPL libraries and reverse-engineer the application as needed to debug
those modifications. No signature enforcement is applied to these libraries.
Qt Addons are not distributed. Qt's third-party attributions are documented at
https://doc.qt.io/qt-6.10/licenses-used-in-qt.html and in the corresponding source.

Microsoft Visual C++ redistributable DLLs supplied by the PySide6 Essentials wheel
are also copied beside Python to support ONNX-first loading on clean Windows.
The manifest records original wheel paths and hashes; CPython's existing runtime
is retained. These DLLs are Microsoft runtime components, not LGPL Qt code.
Applicable redistribution terms: https://visualstudio.microsoft.com/license-terms/vs2022-cruntime/

NumPy, OpenCV, ONNX Runtime, Pillow, PyYAML, Shapely, pyclipper, PyDirectInput, mss,
protobuf, flatbuffers, packaging, six, tqdm and colorama keep their upstream
license files in their installed distributions. Consult their METADATA and the
release manifest for exact versions and project URLs.

## OCR models

RapidOCR 1.4.4: https://github.com/RapidAI/RapidOCR (Apache-2.0).
PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR (Apache-2.0), see
`PaddleOCR-Apache-2.0.txt`.
The extra `PP-OCRv6_rec_small.onnx` is from RapidAI/RapidOCR ModelScope revision
v3.9.2. Its repository model card explicitly declares Apache License 2.0; the
downloaded card is included as `RapidOCR-model-card.md`.
Source: https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv6/rec/PP-OCRv6_rec_small.onnx
SHA256: 6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884
Card: https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/README.md

## Native host and launcher

.NET runtime and Windows Desktop runtime 8.0.30: MIT, see
`dotnet-runtime-LICENSE.txt`, `dotnet-runtime-NOTICES.txt`, and
`dotnet-windowsdesktop-LICENSE.txt`.
Source: https://github.com/dotnet/runtime/tree/v8.0.30
https://github.com/dotnet/windowsdesktop/tree/v8.0.30

Nefarius.ViGEm.Client 1.21.256: MIT, see `ViGEm.NET-LICENSE.txt`.
Source: https://github.com/nefarius/ViGEm.NET
LiteNetLib: see `host/LanInputSync.NOTICES.md` and accompanying host notices.

ViGEmBus 1.22.0 official installer: BSD-3-Clause, see `ViGEmBus-LICENSE.txt`.
Source: https://github.com/nefarius/ViGEmBus/tree/v1.22.0
Release: https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0
The installer remains unmodified and signed by Nefarius Software Solutions e.U.
ViGEmBus is an archived upstream project; compatibility with future Windows
versions or games is not guaranteed.

Inno Setup 6.7.1: https://github.com/jrsoftware/issrc/tree/is-6_7_1
Compiler is a build-time tool and not installed with the workbench.
