# Guias da Central de Treinamentos

Cada módulo tem seu PDF individual. A identidade visual comum usa a referência
do guia de Edição protegida, com DejaVu Sans, faixa azul-petróleo, blocos claros, cabeçalho e rodapé padronizados.

## Atualização dos PDFs

1. Confira o fluxo atual nos serviços, nas rotas e nos templates do módulo.
2. Atualize o conteúdo em `guias-operacionais.json` e suas referências de fonte.
3. Capture a tela real em ambiente de demonstração. Guarde o PNG em
   `capturas-guias`, sem dados pessoais, credenciais ou registros reais.
4. Execute `python scripts/build_operational_guides.py` na raiz do projeto.
   O comando gera os PDFs individuais em `output/pdf` e suas cópias na aplicação.
5. Renderize todas as páginas e confira layout, conteúdo, navegação e fontes.
6. Atualize o inventário, o catálogo e a política de acesso do material.

O gerador depende de ReportLab, Pillow, pypdf e das fontes DejaVu Sans regular e
bold. A variável `TRAINING_FONT_DIR` aceita a pasta das fontes. O script também
reconhece a instalação Linux usual e o runtime de documentos do Codex.

O modelo compartilhado está em `scripts/training_pdf_style.py`. Ajustes de cores, tipografia e elementos comuns devem ser feitos ali para manter a identidade dos
guias desta série. O gerador não acessa banco de dados nem serviços externos.

## Catálogo e permissões

Arquivos em `output/pdf` não são publicados automaticamente. Cada documento
precisa de uma entrada fixa em `app/modules/treinamentos/catalog.py` e de uma
política em `app/modules/treinamentos/access.py`.

A biblioteca e os downloads usam a mesma autorização. Os materiais são separados
pelas abas Prefeitura e Sistema, Agro e Financeiro. Os guias de operação de piloto
exigem as permissões específicas de operação; consultar veículos não autoriza o
guia de abertura e encerramento de turnos.

As rotas de treinamento mantêm os contextos de navegação de cada central. O
perfil dedicado de Ortomosaicos pode consultar seu guia e os materiais comuns de
acesso, preservando o bloqueio das outras funções de negócio.

O inventário e a validação desta leva estão em `inventario-guias.md` e
`validacao-guias-operacionais.json`.

A **Central de vídeos**, em `/treinamentos/videos`, reúne apresentação da
Prefeitura, novidades e tutorial de quadra. A página possui player do Drive, lista
de vídeos e controles anterior/próximo centralizados logo abaixo do player.
Nenhum vídeo, áudio ou miniatura é armazenado no projeto.

Os arquivos são registrados em `TRAINING_VIDEOS`, apenas com metadados e ID do
Drive. Cada vídeo tem uma política em `POLICIES`, independente dos arquivos para
download de `MATERIALS`. Apresentação e novidades seguem a política da apresentação
geral; o tutorial de quadra exige permissão de criar solicitações. A lista e o acesso
direto ao player são filtrados no servidor. Para acrescentar vídeos, cadastre o ID
do Drive e sua política; novos arquivos da pasta não são publicados automaticamente.

## Guia prático na interface

**Guia prático** abre **Aprender na prática**, com a Azul e cartões por módulo.
Cada módulo oferece as funções autorizadas. A escolha abre a tela real e solicita
à IA um tutorial dos controles disponíveis. Há dúvidas durante o guia e narração
opcional com a voz configurada da Azul. As áreas Agro e Financeiro permanecem
separadas conforme o acesso da conta. Consulte `guia-pratico.md` para fluxo,
limites, permissão, dados enviados ao provedor e verificação.
