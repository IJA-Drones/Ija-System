static/
└── css/
    ├── base/
    │   ├── variables.css
    │   ├── reset.css
    │   └── typography.css
    │
    ├── components/
    │   ├── cards.css
    │   ├── badges.css
    │   ├── forms.css
    │   ├── pagination.css
    │   ├── file-upload.css
    │   ├── tables.css
    │   └── sweetalert.css
    │
    ├── modules/
    │   ├── layout.css
    │   ├── navbar.css
    │   ├── sidebar.css
    │   └── admin-context-switch.css
    │
    ├── pages/
    │   ├── dashboard.css
    │   └── map.css
    │
    ├── themes/
    │   ├── dark.css
    │   └── agro.css
    │
    ├── utilities/
    │   ├── animations.css
    │   └── utilities.css
    │
    └── style.css

## Checkpoint do dark mode

Atualizado em 21/08/2026.

- O CSS global e os estilos das páginas foram separados sem alterar o light mode.
- O filtro global recuperou o visual anterior no light e manteve a versão dark.
- O dark mode foi componentizado em `themes/dark/base`, `components`, `modules` e `pages`.
- Login, painel admin, relatório de coleta de imagens, históricos de OS, notificações, menus de relatórios e veículos, navbar e modais de veículos já receberam a paleta dark mais leve.
- `veiculo-logs-detalhe` foi modernizado no dark mode.
- Os cards e a tabela de `veiculos-logs` foram ajustados no dark mode e aguardam validação visual.
- Próxima página da sequência: formulário de OS do piloto.
- Regra da continuação: atualizar uma página por vez e não modificar o light mode.
