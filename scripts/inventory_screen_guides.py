"""Inventory guide integration in templates, without running the app or accessing a database."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def inventory():
    templates = {str(p.relative_to(ROOT / 'app/templates')): p.read_text()
                 for p in (ROOT / 'app/templates').rglob('*.html')}
    parents = {name: re.search(r'''\{%\s*extends\s+['"]([^'"]+)''', text)
               for name, text in templates.items()}

    def inherits_base(name, seen=()):
        if name in seen:
            raise ValueError('Circular template inheritance: ' + name)
        return name == 'base.html' or bool(parents.get(name) and inherits_base(parents[name][1], seen + (name,)))

    pages, excluded = [], []
    for name, text in sorted(templates.items()):
        if inherits_base(name):
            pages.append(dict(template=name, integration='base.html',
                              public_guide="'_portal_chatbot.html'" in text or '"_portal_chatbot.html"' in text))
        elif name == 'app_movel.html':
            pages.append(dict(template=name, integration='standalone-mobile'))
        elif name == 'azul_tutorial.html':
            excluded.append(dict(template=name, reason='Legacy simulated practice room, not an operational screen.'))
        elif '<html' in text.lower():
            raise ValueError('Standalone page without guide integration: ' + name)
    profiles = json.loads((ROOT / 'app/modules/gestao_ti/catalog.json').read_text())['profiles']
    return dict(version=1,
                scope='Template integration only; available controls depend on server authorization, visibility and current form state. This is not a manual review of every screen/profile combination.',
                profiles=[p['id'] for p in profiles] + ['ortomosaico'],
                pages=pages, exclusions=excluded)


if __name__ == '__main__':
    target = ROOT / 'docs/treinamentos/inventario-guia-pratico.json'
    result = inventory()
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f"{len(result['pages'])} templates integrated; {len(result['profiles'])} profile identifiers; {len(result['exclusions'])} legacy simulator.")
