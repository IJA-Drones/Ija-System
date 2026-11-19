"""Retira referências obsoletas sem descartar os capítulos dos guias gerais."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "app/resources/treinamentos/manuais/biblioteca"


def revise_references(backup_dir):
    backup_dir = backup_dir.resolve()
    backup_dir.relative_to((ROOT / "instance/backups").resolve())
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    changes = (
        ("guia-consultas-personalizadas-ija-system-2026-10-17.pdf", 0,
         rb"\( e \) Tj /F2\+0 11 Tf 15\.18 TL \(SINAN\) Tj",
         b"() Tj /F2+0 11 Tf 15.18 TL () Tj", "SINAN"),
        ("guia-contatos-prefeituras-azul-ija-system-2026-10-17.pdf", 6,
         rb" Compartilhamento[^)]*\) Tj T\* \(fluxos e compro[^)]*\) Tj",
         b") Tj", "Compartilhamento"),
    )
    manifest = []
    for filename, page_index, pattern, replacement, obsolete in changes:
        source = LIBRARY / filename
        content = source.read_bytes()
        reader = PdfReader(source)
        data = reader.pages[page_index].get_contents().get_data()
        revised, count = re.subn(pattern, lambda _match: replacement, data)
        if count != 1:
            raise ValueError(f"Trecho original não corresponde ao esperado: {filename}")
        for path in (source, ROOT / "output/pdf" / filename):
            if not path.exists():
                continue
            target = backup_dir / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            original = path.read_bytes()
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            if target.read_bytes() != original:
                raise ValueError("Backup divergente; original preservado")
            manifest.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(original).hexdigest()))
        writer = PdfWriter(clone_from=reader)
        stream = DecodedStreamObject()
        stream.set_data(revised)
        writer.pages[page_index][NameObject("/Contents")] = writer._add_object(stream)
        temporary = backup_dir / (filename + ".revisado")
        with temporary.open("wb") as output:
            writer.write(output)
        checked = PdfReader(temporary)
        if len(checked.pages) != len(reader.pages) or obsolete in (checked.pages[page_index].extract_text() or ""):
            raise ValueError("Verificação do trecho revisado falhou; original preservado")
        for path in (source, ROOT / "output/pdf" / filename):
            if path.exists():
                path.write_bytes(temporary.read_bytes())
        temporary.unlink()
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def revise_screenshots(backup_dir):
    """Recorta as capturas reais no PDF, sem redesenhar ou inventar interfaces."""
    backup_dir = backup_dir.resolve()
    backup_dir.relative_to((ROOT / "instance/backups").resolve())
    captures = (
        ("guia-consultas-personalizadas-ija-system-2026-10-17.pdf", 0,
         "abd45bb0dde35a48b9ef40b124cddc8d", ("cards", .667, .33)),
        ("guia-relatorios-operacionais.pdf", 0,
         "ecdf3cd5db4f9e9960dcb16af47d9872", ("cards", .66, .40)),
        ("guia-central-ti-permissoes.pdf", 0,
         "29a4d9d155aff972b6ad8652a9656fbb", ("rectangle", .25, 0, .75, .60)),
        ("guia-contatos-prefeituras-azul-ija-system-2026-10-17.pdf", 1,
         "d64ccd9f36d8a3176e3b99e6899ae3a8", ("rectangle", .16, 0, .84, .87)),
    )
    for filename, index, image_id, crop in captures:
        source = LIBRARY / filename
        reader = PdfReader(source)
        data = reader.pages[index].get_contents().get_data()
        pattern = (rb"q\n([0-9.]+) 0 0 ([0-9.]+) ([0-9.]+) ([0-9.]+) cm\n/FormXob\."
                   + image_id.encode() + rb" Do\nQ")
        matches = list(re.finditer(pattern, data))
        if len(matches) != 1:
            raise ValueError(f"Captura diferente da esperada: {filename}")
        match = matches[0]
        image = "/FormXob." + image_id + " Do"
        if crop[0] == "cards":
            _kind, edge_x, edge_y = crop
            original = match.group().decode("ascii")
            clip = f"0 0 {edge_x} 1 re {edge_x} {edge_y} {1-edge_x} {1-edge_y} re W n\n"
            replacement = original.replace(image, clip + image)
        else:
            _kind, x, y, width, height = crop
            a, d, e, f = map(float, match.groups())
            scale = min(1 / width, 1 / height)
            cw, ch = a * scale * width, d * scale * height
            cx, cy = e + (a-cw)/2, f + (d-ch)/2
            tx, ty = cx-a*scale*x, cy-d*scale*y
            replacement = (f"q\n{cx:.5f} {cy:.5f} {cw:.5f} {ch:.5f} re W n\n"
                           f"{a*scale:.5f} 0 0 {d*scale:.5f} {tx:.5f} {ty:.5f} cm\n{image}\nQ")
        data = data[:match.start()] + replacement.encode("ascii") + data[match.end():]
        data = data.replace(b"Capturas reais do sistema local", b"Recortes reais do sistema local")
        data = data.replace(b"Tela real em ambiente local", b"Recorte real em ambiente local")
        writer = PdfWriter(clone_from=reader)
        stream = DecodedStreamObject()
        stream.set_data(data)
        writer.pages[index][NameObject("/Contents")] = writer._add_object(stream)
        temporary = backup_dir / (filename + ".revisado")
        temporary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with temporary.open("wb") as output:
            writer.write(output)
        if len(PdfReader(temporary).pages) != len(reader.pages):
            raise ValueError("O recorte alterou a paginação")
        for path in (source, ROOT / "output/pdf" / filename):
            if not path.exists():
                continue
            backup = backup_dir / path.relative_to(ROOT)
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
                output.write(path.read_bytes())
                output.flush()
                os.fsync(output.fileno())
            if backup.read_bytes() != path.read_bytes():
                raise ValueError("Backup divergente; original preservado")
            path.write_bytes(temporary.read_bytes())
        temporary.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(revise_references(args.backup_dir), ensure_ascii=False))
    revise_screenshots(args.backup_dir / "capturas-antes")
