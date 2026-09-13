"""Persist immutable raw assets and resumable audit state using the GitHub REST API.

Each durable state snapshot embeds the manifest and verification receipts.
Canonical JSON assets are compatibility copies; losing their replacement upload
cannot destroy the previously uploaded snapshot. No raw parquet is overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

import pyarrow.parquet as pq
import requests

from src.config import RAW_DIR
from src.data.verification_gate import (
    PART_NAME,
    RECEIPT_NAME,
    SHA256,
    StateIntegrityError,
    _integer,
    _timestamp,
    digest,
    load_json,
    validate_local_parts,
    validate_manifest,
    validate_receipt,
)

log = logging.getLogger(__name__)
DAY_NAME = re.compile(r"ezpass_day_(\d{4}-\d{2}-\d{2})\.parquet\Z")
STATE_NAME = re.compile(r"state_\d{8}T\d+Z_.+\.json\Z")
# A GitHub release holds at most 1000 assets and every upload 422s once it is
# full. Day checkpoints and state snapshots both accumulate one per slice, so
# without pruning the store bricks itself after a few thousand slices -- which
# is exactly what happened on 2026-09-13.
KEEP_SNAPSHOTS = 8
DAY_RECEIPT_NAME = re.compile(r"ezpass_day_(\d{4}-\d{2}-\d{2})\.receipt\.json\Z")
ANCILLARY = ("ezpass_segments.parquet", "weather_hourly.parquet")
MAX_STATE_BYTES = 8 * 1024 * 1024


class ReleaseStoreError(RuntimeError):
    """The release could not be safely read or updated."""


def _encode(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _asset_path(raw_dir: Path, name: str) -> Path:
    if PART_NAME.fullmatch(name):
        return raw_dir / "ezpass_speeds" / name
    if DAY_NAME.fullmatch(name):
        return raw_dir / "ezpass_days" / name
    if name in ANCILLARY:
        return raw_dir / name
    raise StateIntegrityError(f"unsupported raw asset name: {name}")


def _validate_day_receipt(receipt: dict, day: str, asset: dict) -> None:
    try:
        date.fromisoformat(day)
    except ValueError as exc:
        raise StateIntegrityError(f"invalid checkpoint day: {day}") from exc
    if receipt.get("day") != day or receipt.get("checkpoint_sha256") != asset["sha256"]:
        raise StateIntegrityError(f"{day}: day receipt is bound to a different checkpoint")
    if (
        not isinstance(receipt.get("verification_method"), str)
        or not receipt["verification_method"]
    ):
        raise StateIntegrityError(f"{day}: day receipt has no verification method")
    raw = _integer(receipt.get("source_rows"), f"{day} source_rows")
    sampled = _integer(receipt.get("sample_rows"), f"{day} sample_rows")
    if raw < sampled:
        raise StateIntegrityError(f"{day}: checkpoint retained rows exceed raw rows")
    _timestamp(receipt.get("checked_at"), day)


def _validate_snapshot(state: dict) -> dict[str, dict]:
    if state.get("schema_version") != 1:
        raise StateIntegrityError("unsupported release snapshot schema")
    _timestamp(state.get("created_at"), "snapshot created_at")
    parts = validate_manifest(state.get("manifest", {}))
    assets = state.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise StateIntegrityError("snapshot has no raw assets")
    for name, asset in assets.items():
        _asset_path(Path("."), name)
        if not isinstance(asset, dict) or not SHA256.fullmatch(str(asset.get("sha256", ""))):
            raise StateIntegrityError(f"{name}: snapshot asset has invalid SHA256")
        _integer(asset.get("size"), f"{name} size")
        if PART_NAME.fullmatch(name) and name not in parts:
            raise StateIntegrityError(f"snapshot contains an unrecorded month part: {name}")
    for name, part in parts.items():
        if assets.get(name) != {"sha256": part["sha256"], "size": part["bytes"]}:
            raise StateIntegrityError(f"snapshot asset and manifest disagree: {name}")
    receipts = state.get("receipts")
    if not isinstance(receipts, dict):
        raise StateIntegrityError("snapshot receipts must be an object")
    for name, receipt in receipts.items():
        match = RECEIPT_NAME.fullmatch(name)
        part = parts.get(f"ezpass_speeds_{match[1]}.parquet") if match else None
        if part is None or not isinstance(receipt, dict):
            raise StateIntegrityError(f"snapshot has an unbound receipt: {name}")
        validate_receipt(receipt, part)
    day_receipts = state.get("day_receipts", {})
    if not isinstance(day_receipts, dict):
        raise StateIntegrityError("snapshot day_receipts must be an object")
    for name, receipt in day_receipts.items():
        match = DAY_RECEIPT_NAME.fullmatch(name)
        asset = assets.get(f"ezpass_day_{match[1]}.parquet") if match else None
        if asset is None or not isinstance(receipt, dict):
            raise StateIntegrityError(f"snapshot has an unbound checkpoint receipt: {name}")
        _validate_day_receipt(receipt, match[1], asset)
    return parts


class ReleaseStore:
    """A bounded, Python-only client for the release that holds the unattended state."""

    def __init__(
        self,
        repo: str,
        token: str,
        *,
        tag: str = "data-raw",
        session: requests.Session | None = None,
        timeout: float = 60,
    ) -> None:
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is None:
            raise ValueError("repo must be owner/name")
        if not token or timeout <= 0:
            raise ValueError("a GitHub token and positive request timeout are required")
        self.repo, self.tag, self.timeout = repo, tag, timeout
        self.session = session or requests.Session()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "nyc-congestion-pricing-release-store",
        }
        self.base = f"https://api.github.com/repos/{repo}"

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        # GET retries are safe. An uncertain POST is left for the next restore
        # to discover, rather than blindly uploading duplicate asset names.
        attempts = 3 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=(min(10, self.timeout), self.timeout),
                    **kwargs,
                )
            except requests.RequestException as exc:
                if attempt + 1 == attempts:
                    raise ReleaseStoreError(f"GitHub {method} request failed") from exc
                time.sleep(attempt + 1)
                continue
            if response.status_code in (429, 500, 502, 503, 504) and attempt + 1 < attempts:
                response.close()
                time.sleep(attempt + 1)
                continue
            if not 200 <= response.status_code < 300:
                status = response.status_code
                response.close()
                raise ReleaseStoreError(f"GitHub {method} failed with HTTP {status}")
            return response
        raise ReleaseStoreError("GitHub retry budget exhausted")

    def _json(self, method: str, url: str, **kwargs) -> dict | list:
        response = self._request(method, url, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise ReleaseStoreError("GitHub returned invalid JSON") from exc
        finally:
            response.close()

    def _catalogue(self) -> tuple[dict, dict[str, dict]]:
        release = self._json("GET", f"{self.base}/releases/tags/{quote(self.tag, safe='')}")
        assets: dict[str, dict] = {}
        page = 1
        while True:
            batch = self._json(
                "GET",
                f"{self.base}/releases/{release['id']}/assets",
                params={"per_page": 100, "page": page},
            )
            if not isinstance(batch, list):
                raise ReleaseStoreError("GitHub asset catalogue is not a list")
            for asset in batch:
                if asset["name"] in assets:
                    raise StateIntegrityError(f"duplicate release asset: {asset['name']}")
                assets[asset["name"]] = asset
            if len(batch) < 100:
                break
            page += 1
        return release, assets

    def _download(
        self,
        asset: dict,
        dest: Path | None = None,
        *,
        limit: int | None = None,
        collect: bool = False,
    ) -> bytes | str:
        response = self._request(
            "GET",
            f"{self.base}/releases/assets/{asset['id']}",
            headers={"Accept": "application/octet-stream"},
            stream=True,
        )
        chunks = []
        sha = hashlib.sha256()
        size = 0
        started = time.monotonic()
        handle = None
        try:
            if dest is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                handle = dest.open("wb")
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if time.monotonic() - started > self.timeout * 3:
                    raise ReleaseStoreError(
                        f"asset transfer exceeded its time budget: {asset['name']}"
                    )
                size += len(chunk)
                if limit is not None and size > limit:
                    raise StateIntegrityError(f"asset exceeds expected size: {asset['name']}")
                sha.update(chunk)
                if handle is not None:
                    handle.write(chunk)
                elif collect:
                    chunks.append(chunk)
            if size != asset["size"]:
                raise StateIntegrityError(f"asset transfer was truncated: {asset['name']}")
        finally:
            if handle is not None:
                handle.close()
            response.close()
        return b"".join(chunks) if collect else sha.hexdigest()

    def _state_json(self, asset: dict) -> dict:
        try:
            state = json.loads(self._download(asset, limit=MAX_STATE_BYTES, collect=True))
        except (ValueError, UnicodeError) as exc:
            raise StateIntegrityError(f"invalid JSON state asset: {asset['name']}") from exc
        if not isinstance(state, dict):
            raise StateIntegrityError(f"state asset is not an object: {asset['name']}")
        return state

    def _restore_snapshot(self, raw_dir: Path, state: dict, assets: dict[str, dict]) -> None:
        _validate_snapshot(state)
        raw_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".release-restore-", dir=raw_dir.parent) as temp:
            stage = Path(temp)
            for name, expected in state["assets"].items():
                remote = assets.get(name)
                if remote is None or remote["size"] != expected["size"]:
                    raise StateIntegrityError(
                        f"missing or incorrectly sized raw release asset: {name}"
                    )
                destination = _asset_path(stage, name)
                sha = self._download(remote, destination, limit=expected["size"])
                if sha != expected["sha256"]:
                    raise StateIntegrityError(f"raw release asset SHA256 mismatch: {name}")
                local = _asset_path(raw_dir, name)
                if local.exists() and digest(local) != sha:
                    raise StateIntegrityError(
                        f"refusing to overwrite different local raw bytes: {name}"
                    )
            validate_local_parts(stage, state["manifest"])
            self._validate_checkpoint_rows(stage, state)
            # No local state is changed until the complete candidate validates.
            raw_dir.mkdir(parents=True, exist_ok=True)
            for name in state["assets"]:
                destination = _asset_path(raw_dir, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.move(str(_asset_path(stage, name)), destination)
            for name, receipt in state["receipts"].items():
                self._atomic_json(raw_dir / "ezpass_verification" / name, receipt)
            for name, receipt in state.get("day_receipts", {}).items():
                self._atomic_json(raw_dir / "ezpass_days" / name, receipt)
            self._atomic_json(raw_dir / "ezpass_manifest.json", state["manifest"])

    @staticmethod
    def _atomic_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(_encode(value))
        temporary.replace(path)

    @staticmethod
    def _validate_checkpoint_rows(raw_dir: Path, state: dict) -> None:
        for name, receipt in state.get("day_receipts", {}).items():
            day = DAY_RECEIPT_NAME.fullmatch(name)[1]
            path = raw_dir / "ezpass_days" / f"ezpass_day_{day}.parquet"
            try:
                rows = pq.ParquetFile(path).metadata.num_rows
            except Exception as exc:  # noqa: BLE001 - corrupt checkpoint must reject the snapshot
                raise StateIntegrityError(f"{day}: cannot read checkpoint parquet") from exc
            if rows != receipt["sample_rows"]:
                raise StateIntegrityError(f"{day}: checkpoint row count disagrees with receipt")

    def restore(self, raw_dir: Path) -> dict:
        """Restore the newest complete valid snapshot, or strict canonical bootstrap state."""
        raw_dir = Path(raw_dir)
        _, assets = self._catalogue()
        snapshots = sorted(
            [
                asset
                for name, asset in assets.items()
                if name.startswith("state_") and name.endswith(".json")
            ],
            key=lambda asset: (asset.get("created_at", ""), asset["name"]),
            reverse=True,
        )
        invalid = []
        for asset in snapshots:
            try:
                state = self._state_json(asset)
                self._restore_snapshot(raw_dir, state, assets)
                log.info("restored immutable snapshot %s", asset["name"])
                return {
                    "state_asset": asset["name"],
                    "parts": len(state["manifest"]["parts"]),
                    "rejected_snapshots": invalid,
                }
            except StateIntegrityError as exc:
                log.warning("rejecting snapshot %s: %s", asset["name"], exc)
                invalid.append({"asset": asset["name"], "error": str(exc)})
        if snapshots:
            raise StateIntegrityError(
                "no valid immutable release snapshot; canonical fallback refused"
            )
        manifest_asset = assets.get("ezpass_manifest.json")
        if manifest_asset is None:
            raise StateIntegrityError("release has no manifest or immutable state snapshot")
        manifest = self._state_json(manifest_asset)
        parts = validate_manifest(manifest)
        raw_assets = {
            name: {"sha256": p["sha256"], "size": p["bytes"]} for name, p in parts.items()
        }
        # Bootstrap ancillary files have no manifest hash: establish one from
        # their release bytes, then bind it in every subsequent state snapshot.
        for name in ANCILLARY:
            if name in assets:
                raw_assets[name] = {
                    "sha256": self._download(assets[name]),
                    "size": assets[name]["size"],
                }
        receipts = {}
        for name, asset in assets.items():
            if RECEIPT_NAME.fullmatch(name):
                receipts[name] = self._state_json(asset)
        state = {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "manifest": manifest,
            "assets": raw_assets,
            "receipts": receipts,
            "day_receipts": {},
        }
        self._restore_snapshot(raw_dir, state, assets)
        log.info("restored strict canonical bootstrap state (%d parts)", len(parts))
        return {"state_asset": None, "parts": len(parts), "rejected_snapshots": []}

    def _local_state(self, raw_dir: Path) -> dict:
        manifest = load_json(raw_dir / "ezpass_manifest.json")
        parts = validate_local_parts(raw_dir, manifest)
        raw_assets = {
            name: {"sha256": p["sha256"], "size": p["bytes"]} for name, p in parts.items()
        }
        for path in [
            *(raw_dir / "ezpass_days").glob("ezpass_day_*.parquet"),
            *(raw_dir / name for name in ANCILLARY),
        ]:
            if path.exists():
                _asset_path(raw_dir, path.name)
                raw_assets[path.name] = {"sha256": digest(path), "size": path.stat().st_size}
        state = {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "manifest": manifest,
            "assets": raw_assets,
            "receipts": {
                p.name: load_json(p) for p in (raw_dir / "ezpass_verification").glob("*.json")
            },
            "day_receipts": {
                p.name: load_json(p) for p in (raw_dir / "ezpass_days").glob("*.receipt.json")
            },
        }
        _validate_snapshot(state)
        self._validate_checkpoint_rows(raw_dir, state)
        return state

    def _upload(self, release: dict, name: str, data: bytes | Path) -> dict:
        upload_url = release["upload_url"].split("{", 1)[0]
        if isinstance(data, Path):
            with data.open("rb") as handle:
                result = self._json(
                    "POST",
                    upload_url,
                    params={"name": name},
                    headers={"Content-Type": "application/octet-stream"},
                    data=handle,
                )
        else:
            result = self._json(
                "POST",
                upload_url,
                params={"name": name},
                headers={"Content-Type": "application/json"},
                data=data,
            )
        if (
            not isinstance(result, dict)
            or result.get("name") != name
            or result.get("state") != "uploaded"
        ):
            raise ReleaseStoreError(f"upload was not confirmed complete: {name}")
        return result

    def _remote_matches(self, asset: dict, expected: dict) -> bool:
        if asset.get("size") != expected["size"]:
            return False
        advertised = asset.get("digest")
        if isinstance(advertised, str) and advertised.startswith("sha256:"):
            return advertised == f"sha256:{expected['sha256']}"
        return self._download(asset, limit=expected["size"]) == expected["sha256"]

    def _prune(self, state: dict, release: dict, assets: dict[str, dict]) -> dict:
        """Delete release assets that provably cannot be needed again.

        Two kinds qualify, and nothing else is ever touched:

        Day checkpoints exist only to resume an interrupted month. Once that
        month's part is on the release and its hash matches the manifest, the
        day files are redundant by construction -- ``download_month`` deletes
        the local copies for the same reason. Keeping them cost this project a
        full release: 853 day assets from months finished days earlier.

        Both halves of a checkpoint go together. ``publish`` writes the parquet
        from ``state["assets"]`` and its ``.receipt.json`` through the
        compatibility block, so the receipts accrue at the same one-per-day
        rate; matching only the parquet left 408 of them stranded on a release
        that was already full.

        Old state snapshots are history. ``restore`` reads the newest valid one
        and falls back at most a few, so a handful is sufficient provenance. The
        ones that survive have to stay restorable, though: ``restore`` rejects a
        snapshot whose raw assets have gone, so deleting a day file out from
        under one shortens the fallback chain without saying so. Measured on the
        live release, four of the eight newest still pointed at a completed
        month's days. Whatever a kept snapshot references is therefore live too.

        Anything the state about to be published writes -- raw assets and
        compatibility metadata alike -- is excluded regardless, so a mistake in
        the month rule cannot delete live data or race the upload that follows.
        """
        live = (
            set(state["assets"])
            | set(state["receipts"])
            | set(state["day_receipts"])
            | {"ezpass_manifest.json"}
        )
        complete = {
            part["month"]
            for part in state["manifest"].get("parts", [])
            if part.get("complete") is True
        }

        snapshots = sorted((n for n in assets if STATE_NAME.fullmatch(n)), reverse=True)
        for name in snapshots[:KEEP_SNAPSHOTS]:
            try:
                referenced = self._state_json(assets[name]).get("assets")
            except (ReleaseStoreError, StateIntegrityError):
                # Already unrestorable, so it has nothing left to protect.
                continue
            if isinstance(referenced, dict):
                live |= set(referenced)

        doomed = list(snapshots[KEEP_SNAPSHOTS:])
        for name in assets:
            if name in live:
                continue
            day = DAY_NAME.fullmatch(name) or DAY_RECEIPT_NAME.fullmatch(name)
            if day and day.group(1)[:7] in complete:
                doomed.append(name)

        deleted, failed = [], []
        for name in doomed:
            try:
                response = self._request(
                    "DELETE", f"{self.base}/releases/assets/{assets[name]['id']}"
                )
                response.close()
                assets.pop(name, None)
                deleted.append(name)
            except ReleaseStoreError as exc:
                # A failed delete is not fatal: the upload that follows may still
                # fit, and the next pass tries again.
                failed.append({"asset": name, "error": str(exc)})
        if deleted or failed:
            log.info(
                "pruned %d redundant release asset(s); %d remain, %d delete(s) failed",
                len(deleted),
                len(assets),
                len(failed),
            )
        return {"deleted": len(deleted), "failed": failed, "remaining": len(assets)}

    def publish(self, raw_dir: Path) -> dict:
        """Durably publish a checkpoint; raw assets and old snapshots remain immutable."""
        raw_dir = Path(raw_dir)
        state = self._local_state(raw_dir)
        release, assets = self._catalogue()
        # Before uploading, not after: a release at its asset ceiling rejects
        # every upload, so pruning last would never run.
        pruned = self._prune(state, release, assets)
        uploaded_raw = []
        for name, expected in state["assets"].items():
            asset = assets.get(name)
            if asset is None:
                asset = self._upload(release, name, _asset_path(raw_dir, name))
                assets[name] = asset
                uploaded_raw.append(name)
            if not self._remote_matches(asset, expected):
                raise StateIntegrityError(
                    f"refusing to overwrite conflicting raw release asset: {name}"
                )
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        run_id = re.sub(r"[^A-Za-z0-9_-]", "_", os.environ.get("GITHUB_RUN_ID", "local"))
        name = f"state_{stamp}_{run_id}_{uuid.uuid4().hex[:8]}.json"
        data = _encode(state)
        snapshot = self._upload(release, name, data)
        expected = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if not self._remote_matches(snapshot, expected):
            raise StateIntegrityError("uploaded state snapshot failed integrity verification")
        log.info("durable release checkpoint: %s", name)
        # Only compatibility metadata may be replaced, and only after the
        # immutable snapshot and all its referenced raw assets are durable.
        compatibility = {
            "ezpass_manifest.json": state["manifest"],
            **state["receipts"],
            **state["day_receipts"],
        }
        failures = []
        for canonical, value in compatibility.items():
            try:
                payload = _encode(value)
                expected = {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                previous = assets.get(canonical)
                if previous is not None and self._remote_matches(previous, expected):
                    continue
                if previous is not None:
                    response = self._request(
                        "DELETE", f"{self.base}/releases/assets/{previous['id']}"
                    )
                    response.close()
                uploaded = self._upload(release, canonical, payload)
                if not self._remote_matches(uploaded, expected):
                    raise StateIntegrityError(
                        f"compatibility upload failed integrity check: {canonical}"
                    )
            except (ReleaseStoreError, StateIntegrityError) as exc:
                log.warning("durable snapshot saved; compatibility update failed: %s", exc)
                failures.append({"asset": canonical, "error": str(exc)})
        return {
            "state_asset": name,
            "parts": len(state["manifest"]["parts"]),
            "uploaded_raw": uploaded_raw,
            "compatibility_errors": failures,
            "pruned": pruned,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("restore", "publish"))
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--tag", default="data-raw")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not args.repo or not token:
        parser.error("GITHUB_REPOSITORY (or --repo) and GH_TOKEN are required")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = ReleaseStore(args.repo, token, tag=args.tag, timeout=args.timeout)
    print(json.dumps(getattr(store, args.action)(args.raw_dir), indent=2))


if __name__ == "__main__":
    main()
