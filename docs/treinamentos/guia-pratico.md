# Guia prático nas telas reais

O botão **Guia prático** do menu acompanha a tela que já está aberta. O acesso
da Azul com o mesmo nome abre esse guia. Na Central de Treinamentos, **Conhecer
esta tela** permite experimentar. No aplicativo web, os formulários têm o botão
de ajuda no cabeçalho.

O guia destaca campos, filtros, tabelas, mapas e controles. **Ver todas as etapas**
permite escolher um ponto do formulário; **Voltar**, **Próximo**, **Concluir** e
Escape controlam a leitura. A página permanece utilizável. Ao avançar, o guia
confere novamente quais campos estão visíveis, incluindo os condicionais. Ao
abrir um modal ou trocar uma aba Bootstrap, passa ao contexto aberto. Em outra
página, abra o guia novamente.

## Perfis e permissões

O guia usa a página autorizada pelo servidor. Não busca registros, não oferece
rotas de outros módulos e ignora controles ocultos, desabilitados ou bloqueados
pela Central de TI. Campos independentes expressamente liberados dentro de um
formulário bloqueado continuam acessíveis, seguindo `permission-controls.js`.
Consultar o guia não concede permissão de criar, editar, excluir ou aprovar.

Isso mantém os contextos de Prefeitura/UVIS, piloto, Agro, Financeiro, manutenção,
gestão e Ortomosaicos. A política de PDFs e vídeos continua no catálogo e na
autorização de treinamentos; o guia contextual não substitui essa política.

## Cobertura e revisão

`inventario-guia-pratico.json` registra os templates integrados e os identificadores
de perfil. Gere-o com `python scripts/inventory_screen_guides.py`. A integração
comum em `base.html` atende suas páginas autenticadas; o portal público usa
`_portal_chatbot.html` e o aplicativo usa `app_movel.html`. O simulador antigo em
`/azul/tutorial` permanece separado para compatibilidade.

O inventário comprova integração, não revisão manual de todas as combinações de
tela e perfil. As explicações gerais acompanham os rótulos reais; os campos
conhecidos têm orientações específicas em `screen-guide.js`. Ao revisar um fluxo,
confira a regra atual no serviço e teste os controles autorizados e os campos
condicionais. Orientações específicas devem depender do contexto do formulário.
Por exemplo, QUADRA só é explicado como foco quando está entre as opções de foco;
Culex continua sendo uma opção de visita, não uma exigência.

O guia não lê conteúdos digitados nem confirma ações. Não há captura de telas,
gravação, upload, chamada de IA ou áudio. Os rótulos são tratados como texto.
Capturas temporárias da verificação visual ficam fora do repositório.

## Verificação desta entrega — 19/11/2026

- Inventário: 198 templates integrados, incluindo o layout base e o aplicativo;
  não são 198 fluxos revisados manualmente.
- Testes de acesso: os 22 identificadores do catálogo da Central de TI e o perfil
  dedicado `ortomosaico`, com manutenção dos bloqueios de módulos.
- Navegador: formulário real de solicitação UVIS, campos condicionais de Aedes,
  navegação das etapas, entrada pelo menu e páginas de treinamento de outros
  perfis. Conferidos desktop, celular e contexto de modal.
- Sem envio de formulários nos ensaios. Os testes de servidor usam SQLite
  descartável; não alteram Neon ou Render.

As verificações não substituem a revisão editorial dos textos específicos de
cada fluxo operacional.
