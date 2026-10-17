# Controle de acesso por prefeitura - item 4.5.1

## Cadastro de equipes UVIS

O cadastro de equipe comum e o cadastro/atualização do acesso operacional usam a prefeitura da UVIS responsável, validada no servidor. Campos enviados pelo navegador com outra prefeitura ou outro responsável não substituem esse vínculo.

Antes de criar ou atualizar o acesso, o serviço exige uma UVIS cadastrada com prefeitura existente e ativa. Se esse requisito falhar, a operação é recusada com orientação para corrigir o cadastro. No acesso operacional existente, login, senha e prefeitura são preservados quando a validação falha.

A verificação existe no serviço, além das permissões das rotas. Por isso, uma chamada interna também não pode criar uma equipe sem prefeitura. O administrador global pode gerenciar o acesso de uma UVIS, mas o novo acesso pertence à prefeitura dessa UVIS, não à do administrador.

## Escopo e permissões

- A permissão da Central de TI autoriza uma ação; não concede acesso automático a outra prefeitura.
- As consultas municipais continuam filtradas pelo vínculo da conta. As OS de uma equipe UVIS também são limitadas à UVIS responsável.
- Imagens, anexos e exportações mantêm as verificações do registro de origem, inclusive em chamadas diretas por ID.
- Os acessos globais de Admin, Diretor e Dev conservam seu alcance administrativo previsto. Essa capacidade não é concedida aos perfis municipais pela criação de uma equipe.
- A mudança não altera a exceção de edição simultânea dos pilotos/equipes.

## Verificação automatizada

Os testes de isolamento usam duas prefeituras fictícias com a mesma região em SQLite descartável, com a Central de TI ativada e desativada. Cobrem criação de equipes e acesso operacional, campos de vínculo adulterados, prefeitura ausente/inativa, preservação de credenciais em falha, consulta das próprias OS e bloqueio de mídia de outro município.

As suítes relacionadas também verificam denúncias, anexos, filtros, relatórios, exportações, gestão de contas, concessão/revogação de permissões e retornos automáticos:

```bash
.venv/bin/python -m pytest tests/test_municipal_isolation.py tests/test_uvis_os_media_access.py tests/test_central_ti_permissions.py tests/test_central_ti_documentos_permissions.py tests/test_retorno_ciclo_prefeitura_scope.py tests/test_relatorios_region_team_filters.py -q
```

## Publicação e aceite

Não há alteração de esquema nem necessidade de `db upgrade` para esta correção. A implementação não executa correções em massa nas contas existentes; os 16 vínculos UVIS já corrigidos anteriormente são uma intervenção separada.

Após publicar, homologar com contas de teste de duas prefeituras: criar equipe, conferir a prefeitura herdada, abrir suas OS/imagens e confirmar a negativa em registros de outro município. Conferir as permissões efetivamente configuradas no servidor. A cobertura automatizada documenta os cenários exercitados, não substitui o aceite da matriz de perfis/alçadas do contrato.
