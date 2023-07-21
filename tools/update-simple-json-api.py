import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import boto3
import pydantic
from packaging.utils import canonicalize_name
from pyodide_lock.spec import PyodideLockSpec

CDN_URL = "https://cdn.jsdelivr.net/pyodide/v{version}/full/"


def get_tags() -> list[str]:
    """Return a list of Pyodide release versions"""
    url = "https://api.github.com/repos/pyodide/pyodide/tags"
    response = urllib.request.urlopen(url)

    if response.getcode() == 200:
        response = json.loads(response.read().decode())
        tags = [tag["name"].strip("v") for tag in response]
        return [tag for tag in tags if re.match("\\d+\\.\\d+\\.\\d+$", tag)]
    else:
        raise ValueError("Unable to retrieve tags")


def get_pyodide_lock(version: str) -> PyodideLockSpec | None:
    for index_name in ["pyodide-lock.json", "repodata.json", "packages.json"]:
        try:
            response = urllib.request.urlopen(
                CDN_URL.format(version=version) + index_name
            )
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            else:
                raise e
        if response.getcode() == 200:
            break
    else:
        raise ValueError(f"Couldn't find a pyodide index for version {version}")

    data = json.loads(response.read().decode())
    lock = pydantic.parse_obj_as(PyodideLockSpec, data)

    return lock


def create_main_json(db: list[PyodideLockSpec]) -> dict[str, Any]:
    """Create the main JSON file for the simple API"""
    projects = set()
    for lock in db:
        projects.update(lock.packages.keys())
    res = {
        "meta": {"api-version": "1.0"},
        "projects": list(sorted(canonicalize_name(name) for name in projects)),
    }
    return res, projects


def create_project_json(db: list[PyodideLockSpec], name: str) -> dict[str, Any]:
    project_normalized = canonicalize_name(name)
    res = {
        "meta": {"api-version": "1.0"},
        "name": project_normalized,
    }

    files = []

    for lock in db:
        if name not in lock.packages:
            continue
        package = lock.packages[name]
        entry = {
            "filename": package.file_name,
            "url": CDN_URL.format(version=lock.info.version) + package.file_name,
            "hashes": {"sha256": package.sha256},
            "requires-python": "==" + ".".join(lock.info.python.split(".")[:2]),
        }
        files.append(entry)
    # Re-order so that the newest patch releases are picked by pip first
    res["files"] = files[::-1]
    return res


def main(bucket_name: str = "pyodide-pypi-api"):
    tags = get_tags()
    # Skip old versions
    tags = [tag for tag in tags if int(tag.split(".")[1]) > 20]
    db = []
    for tag in tags:
        lock = get_pyodide_lock(tag)
        db.append(lock)

    # Write files to a temporary directory before writing to S3, mostly for debugging
    tmp_dir = Path("/tmp/simple")

    s3 = boto3.client("s3")

    main_json, projects = create_main_json(db)
    (tmp_dir).mkdir(parents=True, exist_ok=True)

    (tmp_dir / "index.json").write_text(json.dumps(main_json, indent=2))
    s3.upload_file(
        tmp_dir / "index.json",
        bucket_name,
        "simple/",
        ExtraArgs={"ContentType": "application/vnd.pypi.simple.v1+json"},
    )

    print(f"Uploading index for {len(projects)} projects:")

    for idx, project in enumerate(list(projects)):
        project_normalized = canonicalize_name(project)
        project_json = create_project_json(db, project)
        (tmp_dir / project_normalized).mkdir(parents=True, exist_ok=True)
        (tmp_dir / project_normalized / "index.json").write_text(
            json.dumps(project_json, indent=2)
        )
        s3.upload_file(
            tmp_dir / project_normalized / "index.json",
            bucket_name,
            f"simple/{project_normalized}/",
            ExtraArgs={"ContentType": "application/vnd.pypi.simple.v1+json"},
        )
        print(".", end="", flush=True)
        if idx % 20 == 0:
            print(idx, end="", flush=True)
    print("")


if __name__ == "__main__":
    main()
