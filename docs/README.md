# Documentação do IJA System

Esta é a entrada da documentação técnica e operacional. A revisão de 25/09/2026 usa o código do commit `846b12f` como base; o inventário pode ser atualizado automaticamente conforme o projeto evolui.

## Comece pelo seu objetivo

| Objetivo | Documento |
| --- | --- |
| Entender o produto | [README do projeto](../README.md) |
| Preparar o ambiente e o primeiro acesso | [Desenvolvimento local](desenvolvimento.md) |
| Configurar banco, segurança e integrações | [Configuração](configuracao.md) e [modelo de ambiente](../.env.example) |
| Entender componentes, dados e permissões | [Arquitetura](arquitetura.md) |
| Localizar qualquer módulo, tabela ou rota | [Referência gerada do código](referencia-codigo.md) |
| Executar verificações e contribuir | [Testes e manutenção](testes.md) |
| Publicar, diagnosticar, migrar ou recuperar dados | [Operação](operacao.md) |
| Conferir o que foi complementado e o que ainda falta | [Revisão de documentação e pendências](revisao-documentacao-2026-09-25.md) |

## Manuais por funcionalidade

| Área | Documentação |
| --- | --- |
| Prefeitura e operação urbana | [Catálogo funcional municipal](IJA_System_Funcionalidades_Prefeitura_Notion.md) |
| Cidadão e triagem | [Portal, denúncias e encaminhamento para UVIS](manuais-operacionais/portal-cidadao-triagem.md) |
| Frota e supervisor | [Supervisor Operacional de Veículos](perfil-supervisor-operacional-veiculos.md), [alertas de limpeza](manuais-operacionais/alertas-limpeza-veiculos-oceano-azul-notion.md) |
| Equipamentos | [Estoque e manutenção](manuais-operacionais/estoque-manutencao-drones-notion.md) |
| Gestão | [Painel do diretor](manuais-operacionais/painel-operacional-diretor-notion.md), [filtro por endereço](manuais-operacionais/painel-gestao-filtro-endereco-notion.md) |
| Agro | [Banco de talentos](manuais-operacionais/banco-talentos-agro-notion.md), [visão técnica dos domínios](arquitetura.md) |
| Retornos | [Visualização do ciclo](README-retorno-automatico.md), [central de retornos automáticos](relatorio-central-retornos-automaticos.md) |
| Endereços e voos | [Bloqueio por endereço resolvido](relatorio-bloqueio-novas-solicitacoes-endereco-resolvido.md), [Place ID e vínculo de KML](relatorio-melhoria-place-id-vinculo-kml-os.md) |
| Arquivos | [Streaming WebDAV](relatorio-upload-stream-webdav.md) |
| Acesso | [Sessões, senhas e CSRF](seguranca-sessoes-senhas.md) |
| Suporte | [Reporte de bugs](notion_reporte_bugs.md) |
| Interface | [Refatoração visual e dark mode](relatorio-refatoracao-visual-css-dark-mode.md), [checkpoint CSS](refatoracao_css_para_arrumar_darkmode.md) |

Os relatórios de funcionalidades registram a entrega e seus testes na época indicada. Os guias de configuração e operação descrevem a revisão atual. Quando houver divergência, confronte com o código e com a data do documento; contagens e resultados antigos não são resultados da suíte atual.

## Documentos históricos e planejamento

- [Documentação técnica INPI em Markdown](documentacao-tecnica-inpi-ija-system.md) e [em Word](documentacao-tecnica-inpi-ija-system.docx): emissão 1.0, de 26/08/2026, referente ao snapshot de 25/08/2026. Permanecem como registro daquela versão. A atualização técnica de setembro está nos guias acima e na [revisão](revisao-documentacao-2026-09-25.md); não foi emitida uma nova versão formal do Word.
- [Auditoria contratual de 15/09/2026](auditoria-contratual-vigilancia-2026-09-15.md) e [evidências](auditoria-vigilancia-evidencias-2026-09-15/): conclusões e inventário daquela data.
- [Novas demandas de vigilância](relatorio-novas-demandas-vigilancia-epidemiologica.md) e [guia de execução](guia-execucao-novas-demandas-vigilancia.md): análises e propostas. Portal, triagem e controles opcionais de segurança já possuem código posterior; a existência desses componentes não comprova atendimento de todo o plano.

## Como manter esta documentação

Ao mudar configuração, permissão, persistência, integração ou fluxo de tela, atualize o guia correspondente junto com a alteração. Inclua comportamento em falha e a forma de verificar o resultado. Use links relativos dentro do repositório e mantenha credenciais, dumps e dados pessoais fora dos exemplos.

Depois de mudar rotas, modelos, módulos ou testes:

```bash
python scripts/build_docs_inventory.py
python scripts/build_docs_inventory.py --check
```

O gerador usa apenas a biblioteca padrão Python. Documentos históricos devem receber nova revisão identificada ou complemento, preservando o snapshot ao qual se referem.
