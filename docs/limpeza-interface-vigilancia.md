# Retirada da vigilância da interface

`Config.VIGILANCIA_UI_ENABLED = False` oculta os módulos de vigilância de todos os
perfis, incluindo DEV e cidadão. As flags anteriores de importação e SINAN não
reativam a interface. A definição fica no código, sem configuração por perfil.

São retirados menus, telas HTML, atalhos de OS, materiais relacionados nos
treinamentos e módulos do editor da Central de TI. O mapa de risco, as ações e o
formulário de suspeita de adoecimento também ficam ocultos no cidadão. Links
antigos para essas telas retornam 404. Agentes existentes entram nos treinamentos,
sem receber acesso adicional.

O cidadão mantém relatos de ocorrências, envio offline, contatos, assistente AZUL,
tutoriais públicos de relatos e boletim, alertas no celular, Telegram, aplicativo
mobile (`/m/`) e página de instalação (`/app`). O painel e o boletim completo
continuam consultando InfoDengue e notícias oficiais. O mapa de risco depende de
cargas internas de LIRAa/SINAN e não é reativado por essas consultas públicas.

O aplicativo web oculta os caminhos de agente e suspeita de adoecimento, inclusive
quando abertos por hash antigo. Registros desses módulos já salvos no aparelho
continuam preservados, sem aparecer ou ser reenviados pela fila do cidadão.
O APK existente é preservado; a alteração do frontend web não recompila o nativo.

Modelos, tabelas, migrações, foreign keys, restrições NOT NULL, permissões salvas,
APIs, exportações e código original são preservados. A retirada visual não exige
migração nem limpeza de registros e não desliga integrações ou rotinas de backend.
A exclusão de dados da POC, autorizada separadamente, está descrita abaixo.

O service worker passa a ser registrado em `/service-worker.js`, para passar pelo
Flask mesmo com WhiteNoise servindo arquivos na raiz. O worker mantém as
notificações push e o cache do aplicativo para uso offline. A versão do cache e
dos scripts muda para atualizar instalações existentes.

Os testes dos módulos arquivados habilitam a interface explicitamente em seus
ambientes descartáveis. `tests/test_interface_visibility.py` verifica a retirada
global, inclusive com as flags antigas habilitadas.

## Pesqueira e materiais de treinamento — 18/11/2026

A limpeza foi aplicada ao PostgreSQL de produção, somente nos registros
identificados como demonstração da POC de Pesqueira (prefeitura 14, IBGE 2610905).
Foram removidos 1.988 registros, incluindo as dependências desses testes. O relato
28 foi incluído após confirmação expressa do usuário. Importações oficiais de
SINAN, dados protegidos de outros municípios e os 146 usuários foram conferidos
antes e depois e permaneceram iguais. Os seis acessos vinculados a Pesqueira,
senhas, perfis e permissões foram mantidos.

Pesqueira ficou inativa para operação, sem excluir o cadastro da prefeitura ou
seus vínculos de usuários. O portal também deixa de oferecê-la no seletor público,
inclusive por um parâmetro antigo ou configuração anterior do InfoDengue.

O backup anterior à exclusão fica em
`instance/backups/pesqueira_poc_cleanup_20261118T191447Z/`, fora dos arquivos
distribuídos. Contém os registros, o SQL de restauração, o plano, os hashes e o
resultado da execução. O evento de auditoria é `197647` (`LIMPEZA_POC`). O script
`scripts/cleanup_pesqueira_poc.py` exige conferência do alvo e do plano antes de
aplicar a exclusão; executar sem `--apply` apenas prepara o plano e o backup.

Os PDFs dedicados aos módulos retirados e o kit de Pesqueira foram arquivados
nesse mesmo backup antes da retirada das pastas publicadas. Os guias das funções
mantidas continuam disponíveis: 26 PDFs, sem referências textuais a Pesqueira.
O guia geral foi revisado para 27 páginas, mantendo os capítulos do sistema e
as capturas das funções disponíveis, retirando os exemplos da POC e os capítulos
dos módulos ocultos. O novo índice tem links e numeração conferidos. Alertas,
Telegram, AZUL, boletim público e aplicativo mobile continuam documentados.
Também foram retiradas orientações obsoletas dos guias de consultas e contatos.
As capturas dos guias de consultas, relatórios, Central de TI e contatos foram
recortadas no próprio PDF para omitir os atalhos dos módulos ocultos, preservando
os pixels das telas reais. O OCR das 128 páginas não encontrou Pesqueira, e as
páginas alteradas foram conferidas novamente após os ajustes.

Validação desta etapa: 81 testes e 11 subtestes passaram; o guia geral foi
renderizado e conferido visualmente. A limpeza do banco já foi efetivada em
produção. As alterações de interface e PDFs estão no checkout local e ainda
dependem da publicação da aplicação.
