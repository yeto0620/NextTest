"""Immutable event/project store for NextTest P2."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import TrainedPredictor, load_predictor, save_predictor

PROJECT_SCHEMA = "nexttest_p2_project_v1"
EVENT_SCHEMA = "nexttest_p2_event_v1"


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write_new(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class ProjectStore:
    root: Path

    @classmethod
    def create(cls, root: str | Path, manifest: dict) -> "ProjectStore":
        root = Path(root)
        if root.exists():
            raise FileExistsError(f"project root already exists: {root}")
        root.mkdir(parents=True)
        store = cls(root)
        _write_new(root / "project_manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
        (root / "events").mkdir()
        (root / "models").mkdir()
        return store

    @property
    def manifest_path(self) -> Path:
        return self.root / "project_manifest.json"

    def manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    @property
    def events_dir(self) -> Path:
        return self.root / "events"

    def events(self) -> list[dict]:
        events = []
        previous = ""
        for index, path in enumerate(sorted(self.events_dir.glob("*.json")), 1):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("schema") != EVENT_SCHEMA or data.get("sequence") != index:
                raise ValueError("event sequence/schema invalid")
            if data.get("prev_event_sha256") != previous:
                raise ValueError("event chain break")
            body = {k: v for k, v in data.items() if k != "event_sha256"}
            if data.get("event_sha256") != _sha_bytes(_canonical(body).encode()):
                raise ValueError("event hash mismatch")
            previous = data["event_sha256"]
            events.append(data)
        return events

    def append_event(self, event_type: str, payload: dict) -> dict:
        events = self.events()
        previous = events[-1]["event_sha256"] if events else ""
        body = {
            "schema": EVENT_SCHEMA,
            "project_id": self.manifest()["project_id"],
            "sequence": len(events) + 1,
            "event_type": event_type,
            "payload": payload,
            "prev_event_sha256": previous,
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        digest = _sha_bytes(_canonical(body).encode())
        body["event_sha256"] = digest
        _write_new(self.events_dir / f"{body['sequence']:06d}.json", (json.dumps(body, indent=2, sort_keys=True) + "\n").encode())
        return body

    def write_model(self, predictor: TrainedPredictor) -> str:
        sha = predictor.manifest.model_sha256
        target = self.root / "models" / sha
        if target.exists():
            raise FileExistsError(f"model version already exists: {sha}")
        manifest = save_predictor(predictor, target)
        actual = str(manifest["model_sha256"])
        if actual != sha:
            actual_target = self.root / "models" / actual
            target.rename(actual_target)
            return actual
        return sha

    def load_model(self, sha: str) -> TrainedPredictor:
        path = self.root / "models" / sha
        if not path.is_dir():
            raise FileNotFoundError(f"model version missing: {sha}")
        return load_predictor(path)

    def event_chain_sha(self) -> str:
        events = self.events()
        return events[-1]["event_sha256"] if events else ""

    def tree_sha(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(p for p in self.root.rglob("*") if p.is_file()):
            digest.update(path.relative_to(self.root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
