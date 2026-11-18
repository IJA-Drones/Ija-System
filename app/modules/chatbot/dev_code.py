"""Bounded, read-only source excerpts from registered handlers and loaded app modules."""
import ast
import hashlib
import inspect
import re
import sys
from pathlib import Path

from flask import current_app

from app.modules.auditoria.diagnostics import clean_text

MAX_FILE_BYTES = 512_000
MAX_SNIPPETS = 5
MAX_LINES = 45
MAX_CHARS = 12_000
SENSITIVE = re.compile(r'password|passwd|senha|secret|token|api.?key|credential|authorization|cookie', re.I)


def _source_path(filename):
    if not isinstance(filename, (str, Path)):
        return None
    root = Path(current_app.root_path).resolve()
    path = Path(filename).resolve()
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    # Config, uploads, instance files and external packages are not source evidence.
    if path.suffix != '.py' or relative.parts[0] not in {'modules', 'shared', 'core'}:
        return None
    return path


def _file(path):
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            return None
        source = raw.decode('utf-8')
        tree = ast.parse(source)
    except (OSError, UnicodeError, SyntaxError):
        return None
    lines = source.splitlines()
    # Do not transmit literal credential values, even if accidentally hardcoded.
    for node in ast.walk(tree):
        targets, value = [], None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        elif isinstance(node, ast.keyword) and node.arg and SENSITIVE.search(node.arg):
            targets, value = [ast.Name(id=node.arg)], node.value
        if value is not None and any(SENSITIVE.search(ast.unparse(target)) for target in targets):
            if any(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in ast.walk(value)):
                for index in range(node.lineno - 1, node.end_lineno):
                    lines[index] = '# literal sensível omitido'
    return tree, lines, hashlib.sha256(raw).hexdigest()


def context(view, audit):
    snippets, seen, files = [], set(), {}
    used = 0
    limited = False

    def add(filename, function, line, origin):
        nonlocal used, limited
        path = _source_path(filename)
        if path is None or not isinstance(function, str) or type(line) is not int:
            return
        if len(snippets) >= MAX_SNIPPETS or used >= MAX_CHARS or (path not in files and len(files) >= 8):
            limited = True
            return
        if path not in files:
            files[path] = _file(path)
        content = files[path]
        if not content:
            return
        tree, lines, fingerprint = content
        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == function and min([node.lineno] + [dec.lineno for dec in node.decorator_list]) <= line <= node.end_lineno]
        if not functions:
            return  # A historical frame that no longer matches is not a source location.
        node = min(functions, key=lambda item: item.end_lineno - item.lineno)
        identity = (path, node.lineno)
        if identity in seen:
            if origin != 'stack_trace':
                return
            relative = 'app/' + str(path.relative_to(Path(current_app.root_path).resolve()))
            if any(item['arquivo'] == relative and item['inicio'] <= line <= item['fim'] for item in snippets):
                return
        if len(snippets) >= MAX_SNIPPETS or used >= MAX_CHARS:
            limited = True
            return
        start = max(node.lineno, line - 12) if origin == 'stack_trace' else node.lineno
        end = min(node.end_lineno, start + MAX_LINES - 1)
        numbered = []
        for number in range(start, end + 1):
            text = f'{number}: {clean_text(lines[number - 1], 350)}'
            if used + len(text) + 1 > MAX_CHARS:
                limited = True
                break
            numbered.append(text)
            used += len(text) + 1
        if not numbered:
            return
        seen.add(identity)
        truncated = start > node.lineno or start + len(numbered) - 1 < node.end_lineno
        limited = limited or truncated
        snippets.append({'arquivo': 'app/' + str(path.relative_to(Path(current_app.root_path).resolve())),
                         'funcao': function, 'inicio': start, 'fim': start + len(numbered) - 1,
                         'origem': origin, 'sha256_arquivo_atual': fingerprint,
                         'truncado': truncated, 'codigo': '\n'.join(numbered)})

    handler = inspect.unwrap(view) if view else None
    if inspect.isfunction(handler):
        add(inspect.getsourcefile(handler), handler.__name__, handler.__code__.co_firstlineno, 'rota')

    # Frames are untrusted audit data: only files belonging to already-loaded app
    # modules can be resolved. No arbitrary path reads or dynamic imports.
    loaded = {}
    for name, module in list(sys.modules.items()):
        if name.startswith(('app.modules.', 'app.shared.', 'app.core.')):
            path = _source_path(getattr(module, '__file__', None))
            if path:
                loaded['app/' + str(path.relative_to(Path(current_app.root_path).resolve()))] = path
    diagnostic = audit.get('registro_selecionado', {}).get('diagnostico', {})
    exceptions = [diagnostic.get('excecao')] + [item.get('excecao') for item in diagnostic.get('logs', [])]
    for exception in exceptions:
        if isinstance(exception, dict):
            for frame in reversed(exception.get('frames', [])):
                path = loaded.get(frame.get('arquivo'))
                if path:
                    add(path, frame.get('funcao'), frame.get('linha'), 'stack_trace')

    if inspect.isfunction(handler):
        for name in handler.__code__.co_names:
            dependency = handler.__globals__.get(name)
            if inspect.isfunction(dependency) and dependency.__module__.startswith('app.'):
                dependency = inspect.unwrap(dependency)
                add(inspect.getsourcefile(dependency), dependency.__name__, dependency.__code__.co_firstlineno, 'dependencia_direta')
    return {'trechos': snippets, 'truncado': limited,
            'versao': 'Código disponível na instância atual; não comprova a versão executada no momento de um erro antigo. '
                      'O SHA-256 identifica o conteúdo atual do arquivo.',
            'limites': 'Até 5 trechos, 45 linhas por trecho e 12 mil caracteres. Sem execução de código, '
                       'variáveis locais ou acesso a arquivos solicitados pelo chat. Trechos podem ser parciais.'}
