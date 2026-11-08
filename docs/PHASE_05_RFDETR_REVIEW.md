# Phase 5 RF-DETR Nano: acquisition and CPU integration review

**Review date:** 2026-11-08. **Current status:** the founder separately approved the native checkpoint download and isolated 65-package installation. Acquisition, safe offline export, numerical checks and genuine CPU inference on generated inputs now pass; see [the implementation record](phase_explanations/PHASE_05.md) and the executed follow-up below. Person-footage evaluation remains pending. Sections 1–9 and the package appendix preserve the concrete pre-approval proposal and its dated checks; statements about awaiting approval describe that earlier review.

The founder requested RF-DETR Nano as the next real detector candidate. The founder also confirmed that no authorized local recording of people is available: keep person-footage evaluation pending and do not open `references/SR.mp4` or other recordings. The earlier YOLOX download hold remains in force. This proposal does not authorize Phase 6, a commit, a push, a deployment or training.

## Recommendation in plain English

Use the official RF-DETR Nano detection checkpoint, convert it locally to ONNX in a separate project export environment, and run that exported file through the existing ONNX Runtime CPU environment. An export changes the file format; it does not train a new model. The operational API, dashboard, database and existing Python environment do not need a new model framework.

RF-DETR Nano has explicit publisher evidence covering its pretrained detection model under Apache-2.0. Its standard checkpoint cannot run directly in ONNX Runtime. The conversion tools are considerably larger than our runtime and need separate installation approval. Successful package resolution is not a successful model export or inference test.

After approval, real pretrained inference on geometric synthetic frames can verify loading, processing, failure handling and CPU resource use. Those frames contain no people: they cannot verify positive person detection, false-negative rate, seating assignment accuracy or restaurant occupancy quality.

## 1. Official model, exact artifacts and checksums

### Proposed acquisition: native publisher checkpoint

| Item | Reviewed value |
| --- | --- |
| Publisher / variant | Roboflow, RF-DETR **Nano detection**, COCO-pretrained; not segmentation, Keypoint, Plus or NAS |
| Export package | `rfdetr==1.12.0`, published 2026-11-06 |
| Pinned source revision | `639eac4555ceb89ef399ccda3fde716bbcfe34cb`, tag `1.12.0` |
| Registry name | `rf-detr-nano.pth` (`ModelWeights.RF_DETR_NANO`) |
| Exact official source | [Publisher checkpoint](https://repo.roboflow.com/rfdetr/nano_coco/checkpoint_best_regular.pth) |
| HTTP HEAD size | **366,287,238 bytes** (349.32 MiB); HEAD retrieves headers, not model contents |
| Publisher MD5 | `fb6504cce7fbdc783f7a46991f07639f`, matching the pinned registry, ETag and storage MD5 header |
| Storage generation / last modification | `1753203874837584`; 2025-07-22 17:04:34 GMT |
| Native checkpoint SHA256 | **Not published in the reviewed native registry; not locally computed because downloading is not approved** |
| Proposed private destination | `.secrets/phase5/models/rfdetr-nano/native/rf-detr-nano.pth` |

The [pinned upstream weight registry](https://github.com/roboflow/rf-detr/blob/639eac4555ceb89ef399ccda3fde716bbcfe34cb/src/rfdetr/assets/model_weights.py) defines that exact URL and MD5. The [release](https://github.com/roboflow/rf-detr/releases/tag/1.12.0) contains package assets, not an official Nano ONNX asset. No publisher-hosted Nano ONNX file was identified in the reviewed registry, release assets or export instructions; community exports are not being substituted.

After acquisition approval, download only this checkpoint over HTTPS with a size bound, check the exact byte count and published MD5, compute SHA256 before loading, and retain the URL/headers/date/hash privately. MD5 is a legacy integrity check, not modern collision-resistant authentication. A newly calculated SHA256 pins the acquired bytes for future runs; it does not independently authenticate the publisher. Stop if the size, registry digest or source changes. Do not guess a SHA256 or treat an ETag as SHA256.

The generated `rfdetr-nano.onnx` will need its **own** byte count, SHA256, tensor contract, opset, class layout and export recipe. Its hash does not exist yet. No runtime catalog entry may be marked verified before these checks actually pass.

### Official alternative inspected, not selected for download

The publisher also hosts a converted [Hugging Face Nano model](https://huggingface.co/Roboflow/rf-detr-nano/tree/9f201577d9415f0378084748d27e68586e6b3600). Its metadata identifies:

- Revision: `9f201577d9415f0378084748d27e68586e6b3600`.
- File: `model.safetensors`, **121,926,336 bytes**.
- Publisher-hosted LFS SHA256: `497b1dbcc8f9d115b806fb82d140d7e22e5b5c3fba45abefef39dd4f99c1f737`.
- Separate `config.json` and `preprocessor_config.json`, with an Apache-2.0 model-card tag.

Only model-card/configuration metadata was inspected. This file is neither ONNX nor byte-identical to the native checkpoint. Its Transformer conversion/export path needs its own parity checks; its SHA256 must not be assigned to the native `.pth` file. Prefer the native checkpoint and publisher exporter for this milestone. Download approval for the native proposal does not include this alternative or a DINOv2 backbone download.

## 2. Commercial licensing and required notices

The [publisher's pinned licensing statement](https://github.com/roboflow/rf-detr/blob/639eac4555ceb89ef399ccda3fde716bbcfe34cb/docs/snippets/license-rfdetr.md) explicitly covers the `rfdetr` code and **Nano, Small, Medium and Large detection models** under Apache-2.0, including commercial closed-source and self-hosted use without a model license fee. This supplies the model-specific evidence missing from the earlier YOLOX review. Atto/Femto/Pico/XL/2XL detection and NAS have different Platform Model License terms and are outside this proposal.

The [Apache-2.0 license](https://github.com/roboflow/rf-detr/blob/639eac4555ceb89ef399ccda3fde716bbcfe34cb/LICENSE) requires retaining the applicable license, copyright and attribution material, marking modifications where required, and preserving applicable NOTICE material when supplied. It does not grant trademark endorsement. Keep the upstream model/code attribution, source revision, conversion record and full license with the private artifact and any eventual distribution. The pinned repository has no root `NOTICE`; the reviewed `rfdetr` wheel supplies its license, with no separate NOTICE identified. Do not invent a publisher NOTICE or remove notices from bundled dependencies.

Review evidence includes all 65 selected wheel archives' notice-file inventories, without installing/importing them. Some metadata uses classifiers instead of SPDX expressions. Tokenizers, flatbuffers and tqdm lack a separately named license file in these reviewed wheels; their exact-version upstream license texts were retrieved separately. Most software uses permissive Apache/MIT/BSD/PSF terms, but **certifi uses MPL-2.0**, **tqdm uses MPL-2.0 and MIT**, regex has Apache/CNRI terms, and native wheels contain additional third-party terms. Preserve full texts; do not describe the complete toolchain as exclusively Apache-2.0.

PyTorch's wheel includes many native-library licenses; ORT has `ThirdPartyNotices.txt`, and OpenCV includes third-party/FFmpeg notices. PyAV adds another native codec stack to the isolated exporter through Supervision's dependencies. Package-level OSV/license metadata is not a complete codec, patent or native-binary audit. These exporter dependencies are not proposed for distribution with the runtime or for processing private recordings. A later distribution must carry the actual applicable notices and receive its own dependency/native-code review. COCO pretraining does not grant rights to restaurant footage, people or a downloaded evaluation dataset.

Sources for separately retained texts: [Tokenizers v0.23.3](https://github.com/huggingface/tokenizers/blob/v0.23.3/LICENSE), [Flatbuffers v25.12.19](https://github.com/google/flatbuffers/blob/v25.12.19/LICENSE), [tqdm v4.70.1](https://github.com/tqdm/tqdm/blob/v4.70.1/LICENCE).

## 3. CPU and existing environment compatibility

The current host actually imports **Python 3.14.0, ONNX Runtime 1.31.1, NumPy 2.5.4 and OpenCV 4.13.0**. ORT reports `CPUExecutionProvider` (and another installed provider); our adapter explicitly selects CPU. No NVIDIA GPU is assumed. The recorded host has an i5-8265U, four cores/eight logical processors and about 15.9 GiB RAM.

The [publisher supports CPU ONNX inference](https://rfdetr.roboflow.com/latest/cookbooks/export-cpu/). The proposed export is a batch-one, static 384-square FP32 detector, ONNX opset 17, using the standard ONNX graph rather than a CUDA/TensorRT engine. Existing ORT is a plausible runtime without additional runtime packages. **Exact graph loading, supported kernels, class mapping, numerical parity, speed and memory are unverified until approved acquisition/export and actual tests.** No compatibility claim rests on package version numbers alone.

The installed runtime cannot export the PyTorch checkpoint. A Windows/Python 3.14 binary-only dry run for `rfdetr[onnx]==1.12.0` resolves successfully with 65 exact distributions, including Torch 2.15.0, TorchVision 0.29.2, Transformers 5.22.2 and ONNX 1.23.2. Native import/ABI compatibility still needs testing. The publisher's [exporter](https://github.com/roboflow/rf-detr/blob/639eac4555ceb89ef399ccda3fde716bbcfe34cb/src/rfdetr/export/_onnx/exporter.py) explicitly selects legacy `dynamo=False`; this proposal adds no onnxscript, CUDA, OpenVINO, training, Plus, inference server or hosted SDK extra.

## 4. Exact dependency installation proposal

Create an isolated environment at **`.cache/phase5-rfdetr-export/.venv`** using the existing Python. Install only the **65 pinned Windows wheels** in [the proposed hash-locked requirements](../services/edge-agent/requirements-phase5-rfdetr-export-windows.txt), using binary-only, no-dependency-expansion and hash verification. The requirements file is a review artifact, **not evidence of installation**. Windows/Python 3.14 is the reviewed platform; the lock is not a Linux/container recipe.

The complete resolved wheel set is **314.9 MiB compressed**; the separate native model is 349.32 MiB. The dry run cached package archives to inspect metadata/notices, but installed nothing and acquired no weights. Installed files, caches, export buffers and the generated ONNX file require additional disk/RAM; allow several GiB and check free resources before installation/export. Use existing project tools for metrics; no additional monitoring package is proposed.

**Setuptools 84.2.1 is included because the selected Torch declares it as a dependency.** This requests new approval for this isolated export environment only. The founder's earlier choice to avoid adding setuptools to the working `.venv` or refreshing editable metadata is preserved. No existing environment package would be upgraded or removed, and no global install, driver, Python version or npm change is proposed.

All 65 exact versions were queried through [OSV's batch API](https://google.github.io/osv.dev/post-v1-querybatch/): **zero listed advisories returned** at this review. Wheel hashes match public PyPI metadata. This is a dated database result, not a guarantee of safety or an audit of bundled native libraries. The complete private pip/OSV/source/notices evidence is under `.secrets/phase5-rfdetr-review/`.

Package versions and license summaries follow in the appendix; the linked lock contains every selected wheel SHA256. [RF-DETR release metadata](https://pypi.org/project/rfdetr/1.12.0/), [Torch release metadata](https://pypi.org/project/torch/2.15.0/), [TorchVision release metadata](https://pypi.org/project/torchvision/0.29.2/), [Transformers release metadata](https://pypi.org/project/transformers/5.22.2/) and [ONNX release metadata](https://pypi.org/project/onnx/1.23.2/) support the package selection. The runtime's current pins remain unchanged.

If resolution/import/export requires another version or package, stop that step and request a revised exact approval. Preserve all existing files and environments; do not silently uninstall, delete or replace anything as a rollback. The new environment is isolated so stopping its use leaves the working runtime available.

## 5. Changes needed in the existing replaceable architecture

| Existing component | Proposed targeted change after approval |
| --- | --- |
| `detectors/base.py` | Retain `detect(BGR) -> normalized Person boxes/scores` and `close()`; no geometry/state rewrite |
| `detectors/onnx_detector.py` | Preserve YOLOX adapter; add explicit RF-DETR adapter/factory dispatch and strict model-specific contracts |
| Approval catalog | Allow a reviewed `rfdetr_nano` ID with its own hash, license evidence and verified status; retain path containment/no auto-download. Current catalog accepts only YOLOX |
| Artifact limits | Current 30 MB limit is too small; use a bounded RF-DETR-specific ONNX limit based on the actual export, without allowing arbitrary unlimited models or external tensor files |
| `analysis_config.py` / local editor | Add the explicit model ID and safe model selection; preserve old profile revisions. Current config and JavaScript hard-code YOLOX |
| `analysis.py` | Choose the approved adapter while retaining sibling supervision, one pending frame, permission checks, stale-result rejection and safe cleanup |
| Association/state engine | Reuse existing seating/exclusion regions, ambiguity checks, evidence windows, manual-state precedence and local shadow output |
| Evaluation/metrics | Add opt-in real-model contract/parity/inference/benchmark evidence, separate from fake-detector tests; retain private outputs |

RF-DETR preprocessing differs from YOLOX: convert BGR to RGB, resize directly to 384 × 384 using the publisher's half-pixel bilinear/no-antialias convention, scale by 255, apply ImageNet mean/std and produce float32 NCHW. It is **not** the YOLOX padded BGR input. Verify a lightweight NumPy/OpenCV implementation numerically against the isolated export environment.

The expected raw outputs are normalized `cx,cy,w,h` boxes and class logits. Apply sigmoid and the publisher's top-query/class selection, then filter the confirmed **COCO sparse person class 1**, convert to original-frame normalized corners, clamp and validate. Do not mistake class 0 for person or remove the final COCO class as generic background. Do not add YOLOX NMS to this set-prediction model. Output names/query count/class count remain acceptance checks on the actual graph, not assumed artifact facts. [Publisher preprocessing/inference contract](https://github.com/roboflow/rf-detr/blob/639eac4555ceb89ef399ccda3fde716bbcfe34cb/src/rfdetr/export/_onnx/inference.py), [publisher decoder](https://github.com/roboflow/rf-detr/blob/639eac4555ceb89ef399ccda3fde716bbcfe34cb/src/rfdetr/export/_runtime/decode.py).

Keep the model's score distinct from an occupancy probability. The existing association algorithm can use feet/torso anchors and reviewed seating regions, but actual seated/occluded-person performance is still unknown. Genuine model output must never be routed through DEMO controls or write canonical table states, cleaning tasks or database events during Phase 5. The local synthetic source/grant/tenant/location/role restrictions remain intact.

## 6. Performance and security risks before installation

1. **A bigger model can be slower.** Nano has approximately 30.5 million parameters; the publisher's GPU latency is not a benchmark for this laptop. CPU throughput, sustained thermals and concurrent Docker load must be measured. No FPS or accuracy is promised.
2. **Cold loading and stale results matter.** The current worker has 15-second loading and 5-second outstanding-inference bounds, a default 2-second result-age limit and a 2 FPS sampling target. Benchmark first. Report overload/UNKNOWN rather than accepting stale boxes or silently extending freshness/permission deadlines. If adjustments are necessary, document them and test them separately.
3. **Export tools consume resources.** A 366 MB checkpoint, model copies, ONNX conversion and native caches can use much more memory than the file size. Run one export/one source, bound threads/processes, check resources and measure peak memory. Metadata resolution does not prove that a Windows native DLL import will succeed; any required system runtime installation needs further approval.
4. **Checkpoint deserialization needs care.** Use the pinned upstream safe loader with `weights_only=True` and its narrow namespace allow-list. The reviewed [loader](https://github.com/roboflow/rf-detr/blob/639eac4555ceb89ef399ccda3fde716bbcfe34cb/src/rfdetr/utilities/io.py) defaults to `trust=False`. Do not enable full-pickle fallback; stop and review if safe loading fails. A hash does not turn a native model loader into a security sandbox.
5. **Prevent hidden downloads/network processing.** Explicit local checkpoint path; private caches; offline Hugging Face/Transformers settings and telemetry disabled. The full checkpoint overwrites the backbone; do not let construction fetch separate DINOv2 weights. Export and runtime must fail on unapproved fetches rather than downloading more files. Runtime uses only local model bytes and existing local frame arrays, never a hosted detector. Test these boundaries; Python-level network blocking is not an OS sandbox.
6. **Keep assets and evidence private.** Use ignored `.secrets/`/`.cache/`, no model uploads, video exports or credential-rich exception text. Existing Git rules cover these destinations. A new model grant does not relax preview authorization, session expiry/revocation, tenant isolation or passive-session rules.
7. **Licensing is component-specific.** Retain model/source/exporter/native notices. No new camera-data rights, vendor endorsement, commercial pilot clearance or representative model validation follows from an Apache model license.

## 7. Work and acceptance checks after both approvals

1. Record the current application/environment hashes, package versions, Git state and read-only preservation evidence. Preserve the earlier 413-test record; do not relabel it as a fresh run.
2. After **installation approval**, create the isolated project export environment, install the exact lock, run `pip check` and native imports. Verify the working `.venv` is unchanged. No Docker image change is needed.
3. After **weight approval**, acquire only the selected native artifact; verify size/MD5, compute SHA256 and preserve the upstream license/provenance. No footage download or alternate model is included.
4. Load offline with safe deserialization; export batch-one static FP32 ONNX/opset 17. Validate graph/self-contained tensors and record the full export recipe and new hash. Compare PyTorch/ONNX raw outputs and preprocessing on generated arrays. These are numerical compatibility tests, not accuracy tests.
5. Implement the RF adapter, bounded catalog/config/UI changes and new tests without weakening older paths. Test wrong hashes, shapes/classes, non-finite outputs, missing models and attempted fetches. Keep existing geometry/state tests independent of model installation.
6. Run actual pretrained inference on authorized generated MP4/arrays, with no fake detector injected. Record the model hash, evidence type, person-score outputs and negative-input observations. Do not call empty predictions a proof of high precision or any positive recall.
7. Benchmark one CPU source after warm-up: pre/inference/post/total p50/p95 time, measured completed FPS, input/sample resolution/rate, result age, dropped frames, process current/peak working set and CPU time. Report timed-loop throughput separately from sampled video FPS. Target at least ten minutes of sustained synthetic processing; document the actual duration and any thermal visibility/soak limits.
8. Feed actual model results through the reviewed seating regions and shadow engine on synthetic video; verify no business-state writes. Use separately labeled fabricated boxes for positive geometry/state edge cases. A no-person model run cannot validate positive table association or transition accuracy.
9. Rerun the existing 413 tests plus new cases, affected lint/JavaScript/frontend/browser checks, authorization/isolation/session/revocation/offline/stale-frame/hung-worker/EOF cleanup cases and preservation/secret checks. Keep real-model opt-in tests distinguishable from simulated unit/process/browser tests.
10. Update [PHASE_05.md](phase_explanations/PHASE_05.md), file descriptions, Windows run/test commands and related status documentation with actual results. Stop after this Phase 5 work; do not commit/push or start Phase 6.

## 8. What remains unverified without authorized person footage

Genuine pretrained inference and CPU benchmarking can be completed on synthetic frames after acquisition approval. The founder has explicitly kept the following evaluation pending:

- Positive real-person detection, box recall/precision/AP and false negatives.
- Seated people, staff crossings, occlusion, crowding and difficult restaurant lighting/camera angles.
- Real seating-region assignment, wrong-table associations and multi-table ambiguity rates.
- Real arrival/departure delay, occupancy interval precision/recall, UNKNOWN coverage and staff-state conflict quality.
- Restaurant-specific accuracy, installation thresholds, multi-camera capacity and deployment readiness.

Later evaluation needs expressly authorized representative clips and independent person/table/interval labels. Do not use `SR.mp4`, other existing recordings, internet photographs or a public dataset merely because it is accessible. Neither a published COCO score nor synthetic/fake-box tests substitute for this evaluation.

## 9. Review verification and file purposes

- Read the permanent rules, master specification, handoff, approved Phase 5 plan and Phase 4 explanation; inspected the actual detector/catalog/config/worker/API/editor boundaries.
- Verified official source tag/revision, model registry, model-specific license, HTTP HEAD size/digest and official alternate artifact metadata. **No weight body was retrieved.**
- Binary-only isolated-environment dry run succeeded; 65 exact wheel hashes cross-checked against PyPI; all 65 exact-version OSV queries returned no listed advisories. Inspected cached wheel notice inventories and separately retrieved three missing upstream license texts. No installation or native RF-DETR import occurred.
- Fresh current-runtime import/provider check passed. The **413-test full suite and seven browser groups are the previous implementation's dated results**, not rerun as part of this metadata/document-only review. Run regressions after approved integration.
- The proposed hash-locked requirements passed a second binary-only, no-install dry run selecting exactly 65 packages. Review preservation checks confirm only the seven intended documentation/proposal files changed since this review began, with no application file changes, deletions, runtime distribution changes, staging or HEAD changes. A bounded scan of 148 Git-eligible files against 50 private candidate values found no secret matches; 20 ignore probes, 123 local document links/anchors and `git diff --check` passed. These checks do not guarantee detection of every possible secret.
- `PHASE_05_RFDETR_REVIEW.md` is this concrete proposal; the new export requirements file pins its 65 wheel artifacts; the Phase 5 explanation, existing dependency review, implementation plan, handoff and explanation index link the current approval/evaluation boundaries. Application functionality, database records, credentials and existing work are preserved.

## Appendix: complete reviewed package and license summary

The table below summarizes package-level metadata/notice evidence. It does not replace full license texts or the native-library inventories. The separate hash lock is authoritative for exact selected wheel artifacts. All entries are proposed for the isolated exporter only; none was installed by this review.

| Package | Version | Package license summary |
| --- | --- | --- |
| `annotated-doc` | `0.0.5` | MIT |
| `annotated-types` | `0.8.0` | MIT |
| `anyio` | `4.16.0` | MIT |
| `av` | `19.0.2` | BSD-3-Clause |
| `certifi` | `2026.10.23` | MPL-2.0 |
| `charset-normalizer` | `3.5.2` | MIT |
| `click` | `8.5.1` | BSD-3-Clause |
| `colorama` | `0.4.6` | BSD-3-Clause (wheel text) |
| `contourpy` | `1.4.0` | BSD-3-Clause |
| `cycler` | `0.12.1` | BSD-3-Clause (wheel text) |
| `defusedxml` | `0.7.1` | PSF license |
| `filelock` | `4.2.9` | MIT |
| `flatbuffers` | `25.12.19` | Apache 2.0 |
| `fonttools` | `4.68.0` | MIT |
| `fsspec` | `2026.9.0` | BSD-3-Clause |
| `h11` | `0.16.0` | MIT |
| `hf-xet` | `1.8.0` | Apache-2.0 |
| `httpcore2` | `2.16.0` | BSD-3-Clause |
| `httpx2` | `2.16.0` | BSD-3-Clause |
| `huggingface_hub` | `2.4.0` | Apache-2.0 |
| `idna` | `3.20` | BSD-3-Clause |
| `Jinja2` | `3.1.6` | BSD-3-Clause (wheel text) |
| `kiwisolver` | `1.5.1` | BSD-3-Clause (wheel text) |
| `markdown-it-py` | `4.2.0` | MIT (wheel texts) |
| `MarkupSafe` | `3.0.4` | BSD-3-Clause |
| `matplotlib` | `3.11.2` | PSF-style Matplotlib license; retain full texts |
| `mdurl` | `0.1.2` | MIT (wheel text) |
| `ml_dtypes` | `0.6.0` | Apache-2.0 |
| `mpmath` | `1.3.0` | BSD-3-Clause |
| `networkx` | `3.7` | BSD-3-Clause |
| `numpy` | `2.5.4` | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `onnx` | `1.23.2` | Apache-2.0 |
| `onnxruntime` | `1.31.1` | MIT License |
| `opencv-python-headless` | `4.13.0.92` | Apache 2.0 |
| `packaging` | `26.3` | Apache-2.0 OR BSD-2-Clause |
| `pillow` | `13.0.0` | MIT-CMU |
| `protobuf` | `7.36.2` | 3-Clause BSD License |
| `pydantic` | `2.14.3` | MIT |
| `pydantic_core` | `2.50.4` | MIT |
| `pyDeprecate` | `0.9.0` | Apache-2.0 |
| `Pygments` | `2.21.0` | BSD-2-Clause |
| `pyparsing` | `3.3.3` | MIT |
| `python-dateutil` | `4.0.0` | BSD-3-Clause |
| `PyYAML` | `6.0.3` | MIT |
| `regex` | `2026.11.7` | Apache-2.0 AND CNRI-Python |
| `requests` | `2.34.2` | Apache-2.0 |
| `rfdetr` | `1.12.0` | Apache License 2.0 |
| `rich` | `15.0.0` | MIT |
| `safetensors` | `0.8.0` | Apache-2.0 (wheel text/classifier) |
| `scipy` | `1.18.1` | BSD-3-Clause and bundled terms |
| `setuptools` | `84.2.1` | MIT |
| `shellingham` | `1.5.4` | ISC License |
| `supervision` | `0.31.5` | MIT |
| `sympy` | `1.14.0` | BSD-3-Clause |
| `tokenizers` | `0.23.3` | Apache-2.0 (upstream text/classifier) |
| `torch` | `2.15.0` | Apache/BSD/BSL/ISC/MIT/Zlib; LLVM exception; bundled terms |
| `torchvision` | `0.29.2` | BSD-3-Clause and bundled terms |
| `tqdm` | `4.70.1` | MPL-2.0 AND MIT |
| `transformers` | `5.22.2` | Apache 2.0 License |
| `truststore` | `0.10.5` | MIT |
| `typer` | `0.28.0` | MIT |
| `typing-inspection` | `0.4.5` | MIT |
| `typing_extensions` | `4.16.0` | PSF-2.0 |
| `tzdata` | `2026.6` | Apache-2.0 |
| `urllib3` | `2.8.0` | MIT |

## 10. Executed follow-up after explicit founder approvals

The founder separately approved the native Nano checkpoint download and the exact 65-package isolated exporter. Both operations completed without modifying the working runtime environment. The official native checkpoint passed its approved byte count and published MD5; acquired SHA256 is `d8d6b9ee57d4d0ed2b1f305163624712a0532cb7bce0c747317984fc5457440d`. The accepted `export-v2/rfdetr-nano.onnx` has **107,826,617 bytes** and SHA256 `ea1a44e23d3381b0a2a188e01cf84da67a89a936e118b37047bc7cb0d21320f1`. The private native/export folders retain the full Apache license and provenance; the private catalog references only this accepted ONNX artifact. The alternative Safetensors, separate DINOv2 weights, YOLOX weights and person footage were not downloaded.

The native toolchain imports and `pip check` pass. Export used the exact pinned package, safe checkpoint deserialization (`trust_checkpoint=False`), local caches and Python-level network denial, with zero attempted outbound connections observed. The graph is self-contained FP32/opset 17, input `input [1,3,384,384]`, outputs `dets [1,300,4]` and `labels [1,300,91]`. No external tensor file or custom operator domain was accepted.

The first workflow was rejected when default ORT graph optimization failed a numerical comparison on one generated noise image. The original file/log is preserved. Testing the same graph with **`ORT_DISABLE_ALL`** passed the unchanged criterion. The accepted export and runtime both explicitly use that conservative setting. Across generated 360×640, 97×53 and 384×384 inputs, preprocessing differed by **0**, boxes by at most **0.00007505**, and logits by at most **0.00010682** against PyTorch. These are numerical differences, not accuracy scores or evidence that optimization is always unsafe on every host.

Actual inference then exposed the publisher's reparameterized-box behavior: normalized coordinates mean image-relative units, not guaranteed bounds of 0–1. Uniform generated inputs produced sizes around 1.08 and slightly off-image centers. The [pinned model implementation](https://github.com/roboflow/rf-detr/blob/639eac4555ceb89ef399ccda3fde716bbcfe34cb/src/rfdetr/models/lwdetr.py) computes centers and positive sizes without a final sigmoid in that branch. The adapter now permits bounded off-image raw boxes, rejects non-finite/negative-size/gross outputs, and clips converted corners. Tests cover this genuine contract and invalid values separately.

The new adapter/factory/catalog/config/UI changes are implemented with manager approval for model switches. Existing synthetic-only grants, session expiry/revocation, tenant/location isolation, manual cleaning/blocks and local shadow-only output remain enforced. The full suite passed **445 tests**, one existing warning, **105.65 seconds**; 413 earlier tests remain unchanged. Four opt-in cases use the real model; 28 new constructed-input/permission cases are simulated. Six real-model browser groups and the previous seven no-model browser groups pass, with all browser human authority explicitly simulated. No positive-person or restaurant evaluation has been performed. See [the complete Phase 5 explanation](phase_explanations/PHASE_05.md) for execution commands, benchmark results, preservation checks and remaining evaluation requirements.

The actual ten-minute synthetic benchmark completed **1,184 frames in 600.075 seconds (1.973 FPS)** against a 2 FPS target, missing 17 sample slots without backlog. Sustained inference p50/p95 was **279.18/365.92 ms**; complete detection p50/p95 **331.87/421.09 ms**, maximum **846.22 ms**. The short 50-frame unpaced loop achieved **3.155 FPS**. Final/peak process working set was **380.57/396.28 MiB**, with about 1.40 logical-core equivalents of CPU time during the paced run. No geometric frame produced a person candidate above the 0.05 adapter cutoff. This is negative-only synthetic evidence, not person recall, representative false-positive rate or restaurant accuracy. The paced harness excludes full reader/IPC/browser latency and is not multi-camera or thermal certification.
