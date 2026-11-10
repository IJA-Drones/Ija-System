"""Build reviewed, reusable voice clips once; never synthesize customer content."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask
from config import Config
from app.modules.chatbot import recordings, voice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate', action='store_true', help='Generate missing clips using the configured API.')
    parser.add_argument('--only', nargs='+', help='Limit generation to the named catalog entries.')
    args = parser.parse_args()
    app = Flask('azul-recordings', static_folder=str(ROOT / 'app/static'))
    app.config.from_object(Config)
    manifest_path = recordings.DIRECTORY / 'manifest.json'
    with app.app_context():
        catalog = recordings.catalog()
        if args.only:
            unknown = set(args.only) - catalog.keys()
            if unknown:
                parser.error('Unknown catalog entries: ' + ', '.join(sorted(unknown)))
            catalog = {name: catalog[name] for name in args.only}
        preset = {'style': recordings.STYLE, 'voice': app.config['AZUL_VOICE'],
                  'model': app.config['AZUL_VOICE_MODEL']}
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            manifest = {}
        if any(manifest.get(key) != value for key, value in preset.items()):
            manifest = {**preset, 'clips': {}}
        failed = False
        for name, text in catalog.items():
            key = recordings.text_key(text)
            destination = recordings.DIRECTORY / (key + '.wav')
            entry = manifest['clips'].get(key, {})
            if (destination.is_file() and entry.get('text') == text
                    and hashlib.sha256(destination.read_bytes()).hexdigest() == entry.get('audio_sha256')):
                print(name + ': already recorded', flush=True)
                continue
            if not args.generate:
                print(name + ': missing (use --generate)', flush=True)
                continue
            try:
                data = voice.synthesize(text).getvalue()
            except Exception:
                print(name + ': generation failed; no recording published', flush=True)
                failed = True
                continue
            recordings.DIRECTORY.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix('.tmp')
            temporary.write_bytes(data)
            temporary.replace(destination)
            manifest['clips'][key] = {'name': name, 'text': text,
                                      'audio_sha256': hashlib.sha256(data).hexdigest()}
            temporary = manifest_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
            temporary.replace(manifest_path)
            print(name + ': recorded', flush=True)
        return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
