# Phase 5 dependency and model acquisition review

> **Approved RF-DETR acquisition/tooling executed — 2026-11-08:** After the concrete follow-up review, the founder separately approved the official Nano native checkpoint and the exact isolated 65-package exporter. [PHASE_05.md](phase_explanations/PHASE_05.md) records successful installation/import/export/numerical checks and genuine CPU inference on generated input. The working `.venv` retains only its original three approved runtime additions; setuptools/export tools live in the separate ignored environment. No other weights, real footage, npm or global software was acquired/installed. The prior review below remains historical, and the YOLOX hold is unchanged.

> **RF-DETR follow-up, 2026-11-08:** The founder requested RF-DETR Nano as the next candidate and confirmed real-person footage evaluation must remain pending. [The new concrete review](PHASE_05_RFDETR_REVIEW.md) records its official model-specific Apache-2.0 evidence, native artifact/checksum, CPU/export proposal, 65-package isolated-export lock and separate download/installation approval gates. No weights were downloaded and no packages were installed; the dry run cached package archives for review. The YOLOX review and original approvals below are retained as history; that download hold remains in force.

**Date:** 2026-11-08. **Current decision:** the founder approved the three exact project-only packages below; installation and `pip check` passed. The founder explicitly held the model download until weight licensing is clarified. No YOLOX weights were acquired. The preparation/dry-run evidence below preserves its original review context.

The founder approved Phase 5 architecture, YOLOX-Tiny as the initial CPU candidate, and **synthetic footage only**. Real-person footage, training and commercial deployment remain unapproved. The later RF-DETR review request does not itself authorize its weight download or package installation; see the follow-up above.

The installed ORT version imports successfully and reports its CPU execution provider. Exact YOLOX graph loading/pretrained inference remain **unverified and blocked by the model hold**; package import is not model compatibility proof. See [the actual Phase 5 work record](phase_explanations/PHASE_05.md).

## Exact project-only package additions

The existing Windows CPython 3.14 environment resolved this binary-only pip dry run without replacing any existing packages:

| Package | License | Selected wheel SHA256 |
| --- | --- | --- |
| `onnxruntime==1.31.1` | MIT | `0a3998e18cb667ef54287556bd62291a788ed235723dd90c83b2294b24e71d81` |
| `protobuf==7.36.2` | BSD-3-Clause | `a300819d441e078a5608c0d3c709796bb548136058fda017ae51d425b44fd353` |
| `flatbuffers==25.12.19` | Apache-2.0 | `7634f50c427838bb021c2d66a3d1168e9d199b0607e6329399f04846d42e20b4` |

Existing NumPy/packaging satisfy the remaining runtime requirements. The wheels are Windows AMD64 CPython 3.14 for ORT, CPython stable-ABI Windows AMD64 for protobuf, and pure Python for flatbuffers. Public metadata and a dry run do not prove a successful native import/inference; those tests follow installation approval.

OSV exact-version queries returned no listed advisories for these three versions at the recorded check. This is not a complete native-code audit or a guarantee against undiscovered defects. Evidence stays in private `.secrets/phase5-dependency-review.json` and the pip report. Sources: [ORT release](https://pypi.org/project/onnxruntime/1.31.1/), [protobuf release](https://pypi.org/project/protobuf/7.36.2/), [flatbuffers release](https://pypi.org/project/flatbuffers/25.12.19/), [OSV API](https://google.github.io/osv.dev/post-v1-query/).

If approved, install only these exact wheels into the existing project `.venv`, record the before/after distribution list and run import, `pip check`, regression and inference checks. Do not refresh editable metadata, install setuptools, add PyTorch/ONNX/export tools, install globally, alter npm, drivers or Docker images. Preserve the existing environment; any incompatibility requiring a replacement package needs further approval. Rollback would be separately reviewed rather than automatically uninstalling packages or deleting the environment.

## Exact proposed model

- Official publisher: Megvii-BaseDetection/YOLOX.
- Release: `0.1.1rc0`; asset ID `42724912`, `yolox_tiny.onnx`, **20,219,662 bytes**, asset last updated 2021-08-18.
- [Official download](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx), linked from the [publisher's ONNX guide](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/demo/ONNXRuntime/README.md).
- Input expected from the official demo: BGR, float32 NCHW, 416-square letterbox with upper-left placement/padding 114, no generic RGB/255 normalization. Exact tensors/output decode/opset must be verified after an approved download.
- GitHub reports no publisher digest for this legacy asset. Compute SHA256 after an approved HTTPS acquisition, record source/asset metadata, and pin that local artifact hash. A self-computed hash provides later integrity checking, not independent authentication.
- Keep weights and provenance private under ignored `.secrets/phase5/models/`. No automated runtime download, public redistribution, training or other model acquisition.

## Licensing finding that needs an explicit decision

The [official repository license](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE) is Apache-2.0. However, the release body/asset metadata do not separately identify a license grant for this pretrained weight file. An [upstream question about weight licensing](https://github.com/Megvii-BaseDetection/YOLOX/issues/1865) remains open with no maintainer clarification found in this review. Third-party statements are not a substitute for publisher evidence.

**Commercial clearance is therefore unresolved.** Do not describe these weights as commercially cleared, redistribute them, or use them for a pilot/public deployment based on this review. Retain upstream attribution/license material if acquisition is approved; that alone does not resolve the missing weight-specific statement.

The approved plan says to stop an artifact path whose weight rights cannot be documented. The founder may keep that gate closed, or explicitly approve an exception for **private local experimental evaluation only**, understanding this uncertainty. Such an exception would authorize acquisition/use for the local tests, not establish legal rights or commercial clearance. No licensing inquiry is sent on the founder's behalf.

RF-DETR Nano remains an optional separately approved alternative. Its clearer published model terms do not authorize silently changing the selected candidate, installing its export stack, or downloading it.

## Footage and verification boundary

The founder selected existing/generated synthetic footage only. Do not open `references/SR.mp4` or other real-person recordings. A real pretrained model running on geometric synthetic frames verifies actual runtime execution and negative-input behavior; it does **not** establish positive person recall, real table assignments or restaurant occupancy accuracy. Those evaluations must remain explicitly pending.
