"""WebDAV folder preparation keeps the common upload path to one request."""
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from app.shared import skybox


@pytest.mark.parametrize('path', ['file.jsonl', '/file.jsonl'])
def test_root_file_needs_no_collection_request(monkeypatch, path):
    request = Mock()
    monkeypatch.setattr(skybox, '_request', request)

    skybox._ensure_parent_collections(path)

    request.assert_not_called()


@pytest.mark.parametrize('status', [201, 405])
def test_ready_parent_needs_one_request_regardless_of_depth(monkeypatch, status):
    request = Mock(return_value=SimpleNamespace(status_code=status))
    monkeypatch.setattr(skybox, '_request', request)
    parent = 'auditoria_sistema/installation/prefeitura-1/2026/11/06'

    skybox._ensure_parent_collections(parent + '/batch.jsonl')

    request.assert_called_once_with('MKCOL', parent)


@pytest.mark.parametrize('existing', [set(), {'root'}, {'root', 'root/tenant'}])
def test_missing_ancestors_are_created_in_order_then_leaf_is_retried(monkeypatch, existing):
    folders = set(existing)
    calls = []

    def request(method, path):
        calls.append((method, path))
        assert method == 'MKCOL'
        if path in folders:
            return SimpleNamespace(status_code=405)
        if '/' in path and path.rsplit('/', 1)[0] not in folders:
            return SimpleNamespace(status_code=409)
        folders.add(path)
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(skybox, '_request', request)

    skybox._ensure_parent_collections('root/tenant/day/batch.jsonl')

    assert 'root/tenant/day' in folders
    if 'root/tenant' in existing:
        assert calls == [('MKCOL', 'root/tenant/day')]
    else:
        assert calls == [('MKCOL', 'root/tenant/day'), ('MKCOL', 'root'),
                         ('MKCOL', 'root/tenant'), ('MKCOL', 'root/tenant/day')]


@pytest.mark.parametrize('status,error', [
    (401, skybox.SkyboxAuthenticationError),
    (403, skybox.SkyboxPermissionError),
    (404, skybox.SkyboxError),
    (429, skybox.SkyboxError),
    (500, skybox.SkyboxError),
    (503, skybox.SkyboxError),
    (507, skybox.SkyboxError),
])
def test_other_failures_do_not_trigger_ancestor_requests(monkeypatch, status, error):
    request = Mock(return_value=SimpleNamespace(status_code=status))
    monkeypatch.setattr(skybox, '_request', request)

    with pytest.raises(error, match=str(status)):
        skybox._ensure_parent_collections('root/tenant/day/batch.jsonl')

    request.assert_called_once_with('MKCOL', 'root/tenant/day')


@pytest.mark.parametrize('status,error', [
    (401, skybox.SkyboxAuthenticationError),
    (403, skybox.SkyboxPermissionError),
    (409, skybox.SkyboxError),
    (503, skybox.SkyboxError),
])
def test_failed_ancestor_stops_preparation(monkeypatch, status, error):
    request = Mock(side_effect=[SimpleNamespace(status_code=409), SimpleNamespace(status_code=status)])
    monkeypatch.setattr(skybox, '_request', request)

    with pytest.raises(error, match=str(status)):
        skybox._ensure_parent_collections('root/tenant/day/batch.jsonl')

    assert request.call_args_list == [call('MKCOL', 'root/tenant/day'), call('MKCOL', 'root')]


def test_persistent_leaf_conflict_is_not_reported_as_success(monkeypatch):
    request = Mock(side_effect=[SimpleNamespace(status_code=status) for status in [409, 405, 201, 409]])
    monkeypatch.setattr(skybox, '_request', request)

    with pytest.raises(skybox.SkyboxError, match='409'):
        skybox._ensure_parent_collections('root/tenant/day/batch.jsonl')

    assert request.call_args_list == [call('MKCOL', 'root/tenant/day'), call('MKCOL', 'root'),
                                      call('MKCOL', 'root/tenant'), call('MKCOL', 'root/tenant/day')]


def test_top_level_conflict_has_no_ancestor_to_retry(monkeypatch):
    request = Mock(return_value=SimpleNamespace(status_code=409))
    monkeypatch.setattr(skybox, '_request', request)

    with pytest.raises(skybox.SkyboxError, match='409'):
        skybox._ensure_parent_collections('root/batch.jsonl')

    request.assert_called_once_with('MKCOL', 'root')


def test_each_upload_checks_current_folder_state_without_cache(monkeypatch):
    request = Mock(side_effect=[SimpleNamespace(status_code=status) for status in [405, 409, 405, 201, 201]])
    monkeypatch.setattr(skybox, '_request', request)

    skybox._ensure_parent_collections('root/tenant/day/first.jsonl')
    # The provider removed an ancestor, so this file must rebuild the hierarchy.
    skybox._ensure_parent_collections('root/tenant/day/second.jsonl')

    assert request.call_args_list == [call('MKCOL', 'root/tenant/day'), call('MKCOL', 'root/tenant/day'),
                                      call('MKCOL', 'root'), call('MKCOL', 'root/tenant'),
                                      call('MKCOL', 'root/tenant/day')]
