"""Export reviewed Git objects without touching active development checkouts.

This prepares source only. It does not certify builds/tests or package production
configuration, installed dependencies, published static assets, or user data.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile


def git(repository, *args):
    return subprocess.check_output(["git", "-C", str(repository), *args])


def checked_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(p in (".", "..") for p in value.split("/")):
        raise ValueError(f"Unsafe release path: {value}")
    return path


def inspect_revision(repository, revision, forbidden):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Release revisions must be full commit IDs")
    if git(repository, "cat-file", "-t", revision).strip() != b"commit":
        raise ValueError("Release revision is not a commit")
    links = {}
    for entry in git(repository, "ls-tree", "-rz", "-r", revision).split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode()
        if any(path == p or path.startswith(p + "/") for p in forbidden):
            raise ValueError(f"Unreleased hardware in candidate: {path}")
        mode, kind, sha = metadata.decode().split()
        if mode == "160000":
            links[path] = sha
    return links


def export(repository, revision, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile() as archive:
        subprocess.run(["git", "-C", str(repository), "archive", revision], stdout=archive, check=True)
        archive.seek(0)
        with tarfile.open(fileobj=archive) as source:
            # Config is supplied independently; never pick up an env file from
            # Git or a development checkout as part of the source release.
            members = [m for m in source.getmembers()
                       if not any(p == ".env" or p.startswith(".env.") for p in PurePosixPath(m.name).parts)]
            source.extractall(destination, members=members, filter="data")


def prepare(workspace, manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    reviewed = []
    for name, config in manifest["repositories"].items():
        path = checked_path(name)
        if len(path.parts) != 1:
            raise ValueError("Repository name must be one path component")
        forbidden = {"backend": ["hardware"], "vendistri": ["src/vend/hardware"]}.get(name, [])
        links = inspect_revision(workspace / name, config["revision"], forbidden)
        submodules = config["submodules"]
        if links != {p: item["revision"] for p, item in submodules.items()}:
            raise ValueError(f"Unreviewed or mismatched submodule in {name}")
        for path, item in submodules.items():
            checked_path(path)
            repo_path = checked_path(item["repository"])
            if len(repo_path.parts) != 1:
                raise ValueError("Submodule repository must be one path component")
            inspect_revision(workspace / item["repository"], item["revision"], [])
        reviewed.append((name, config))
    # Refuse existing output: never overwrite a previous package or user files.
    output.mkdir(mode=0o700)
    for name, config in reviewed:
        target = output / name
        export(workspace / name, config["revision"], target)
        for path, item in config["submodules"].items():
            target_path = target / path
            # Prevent a malicious Git tree from escaping through a parent link.
            if not target_path.resolve().is_relative_to(target.resolve()):
                raise ValueError("Submodule destination escapes its repository")
            export(workspace / item["repository"], item["revision"], target_path)
    (output / "source-release.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and not path.is_symlink():
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}")
    (output / "source.sha256").write_text("\n".join(rows) + "\n")
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("release.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    count = prepare(args.workspace.resolve(), args.manifest.resolve(), args.output.resolve())
    print(f"Prepared {count} checksummed source files in {args.output}; build/runtime acceptance remains pending")
