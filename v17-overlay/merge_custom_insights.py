#!/usr/bin/env python3
"""Apply the existing custom Insights archive without modifying its Analytics implementation."""
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile
import sys

ARCHIVE = Path("SimpMusic-Insights-stage1-patch.zip")
MAIN_BASE = "140673ab2f2b83d5a2264d3a5f51f1dce3ab6b05"
CORE_URL = "https://github.com/maxrave-dev/core.git"
APP_URL = "https://github.com/maxrave-dev/SimpMusic.git"

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

if not ARCHIVE.is_file():
    raise SystemExit("Missing custom Insights archive on the Cloud-Sync branch.")

# The archive's app files are based on the custom 2.6 app tree, so apply those directly.
# Its core files are older than our pinned 2.7 core and must be merged, never blindly overwritten.
run(["git", "fetch", APP_URL, MAIN_BASE])
core_base_line = run(
    ["git", "ls-tree", MAIN_BASE, "core"],
    text=True, stdout=subprocess.PIPE,
).stdout.strip().split()
if len(core_base_line) < 3:
    raise SystemExit("Could not resolve the core submodule commit used by the Insights archive base.")
CORE_BASE = core_base_line[2]
run(["git", "-C", "core", "fetch", CORE_URL, CORE_BASE])
run(["git", "-C", "core", "cat-file", "-e", f"{CORE_BASE}^{{commit}}"])
run(["git", "-C", "core", "merge-base", "--is-ancestor", CORE_BASE, "HEAD"])

merged_core = {}
app_files = []
with zipfile.ZipFile(ARCHIVE) as archive, tempfile.TemporaryDirectory() as temp_dir:
    temp = Path(temp_dir)
    for index, name in enumerate(archive.namelist()):
        if not name or name.endswith("/") or name == "PATCH_NOTES.txt":
            continue
        rel = PurePosixPath(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise SystemExit(f"Unsafe archive path: {name}")
        overlay_data = archive.read(name)
        if rel.parts[0] != "core":
            target = Path(*rel.parts)
            app_files.append((target, overlay_data))
            continue

        target_rel = Path(*rel.parts[1:])
        target = Path("core") / target_rel
        if not target.exists():
            merged_core[target] = overlay_data
            continue

        base_result = subprocess.run(
            ["git", "-C", "core", "show", f"{CORE_BASE}:{target_rel.as_posix()}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if base_result.returncode != 0:
            raise SystemExit(f"Core overlay target has no merge-base file: {target_rel}")

        current_file = temp / f"current-{index}"
        base_file = temp / f"base-{index}"
        overlay_file = temp / f"overlay-{index}"
        current_file.write_bytes(target.read_bytes())
        base_file.write_bytes(base_result.stdout)
        overlay_file.write_bytes(overlay_data)
        result = subprocess.run(
            [
                "git", "merge-file", "-p",
                "-L", "SimpMusic custom core",
                "-L", "official 2.6 core base",
                "-L", "Insights stage 1",
                str(current_file), str(base_file), str(overlay_file),
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise SystemExit(f"Insights core merge conflict in {target_rel}")
        merged_core[target] = result.stdout

for target, data in app_files:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
for target, data in merged_core.items():
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

print(f"Applied {len(app_files)} custom Insights app files and merged {len(merged_core)} core files into the pinned 2.7 core.")
