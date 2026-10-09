"""Valida o CSV provisório em memória, sem importar a aplicação, banco ou rede."""

import argparse
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_ija_vigilancia_preview"


def _load_preview_modules():
    # O pacote isolado evita executar app/__init__.py e seus imports Flask/SQLAlchemy.
    if PACKAGE_NAME not in sys.modules:
        package = ModuleType(PACKAGE_NAME)
        package.__path__ = [str(ROOT / "app" / "modules" / "vigilancia")]
        package.__package__ = PACKAGE_NAME
        sys.modules[PACKAGE_NAME] = package
    return (
        importlib.import_module(f"{PACKAGE_NAME}.service"),
        importlib.import_module(f"{PACKAGE_NAME}.sample"),
    )


def _municipio_id(value):
    try:
        identifier = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Informe um identificador inteiro positivo.") from exc
    if not 1 <= identifier <= _load_preview_modules()[0].MAX_PREFEITURA_ID:
        raise argparse.ArgumentTypeError("Informe um identificador positivo compatível com o código interno da prefeitura.")
    return identifier


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo", nargs="?", type=Path, help="CSV UTF-8 a validar; use apenas dados sintéticos ou autorizados.")
    parser.add_argument("--sample", action="store_true", help="Valida cinco linhas ficcionais geradas localmente.")
    parser.add_argument("--municipio-id", type=_municipio_id, required=True, help="Município esperado para todas as linhas.")
    parser.add_argument("--output", type=Path, help="Grava o resultado completo em JSON UTF-8 neste arquivo local.")
    args = parser.parse_args(argv)
    if args.sample == (args.arquivo is not None):
        parser.error("Escolha um arquivo CSV ou --sample, exclusivamente.")
    if args.arquivo is not None and args.output is not None and args.arquivo.resolve() == args.output.resolve():
        parser.error("O JSON de saída deve usar um caminho diferente do CSV de origem.")
    return args


def _write_output(path, result):
    if path is not None:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    args = parse_args(argv)
    service, sample = _load_preview_modules()
    try:
        if args.sample:
            content = sample.build_sample_csv(args.municipio_id)
        else:
            with args.arquivo.open("rb") as stream:
                content = stream.read(service.MAX_FILE_BYTES + 1)
        result = service.preview_csv(content, prefeitura_id=args.municipio_id)
    except (OSError, service.PreviewValidationError) as exc:
        failure = {"layout": service.LAYOUT_VERSION, "status": "INVALIDO", "erro": str(exc)}
        try:
            _write_output(args.output, failure)
        except OSError as output_error:
            print(f"Não foi possível gravar o JSON: {output_error}", file=sys.stderr)
        print(f"Estrutura/arquivo inválido: {exc}", file=sys.stderr)
        return 2

    try:
        _write_output(args.output, result)
    except OSError as exc:
        print(f"Não foi possível gravar o JSON: {exc}", file=sys.stderr)
        return 2

    summary = result["resumo"]
    print(f"Layout provisório: {service.LAYOUT_VERSION}")
    print(f"Município: {args.municipio_id}; linhas: {summary['linhas']}; aceitas: {summary['aceitas']}; duplicadas: {summary['duplicadas']}; rejeitadas: {summary['rejeitadas']}.")
    for indicator in result["indicadores"]:
        value = "indisponível" if indicator["iip"] is None else f"{indicator['iip']:.2f}%"
        print(f"Prévia LIRAa {indicator['levantamento_codigo']} / {indicator['estrato_codigo']} / {indicator['area_codigo']}: {value} ({indicator['status']}).")
    print("Resultado em memória; não confirma índice oficial e não aplica dados ao banco.")
    if args.output:
        print(f"JSON local: {args.output}")
    return 1 if summary["rejeitadas"] or result["erros"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
