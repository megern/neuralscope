"""Hash the exact offline wheels produced from the source-verified builder."""

from email.parser import BytesParser
import hashlib
from pathlib import Path
import re
import sys
from zipfile import ZipFile

wheel_directory = Path(sys.argv[1])
requirements = []
for wheel in sorted(wheel_directory.glob("*.whl")):
    with ZipFile(wheel) as archive:
        records = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(records) != 1:
            raise ValueError("Expected one wheel metadata record")
        metadata = BytesParser().parsebytes(archive.read(records[0]))
    name, version = metadata["Name"], metadata["Version"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or not re.fullmatch(
        r"[A-Za-z0-9_.+!]+", version
    ):
        raise ValueError("Unexpected distribution metadata")
    requirements.append(
        f"{name}=={version} --hash=sha256:{hashlib.sha256(wheel.read_bytes()).hexdigest()}"
    )
if not requirements:
    raise ValueError("No built wheels")
(wheel_directory / "built-requirements.lock").write_text("\n".join(requirements) + "\n")
