"""Aceite da prévia provisória: integridade do lote, denominador e CLI sem aplicação."""

import csv
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = ROOT / "scripts" / "validate_vigilancia_preview.py"
spec = importlib.util.spec_from_file_location("vigilancia_preview_cli_tests", CLI_PATH)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
service, sample = cli._load_preview_modules()


def record(**overrides):
    return {
        "municipio_id": "1",
        "origem": "LIRAA",
        "imovel_codigo": "0001",
        "inspecao_codigo": "00001",
        "data_inspecao": "2026-01-10",
        "bairro": "Bairro Sintético São João",
        "area_codigo": "001",
        "levantamento_codigo": "0001",
        "estrato_codigo": "01",
        "situacao": "INSPECIONADO",
        "positivo_aedes": "SIM",
        "latitude": "",
        "longitude": "",
        **overrides,
    }


def csv_content(rows, *, headers=service.CSV_COLUMNS, delimiter=",", bom=False):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(name, "") for name in headers] if isinstance(row, dict) else row)
    return stream.getvalue().encode("utf-8-sig" if bom else "utf-8")


class VigilanciaPreviewTests(unittest.TestCase):
    def preview(self, rows):
        return service.preview_csv(csv_content(rows), prefeitura_id=1)

    def assert_rejected(self, overrides, *, field=None, code=None):
        result = self.preview([record(**overrides)])
        self.assertEqual(result["status"], "COM_PENDENCIAS")
        self.assertEqual(result["resumo"]["aceitas"], 0)
        self.assertEqual(result["resumo"]["rejeitadas"], 1)
        self.assertEqual(result["registros"], [])
        self.assertTrue(result["erros"])
        self.assertTrue(all(error["linha"] == 2 for error in result["erros"]))
        if field:
            self.assertTrue(any(error["campo"] == field for error in result["erros"]))
        if code:
            self.assertTrue(any(error["codigo"] == code for error in result["erros"]))
        return result

    def test_synthetic_sample_counts_unique_liraa_properties_and_excludes_focal(self):
        result = service.preview_csv(sample.build_sample_csv(17), prefeitura_id=17)
        self.assertEqual(result["layout"], "ija-vigilancia-preview-v1")
        self.assertTrue(result["provisorio"])
        self.assertFalse(result["persistido"])
        self.assertEqual(result["status"], "VALIDADO")
        self.assertEqual(result["resumo"], {
            "linhas": 5, "aceitas": 5, "duplicadas": 0, "rejeitadas": 0,
            "imoveis": 5, "inspecoes": 5, "sem_coordenadas": 2,
        })
        self.assertEqual(len(result["indicadores"]), 1)
        indicator = result["indicadores"][0]
        self.assertEqual(indicator["imoveis_inspecionados"], 3)
        self.assertEqual(indicator["imoveis_positivos"], 1)
        self.assertEqual(indicator["imoveis_pendentes"], 1)
        self.assertEqual(indicator["iip"], 33.33)
        self.assertEqual(indicator["status"], "PREVIA")
        self.assertTrue(all(row["municipio_id"] == 17 for row in result["registros"]))
        self.assertTrue(all("SINTETIC" in row["imovel_codigo"] for row in result["registros"]))
        self.assertTrue(all(row["data_inspecao"] == "2026-01-10" for row in result["registros"]))

    def test_focal_records_do_not_create_liraa_indicators(self):
        result = self.preview([record(origem="FOCAL", levantamento_codigo="", estrato_codigo="")])
        self.assertEqual(result["resumo"]["aceitas"], 1)
        self.assertEqual(result["indicadores"], [])

    def test_pending_property_is_not_denominator_and_zero_is_unavailable(self):
        result = self.preview([record(situacao="RECUSADO", positivo_aedes="")])
        indicator = result["indicadores"][0]
        self.assertEqual(indicator["imoveis_inspecionados"], 0)
        self.assertEqual(indicator["imoveis_pendentes"], 1)
        self.assertIsNone(indicator["iip"])
        self.assertEqual(indicator["status"], "INDISPONIVEL")

    def test_one_rejected_row_blocks_every_other_group_percentage(self):
        result = self.preview([
            record(),
            record(imovel_codigo="0002", inspecao_codigo="00002", levantamento_codigo="0002", positivo_aedes="NAO"),
            record(imovel_codigo="0003", inspecao_codigo="00003", origem="FOCAL", levantamento_codigo="", estrato_codigo="", data_inspecao="2026-02-30"),
        ])
        self.assertEqual(result["resumo"]["rejeitadas"], 1)
        self.assertEqual(len(result["indicadores"]), 2)
        self.assertTrue(all(indicator["iip"] is None for indicator in result["indicadores"]))
        self.assertTrue(all(indicator["status"] == "INDISPONIVEL" for indicator in result["indicadores"]))

    def test_text_identifiers_keep_leading_zeros_and_utf8_bom_semicolon(self):
        result = service.preview_csv(csv_content([record()], delimiter=";", bom=True), prefeitura_id=1)
        normalized = result["registros"][0]
        for name in ("imovel_codigo", "inspecao_codigo", "area_codigo", "levantamento_codigo", "estrato_codigo"):
            self.assertEqual(normalized[name], record()[name])
        self.assertEqual(normalized["bairro"], "Bairro Sintético São João")
        self.assertEqual(normalized["municipio_id"], 1)

    def test_invalid_dates_are_rejected(self):
        for value in ("2026-02-30", "2026-13-01", "10/01/2026", "2026-1-10", "2026-01-10T10:00:00"):
            with self.subTest(value=value):
                self.assert_rejected({"data_inspecao": value}, field="data_inspecao", code="DATA_INVALIDA")

    def test_nonfinite_out_of_range_or_unpaired_coordinates_are_rejected(self):
        for latitude, longitude in (("NaN", "0"), ("inf", "0"), ("-inf", "0"), ("91", "0"), ("-91", "0"), ("0", "181"), ("0", "-181"), ("-23.5", ""), ("", "-46.6")):
            with self.subTest(latitude=latitude, longitude=longitude):
                self.assert_rejected({"latitude": latitude, "longitude": longitude})

    def test_absent_and_zero_coordinates_are_distinguished(self):
        result = self.preview([
            record(),
            record(imovel_codigo="0002", inspecao_codigo="00002", latitude="0", longitude="0", positivo_aedes="NAO"),
        ])
        self.assertIsNone(result["registros"][0]["latitude"])
        self.assertEqual(result["registros"][1]["latitude"], 0.0)
        self.assertEqual(result["resumo"]["sem_coordenadas"], 1)
        self.assertEqual(len(result["pontos"]), 1)

    def test_wrong_municipality_is_quarantined(self):
        self.assert_rejected({"municipio_id": "2"}, field="municipio_id", code="MUNICIPIO_FORA_ESCOPO")

    def test_huge_municipality_identifiers_are_handled_without_traceback(self):
        self.assert_rejected({"municipio_id": "9" * 5000}, field="municipio_id", code="MUNICIPIO_INVALIDO")
        self.assert_rejected({"municipio_id": str(service.MAX_PREFEITURA_ID + 1)}, field="municipio_id", code="MUNICIPIO_INVALIDO")
        with self.assertRaises(service.PreviewValidationError) as invalid_scope:
            service.preview_csv(csv_content([record()]), prefeitura_id=service.MAX_PREFEITURA_ID + 1)
        self.assertEqual(invalid_scope.exception.codigo, "PREFEITURA_INVALIDA")

    def test_origin_specific_and_inspection_outcome_rules(self):
        for overrides in (
            {"origem": "OUTRA"},
            {"levantamento_codigo": ""},
            {"estrato_codigo": ""},
            {"origem": "FOCAL"},
            {"situacao": "PENDENTE"},
            {"positivo_aedes": ""},
            {"situacao": "FECHADO", "positivo_aedes": "SIM"},
        ):
            with self.subTest(overrides=overrides):
                self.assert_rejected(overrides)

    def test_required_identifiers_and_area_are_rejected_when_absent(self):
        for name in ("imovel_codigo", "inspecao_codigo", "bairro", "area_codigo"):
            with self.subTest(name=name):
                self.assert_rejected({name: ""}, field=name)

    def test_missing_extra_and_repeated_headers_stop_validation(self):
        headers_cases = (
            service.CSV_COLUMNS[:-1],
            (*service.CSV_COLUMNS, "coluna_extra"),
            (*service.CSV_COLUMNS[:-1], "latitude"),
        )
        for headers in headers_cases:
            with self.subTest(headers=headers):
                with self.assertRaises(service.PreviewValidationError):
                    service.preview_csv(csv_content([record()], headers=headers), prefeitura_id=1)

    def test_bad_csv_quoting_and_row_arity_stop_validation(self):
        header = ",".join(service.CSV_COLUMNS).encode("utf-8") + b"\n"
        malformed = header + b'1,LIRAA,"unclosed\n'
        with self.assertRaises(service.PreviewValidationError):
            service.preview_csv(malformed, prefeitura_id=1)
        for values in (list(record().values())[:-1], [*record().values(), "EXTRA"]):
            with self.subTest(length=len(values)):
                with self.assertRaises(service.PreviewValidationError):
                    service.preview_csv(csv_content([values]), prefeitura_id=1)

    def test_empty_header_only_and_invalid_encoding_stop_validation(self):
        for content in (b"", b"  \n", csv_content([]), b"\xffinvalid"):
            with self.subTest(content=content):
                with self.assertRaises(service.PreviewValidationError):
                    service.preview_csv(content, prefeitura_id=1)

    def test_size_and_row_limits_stop_validation(self):
        with self.assertRaises(service.PreviewValidationError) as too_large:
            service.preview_csv(b"x" * (service.MAX_FILE_BYTES + 1), prefeitura_id=1)
        self.assertEqual(too_large.exception.codigo, "ARQUIVO_MUITO_GRANDE")
        content = csv_content([record()] * (service.MAX_ROWS + 1))
        self.assertLess(len(content), service.MAX_FILE_BYTES)
        with self.assertRaises(service.PreviewValidationError) as too_many:
            service.preview_csv(content, prefeitura_id=1)
        self.assertEqual(too_many.exception.codigo, "MUITAS_LINHAS")

    def test_identical_duplicates_are_counted_once(self):
        result = self.preview([record(), record()])
        self.assertEqual(result["resumo"], {
            "linhas": 2, "aceitas": 1, "duplicadas": 1, "rejeitadas": 0,
            "imoveis": 1, "inspecoes": 1, "sem_coordenadas": 1,
        })
        self.assertEqual(result["indicadores"][0]["imoveis_inspecionados"], 1)

    def test_changed_same_inspection_quarantines_all_copies(self):
        result = self.preview([record(), record(), record(positivo_aedes="NAO")])
        self.assertEqual(result["resumo"], {
            "linhas": 3, "aceitas": 0, "duplicadas": 0, "rejeitadas": 3,
            "imoveis": 0, "inspecoes": 0, "sem_coordenadas": 0,
        })
        self.assertEqual({error["linha"] for error in result["erros"]}, {2, 3, 4})
        self.assertTrue(all(error["codigo"] == "INSPECAO_CONFLITANTE" for error in result["erros"]))
        self.assertEqual(result["registros"], [])

    def test_reinspections_do_not_inflate_property_denominator(self):
        result = self.preview([
            record(), record(inspecao_codigo="00002"),
            record(imovel_codigo="0002", inspecao_codigo="00003", positivo_aedes="NAO"),
        ])
        self.assertEqual(result["resumo"]["inspecoes"], 3)
        self.assertEqual(result["resumo"]["imoveis"], 2)
        indicator = result["indicadores"][0]
        self.assertEqual(indicator["imoveis_inspecionados"], 2)
        self.assertEqual(indicator["imoveis_positivos"], 1)
        self.assertEqual(indicator["iip"], 50.0)

    def test_completed_inspection_resolves_pending_property_in_group(self):
        result = self.preview([record(situacao="FECHADO", positivo_aedes=""), record(inspecao_codigo="00002")])
        self.assertEqual(result["resumo"]["aceitas"], 2)
        indicator = result["indicadores"][0]
        self.assertEqual(indicator["imoveis_inspecionados"], 1)
        self.assertEqual(indicator["imoveis_pendentes"], 0)

    def test_newer_pending_visit_is_not_hidden_by_earlier_inspection(self):
        result = self.preview([
            record(data_inspecao="2026-01-10"),
            record(inspecao_codigo="00002", data_inspecao="2026-01-11", situacao="RECUSADO", positivo_aedes=""),
        ])
        self.assertEqual(result["resumo"]["aceitas"], 2)
        indicator = result["indicadores"][0]
        self.assertEqual(indicator["imoveis_inspecionados"], 1)
        self.assertEqual(indicator["imoveis_pendentes"], 1)
        self.assertEqual(indicator["iip"], 100.0)

    def test_contradictory_liraa_reinspections_require_review(self):
        result = self.preview([record(), record(inspecao_codigo="00002", positivo_aedes="NAO")])
        self.assertEqual(result["resumo"]["rejeitadas"], 2)
        self.assertEqual(result["resumo"]["aceitas"], 0)
        self.assertTrue(all(error["codigo"] == "RESULTADO_LIRAA_CONFLITANTE" for error in result["erros"]))

    def test_changed_property_territory_requires_review(self):
        result = self.preview([record(), record(inspecao_codigo="00002", area_codigo="002")])
        self.assertEqual(result["resumo"]["rejeitadas"], 2)
        self.assertTrue(all(error["codigo"] == "IMOVEL_INCONSISTENTE" for error in result["erros"]))

    def test_property_in_conflicting_strata_quarantines_all_liraa_occurrences(self):
        result = self.preview([
            record(),
            record(inspecao_codigo="00002", estrato_codigo="02"),
            record(inspecao_codigo="00003", situacao="FECHADO", positivo_aedes=""),
        ])
        self.assertEqual(result["resumo"]["rejeitadas"], 3)
        self.assertEqual(result["resumo"]["aceitas"], 0)
        self.assertEqual({error["linha"] for error in result["erros"]}, {2, 3, 4})
        self.assertTrue(all(error["codigo"] == "ESTRATO_LIRAA_CONFLITANTE" for error in result["erros"]))

    def test_property_may_change_stratum_in_a_different_liraa_survey(self):
        result = self.preview([record(), record(inspecao_codigo="00002", levantamento_codigo="0002", estrato_codigo="02")])
        self.assertEqual(result["resumo"]["aceitas"], 2)
        self.assertEqual(result["resumo"]["rejeitadas"], 0)
        self.assertEqual(len(result["indicadores"]), 2)
        self.assertTrue(all(indicator["imoveis_inspecionados"] == 1 for indicator in result["indicadores"]))

    def test_rerun_is_deterministic_without_mutating_input(self):
        content = sample.build_sample_csv(1)
        first = service.preview_csv(content, prefeitura_id=1)
        self.assertEqual(service.preview_csv(content, prefeitura_id=1), first)
        first["registros"][0]["bairro"] = "alterado pelo consumidor"
        self.assertNotEqual(service.preview_csv(content, prefeitura_id=1)["registros"][0]["bairro"], first["registros"][0]["bairro"])
        self.assertEqual(sample.build_sample_csv(1), content)

    def test_sample_rejects_invalid_municipality(self):
        for value in (0, -1, True, "1", None, service.MAX_PREFEITURA_ID + 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    sample.build_sample_csv(value)


class VigilanciaPreviewCliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, "-S", str(CLI_PATH), *map(str, arguments)], cwd=ROOT, capture_output=True, text=True, check=False)

    def test_sample_cli_works_without_site_packages_or_database(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sample.json"
            result = self.run_cli("--sample", "--municipio-id", 17, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["prefeitura_id"], 17)
            self.assertFalse(payload["persistido"])
            self.assertEqual(payload["indicadores"][0]["iip"], 33.33)
            self.assertIn("33.33%", result.stdout)
            self.assertNotIn("ROTAS CARREGADAS", result.stdout)

    def test_file_cli_marks_rejections_and_leaves_source_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            output = Path(directory) / "result.json"
            content = csv_content([record(municipio_id="2")])
            source.write_bytes(content)
            result = self.run_cli(source, "--municipio-id", 1, "--output", output)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(source.read_bytes(), content)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["resumo"]["rejeitadas"], 1)

    def test_cli_reports_structural_errors_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "error.json"
            result = self.run_cli(Path(directory) / "missing.csv", "--municipio-id", 1, "--output", output)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "INVALIDO")
            source = Path(directory) / "bad.csv"
            source.write_bytes(b"unknown\nvalue\n")
            result = self.run_cli(source, "--municipio-id", 1)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Estrutura/arquivo inválido", result.stderr)

    def test_cli_requires_exactly_one_input_and_positive_municipality(self):
        for arguments in (("--municipio-id", "1"), ("--sample", "file.csv", "--municipio-id", "1"), ("--sample", "--municipio-id", "0"), ("--sample", "--municipio-id", str(service.MAX_PREFEITURA_ID + 1)), ("--sample", "--municipio-id", "9" * 5000)):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_cli(*arguments).returncode, 2)

    def test_cli_cannot_overwrite_csv_with_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            original = csv_content([record()])
            source.write_bytes(original)
            result = self.run_cli(source, "--municipio-id", 1, "--output", source)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
