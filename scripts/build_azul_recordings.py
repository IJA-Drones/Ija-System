"""Build reviewed, reusable voice clips once; never synthesize customer content."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import io
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask
from config import Config
from app.modules.chatbot import recordings, voice, voice_profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate', action='store_true', help='Generate missing clips using the configured API.')
    parser.add_argument('--only', nargs='+', help='Limit generation to the named catalog entries.')
    parser.add_argument('--profile', choices=tuple(voice_profiles.PROFILES), default='original')
    args = parser.parse_args()
    app = Flask('azul-recordings', static_folder=str(ROOT / 'app/static'))
    app.config.from_object(Config)
    app.config['AZUL_VOICE_PROFILE'] = args.profile
    manifest_path = recordings.manifest_path(args.profile)
    with app.app_context():
        catalog = recordings.catalog(args.profile)
        if args.only:
            unknown = set(args.only) - catalog.keys()
            if unknown:
                parser.error('Unknown catalog entries: ' + ', '.join(sorted(unknown)))
            catalog = {name: catalog[name] for name in args.only}
        chosen = voice_profiles.spec(args.profile)
        preset = {key: chosen[key] for key in ('style', 'voice', 'model')}
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            manifest = {}
        if any(manifest.get(key) != value for key, value in preset.items()):
            manifest = {**preset, 'clips': {}}
        failed = False
        for name, text in catalog.items():
            key = recordings.text_key(text, args.profile)
            destination = recordings.DIRECTORY / (key + '.wav')
            entry = manifest['clips'].get(key, {})
            valid_audio = False
            if destination.is_file():
                try:
                    with wave.open(str(destination)) as recorded: valid_audio = recorded.getnframes() > 0
                except (OSError, wave.Error, EOFError):
                    pass
            if (valid_audio and entry.get('text') == text
                    and hashlib.sha256(destination.read_bytes()).hexdigest() == entry.get('audio_sha256')):
                print(name + ': already recorded', flush=True)
                continue
            if not args.generate:
                print(name + ': missing (use --generate)', flush=True)
                continue
            try:
                if chosen['model'] == 'browser-pt-BR':
                    if sys.platform != 'darwin':
                        raise ValueError('Amostras nativas devem ser preparadas em um Mac com voz Luciana pt-BR.')
                    with tempfile.TemporaryDirectory() as temporary_dir:
                        aiff = str(Path(temporary_dir) / 'speech.aiff')
                        wav = str(Path(temporary_dir) / 'speech.wav')
                        subprocess.run(['/usr/bin/say', '-v', 'Luciana', '-r', '175', '-o', aiff, text], check=True, capture_output=True)
                        subprocess.run(['/usr/bin/afconvert', '-f', 'WAVE', '-d', 'LEI16@24000', '-c', '1', aiff, wav], check=True, capture_output=True)
                        data = Path(wav).read_bytes()
                else:
                    data = voice.synthesize(text, profile=args.profile).getvalue()
                with wave.open(io.BytesIO(data)) as recorded:
                    if not recorded.getnframes():
                        raise ValueError('A síntese não produziu áudio.')
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
