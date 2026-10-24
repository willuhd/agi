"""Make the shareable bundle:  python package.py  ->  dist/schoolmap-<version>.zip"""
import shutil
import zipfile
from pathlib import Path

import schoolmap

HERE = Path(__file__).parent
NAME = f"schoolmap-{schoolmap.__version__}"
INCLUDE = ["schoolmap", "output", "floor_plans", "examples", "tests", "tools",
           "README.md", "pyproject.toml", "requirements.txt", "build.py", "package.py"]
SKIP_DIRS = {"__pycache__", "debug", ".pytest_cache"}


def main():
    dist = HERE / "dist"
    stage = dist / NAME
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for item in INCLUDE:
        src = HERE / item
        if src.is_dir():
            shutil.copytree(src, stage / item, ignore=shutil.ignore_patterns(*SKIP_DIRS, "*.pyc"))
        else:
            shutil.copy2(src, stage / item)
    zpath = dist / f"{NAME}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(dist))
    print(f"{zpath}  ({zpath.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
