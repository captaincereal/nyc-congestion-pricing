import hashlib
import json

import pandas as pd
import pytest

from src.config import EZPASS_TIME_COL
from src.data.download_ezpass import VERIFICATION_METHOD
from src.data.release_store import ReleaseStore, ReleaseStoreError
from src.data.verification_gate import StateIntegrityError, digest, verification_summary
from tests.test_verification_gate import make_archive, write_json


class Response:
    def __init__(self, value=None, *, content=b"", status=200):
        self.value, self.content, self.status_code = value, content, status

    def json(self):
        return self.value

    def close(self):
        pass

    def iter_content(self, chunk_size):
        yield self.content


class GitHub:
    """Synthetic release storage, including deletion-before-upload failure behavior."""

    def __init__(self, *, digests=True):
        self.assets = {}
        self.next_id = 1
        self.calls = []
        self.fail_uploads = set()
        self.fail_prefix = None
        self.digests = digests

    def add(self, name, data):
        ident = self.next_id
        self.next_id += 1
        asset = {
            "id": ident,
            "name": name,
            "size": len(data),
            "state": "uploaded",
            "created_at": f"2026-09-12T00:00:{ident:02d}Z",
        }
        if self.digests:
            asset["digest"] = "sha256:" + hashlib.sha256(data).hexdigest()
        self.assets[ident] = (asset, data)
        return dict(asset)

    def request(self, method, url, **kwargs):
        assert kwargs["timeout"][0] <= 10 and kwargs["timeout"][1] == 60
        name = kwargs.get("params", {}).get("name")
        self.calls.append((method, url, name))
        if method == "GET" and "/releases/tags/" in url:
            return Response(
                {
                    "id": 1,
                    "upload_url": "https://uploads.github.com/repos/test/repo/releases/1/assets{?name,label}",
                }
            )
        if method == "GET" and url.endswith("/releases/1/assets"):
            page = kwargs["params"]["page"]
            return Response(
                [dict(a) for a, _ in self.assets.values()][(page - 1) * 100 : page * 100]
            )
        if method == "GET" and "/releases/assets/" in url:
            asset, data = self.assets[int(url.rsplit("/", 1)[-1])]
            return Response(content=data)
        if method == "DELETE":
            self.assets.pop(int(url.rsplit("/", 1)[-1]))
            return Response(status=204)
        if method == "POST":
            if name in self.fail_uploads or (
                self.fail_prefix and name.startswith(self.fail_prefix)
            ):
                return Response(status=500)
            assert name not in {a["name"] for a, _ in self.assets.values()}
            data = kwargs["data"]
            if hasattr(data, "read"):
                data = data.read()
            return Response(self.add(name, data), status=201)
        raise AssertionError((method, url))


def seed_remote(fake, raw):
    for path in [
        *(raw / "ezpass_speeds").glob("*.parquet"),
        raw / "ezpass_manifest.json",
        *(raw / "ezpass_verification").glob("*.json"),
    ]:
        fake.add(path.name, path.read_bytes())


@pytest.mark.parametrize("digests", [True, False])
def test_strict_canonical_restore_and_immutable_snapshot_roundtrip(tmp_path, digests):
    raw, targets, _, _ = make_archive(tmp_path / "source")
    fake = GitHub(digests=digests)
    seed_remote(fake, raw)
    store = ReleaseStore("test/repo", "test-token", session=fake)
    restored = tmp_path / "restored"
    assert store.restore(restored)["state_asset"] is None
    assert verification_summary(restored, targets)["gate_passed"]
    before = {a["id"] for a, _ in fake.assets.values() if a["name"].endswith(".parquet")}
    published = store.publish(restored)
    assert published["state_asset"].startswith("state_")
    assert published["uploaded_raw"] == []
    assert not any(
        method == "DELETE" and int(url.rsplit("/", 1)[-1]) in before
        for method, url, _ in fake.calls
    )
    final = tmp_path / "final"
    assert store.restore(final)["state_asset"] == published["state_asset"]
    assert verification_summary(final, targets)["gate_passed"]


def test_canonical_replacement_failure_cannot_destroy_durable_progress(tmp_path):
    raw, targets, _, _ = make_archive(tmp_path / "source")
    fake = GitHub()
    seed_remote(fake, raw)
    fake.fail_uploads.add("ezpass_manifest.json")
    store = ReleaseStore("test/repo", "test-token", session=fake)
    published = store.publish(raw)
    assert published["compatibility_errors"]
    assert "ezpass_manifest.json" not in {a["name"] for a, _ in fake.assets.values()}
    destination = tmp_path / "restored"
    assert store.restore(destination)["state_asset"] == published["state_asset"]
    assert verification_summary(destination, targets)["gate_passed"]
    snapshot_upload = next(
        i for i, call in enumerate(fake.calls) if call[0] == "POST" and call[2].startswith("state_")
    )
    first_delete = next(i for i, call in enumerate(fake.calls) if call[0] == "DELETE")
    assert snapshot_upload < first_delete


def test_failed_snapshot_upload_preserves_canonical_state(tmp_path):
    raw, _, _, _ = make_archive(tmp_path / "source")
    fake = GitHub()
    seed_remote(fake, raw)
    fake.fail_prefix = "state_"
    store = ReleaseStore("test/repo", "test-token", session=fake)
    with pytest.raises(ReleaseStoreError):
        store.publish(raw)
    assert not any(method == "DELETE" for method, _, _ in fake.calls)
    assert "ezpass_manifest.json" in {a["name"] for a, _ in fake.assets.values()}


def test_conflicting_raw_asset_is_never_overwritten(tmp_path):
    raw, _, part, _ = make_archive(tmp_path / "source")
    fake = GitHub()
    fake.add(part["part"], b"different")
    store = ReleaseStore("test/repo", "test-token", session=fake)
    with pytest.raises(StateIntegrityError, match="conflicting raw"):
        store.publish(raw)
    assert not any(method in ("DELETE", "POST") for method, _, _ in fake.calls)


def test_new_raw_assets_are_uploaded_before_state_snapshot(tmp_path):
    raw, _, part, _ = make_archive(tmp_path / "source")
    fake = GitHub()
    store = ReleaseStore("test/repo", "test-token", session=fake)
    published = store.publish(raw)
    assert published["uploaded_raw"] == [part["part"]]
    names = [name for method, _, name in fake.calls if method == "POST"]
    assert names[0] == part["part"]
    assert names[1].startswith("state_")


def test_corrupt_newest_snapshot_falls_back_to_last_valid_snapshot(tmp_path):
    raw, targets, _, _ = make_archive(tmp_path / "source")
    fake = GitHub()
    store = ReleaseStore("test/repo", "test-token", session=fake)
    published = store.publish(raw)
    fake.add("state_broken.json", b"{corrupt")
    destination = tmp_path / "restored"
    result = store.restore(destination)
    assert result["state_asset"] == published["state_asset"]
    assert len(result["rejected_snapshots"]) == 1
    assert verification_summary(destination, targets)["gate_passed"]


def test_invalid_snapshots_do_not_fall_back_to_untrusted_canonical_state(tmp_path):
    raw, _, _, _ = make_archive(tmp_path / "source")
    fake = GitHub()
    seed_remote(fake, raw)
    fake.add("state_broken.json", b"{corrupt")
    with pytest.raises(StateIntegrityError, match="canonical fallback refused"):
        ReleaseStore("test/repo", "test-token", session=fake).restore(tmp_path / "restored")


def test_restore_checks_downloaded_bytes_even_with_advertised_digest(tmp_path):
    raw, _, part, _ = make_archive(tmp_path / "source")
    fake = GitHub()
    store = ReleaseStore("test/repo", "test-token", session=fake)
    store.publish(raw)
    for ident, (asset, data) in list(fake.assets.items()):
        if asset["name"] == part["part"]:
            fake.assets[ident] = (asset, b"x" * len(data))
    destination = tmp_path / "restored"
    with pytest.raises(StateIntegrityError, match="no valid immutable"):
        store.restore(destination)
    assert not (destination / "ezpass_manifest.json").exists()


def test_local_manifest_corruption_stops_before_any_remote_mutation(tmp_path):
    raw, _, _, _ = make_archive(tmp_path / "source")
    (raw / "ezpass_manifest.json").write_text("{corrupt", encoding="utf-8")
    fake = GitHub()
    with pytest.raises(StateIntegrityError, match="valid JSON"):
        ReleaseStore("test/repo", "test-token", session=fake).publish(raw)
    assert fake.calls == []


def test_checkpoint_parquet_and_count_receipt_survive_snapshot_restore(tmp_path):
    raw, _, _, _ = make_archive(tmp_path / "source")
    checkpoint = raw / "ezpass_days" / "ezpass_day_2024-07-01.parquet"
    checkpoint.parent.mkdir()
    pd.DataFrame({EZPASS_TIME_COL: ["2024-07-01T12:00:00"]}).to_parquet(checkpoint, index=False)
    sidecar = {
        "day": "2024-07-01",
        "checkpoint_sha256": digest(checkpoint),
        "verification_method": VERIFICATION_METHOD,
        "source_rows": 2,
        "sample_rows": 1,
        "checked_at": "2026-09-12T12:00:00+00:00",
    }
    write_json(checkpoint.with_suffix(".receipt.json"), sidecar)
    fake = GitHub()
    store = ReleaseStore("test/repo", "test-token", session=fake)
    store.publish(raw)
    restored = tmp_path / "restored"
    store.restore(restored)
    assert digest(restored / "ezpass_days" / checkpoint.name) == digest(checkpoint)
    assert (
        json.loads((restored / "ezpass_days" / "ezpass_day_2024-07-01.receipt.json").read_text())
        == sidecar
    )


def test_unsafe_receipt_name_is_rejected_before_publication(tmp_path):
    raw, _, _, _ = make_archive(tmp_path / "source")
    write_json(raw / "ezpass_verification" / "unrelated.json", {})
    fake = GitHub()
    with pytest.raises(StateIntegrityError, match="unbound receipt"):
        ReleaseStore("test/repo", "test-token", session=fake).publish(raw)
    assert fake.calls == []


# --- Release-asset pruning --------------------------------------------------
# A GitHub release holds at most 1000 assets and rejects every upload once it is
# full. On 2026-09-13 the backfill died exactly there: 853 day checkpoints from
# months finished days earlier, plus 89 state snapshots, filled the release and
# publish() began raising HTTP 422. These cover the rule that stops it.


def _seeded_store(tmp_path):
    raw, targets, _, _ = make_archive(tmp_path / "source")
    fake = GitHub()
    seed_remote(fake, raw)
    store = ReleaseStore("test/repo", "test-token", session=fake)
    restored = tmp_path / "restored"
    store.restore(restored)
    return raw, targets, fake, store, restored


def _add_asset(fake, name, payload=b"stale"):
    fake.add(name, payload)


def test_day_checkpoints_of_completed_months_are_deleted(tmp_path):
    """The month part supersedes them; download_month deletes the local copies
    for the same reason."""
    _, _, fake, store, restored = _seeded_store(tmp_path)
    manifest = json.loads((restored / "ezpass_manifest.json").read_text())
    done = [p["month"] for p in manifest["parts"] if p.get("complete")][0]
    _add_asset(fake, f"ezpass_day_{done}-05.parquet")
    _add_asset(fake, f"ezpass_day_{done}-06.parquet")

    result = store.publish(restored)

    assert result["pruned"]["deleted"] >= 2
    names = {a["name"] for a, _ in fake.assets.values()}
    assert f"ezpass_day_{done}-05.parquet" not in names
    assert f"ezpass_day_{done}-06.parquet" not in names


def test_day_checkpoints_of_unfinished_months_survive(tmp_path):
    """Deleting these would discard the only record of an interrupted month."""
    _, _, fake, store, restored = _seeded_store(tmp_path)
    _add_asset(fake, "ezpass_day_2099-12-01.parquet")

    store.publish(restored)

    names = {a["name"] for a, _ in fake.assets.values()}
    assert "ezpass_day_2099-12-01.parquet" in names


def test_month_parts_and_receipts_are_never_pruned(tmp_path):
    """The archive itself is immutable. Only scaffolding is collectable."""
    _, _, fake, store, restored = _seeded_store(tmp_path)
    protected = {
        a["name"]
        for a, _ in fake.assets.values()
        if a["name"].startswith(("ezpass_speeds_", "ezpass_verify_", "ezpass_segments"))
    }
    assert protected, "fixture should contain protected assets"

    store.publish(restored)

    names = {a["name"] for a, _ in fake.assets.values()}
    assert protected <= names


def test_only_the_newest_state_snapshots_are_kept(tmp_path):
    """restore() reads the newest valid snapshot and falls back a little; a
    handful is enough provenance, and unbounded growth is what filled the
    release."""
    from src.data.release_store import KEEP_SNAPSHOTS

    _, _, fake, store, restored = _seeded_store(tmp_path)
    for i in range(KEEP_SNAPSHOTS + 6):
        _add_asset(fake, f"state_20260101T00000{i:04d}Z_run_{i:04d}.json", b"{}")

    store.publish(restored)

    remaining = sorted(a["name"] for a, _ in fake.assets.values() if a["name"].startswith("state_"))
    assert len(remaining) <= KEEP_SNAPSHOTS + 1, remaining


def test_assets_the_new_state_references_are_never_pruned(tmp_path):
    """Belt and braces: whatever the snapshot about to be written points at is
    excluded regardless of the month rule."""
    _, _, fake, store, restored = _seeded_store(tmp_path)
    state = store._local_state(restored)
    release, assets = store._catalogue()

    store._prune(state, release, assets)

    names = {a["name"] for a, _ in fake.assets.values()}
    assert set(state["assets"]) <= names


def test_a_failed_delete_does_not_abort_the_publish(tmp_path):
    """Pruning is housekeeping. A delete that fails must not cost the pass its
    durable checkpoint."""
    _, _, fake, store, restored = _seeded_store(tmp_path)
    manifest = json.loads((restored / "ezpass_manifest.json").read_text())
    done = [p["month"] for p in manifest["parts"] if p.get("complete")][0]
    _add_asset(fake, f"ezpass_day_{done}-05.parquet")
    fake.fail_prefix = "DELETE"

    result = store.publish(restored)

    assert result["state_asset"].startswith("state_")
