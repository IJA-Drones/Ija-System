"""The pilot sees saved attachments after media operations, within their own scope."""
import json
import re
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.models import Equipe, OrdemServico, Prefeitura, Solicitacao
from app.modules.piloto_os import routes, service
from test_sprint1_workflows import app, client


DAY = date(2026, 11, 16)


def dashboard_counts(response):
    assert response.status_code == 200
    groups = re.findall(r'<div\b[^>]*data-os-media-counts="(\d+)"[^>]*>(.*?)</div>',
                        response.get_data(as_text=True), re.S)
    return {
        int(sid): {
            kind: int(re.search(r'data-media-count="' + kind + r'"[^>]*>\s*<i\b[^>]*></i>(\d+)', body).group(1))
            for kind in ('imagens', 'videos')
        }
        for sid, body in groups
    }


def prepare(app, monkeypatch):
    monkeypatch.setattr(service, 'current_piloto_dashboard_date', lambda: DAY)
    with app.app_context():
        request = db.session.get(Solicitacao, 1)
        request.data_agendamento = DAY
        request.status = 'APROVADO'
        db.session.commit()
    return client(app, 3)


def test_dashboard_follows_uploads_and_removals_instead_of_reported_quantities(app, monkeypatch):
    c = prepare(app, monkeypatch)
    assert dashboard_counts(c.get('/piloto/os')) == {1: dict(imagens=0, videos=0)}
    with app.app_context():
        db.session.add(OrdemServico(solicitacao_id=1, equipe_id=1,
            quantidade_imagens_registradas=99, quantidade_videos_registradas=77))
        db.session.commit()
    assert dashboard_counts(c.get('/piloto/os')) == {1: dict(imagens=0, videos=0)}

    uploads = [
        ('upload-stream', 'principal.jpg', 1, 0),
        ('upload-complementary-stream', 'extra-1.jpg', 2, 0),
        ('upload-complementary-stream', 'extra-2.jpg', 3, 0),
        ('upload-video-stream', 'video.mp4', 3, 1),
    ]
    for endpoint, filename, images, videos in uploads:
        with patch.object(routes, '_upload_request_stream_to_webdav',
                          return_value=(filename, 'https://storage.invalid/' + filename, None, None)):
            assert c.put('/api/os/1/' + endpoint, data=b'isolated-media').status_code == 201
        assert dashboard_counts(c.get('/piloto/os')) == {1: dict(imagens=images, videos=videos)}

    with patch.object(routes, '_upload_request_stream_to_webdav',
                      return_value=(None, None, {'error': 'Falha simulada no armazenamento'}, 503)):
        assert c.put('/api/os/1/upload-complementary-stream', data=b'isolated-media').status_code == 503
    assert dashboard_counts(c.get('/piloto/os')) == {1: dict(imagens=3, videos=1)}

    with patch.object(routes, '_delete_os_media_path') as storage:
        assert c.delete('/api/os/1/imagem-principal').status_code == 200
        assert c.delete('/api/os/1/video').status_code == 200
        assert storage.call_count == 2
    assert dashboard_counts(c.get('/piloto/os')) == {1: dict(imagens=2, videos=0)}


def test_dashboard_counts_keep_team_municipality_day_and_pagination_scope(app, monkeypatch):
    c = prepare(app, monkeypatch)
    with app.app_context():
        db.session.add(Prefeitura(id=2, nome='Outro municipio', slug='outro-municipio'))
        db.session.add(Equipe(id=2, nome_equipe='Outra equipe', prefeitura_id=1, regiao='OESTE', ativa=True))
        db.session.flush()
        for sid in range(1, 10):
            request = db.session.get(Solicitacao, sid)
            request.data_agendamento = DAY
            request.status = 'APROVADO'
            if sid == 8:
                request.equipe_id = 2
            if sid == 9:
                request.prefeitura_id = 2
            db.session.add(OrdemServico(solicitacao_id=sid, equipe_id=request.equipe_id,
                imagem_principal=f'webdav://test/{sid}/principal.jpg',
                outras_imagens=json.dumps([f'webdav://test/{sid}/extra.jpg']),
                quantidade_imagens_registradas=99))
        db.session.commit()
    first = dashboard_counts(c.get('/piloto/os'))
    second = dashboard_counts(c.get('/piloto/os?page=2'))
    assert len(first) == 6 and len(second) == 1
    assert set(first) | set(second) == set(range(1, 8))
    assert all(count == dict(imagens=2, videos=0) for count in [*first.values(), *second.values()])


def test_dashboard_with_no_active_team_has_no_attachment_counts(app, monkeypatch):
    c = prepare(app, monkeypatch)
    with app.app_context():
        db.session.get(Equipe, 1).ativa = False
        db.session.commit()
    assert dashboard_counts(c.get('/piloto/os')) == {}
