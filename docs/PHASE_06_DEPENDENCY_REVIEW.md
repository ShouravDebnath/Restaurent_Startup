# Phase 6 exact dependency installation review

**Resumed checks - 2026-11-11:** Exact-version OSV queries again found no listed advisories for the three approved additions. Host/image dependency checks and native Linux signature/digest/tamper checks passed. The API image rebuilt for the event-route correction still preserves every original runtime version and adds only those same three approved packages. No host installation or dependency upgrade occurred. A broader inventory audit identified older pip/pytest advisories, detailed below; npm still reports eight affected packages (one high, seven moderate). The public/pilot deployment hold remains.

**Reviewed:** 2026-11-08, UTC evidence timestamps. **Status:** Separately approved and installed in the project .venv and API image. Exact hashes were enforced; native Windows/Linux signatures and pip checks passed. API inventory adds exactly the approved three packages and preserves all original versions.

The founder approved Phase 6 architecture but explicitly requires separate approval before dependencies are installed. These are the only proposed new runtime packages. No optional extras, model/export tooling, HTTPX replacement, npm upgrade, global software or system certificate installation is included.

| Package | Exact version | License | Purpose |
| --- | --- | --- | --- |
| `cryptography` | `50.0.2` | Apache-2.0 OR BSD-3-Clause | Ed25519 keys/signatures and private local TLS test-certificate tooling |
| `http-message-signatures` | `3.0.0` | Apache-2.0; retain LICENSE/NOTICE | Standard RFC 9421 signature parsing/serialization/verification |
| `http-sf` | `1.5.0` | MIT | Structured HTTP signature/digest fields; required dependency of the signature package |

Official release metadata: [Cryptography](https://pypi.org/project/cryptography/50.0.2/), [HTTP Message Signatures](https://pypi.org/project/http-message-signatures/3.0.0/), [HTTP Structured Fields](https://pypi.org/project/http-sf/1.5.0/). The exact 3.0.0 signature release supports `body=` digest generation/verification, unlike the earlier documentation snapshot; the integration will explicitly supply exact body bytes and enforce required coverage independently. No algorithm negotiation/digest-only authentication is allowed.

## Verified artifacts

Downloaded wheel archives only for inspection, outside Git under ignored `.cache/phase6-dependency-review/`. Their SHA-256 values match PyPI release metadata. Full upstream license/NOTICE files were inspected/extracted into that private review directory; this does not install/import the package.

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `cryptography-50.0.2-cp311-abi3-win_amd64.whl` | 3,824,692 | `7afa5a6602a9f29af1f3a2965f831bae7c9d5d597b7cbb716d41ab3b7d89879c` |
| `cryptography-50.0.2-cp311-abi3-manylinux_2_34_x86_64.whl` | 4,752,576 | `9dab55f57c74c3cad24c323bacbbd04be4705ba6eb0d92e920b1fc4837ed5079` |
| `http_message_signatures-3.0.0-py3-none-any.whl` | 53,460 | `c289966e1b2950517cd57aed166be5e981de96f0cd29f69173f09ac547a8552a` |
| `http_sf-1.5.0-py3-none-any.whl` | 27,696 | `031282bd376549b04fcaa397d9ef351acdc5bd383435cccd1d8ea17b1661c80e` |

The reviewed manifests are [Windows additions](../services/edge-agent/requirements-phase6-windows.txt) and [Linux API additions](../services/api/requirements-phase6-linux.txt). The Windows install totals approximately 3.73 MiB. The selected Linux wheel targets x86_64/glibc 2.34+; no ARM, macOS or older libc support is claimed.

## Dry run, security and compatibility

- The working Python 3.14 binary-only `pip install --dry-run --report ...` proposes **exactly these three additions**, with no upgrades/removals. Existing CFFI 2.1.1, pycparser 3.12 and typing-extensions 4.16.0 satisfy supporting requirements. No setuptools/build-tool install is needed for these binary wheels.
- Matching binary tags are available for Windows CPython 3.14 and the API's Linux CPython 3.12. Published compatibility was not native proof at review time. After approval the actual Windows/Linux signature/digest, image inventory and dependency checks passed; see PHASE_06.md.
- Exact-version [OSV API](https://google.github.io/osv.dev/api/) queries for all three returned **no listed advisories** at review time. This is not a vulnerability-free guarantee, full native/OpenSSL audit or security certification.
- Cryptography contains native code. Standard signature parsing still needs strict allowed algorithms/covered fields, independent request/body binding checks, freshness/nonces, bounded parsing and adversarial tests. A valid signature does not prove model accuracy.
- The signature package's optional `httpx2`, docs/tests extras and requests/aiohttp integrations are excluded. Adapt the existing HTTPX 0.28.1 and ASGI message boundary without replacing the existing test client.
- Keep the original API runtime lock versions. The approval request also covers declaring these exact additions and installing them into a rebuilt **project API image**, without upgrading its existing packages. Verify the image's dependency inventory before replacing the old application container. Existing DB credentials/container/volume must remain intact.

Private machine-readable dry-run, release metadata, wheel hashes and OSV evidence are retained under `.secrets/phase6-implementation/`. No secret values or private footage were sent in those metadata requests.

## Broader installed-package audit - 2026-11-11

The resumed audit queried OSV for **63 unique public package/version pairs**
across the working environment and API image. It excluded the two local project
packages and did not send credentials or files. Beyond npm's eight affected
packages, it found the following older tooling advisories. GHSA and PYSEC aliases
refer to the same issues; they are not counted twice.

| Installed tool | Findings and recorded fixed-version bounds |
| --- | --- |
| Host pip **25.2**, API-image pip **25.0.1** | Six distinct advisories: [fallback tar extraction](https://osv.dev/vulnerability/GHSA-4xh5-x5gv-qwph), [archive interpretation conflict](https://osv.dev/vulnerability/GHSA-58qw-9mgm-455v), [path traversal](https://osv.dev/vulnerability/GHSA-6vgw-5pg2-w6jp), [untrusted functionality](https://osv.dev/vulnerability/GHSA-jp4c-xjxw-mgf9), [doubly encoded index URLs](https://osv.dev/vulnerability/GHSA-qwm4-qh6w-59xr), and [script entry-point paths](https://osv.dev/vulnerability/GHSA-wf93-45jw-7689). OSV labels five moderate and one low; the highest recorded fixed-version bound is **26.2.0** |
| Host pytest **8.4.2** | [Temporary-directory handling, moderate](https://github.com/advisories/GHSA-6w46-j5rx-g56g), recorded fixed version **9.0.3**. The described attack concerns UNIX local-user temporary directories; this Windows test pass does not validate Linux CI safety |

These are advisory matches, not evidence that this machine was exploited. The
pip issues concern installation/build tooling, not a new authenticated device
endpoint. Python version and installation input affect individual exposure; for
example the [pip tar advisory](https://github.com/advisories/GHSA-4xh5-x5gv-qwph)
describes a fallback not used by PEP 706-capable Python. That does not dismiss
the other findings or certify this installation process.

No other package/version in that queried inventory had a listed OSV match. This
does not cover the isolated model exporter, all bundled native libraries, unknown
vulnerabilities, or runtime exploitability. The three approved Phase 6 additions
still had no listed advisories in their exact-version checks.

**Pending decision:** prepare a separate reviewed pip/test-tool upgrade, check the
exact selected versions and transitive changes, and obtain founder approval
before installation or CI constraints are changed. The fixed bounds above are
advisory information, not a compatibility-tested upgrade proposal. Pytest 9 is a
major-version change. No packages or dependency constraints were changed in this
review. Resolve these tooling findings, npm's high-risk finding and the other
documented security gates before public/pilot deployment.

## Original approval scope

Requested: install these three exact packages only in the working project `.venv` and the project API image, with the reviewed hashes and existing dependency constraints; run compatibility/security tests afterward. No global installs, other weights, package upgrades, public deployment or existing-database migration is included. Migrations to the retained business database require a separate risk review and approval after restored-backup rehearsal.
