"""Gera o inventário técnico sem importar a aplicação, ler .env ou acessar o banco."""

import argparse
import ast
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "referencia-codigo.md"


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def literal(node, default=None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def code(value):
    return "`" + str(value).replace("|", "&#124;") + "`"


def render_inventory():
    python_files = sorted((ROOT / "app").rglob("*.py"))
    modules = sorted(p for p in (ROOT / "app/modules").iterdir() if (p / "__init__.py").exists())
    routes = []
    for path in python_files:
        for node in ast.walk(parse(path)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr
                if method not in {"route", "get", "post", "put", "patch", "delete"} or not decorator.args:
                    continue
                rule = literal(decorator.args[0])
                if not isinstance(rule, str):
                    continue
                kwargs = {kw.arg: kw.value for kw in decorator.keywords}
                methods = literal(kwargs.get("methods"), ["GET"] if method == "route" else [method.upper()])
                endpoint = literal(kwargs.get("endpoint"), node.name)
                routes.append((path.relative_to(ROOT).as_posix(), decorator.lineno, rule, methods, endpoint))

    models = []
    for node in parse(ROOT / "app/models.py").body:
        if not isinstance(node, ast.ClassDef):
            continue
        table = None
        fields = []
        foreign_keys = []
        for field in node.body:
            if not isinstance(field, ast.Assign) or not isinstance(field.targets[0], ast.Name):
                continue
            name = field.targets[0].id
            if name == "__tablename__":
                table = literal(field.value)
            if isinstance(field.value, ast.Call) and ast.unparse(field.value.func) == "db.Column":
                fields.append(name)
                for call in ast.walk(field.value):
                    if isinstance(call, ast.Call) and ast.unparse(call.func) == "db.ForeignKey":
                        foreign_keys.append(f"{name} → {literal(call.args[0])}")
        if table:
            models.append((node.name, table, fields, foreign_keys))

    revisions = {}
    for path in sorted((ROOT / "migrations/versions").glob("*.py")):
        values = {}
        for node in parse(path).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                values[node.targets[0].id] = literal(node.value)
        if values.get("revision"):
            revisions[values["revision"]] = values.get("down_revision")
    parents = {parent for value in revisions.values() for parent in
               (value if isinstance(value, tuple) else (value,)) if parent}
    heads = sorted(set(revisions) - parents)
    bases = sorted(revision for revision, parent in revisions.items() if parent is None)

    test_files = sorted((ROOT / "tests").glob("test_*.py"))
    test_counts = [(path.name, sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 and node.name.startswith("test_") for node in ast.walk(parse(path))))
                   for path in test_files]
    lines = [
        "# Referência do código", "",
        "Arquivo gerado por `python scripts/build_docs_inventory.py`. Não editar as tabelas manualmente.", "",
        "O inventário lê apenas o código-fonte com AST. Não importa a aplicação, não lê `.env` e não acessa serviços externos.",
        "As rotas são declarações estáticas: não incluem a rota estática criada pelo Flask nem métodos HEAD/OPTIONS implícitos.",
        "A presença de uma rota não comprova permissão de acesso, funcionamento em produção ou um contrato de API pública.", "",
        "## Dimensão do código", "",
        "| Item | Quantidade |", "| --- | ---: |",
        f"| Módulos em `app/modules` | {len(modules)} |",
        f"| Arquivos Python em `app` | {len(python_files)} |",
        f"| Declarações de rotas | {len(routes)} |",
        f"| Modelos com tabela em `app/models.py` | {len(models)} |",
        f"| Templates HTML | {len(list((ROOT / 'app/templates').rglob('*.html')))} |",
        f"| Arquivos CSS, incluindo bundle | {len(list((ROOT / 'app/static').rglob('*.css')))} |",
        f"| Arquivos JavaScript em `app/static`, incluindo service worker | {len(list((ROOT / 'app/static').rglob('*.js')))} |",
        f"| Revisões Alembic | {len(revisions)} |",
        f"| Arquivos Python de teste | {len(test_files)} |",
        f"| Funções/métodos Python com prefixo `test_` | {sum(n for _, n in test_counts)} |",
        f"| Arquivos Node de teste | {len(list((ROOT / 'tests').glob('*.test.cjs')))} |", "",
        "A contagem estática de testes não inclui subtestes e não substitui a execução da suíte.", "",
        "## Módulos", "", "| Módulo | Rotas declaradas | Fontes Python |", "| --- | ---: | ---: |",
    ]
    counts = Counter(path.split("/")[2] for path, *_ in routes if path.startswith("app/modules/"))
    for path in modules:
        lines.append(f"| [{path.name}](../app/modules/{path.name}/) | {counts[path.name]} | {len(list(path.rglob('*.py')))} |")
    lines += ["", "## Modelos e vínculos", "",
              "Os campos abaixo são declarações diretas da classe. Tipos, defaults, índices, relacionamentos ORM e campos herdados devem ser consultados em [models.py](../app/models.py).", "",
              "| Modelo | Tabela | Campos declarados | Chaves estrangeiras declaradas |",
              "| --- | --- | --- | --- |"]
    for name, table, fields, keys in models:
        lines.append(f"| {code(name)} | {code(table)} | {', '.join(map(code, fields))} | {'; '.join(map(code, keys)) or '—'} |")
    lines += ["", "## Migrações", "", f"Heads: {', '.join(map(code, heads))}.", "",
              f"Bases: {', '.join(map(code, bases))}.", "",
              "Um head único verifica a estrutura do grafo; não comprova instalação em banco vazio nem atualização de uma base existente. Veja o [guia de operação](operacao.md).", "",
              "## Rotas por arquivo", "",
              "O endpoint mostrado é o nome local declarado. Em geral recebe o prefixo `main.`; autenticação usa `auth.` e sessão usa `session_security.`. Health checks são registrados diretamente na aplicação."]
    previous = None
    for path, line, rule, methods, endpoint in sorted(routes):
        if path != previous:
            lines += ["", f"### {path}", "", f"Fonte: [{path}](../{path}).", "",
                      "| Método | Caminho | Endpoint local | Linha |", "| --- | --- | --- | ---: |"]
            previous = path
        lines.append(f"| {', '.join(methods)} | {code(rule)} | {code(endpoint)} | {line} |")
    lines += ["", "## Testes Python", "", "| Arquivo | Casos declarados |", "| --- | ---: |"]
    for name, count in test_counts:
        lines.append(f"| [{name}](../tests/{name}) | {count} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verifica sem gravar; retorna 1 se o inventário estiver desatualizado.")
    args = parser.parse_args()
    expected = render_inventory()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            print("Inventário desatualizado. Execute python scripts/build_docs_inventory.py.")
            return 1
        print("Inventário de documentação atualizado.")
        return 0
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Inventário gerado: {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
