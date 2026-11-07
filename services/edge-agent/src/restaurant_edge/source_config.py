"""Private source configuration. Browser requests can select only a scoped opaque alias."""

import ipaddress
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    reference: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    organization_id: UUID
    location_id: UUID
    camera_id: UUID
    kind: Literal["mp4", "webcam", "rtsp"]
    synthetic: bool = False
    authorized: Literal[True]
    file: str | None = Field(default=None, repr=False)
    device_index: int = Field(default=0, ge=0, le=7)
    host: str | None = Field(default=None, repr=False)
    port: int = Field(default=554, ge=1, le=65535)
    stream_path: str = Field(default="/", pattern=r"^/[A-Za-z0-9._~/-]{0,200}$", repr=False)
    credential_required: bool = True

    @model_validator(mode="after")
    def source_rules(self):
        if self.kind == "mp4" and (not self.file or "://" in self.file):
            raise ValueError("An authorized local MP4 reference is required")
        if self.kind == "rtsp":
            try:
                host = ipaddress.ip_address(self.host or "")
            except ValueError:
                raise ValueError("Use an explicitly authorized literal camera IP") from None
            private_lan = [ipaddress.ip_network(n) for n in
                           ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"]]
            if not any(host in network for network in private_lan if network.version == host.version):
                raise ValueError("Camera destination is outside the private LAN policy")
            if ".." in self.stream_path:
                raise ValueError("Unsupported stream path")
        return self


class SourceRegistry:
    def __init__(self, definitions, roots):
        self.roots = [Path(p).resolve(strict=True) for p in roots]
        self.entries = {}
        for definition in definitions:
            key = (str(definition.organization_id), str(definition.location_id), str(definition.camera_id),
                   definition.reference)
            if key in self.entries:
                raise ValueError("Duplicate scoped source reference")
            if definition.kind == "mp4":
                path = Path(definition.file).resolve(strict=True)
                if path.suffix.lower() != ".mp4" or not any(path.is_relative_to(r) for r in self.roots):
                    raise ValueError("MP4 is outside the authorized roots")
                if path.stat().st_size > 2 * 1024**3:
                    raise ValueError("MP4 exceeds the local input limit")
                with path.open("rb") as f:
                    if f.read(12)[4:8] != b"ftyp":
                        raise ValueError("Input is not a supported MP4 container")
                definition.file = str(path)
            self.entries[key] = definition

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if set(data) != {"version", "roots", "sources"} or data["version"] != 1:
            raise ValueError("Unsupported private source configuration")
        return cls([SourceDefinition.model_validate(d) for d in data["sources"]], data["roots"])

    def get(self, organization, location, camera, reference):
        return self.entries.get(tuple(map(str, (organization, location, camera, reference))))
