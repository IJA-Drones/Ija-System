# Relatório de Refatoração Visual e Dark Mode

| Informação | Valor |
|---|---|
| Projeto | IJA System |
| Branch | `ajuste-dark` |
| Data | 24/08/2026 |
| Status | Implementado e validado |

> Esta entrega reorganizou a base visual do sistema, preservou o light mode existente e criou uma estrutura sustentável para a evolução do dark mode.

## 1. Resumo executivo

O trabalho foi dividido em duas grandes etapas:

1. **Refatoração estrutural do CSS**, retirando estilos dos templates e separando responsabilidades entre estilos globais, componentes, módulos, páginas e temas.
2. **Modernização visual do dark mode**, deixando a interface mais clara, corporativa, harmônica e consistente, sem modificar o layout funcional das páginas.

A mudança resolveu problemas como:

- CSS duplicado entre páginas.
- Botões visualmente diferentes para a mesma ação.
- Filtros com estilos inconsistentes.
- Regras de dark mode misturadas com o light mode.
- Estilos extensos dentro dos templates HTML.
- Cards e tabelas com pouco contraste no dark mode.
- Muitas requisições de arquivos CSS globais.
- Dificuldade para modificar uma página sem afetar outras.

> **Imagem sugerida:** visão geral de uma tela antes e depois da modernização.

## 2. Arquitetura anterior

Antes da refatoração, boa parte da estilização estava concentrada em arquivos grandes ou diretamente nos templates.

Os principais problemas eram:

- Blocos `<style>` dentro dos arquivos HTML.
- Regras globais misturadas com estilos específicos.
- Dark mode distribuído em diferentes arquivos.
- Componentes semelhantes com implementações diferentes.
- Alterações em um botão ou filtro exigiam ajustes em várias páginas.
- Maior risco de regressão visual.
- Navegador carregando uma cadeia de arquivos por meio de vários `@import`.
- Dificuldade para descobrir qual arquivo controlava determinado elemento.

## 3. Nova estrutura CSS

A estrutura foi dividida por responsabilidade.

| Diretório | Responsabilidade |
|---|---|
| `base` | Variáveis, reset e tipografia global |
| `components` | Botões, filtros, cards, tabelas, formulários e outros componentes |
| `modules` | Navbar, sidebar, layout e alternância de contexto |
| `pages` | Regras exclusivas de cada página |
| `themes` | Tema Agro e entrada do dark mode |
| `themes/dark` | Componentes, módulos e páginas específicas do dark mode |
| `utilities` | Classes utilitárias e animações |

Atualmente, a estrutura possui:

- `18` arquivos de componentes reutilizáveis.
- `85` arquivos com estilos específicos de páginas.
- `33` arquivos dark específicos de páginas.
- Nenhum bloco `<style>` restante nos templates.
- Um bundle global para os estilos compartilhados.

O ponto de entrada da estrutura é `app/static/css/style.css`.

> **Imagem sugerida:** captura da árvore de diretórios da nova estrutura CSS.

## 4. Componentes globais

### 4.1. Botões

Os botões passaram a utilizar o componente global existente, evitando estilizações isoladas ou inline.

Foram padronizados tamanho, espaçamento, bordas, tipografia, ícones, sombras, transições e estados de hover, active, focus e disabled.

| Classe | Utilização |
|---|---|
| `btn-primary` | Ação principal |
| `btn-success` | Confirmação ou ação positiva |
| `btn-secondary` | Ação verde secundária e exportações Excel |
| `btn-danger` | Exclusão ou ação destrutiva |
| `btn-outline-secondary` | Voltar ou cancelar |
| `btn-outline-danger` | PDF ou ação destrutiva secundária |

Exemplos corrigidos:

- Botões de manutenção agora possuem hierarquia visual.
- Botões de voltar seguem o mesmo padrão.
- Botões de exclusão utilizam a variante de perigo.
- Exportações Excel utilizam botão verde.
- Ações secundárias não competem visualmente com a ação principal.

O componente está em `app/static/css/components/buttons.css`.

> **Imagem sugerida:** conjunto de botões padronizados em uma listagem.

### 4.2. Filtros

Os filtros foram transformados em um componente reutilizável com:

- Cabeçalho expansível.
- Indicador de abertura e fechamento.
- Campos e selects consistentes.
- Área de ações.
- Resumo dos resultados.
- Badge com quantidade de filtros.
- Comportamento próprio para dark mode.

O visual anterior do filtro foi preservado no light mode. No dark mode foram aplicados fundo mais suave, separação visual das tabelas, labels com maior contraste, placeholders legíveis e foco azul discreto.

O componente está em `app/static/css/components/filters.css`.

> **Imagem sugerida:** comparação do filtro no light mode e no dark mode.

### 4.3. Outros componentes

Também foram separados e padronizados:

- Cards, tabelas, formulários, alertas e badges.
- Paginação, modais e SweetAlert.
- Chatbot, loading e logos.
- Upload de arquivos e indicador global de upload.
- List groups e chip multi-select.
- Toolbar de páginas e retorno de ciclo.

## 5. Bundle CSS

Foi criado um sistema de geração do bundle global. O script `scripts/build_css_bundle.py` percorre os imports locais e gera `app/static/css/style.bundle.css`.

### 5.1. Funcionamento

- Os arquivos continuam separados para desenvolvimento.
- O navegador recebe um único arquivo global consolidado.
- Imports externos continuam funcionando normalmente.
- Dependências locais são incorporadas ao bundle.
- Ciclos e arquivos ausentes geram erro durante a construção.
- O bundle não deve ser editado manualmente.
- A URL utiliza versionamento para evitar cache desatualizado.

### 5.2. Benefícios

- Menos requisições CSS no carregamento global.
- Melhor desempenho no localhost.
- Estrutura organizada sem penalizar a entrega ao navegador.
- Menor risco de carregar arquivos fora de ordem.
- Validação automática para impedir bundle desatualizado.
- Facilidade para manter o CSS componentizado.

O `Procfile` gera o bundle antes da inicialização da aplicação em produção.

> **Imagem sugerida:** aba Network demonstrando o carregamento do bundle CSS.

## 6. Estrutura do dark mode

O dark mode deixou de ser um único arquivo extenso e passou a seguir a mesma organização do CSS principal.

A estrutura possui:

- Variáveis dark.
- Componentes dark.
- Módulos estruturais dark.
- Estilos dark específicos por página.
- Tema complementar para o modo Agro.

O carregamento é centralizado em `app/static/css/themes/dark/core.css`. Essa separação permite melhorar uma página sem afetar o light mode, outras páginas, o modo Agro ou componentes não relacionados.

## 7. Direção visual do dark mode

A modernização manteve a estrutura e o funcionamento das páginas, alterando principalmente cores, contraste e hierarquia.

A nova direção utiliza:

- Azul-marinho mais suave como fundo.
- Superfícies em diferentes níveis para cards, filtros e tabelas.
- Azul claro em títulos e ações principais.
- Verde para ações positivas e exportações Excel.
- Vermelho controlado para exclusões.
- Textos principais claros, sem branco excessivamente forte.
- Textos secundários com contraste suficiente.
- Bordas discretas para separar conteúdos.
- Sombras mais leves e corporativas.
- Menos saturação nos menus e cards.

O objetivo foi reduzir o aspecto pesado do dark anterior sem transformar o sistema em um tema claro.

> **Imagem sugerida:** painel administrativo no novo dark mode.

## 8. Páginas modernizadas

### 8.1. Login

- Fundo dark suavizado.
- Painel com menos peso visual.
- Contraste levemente aumentado após validação.
- Campos e textos mais legíveis.
- Preservação da composição original.

> **Imagem sugerida:** tela de login no dark mode.

### 8.2. Administração e histórico de OS

- Títulos em azul e textos de filtro em azul suave.
- Fundo geral e separadores mais claros.
- Cards de solicitações com melhor contraste.
- Filtro visualmente separado da tabela.
- Tabelas e filtros harmonizados.
- Botões alinhados ao componente global.
- Botão “Exportar tudo” padronizado em verde.

> **Imagem sugerida:** dashboard administrativo e histórico de OS.

### 8.3. Relatórios

Foram revisados o menu de relatórios, coleta de imagens, logs de voo, relatórios de OS, retornos automáticos e relatórios de equipes.

Melhorias aplicadas:

- Redução de cores excessivamente fortes.
- Cards com textos mais legíveis.
- Filtros padronizados.
- Tabelas coerentes com o restante da página.
- Correção da tabela de voos processados que cobria os botões.

> **Imagem sugerida:** menu de relatórios e relatório de logs de voo.

### 8.4. Veículos

Foram revisados o menu, a listagem, os logs, detalhes dos logs, alertas, limpezas, modal de ações e campo para troca de equipe.

Melhorias aplicadas:

- Menus menos saturados.
- Cards sem fundo branco no dark mode.
- Tabelas integradas à paleta da página.
- Modais completamente adaptados ao dark.
- Campos e selects com contraste adequado.
- Ações padronizadas.

> **Imagem sugerida:** listagem de veículos e modal de ações.

### 8.5. Cadastros e listagens

Foram modernizadas as páginas de prefeituras, usuários, UVIS, clientes, pilotos, equipes, menus de clientes e feedbacks.

A revisão padronizou cards, tabelas, botões, filtros e estados vazios.

> **Imagem sugerida:** listagem de prefeituras, usuários ou clientes.

### 8.6. Agenda

- Calendário adaptado à nova paleta.
- Cards, eventos e controles com melhor contraste.
- Formulários e filtros consistentes.
- Preservação das características próprias do calendário.

> **Imagem sugerida:** agenda exibindo eventos no dark mode.

### 8.7. Estoque e manutenção

Foram revisados a listagem e o formulário de estoque, equipamentos em manutenção, detalhes, peças e históricos.

Melhorias aplicadas:

- Cards e tabelas compatíveis com dark mode.
- Formulários mais legíveis.
- Botões com hierarquia semântica.
- Excel em verde.
- PDF em vermelho outline.
- Encerramento em verde.
- Voltar e cancelar em estilo secundário.

> **Imagem sugerida:** painel de estoque e detalhes de uma manutenção.

## 9. Módulo Agro

O módulo Agro recebeu uma refatoração completa, mantendo seu layout e suas características próprias.

Foram contemplados:

- Dashboard Agro e dashboard do piloto.
- Clientes, fornecedores, contratos e orçamentos.
- Ordens de serviço e logs de voo.
- Equipes, pilotos e equipamentos.
- Banco de talentos.
- Bancos e conciliação.
- Contas a pagar e receber.
- Entradas, saídas e categorias financeiras.
- Configurações e relatórios financeiros.

### 9.1. Identidade Agro

O Agro mantém sua cor verde, mas com tons menos saturados e mais corporativos.

- Navbar e sidebar utilizam verde escuro.
- Ações recebem verde claro controlado.
- Textos mantêm contraste.
- Cards utilizam superfícies escuras neutras.
- Estados financeiros possuem cores sem excesso de saturação.
- A logo fica branca no Dark Agro, evitando conflito entre azul e verde.
- O fundo azulado da marca foi removido.
- O light mode não foi alterado.

A configuração está em `app/static/css/themes/dark/agro-mode.css`.

> **Imagem sugerida:** dashboard Agro mostrando navbar, sidebar e logo branca.

## 10. Preservação do light mode

Uma das principais regras da refatoração foi não redesenhar o light mode.

As medidas adotadas foram:

- Estilos dark isolados por `body.dark-mode`.
- Arquivos exclusivos dentro de `themes/dark`.
- Recuperação do visual original dos filtros no light.
- Separação entre estilo estrutural e cor do tema.
- Manutenção do layout, espaçamentos e fluxo funcional.
- Comparação com estilos antigos durante a extração.
- Alterações visuais concentradas no modo escuro.

> **Imagem sugerida:** mesma página no light e dark para demonstrar a preservação do layout.

## 11. Benefícios

### 11.1. Para o usuário

- Interface mais confortável em ambientes com pouca luz.
- Textos e informações importantes mais legíveis.
- Botões previsíveis em todas as páginas.
- Menos confusão entre ações principais, secundárias e destrutivas.
- Filtros com funcionamento e aparência consistentes.
- Menor fadiga visual.
- Navegação mais harmoniosa entre módulos.
- Identidade preservada entre UVIS, Prefeitura e Agro.
- Melhor experiência em desktop e dispositivos móveis.

### 11.2. Para desenvolvimento

- Redução de CSS duplicado.
- Menor risco de uma alteração afetar páginas não relacionadas.
- Facilidade para localizar estilos.
- Componentes reutilizáveis.
- Dark mode evoluindo independentemente do light.
- Templates menores e mais legíveis.
- Nenhum bloco `<style>` restante nos templates.
- Padronização de nomenclatura e responsabilidades.
- Bundle verificável automaticamente.
- Novas páginas podem reutilizar componentes existentes.

### 11.3. Para desempenho

- Um único bundle para o CSS global.
- Eliminação da cadeia de imports locais no navegador.
- Menor quantidade de requisições no carregamento principal.
- Versionamento automático para controle de cache.
- Preload das logos.
- Construção automática antes da inicialização em produção.
- Possibilidade futura de minificação sem alterar a arquitetura.

O bundle não elimina os arquivos componentizados. Ele apenas consolida sua entrega ao navegador.

## 12. Validações realizadas

| Validação | Resultado |
|---|---|
| Suíte automatizada | `119 testes aprovados` |
| Templates Jinja | `154 templates compilados` |
| Testes do bundle CSS | Aprovados |
| Testes específicos do Agro | Aprovados |
| Bundle desatualizado | Não detectado |
| Imports CSS locais no bundle | Nenhum |
| Conflitos de merge | Resolvidos |
| Marcadores de conflito | Nenhum |
| Configuração Gunicorn | Válida |
| Healthcheck HTTPS | `200 OK` |
| Erros de formatação no diff | Nenhum |

Os avisos restantes são relacionados ao uso legado de `Query.get()` do SQLAlchemy e não representam falhas desta alteração visual.

## 13. Pontos de atenção

Apesar da validação automatizada, mudanças visuais sempre exigem conferência manual.

Recomenda-se verificar:

- Páginas autenticadas para cada tipo de usuário.
- Responsividade em celular e tablet.
- Tabelas com grande quantidade de dados.
- Modais e dropdowns próximos às bordas da tela.
- Contraste de badges com estados menos comuns.
- Exportações e mensagens de feedback.
- Cache do navegador após novas alterações.

Ainda existem atributos `style` pontuais em alguns templates, embora todos os grandes blocos `<style>` tenham sido removidos. Eles podem ser tratados futuramente sem bloquear a arquitetura atual.

O arquivo legado `style.text` foi preservado como referência histórica e não participa do carregamento principal.

## 14. Resultado final

A alteração não foi apenas uma troca de cores. Ela estabeleceu uma base visual reutilizável para o sistema.

O resultado entrega:

- CSS organizado e componentizado.
- Dark mode moderno e corporativo.
- Light mode preservado.
- Identidade própria para o Agro.
- Componentes consistentes.
- Melhor desempenho de carregamento.
- Menor custo de manutenção.
- Base preparada para futuras melhorias visuais.

> A partir desta refatoração, novas páginas devem priorizar os componentes existentes e adicionar apenas estilos realmente específicos dentro de `pages`. Alterações dark devem permanecer dentro de `themes/dark`, evitando regressões no light mode.

## 15. Registro visual

Esta seção pode ser utilizada para concentrar as imagens finais antes da exportação para PDF.

### 15.1. Visão geral

> Adicionar imagem da tela principal no dark mode.

### 15.2. Componentes

> Adicionar imagens dos botões, filtros, cards e tabelas padronizados.

### 15.3. Administração e relatórios

> Adicionar imagens do dashboard administrativo, histórico de OS e relatórios.

### 15.4. Veículos, estoque e manutenção

> Adicionar imagens das listagens, modais e formulários atualizados.

### 15.5. Módulo Agro

> Adicionar imagens do dashboard Agro, área financeira e identidade visual verde.

### 15.6. Comparação entre temas

> Adicionar comparações da mesma página no light mode e no dark mode.
