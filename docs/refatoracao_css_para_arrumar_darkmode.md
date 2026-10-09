# Refatoração CSS para Arrumar Dark Mode

## Estrutura em esqueleto

```text
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
```

## Checkpoint do Dark Mode

### Como era antes

Antes da refatoração, a maior parte do CSS ficava concentrada em um arquivo principal, normalmente o `style.css` ou um conjunto pequeno de arquivos globais. Isso fazia com que:

- estilos de base, componentes e páginas ficassem misturados;
- o dark mode dependesse de regras espalhadas e difíceis de localizar;
- ajustes em uma tela pudessem afetar outras páginas;
- o carregamento do CSS ficasse menos eficiente por conta de imports encadeados e regras acumuladas no mesmo ponto.

### Como ficou agora

Com a separação por responsabilidade, a estrutura passou a ficar organizada em:

- `base` para variáveis, reset e tipografia;
- `components` para elementos reutilizáveis;
- `modules` para layout, navbar, sidebar e comportamento estrutural;
- `pages` para regras específicas de cada tela;
- `themes` para `dark.css` e `agro.css`;
- `utilities` para utilitários e animações.

Isso deixou o dark mode mais fácil de manter e evoluir, sem mexer no light mode.

### Otimização do carregamento do CSS

Sim, essa refatoração também ajuda a otimizar o carregamento do CSS.

Os principais ganhos são:

- menos CSS duplicado;
- menos dependência de arquivos grandes concentrando tudo em um só ponto;
- organização para gerar um bundle global quando necessário;
- menor risco de carregamento fora de ordem;
- melhor controle de cache e manutenção.

Na prática, a aplicação passa a ter uma base visual mais modular no desenvolvimento e mais eficiente na entrega ao navegador.

## Próximo checkpoint

- Atualizar uma página por vez.
- Validar visualmente o dark mode sem alterar o light mode.
- Manter os estilos novos dentro de `themes/dark` quando forem regras exclusivas do tema escuro.
