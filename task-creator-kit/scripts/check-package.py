#!/usr/bin/env python3
import argparse
import io
from pathlib import Path
import re
import sys
import tomllib
import zipfile

SECTIONS = ("Summary", "What the agent sees", "What the agent must get right",
            "What makes it hard", "How the answers are produced", "Checks run", "Running it")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", type=Path)
    parser.add_argument("--zip", type=Path)
    args = parser.parse_args()
    root = args.task.resolve()
    assert root.is_dir(), f"Missing task: {root}"
    for name in ("instruction.md", "README.md", "task.toml", "environment/Dockerfile",
                 "solution/solve.sh", "tests/test.sh"):
        assert (root / name).is_file(), f"Missing {name}"
    config = tomllib.loads((root / "task.toml").read_text())
    assert config["task"]["version"], "Missing task version"
    assert config["environment"]["network_mode"], "Missing environment.network_mode"
    readme = (root / "README.md").read_text()
    headings = dict(re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", readme, re.M | re.S))
    for section in SECTIONS:
        assert headings.get(section, "").strip(), f"Missing README section {section}"
    dockerfile = (root / "environment/Dockerfile").read_text()
    assert all(token in dockerfile for token in ("tmux=3.3a-3", "command -v tmux", "tmux -V")), "Missing pinned tmux install and version check"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            assert not path.is_symlink(), f"Unexpected symlink {relative}"
            assert not any(part in {".git", "__pycache__"} for part in relative.parts), relative
            if path.is_file():
                if "compose" in path.name and path.suffix in {".yml", ".yaml"}:
                    contents = path.read_text()
                    assert "network_mode" not in contents and "harbor-docker-egress-control-sidecar" not in contents
                archive.write(path, relative.as_posix())
    payload = output.getvalue()
    assert len(payload) <= 2_500_000, "Task ZIP exceeds 2.5 MB"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.testzip() is None
    if args.zip:
        destination = args.zip.resolve()
        assert not destination.is_relative_to(root), "Put the ZIP outside the task"
        with destination.open("xb") as stream:
            stream.write(payload)
    print(f"{root.name}: package checks passed, {len(payload)} bytes")

if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, KeyError, ValueError) as error:
        sys.exit(str(error))
