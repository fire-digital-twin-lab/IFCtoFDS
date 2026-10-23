from types import SimpleNamespace

from ifc_to_fds.modules.jobs.infrastructure.retention import FilesystemJobRetention


class Store:
    def __init__(self):
        self.values = {}

    def items(self):
        return list(self.values.items())

    def all_jobs(self):
        return list(self.values.values())

    def delete(self, key):
        self.values.pop(key, None)


def test_production_retention_respects_durable_downloads_and_active_jobs(tmp_path):
    repository = Store()
    service = SimpleNamespace(
        root=tmp_path, repository=repository, retention_s=10, clock=lambda: 100
    )
    for key, extra in [
        ("durable", {"durable": True}),
        ("download", {"last_accessed": 95}),
        ("expired", {}),
        ("active", {"finished": None}),
    ]:
        directory = tmp_path / f"job-{key}"
        directory.mkdir()
        (directory / "result.json").write_text("{}")
        repository.values[key] = {
            "id": key,
            "directory": str(directory),
            "finished": 1,
            **extra,
        }
    retention = FilesystemJobRetention()
    retention.sweep(service, 100)
    assert set(repository.values) == {"durable", "download", "active"}
    assert not (tmp_path / "job-expired").exists()
    assert (tmp_path / "job-durable/result.json").is_file()
    retention.sweep(service, 106)
    assert "download" not in repository.values
    assert not (tmp_path / "job-download").exists()
    assert (tmp_path / "job-active").is_dir()


def test_production_retention_never_deletes_outside_owned_root(tmp_path):
    owned = tmp_path / "owned"
    outside = tmp_path / "outside"
    owned.mkdir()
    outside.mkdir()
    (outside / "keep.txt").write_text("outside job ownership")
    repository = Store()
    repository.values["invalid"] = {
        "id": "invalid",
        "directory": str(outside),
        "finished": 1,
    }
    service = SimpleNamespace(root=owned, repository=repository, retention_s=10)
    FilesystemJobRetention().sweep(service, 100)
    assert (outside / "keep.txt").read_text() == "outside job ownership"


def test_startup_cleanup_uses_job_activity_instead_of_directory_mtime(tmp_path):
    import os

    repository = Store()
    service = SimpleNamespace(
        root=tmp_path, repository=repository, retention_s=10, clock=lambda: 100
    )
    for key, extra in [
        ("durable", {"durable": True}),
        ("download", {"last_accessed": 95}),
        ("expired", {}),
        ("active", {"finished": None}),
    ]:
        directory = tmp_path / f"job-{key}"
        directory.mkdir()
        os.utime(directory, (1, 1))
        repository.values[key] = {
            "id": key,
            "directory": str(directory),
            "finished": 1,
            **extra,
        }
    FilesystemJobRetention().cleanup_orphaned_directories(service)
    assert set(repository.values) == {"durable", "download", "active"}
    assert not (tmp_path / "job-expired").exists()
    assert all((tmp_path / f"job-{key}").is_dir() for key in repository.values)


def test_startup_cleanup_does_not_follow_external_resolution(tmp_path, monkeypatch):
    from pathlib import Path

    owned = tmp_path / "owned"
    outside = tmp_path / "outside"
    owned.mkdir()
    outside.mkdir()
    alias = owned / "job-external"
    alias.mkdir()
    (outside / "keep.txt").write_text("keep")
    original = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda p, *args, **kwargs: (
            outside if p == alias else original(p, *args, **kwargs)
        ),
    )
    service = SimpleNamespace(
        root=owned, repository=Store(), retention_s=10, clock=lambda: 100
    )
    FilesystemJobRetention().cleanup_orphaned_directories(service)
    assert (outside / "keep.txt").read_text() == "keep"
