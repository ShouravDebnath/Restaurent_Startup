# Phase 4 dependency installation review

**Implementation outcome:** SHA256-checked wheels were installed without dependency upgrades or global installs. OpenCV reports 4.13.0 with FFmpeg enabled. Seven exact additions are recorded below. The editable metadata/console shortcut refresh was blocked by missing setuptools; the founder declined that extra installation and chose the verified `python -m restaurant_edge.cli` command. No setuptools was installed in the project `.venv`. The API image constrains the existing 31 runtime package versions; no OpenCV/cloud video dependency or new RTSP server image was added. Original review-time statements below describe the pre-install assessment.

**Date:** 2026-11-08, Asia/Dhaka. **Status:** The founder approved and the seven exact project-only additions were installed. All earlier host package versions are preserved.

The pip dry run accepted the Windows AMD64 wheels and current Python 3.14 environment. It selected only these seven additions; existing NumPy 2.5.4, API, testing and web packages need no upgrade/downgrade. Actual generated MP4 decoding and a temporary Windows Credential Locker write/read/remove canary passed after installation.

| Package | Exact proposed version | Declared license | Purpose |
| --- | --- | --- | --- |
| opencv-python-headless | 4.13.0.92 | Apache-2.0; packaging/third-party notices also apply | Decode video, generate synthetic MP4, JPEG preview |
| keyring | 25.7.0 | MIT | Windows-backed private camera credential storage |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | Required Windows access for keyring |
| jaraco.classes | 3.4.0 | MIT, package classifier | Required keyring support |
| jaraco.context | 6.1.2 | MIT | Required keyring support |
| jaraco.functools | 4.6.0 | MIT | Required keyring support |
| more-itertools | 11.2.1 | MIT | Required supporting dependency |

Version-specific PyPI metadata, resolver report and wheel SHA256 values are retained privately under `.secrets/phase4-*`. No package was installed to perform this review. A newer OpenCV 5.x release exists; the proposal deliberately selects the reviewed 4.x interface instead.

A read-only OSV query on 2026-11-08, Asia/Dhaka found **no reported PyPI advisories for these seven exact versions**. This is not a complete audit of bundled native codecs/FFmpeg and is not a security certification. Video readers will still require process isolation, restricted inputs/resources and redacted native output.

Official references: [OpenCV packaging/license notices](https://github.com/opencv/opencv-python#licensing), [keyring/Windows backend](https://keyring.readthedocs.io/en/latest/), [OSV API](https://google.github.io/osv.dev/api/). OpenCV wheels bundle FFmpeg with its own LGPL notice and additional third-party notices; a separate FFmpeg/system runtime install is not proposed. Preserve all applicable notices and record actual decoder build information after installation.

Approval is requested only for the seven pinned project `.venv` additions, plus updating the existing editable edge package's declared dependency metadata after the feature files are prepared. No global installation, npm upgrade, detector/model, system Python, standalone FFmpeg or extra RTSP test-server image is included. API/web image rebuilds later use existing declared dependencies; no new cloud video dependency is needed.
