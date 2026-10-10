"""La base publicada en lulo_app/dataset es exactamente la que produce la ingesta desde el Excel original."""

import hashlib
import json
import sys
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ingest_reto  # noqa: E402

DATASET = ROOT / "lulo_app" / "dataset"
MANIFEST = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_is_the_one_in_the_manifest():
    assert sha(ingest_reto.DEFAULT_SRC) == MANIFEST["fuente"]["sha256"]


def test_committed_files_match_their_manifest_hashes():
    for name, digest in MANIFEST["archivos"].items():
        assert sha(DATASET / name) == digest, name


def test_reingesting_reproduces_every_file(tmp_path):
    ingest_reto.ingest(ingest_reto.DEFAULT_SRC, tmp_path)
    for name in [*MANIFEST["archivos"], "manifest.json", "CALIDAD.md"]:
        assert sha(tmp_path / name) == sha(DATASET / name), name


def test_counts_and_cutoff():
    f = MANIFEST["filas"]
    assert MANIFEST["periodo"] == {"inicio": "2025-11-01", "corte": "2026-10-08"}
    assert f["clientes"] == 600 and f["uso_app"] == 600
    # Todo lo excluido es posterior al corte, y nada se pierde: incluidos + excluidos = total del Excel.
    assert f["movimientos"] + 444 == 20917
    assert f["cajitas"] + 118 == 1826
    assert f["excluidos"] == 444 + 118
    assert max(r.split(",")[2] for r in (DATASET / "movimientos.csv").read_text("utf-8").splitlines()[1:]) <= "2026-10-08"


def test_conversion_column_is_flagged_not_overwritten():
    rows = (DATASET / "campanas_previas.csv").read_text("utf-8").splitlines()
    soat = rows[1].split(",")
    assert soat[0] == "SOAT renovación"
    assert soat[6] == "0.0424"   # lo que reporta el archivo (ventas/elegibles)
    assert soat[7] == "0.129"    # ventas/impactados recalculado: 178/1380


def test_schema_change_stops_the_ingest(tmp_path):
    wb = openpyxl.load_workbook(ingest_reto.DEFAULT_SRC)
    wb["Movimientos"].cell(row=ingest_reto.HEADER_ROW, column=3).value = "monto"
    bad = tmp_path / "mal.xlsx"
    wb.save(bad)
    with pytest.raises(ingest_reto.SchemaError, match="Encabezados de «Movimientos»"):
        ingest_reto.ingest(bad, tmp_path / "out")
    assert ingest_reto.main(["--src", str(bad), "--out", str(tmp_path / "out2")]) == 1
