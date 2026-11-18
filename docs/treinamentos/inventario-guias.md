# Inventário dos guias de treinamento

Revisão: 17/11/2026. Leva com 17 PDFs individuais por módulo, de três páginas cada.

## Comparação com a biblioteca existente

O catálogo anterior continha 22 PDFs, concentrados em vigilância, atendimento ao cidadão, consultas, proteção de acesso e apresentações. Os novos guias abaixo completam temas sem um roteiro operacional próprio em PDF. As referências são do checkout local revisado nesta leva.

| Módulo / guia | PDF | Fonte principal |
| --- | --- | --- |
| Agenda e notificações | [guia-agenda-notificacoes.pdf](../../output/pdf/guia-agenda-notificacoes.pdf) | [app/modules/agenda_notificacoes/routes.py:21](../../app/modules/agenda_notificacoes/routes.py#L21) |
| Equipes e acesso UVIS | [guia-equipes-acesso-uvis.pdf](../../output/pdf/guia-equipes-acesso-uvis.pdf) | [app/modules/uvis_equipes/routes.py:107](../../app/modules/uvis_equipes/routes.py#L107) |
| Checklists semanais | [guia-checklists-semanais.pdf](../../output/pdf/guia-checklists-semanais.pdf) | [app/modules/piloto_checklists/routes.py:23](../../app/modules/piloto_checklists/routes.py#L23) |
| Frota e turnos | [guia-frota-turnos.pdf](../../output/pdf/guia-frota-turnos.pdf) | [app/modules/veiculos/routes.py:574](../../app/modules/veiculos/routes.py#L574) |
| Rastreamento de veículos | [guia-rastreamento-veiculos.pdf](../../output/pdf/guia-rastreamento-veiculos.pdf) | [app/modules/veiculos/rastreamento.py:1](../../app/modules/veiculos/rastreamento.py#L1) |
| Estoque de peças | [guia-estoque-pecas.pdf](../../output/pdf/guia-estoque-pecas.pdf) | [app/modules/estoque/routes.py:29](../../app/modules/estoque/routes.py#L29) |
| Manutenção de equipamentos | [guia-manutencao-equipamentos.pdf](../../output/pdf/guia-manutencao-equipamentos.pdf) | [app/modules/equipamentos/routes.py:275](../../app/modules/equipamentos/routes.py#L275) |
| Central de TI | [guia-central-ti-permissoes.pdf](../../output/pdf/guia-central-ti-permissoes.pdf) | [app/modules/gestao_ti/routes.py:72](../../app/modules/gestao_ti/routes.py#L72) |
| Reporte de bugs | [guia-reporte-acompanhamento-bugs.pdf](../../output/pdf/guia-reporte-acompanhamento-bugs.pdf) | [app/modules/feedback/routes.py:367](../../app/modules/feedback/routes.py#L367) |
| Painel operacional | [guia-painel-operacional.pdf](../../output/pdf/guia-painel-operacional.pdf) | [app/modules/painel_operacional/routes.py:15](../../app/modules/painel_operacional/routes.py#L15) |
| Banco de talentos Agro | [guia-banco-talentos-agro.pdf](../../output/pdf/guia-banco-talentos-agro.pdf) | [app/modules/agro/talent_bank_routes.py:89](../../app/modules/agro/talent_bank_routes.py#L89) |
| Central Financeiro | [guia-central-financeiro.pdf](../../output/pdf/guia-central-financeiro.pdf) | [app/modules/financeiro/routes.py:127](../../app/modules/financeiro/routes.py#L127) |
| Ortomosaicos e curvas | [guia-ortomosaicos.pdf](../../output/pdf/guia-ortomosaicos.pdf) | [app/modules/ortomosaicos/routes.py:101](../../app/modules/ortomosaicos/routes.py#L101) |
| Relatórios operacionais | [guia-relatorios-operacionais.pdf](../../output/pdf/guia-relatorios-operacionais.pdf) | [app/modules/relatorios/routes.py:320](../../app/modules/relatorios/routes.py#L320) |
| Mapas operacionais | [guia-mapas-operacionais.pdf](../../output/pdf/guia-mapas-operacionais.pdf) | [app/modules/mapas/routes.py:114](../../app/modules/mapas/routes.py#L114) |
| Agro: comercial e operação | [guia-agro-comercial-operacao.pdf](../../output/pdf/guia-agro-comercial-operacao.pdf) | [app/modules/agro/routes.py:3895](../../app/modules/agro/routes.py#L3895) |
| Usuários e prefeituras | [guia-usuarios-prefeituras.pdf](../../output/pdf/guia-usuarios-prefeituras.pdf) | [app/modules/usuarios/routes.py:449](../../app/modules/usuarios/routes.py#L449) |

## Identidade visual comum

- Referência: guia de Edição protegida já existente na biblioteca.
- Fonte DejaVu Sans e DejaVu Sans Bold; azul-petróleo #008ea4; títulos #12344a; fundos claros #eef6fa e #e8f6f5.
- Estrutura: visão geral e tela real; passo a passo; conferência, campos e dúvidas.
- Cabeçalho, rodapé e paginação mantidos pelo módulo compartilhado `scripts/training_pdf_style.py`.
- Capturas dos templates reais em SQLite descartável, com dados fictícios e sem requisições de gravação. Fontes e hashes registrados no manifesto de capturas.

## Publicação e permissões

- PDFs cadastrados individualmente no catálogo fechado; cópias da aplicação e de `output/pdf` conferidas.
- `app/modules/treinamentos/access.py` exige política explícita para cada material, inclusive PDFs antigos, CSVs e kits.
- A listagem e os downloads usam a mesma verificação. Permissões explícitas da Central de TI substituem o fallback legado, preservando as restrições fixas dos módulos.
- Abas Prefeitura e Sistema, Agro e Financeiro exibem apenas os conteúdos autorizados do respectivo contexto. Materiais gerais de acesso permanecem comuns.
- Os guias operacionais de piloto exigem a ação correspondente; consultar veículos não concede o guia de operação de turnos.
- O guia geral que reúne áreas técnicas é restrito; o tutorial de quadra continua pausado.

## Estado desta leva

- 17 PDFs, 51 páginas; cópias e navegação interna verificadas.
- Revisão visual de todas as páginas e verificação de limites geométricos do texto.
- Verificações de permissões, abas, acesso direto, HEAD, intervalos de bytes e revogação realizadas com dados descartáveis.
- 65 testes e 519 subtestes de treinamento, permissões e perfil de Ortomosaicos aprovados. O teste de arquivos entre municípios foi concluído com a dependência declarada pyshp em pasta temporária.
- Na verificação ampliada, testes antigos do Financeiro falharam por expectativas sobre o formulário da Azul e sua chave de sessão. Os mesmos comportamentos foram reproduzidos usando o template base original; não foram alterados nesta leva.
- Código e arquivos preparados localmente; sem commit, push ou deploy nesta leva.
- Novos guias e o vídeo de quadras aguardam nova orientação após a mudança do fluxo.
