"""Bounded request diagnostics, persisted alongside the existing audit response.

Capture message templates (never interpolation arguments), exception types and stack
locations. No exception values, SQL parameters, locals, headers or request bodies.
"""
import ast
import linecache
import logging
import re
from pathlib import Path

from flask import current_app, g, has_request_context

MAX_LOGS = 10
MAX_FRAMES = 12


def clean_text(value, limit=500):
    text = str(value)
    text = re.sub(r'https?://\S+', '[URL omitida]', text, flags=re.I)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b', '[email omitido]', text, flags=re.I)
    text = re.sub(r'(?i)\b(?:bearer\s+\S+|(?:password|senha|token|secret|api[_-]?key|authorization|cookie)\s*[:=]\s*[^\s,;]+)', '[segredo omitido]', text)
    return text[:limit]


def exception_evidence(error):
    frames = []
    tb = error.__traceback__
    while tb:
        code = tb.tb_frame.f_code
        try:
            filename = 'app/' + str(Path(code.co_filename).resolve().relative_to(Path(current_app.root_path).resolve()))
        except ValueError:
            filename = Path(code.co_filename).name
        frames.append({'arquivo': filename, 'funcao': code.co_name, 'linha': tb.tb_lineno})
        tb = tb.tb_next
    return {'tipo': type(error).__name__, 'frames': frames[-MAX_FRAMES:]}


def record_exception(error, *, reason=None):
    if not has_request_context():
        return
    item = exception_evidence(error)
    if reason in {'busy', 'expired', 'stale'}:
        item['motivo'] = reason
    g.audit_exception = item


class RequestDiagnostics(logging.Handler):
    def emit(self, record):
        if not has_request_context() or not getattr(g, 'audit_request_id', None):
            return
        try:
            logs = getattr(g, 'audit_diagnostic_logs', [])
            if len(logs) >= MAX_LOGS:
                g.audit_diagnostic_truncated = True
                return
            item = {'nivel': record.levelname, 'logger': clean_text(record.name, 100)}
            # Only source-code literal templates are accepted. Dynamic f-strings,
            # exception objects and formatted values may contain private payloads.
            source_line = linecache.getline(record.pathname, record.lineno).strip()
            try:
                tree = ast.parse(source_line)
                calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Attribute)
                         and node.func.attr in {'warning', 'error', 'exception', 'critical', 'log'}]
                literal = next((node.args[0].value for node in calls if node.args
                                and isinstance(node.args[0], ast.Constant)
                                and isinstance(node.args[0].value, str)), None)
            except (SyntaxError, ValueError):
                literal = None
            item['mensagem_modelo'] = clean_text(literal) if literal == record.msg else '[mensagem dinâmica omitida]'
            if record.exc_info and record.exc_info[1]:
                item['excecao'] = exception_evidence(record.exc_info[1])
            logs.append(item)
            g.audit_diagnostic_logs = logs
        except Exception:
            # Diagnostics must never change the response or log recursively.
            pass


def register_diagnostics(app):
    # Flask app instances can share the same named logger in tests/workers.
    if not any(isinstance(handler, RequestDiagnostics) for handler in app.logger.handlers):
        app.logger.addHandler(RequestDiagnostics(level=logging.WARNING))


def request_diagnostics():
    data = {'versao': 1, 'logs': getattr(g, 'audit_diagnostic_logs', []),
            'logs_truncados': getattr(g, 'audit_diagnostic_truncated', False)}
    from app.modules.auditoria.releases import release_sha
    sha = release_sha(current_app)
    if sha:
        data['release_sha'] = sha
    if getattr(g, 'audit_exception', None):
        data['excecao'] = g.audit_exception
    return data
