"""Build a byte-deterministic, allowlisted installable ZIP."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_FILES = (
    "logo.png", "main.py", "default_config.yaml", "README.md", "database/destinations.json",
    "dependencies/destination_engine.py", "dependencies/sra_storage.py",
    "dependencies/sra_keybinds.py", "dependencies/sra_desktop.py",
    "dependencies/sra_navigation.py",
)
EXTRA_FILES = ("LICENSE", "NOTICE.md", "CHANGELOG.md", "docs/COMPATIBILITY.md", "docs/UEX.md")


def build(output, root=ROOT):
    files = {name: root / "set_route_ai" / name for name in PAYLOAD_FILES}
    files.update({name: root / name for name in EXTRA_FILES})
    # Deliberately no globs: future user files cannot enter a release.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, path in sorted(files.items()):
            info = zipfile.ZipInfo("set_route_ai/" + name, (2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, path.read_bytes())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/SetRouteAI-3.2.0.zip")
    args = parser.parse_args()
    print(build(args.output))


if __name__ == "__main__":
    main()
