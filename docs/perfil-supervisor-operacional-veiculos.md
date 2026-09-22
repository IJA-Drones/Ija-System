# Perfil Supervisor Operacional de Veículos

## Identificação

- **Nome técnico:** `sup_veiculos`
- **Nome exibido:** Supervisor Operacional de Veículos
- **Finalidade:** supervisionar a operação de veículos, equipes e ordens de serviço da prefeitura vinculada.

## Objetivo do perfil

O `sup_veiculos` foi criado para representar uma pessoa responsável pela operação da frota. Ele acompanha os veículos, organiza equipes, acompanha as ordens de serviço e pode executar as rotinas operacionais que normalmente seriam realizadas por um piloto.

Esse perfil é útil quando existe uma liderança operacional responsável por uma equipe, mas não necessariamente existe um cadastro de piloto titular para essa equipe.

## Responsabilidades principais

O supervisor pode:

- acompanhar a frota e o rastreamento dos veículos;
- iniciar, acompanhar e encerrar turnos;
- registrar quilometragem, abastecimentos e limpezas;
- consultar logs operacionais e alertas de limpeza;
- preencher checklists semanais de veículos e drones;
- acessar a dosagem e os fluxos operacionais de OS;
- consultar o histórico de ordens de serviço;
- preencher formulários operacionais e concluir OS da equipe vinculada;
- cadastrar, editar, listar e organizar equipes OA dentro do escopo permitido;
- associar supervisores às equipes;
- acompanhar pilotos, veículos e equipamentos relacionados à operação;
- consultar relatórios e agendas necessários à supervisão.

## Supervisor sem piloto titular

O piloto titular é opcional quando uma equipe possui um supervisor operacional.

Ao selecionar um supervisor no cadastro ou na edição da equipe:

1. a equipe pode permanecer sem piloto titular;
2. o supervisor passa a ser o responsável operacional da equipe;
3. o sistema usa a equipe vinculada ao supervisor nos fluxos de OS, histórico, checklist, dosagem e veículos;
4. não é necessário criar um registro fictício em `Pilotos`;
5. o supervisor não precisa possuir `piloto_id`.

A associação é feita pelo campo interno de vínculo operacional da conta do supervisor. Quando a equipe é alterada, o vínculo do supervisor é atualizado junto com a equipe.

## Escopo de acesso

O acesso do supervisor é limitado pela `prefeitura_id` da conta. Ele não deve visualizar ou operar dados de outras prefeituras.

Além do limite municipal, os fluxos operacionais de OS usam a equipe vinculada ao supervisor. Assim, a conta não deve assumir automaticamente todas as equipes apenas por possuir o mesmo município.

O perfil não é um administrador global. Portanto, ele não deve:

- gerenciar contas administrativas globais;
- alterar políticas de segurança do sistema;
- acessar configurações internas de desenvolvimento;
- visualizar dados fora do escopo municipal e operacional autorizado.

## Telas relacionadas

As telas esperadas para esse perfil são as relacionadas à operação:

- Central de Veículos;
- Frota e rastreamento;
- Abrir e encerrar turno;
- Logs diários e logs de limpeza;
- Abastecimentos e mídias operacionais;
- Alertas de limpeza;
- Checklist semanal;
- Dosagem;
- OS da equipe e histórico de OS;
- Cadastro, edição e listagem de equipes OA;
- Agenda e relatórios operacionais;
- Equipamentos e pilotos quando necessários para a gestão da operação.

## Benefícios para a operação

- reduz a dependência de um piloto titular cadastrado;
- evita a criação de usuários ou pilotos fictícios;
- centraliza a responsabilidade operacional em uma conta própria;
- melhora a rastreabilidade de turnos, abastecimentos, limpezas e checklists;
- permite que a liderança acompanhe a execução das OS;
- mantém a separação entre supervisão operacional e administração global;
- preserva o isolamento dos dados por prefeitura e equipe.

## Cadastro recomendado

Para criar uma conta corretamente:

1. cadastrar o usuário com o tipo `sup_veiculos`;
2. informar a prefeitura da operação;
3. garantir que a conta esteja ativa e consiga autenticar;
4. cadastrar ou editar a equipe OA;
5. selecionar o supervisor na seção de supervisores da equipe;
6. deixar o piloto titular vazio quando o supervisor assumir a função;
7. validar o acesso à equipe, aos veículos, ao checklist, à dosagem e às OS.

## Observação operacional

A conta só deve ser associada a equipes compatíveis com sua prefeitura. Se o supervisor for removido da equipe, ele deixa de atuar como responsável operacional daquela equipe e os fluxos dependentes do vínculo devem deixar de aparecer ou retornar acesso negado.
