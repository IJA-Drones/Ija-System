"""Arquiva PDFs retirados e o kit Pesqueira fora das pastas distribuídas."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.modules.treinamentos.catalog import ARCHIVED_MATERIALS, RESOURCE_DIR


def candidates():
    selected = {RESOURCE_DIR / relative for relative, mime in ARCHIVED_MATERIALS.values()
                if mime == "application/pdf"}
    output = ROOT / "output/pdf"
    selected.update(output / path.name for path in tuple(selected))
    selected.update(output / name for name in (
        "IJA-DRONES-Guia-do-Sistema-Atualizado-20261021.pdf",
        "Treinamentos-LIRAa-20261021.pdf", "Treinamentos-Mapa-de-Risco-20261021.pdf",
        "LIRAa-e-SINAN-Conceitos-e-Guia-Pratico-IJA-System.pdf",
    ))
    selected.add(RESOURCE_DIR / "kit-testes-pesqueira-demo.zip")
    return sorted(path for path in selected if path.is_file())


def archive(backup_dir):
    backup_dir = backup_dir.resolve()
    backup_dir.relative_to((ROOT / "instance/backups").resolve())
    manifest = []
    for source in candidates():
        relative = source.relative_to(ROOT)
        target = backup_dir / "materiais" / relative
        content = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        sha = hashlib.sha256(content).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
            raise ValueError("Cópia divergente; os originais não foram removidos.")
        manifest.append(dict(path=str(relative), backup=str(target.relative_to(ROOT)), sha256=sha, bytes=len(content)))
    manifest_path = backup_dir / "materiais-manifest.json"
    with os.fdopen(os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(dict(files=manifest), stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    # Todos os originais têm cópia conferida antes da primeira retirada.
    for item in manifest:
        source = ROOT / item["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Um original mudou durante a revisão; retirada interrompida.")
        source.unlink()
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    if args.backup_dir:
        result = archive(args.backup_dir)
        print(json.dumps(dict(archived=len(result), pdfs=sum(row["path"].endswith(".pdf") for row in result),
                              manifest=str(args.backup_dir / "materiais-manifest.json")), ensure_ascii=False))
    else:
        print(json.dumps([str(path.relative_to(ROOT)) for path in candidates()], ensure_ascii=False, indent=2))
