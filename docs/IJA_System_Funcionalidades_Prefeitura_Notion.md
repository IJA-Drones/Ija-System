# IJA System - Funcionalidades do Âmbito Prefeitura

**Documento consolidado para importação no Notion**  
**Sistema:** IJA System  
**Escopo:** Prefeitura, administração municipal, regionais, UVIS, equipes operacionais, pilotos urbanos, operação de campo e Portal do Cidadão  
**Atualização incorporada:** Integração do Portal do Cidadão com a API InfoDengue - 16/09/2026

---

## 1. Visão geral do âmbito Prefeitura

O âmbito Prefeitura do IJA System reúne as funcionalidades relacionadas à gestão municipal e à operação urbana com drones, abrangendo administração, usuários, UVIS, regiões, solicitações, agenda, equipes, pilotos, ordens de serviço, execução em campo, veículos, equipamentos, mapas, registros de voo, relatórios e atendimento público por meio do Portal do Cidadão.

O sistema aplica segregação de dados por prefeitura, região, UVIS, equipe e usuário, de forma que cada perfil visualize e manipule apenas os dados compatíveis com o seu escopo e suas permissões.

### Fluxo funcional principal

Prefeitura / Administração → UVIS → Solicitação → Validação de endereço e localização → Análise e aprovação → Agenda → Atribuição de equipe/piloto → Ordem de Serviço → Execução em campo → Formulário, dosagem e mídias → Conclusão → Retorno automático, quando necessário → Histórico → Relatórios e prestação de contas.

Em paralelo, o sistema mantém gestão de usuários, regiões, UVIS, equipes, pilotos, veículos, drones, baterias, equipamentos, manutenção, estoque, checklists, mapas, logs DJI/KML, notificações, auditoria e recursos do Portal do Cidadão.

---

# 2. Autenticação, perfis e controle de acesso

## 2.1 Login e autenticação

- Login de usuários autenticados.
- Redirecionamento após o login conforme o perfil do usuário.
- Controle de sessão autenticada.
- Validação do perfil antes da abertura de telas e execução de ações.
- Controle de leitura, edição, exclusão e exportação conforme permissão.

## 2.2 Perfis relacionados ao âmbito Prefeitura

- Administrador geral.
- Diretor.
- Administrador de prefeitura (`prefeitura_admin`).
- Operador / operário administrativo.
- Visualizador / perfil somente leitura.
- Regional.
- UVIS.
- Equipe operacional da UVIS (`equipe_uvis`).
- Piloto urbano.
- Equipe operacional urbana.

## 2.3 Escopo por Prefeitura

- Vinculação do administrador à prefeitura correspondente.
- Restrição das consultas à prefeitura vinculada.
- Segregação de solicitações por prefeitura.
- Segregação de equipes, pilotos, veículos e recursos operacionais.
- Prevenção de exibição cruzada de dados entre prefeituras.
- Consulta vazia para perfis escopados sem vínculo válido quando aplicável.

## 2.4 Escopo regional

- Vinculação do usuário a uma região.
- Consulta limitada à região autorizada.
- Filtros regionais em solicitações, relatórios e históricos.
- Restrição de recursos operacionais conforme a região.

## 2.5 Escopo UVIS e equipe

- Associação do usuário à UVIS correspondente.
- Associação de conta operacional à UVIS-mãe.
- Restrição por equipe UVIS.
- Restrição de OS e histórico conforme unidade e equipe.

---

# 3. Administração da Prefeitura

## 3.1 Painel administrativo

- Painel administrativo central.
- Acompanhamento das solicitações recebidas.
- Visualização das solicitações por status.
- Filtro por período.
- Filtro por endereço.
- Filtro por UVIS.
- Filtro por região.
- Filtro por prefeitura.
- Filtro por equipe.
- Filtro por piloto.
- Consulta de OS em andamento.
- Consulta de histórico de OS.
- Consulta de formulários preenchidos pelas equipes.
- Visualização de mapas.
- Consulta de métricas operacionais.
- Visualização do contexto de campo.
- Exportação de dados em planilhas e documentos.

## 3.2 Decisões administrativas sobre solicitações

- Colocar solicitação em análise.
- Aprovar solicitação.
- Aprovar solicitação com recomendações.
- Negar solicitação.
- Cancelar solicitação quando autorizado.
- Atualizar estado da solicitação.
- Inserir ou alterar protocolo.
- Inserir justificativa.
- Atribuir equipe.
- Atribuir piloto.
- Acompanhar execução e conclusão.

## 3.3 Cadastros estruturais

- Administração de prefeituras.
- Administração de UVIS.
- Administração de usuários.
- Administração de regiões e vínculos de acesso.
- Administração de equipes.
- Administração de pilotos.
- Administração de credenciais.

---

# 4. Gestão de usuários e Prefeitura

## 4.1 Usuários

- Cadastro de usuários.
- Listagem de usuários.
- Edição de usuários.
- Exclusão de usuários conforme permissão.
- Gerenciamento de credenciais.
- Vinculação do usuário à prefeitura.
- Vinculação do usuário à região.
- Vinculação do usuário à UVIS.
- Definição de perfil de acesso.
- Alternância e gerenciamento administrativo de usuários quando permitido.

## 4.2 Prefeitura

- Cadastro de prefeitura.
- Edição de prefeitura.
- Vinculação de usuários à prefeitura.
- Uso da prefeitura como escopo para consultas e filtros.
- Isolamento dos dados municipais.

---

# 5. Gestão de UVIS

- Cadastro de UVIS.
- Listagem de UVIS.
- Edição de UVIS.
- Exclusão de UVIS.
- Exportação de UVIS.
- Associação da UVIS à estrutura administrativa.
- Vinculação da UVIS à prefeitura correspondente.
- Uso da UVIS como filtro de solicitações e relatórios.
- Uso da UVIS na atribuição de demandas.

---

# 6. Solicitações urbanas e demandas municipais

## 6.1 Cadastro da solicitação

A solicitação funciona como a demanda inicial da operação urbana.

Campos e informações contemplados:

- Data de agendamento.
- Hora de agendamento.
- Foco da operação.
- Tipo de operação.
- Tipo de visita.
- Tipo de imóvel.
- Altura de voo.
- Distrito administrativo.
- Logradouro.
- Número do imóvel ou indicação S/N.
- Endereço.
- Coordenadas geográficas.
- Google Place ID.
- Perímetros.
- Anexos.
- Protocolo.
- Justificativa.
- UVIS responsável.
- Equipe.
- Piloto.
- Status.
- Usuário solicitante.

## 6.2 Validações da solicitação

- Validação do logradouro.
- Validação para impedir inclusão indevida do número predial no campo de logradouro.
- Aceitação controlada de número do imóvel ou S/N.
- Obrigatoriedade do distrito administrativo.
- Definição da UVIS responsável conforme o perfil.
- Validação de tipo de visita.
- Validação de tipo de imóvel.
- Validação de foco.
- Conversão e normalização de coordenadas.
- Identificação de área geográfica restrita.
- Resolução de Place ID quando necessário.

## 6.3 Estados da solicitação

- PENDENTE.
- EM ANÁLISE.
- APROVADO.
- APROVADO COM RECOMENDAÇÕES.
- NEGADO.
- EM EXECUÇÃO.
- CONCLUÍDO.
- CANCELADO.

## 6.4 Regras de edição

- Usuários não administrativos podem editar solicitações próprias conforme as regras de estado.
- Solicitações pendentes podem ser corrigidas.
- Solicitações negadas podem ser corrigidas e reenviadas quando permitido.
- Perfis administrativos podem alterar estado, protocolo e justificativa conforme suas permissões.

## 6.5 Cancelamento

- Cancelamento autorizado da solicitação.
- Listagem de solicitações canceladas.
- Preservação do histórico do cancelamento.

---

# 7. CEP, endereço, geolocalização e controle territorial

## 7.1 Consulta de endereço

- Consulta de endereço por CEP.
- Busca de CEP por endereço.
- Integração com ViaCEP.
- Fallback por BrasilAPI quando aplicável.
- Preenchimento de informações de endereço.

## 7.2 Geocodificação

- Geocodificação direta.
- Geocodificação reversa.
- Integração com Google Maps.
- Obtenção e normalização de coordenadas.
- Resolução de Google Place ID.

## 7.3 Prevenção de duplicidade e bloqueio

- Verificação de solicitações existentes para o mesmo local.
- Bloqueio preventivo de solicitações duplicadas quando aplicável.
- Verificação por Place ID.
- Verificação por endereço e demais critérios disponíveis.
- Bloqueio de nova solicitação quando existir endereço concluído e marcado como bloqueado.
- Respeito ao escopo de prefeitura durante a verificação.

## 7.4 Áreas restritas e perímetros

- Registro de perímetro.
- Identificação de área geográfica restrita.
- Apoio visual por mapas.

---

# 8. Agenda operacional e notificações

## 8.1 Agenda

- Agenda operacional.
- Visualização de solicitações por período.
- Visões específicas por perfil.
- Agenda para piloto.
- Agenda para equipe.
- Agenda para UVIS.
- Agenda para administração.
- Filtros por período.
- Exportação da agenda em Excel.
- Cálculo de rotas do dia quando aplicável.
- Apoio ao deslocamento das equipes.

## 8.2 Notificações internas

- Criação e disponibilização de notificações internas.
- Título da notificação.
- Mensagem.
- Link relacionado.
- Data da notificação.
- Controle de leitura.
- Marcação como lida.
- Exclusão lógica.
- Limpeza de notificações.
- Notificação individual.
- Notificação ampliada para perfis autorizados.

---

# 9. Equipes UVIS

## 9.1 Cadastro e estrutura da equipe

- Criação de equipe UVIS.
- Inclusão de até cinco membros.
- Cadastro de função de cada membro.
- Cadastro de contato.
- Geração de nomes sugeridos.
- Geração de logins sugeridos.
- Validação de credenciais.

## 9.2 Conta operacional

- Criação de conta `equipe_uvis`.
- Vinculação da conta à UVIS-mãe.
- Restrição do acesso ao escopo da unidade.

## 9.3 Operação da equipe UVIS

- Painel próprio da equipe.
- Consulta das solicitações autorizadas.
- Formulário próprio de execução.
- Registro de campo.
- Histórico operacional.
- Acompanhamento das solicitações da unidade.

---

# 10. Pilotos urbanos e equipes operacionais

## 10.1 Pilotos urbanos

- Cadastro de piloto.
- Listagem de pilotos.
- Edição de piloto.
- Exclusão de piloto.
- Vinculação à prefeitura.
- Região principal.
- Região alternativa.
- Telefone.
- Vínculo com UVIS.
- Vínculo com equipe.
- Consulta das OS compatíveis com o piloto/equipe.

## 10.2 Equipes operacionais urbanas

- Cadastro de equipe.
- Listagem de equipes.
- Edição de equipe.
- Exclusão de equipe.
- Credenciais da equipe.
- Agrupamento de pilotos.
- Associação de recursos operacionais.
- Restrição das consultas por prefeitura.
- Restrição das consultas por região.
- Restrição conforme composição da equipe.

---

# 11. Ordens de Serviço urbanas

## 11.1 Fila e distribuição de OS

- Fila de OS aprovadas.
- Fila por piloto.
- Fila por equipe.
- Atribuição de responsável.
- Abertura da OS para execução.

## 11.2 Formulário operacional

A OS urbana pode registrar:

- Responsável.
- Data da execução.
- Horário de início.
- Horário de término.
- Situação da aplicação.
- Larva visualizada.
- Necessidade de retorno.
- Produto utilizado.
- Formulação.
- Dosagem.
- Quantidade aplicada.
- Taxa / área.
- Tipo de aplicação.
- Drone de pulverização.
- Drone de monitoramento.
- Condições climáticas.
- Motivo de não realização.
- Observações.
- Piloto.
- Auxiliar.
- Assinaturas.
- Mídias da execução.

## 11.3 Dosagem

- Cálculo de dosagem planejada.
- Registro da dosagem utilizada.
- Registro de quantidade aplicada.
- Registro de taxa por área.
- Associação da dosagem ao produto e à operação.

## 11.4 Associação de drones

- Seleção dos drones utilizados na execução.
- Associação do equipamento à OS.
- Preservação de snapshot dos dados relevantes do equipamento.

## 11.5 Conclusão

- Conclusão transacional da OS.
- Atualização da solicitação correspondente.
- Registro definitivo do formulário.
- Preservação do histórico operacional.
- Geração de retorno quando necessário.

## 11.6 Exportação da OS

- Exportação em PDF.
- Exportação em Excel.
- Geração de documento operacional.

---

# 12. Retorno automático

## 12.1 Geração do retorno

- Identificação da necessidade de nova visita no formulário de execução.
- Criação automática de nova solicitação.
- Herança dos dados necessários da solicitação original.
- Vinculação da nova solicitação à origem.
- Retorno da nova solicitação ao fluxo de agendamento e aprovação.

## 12.2 Ciclo de retorno

- OS inicial.
- Solicitações e OS geradas como retorno.
- Encadeamento de múltiplas etapas.
- Preservação da origem do ciclo.
- Proteção contra ciclos inválidos.
- Limite defensivo na montagem da cadeia.

## 12.3 Consulta do ciclo

- Filtro de solicitações que são retorno.
- Filtro de solicitações que geraram retorno.
- Filtro de qualquer item pertencente a um ciclo.
- Visualização do ciclo completo.
- Consulta da OS inicial.
- Consulta das etapas sucessoras.
- Visualização de status.
- Visualização de agendamento.
- Visualização da execução.
- Visualização da situação e informações de campo.
- Visualização de mídias associadas.

---

# 13. Mídias, anexos e armazenamento

## 13.1 Anexos de solicitações

- Upload de anexos.
- Visualização de anexos.
- Download de anexos.
- Remoção controlada.
- Validação de permissão para leitura e exclusão.

## 13.2 Mídias de Ordens de Serviço

- Upload de imagem principal.
- Upload de imagens complementares.
- Upload de vídeos.
- Visualização por usuários autorizados.
- Exclusão controlada de mídia.

## 13.3 Upload de arquivos grandes

- Upload em streaming.
- Envio por chunks.
- Sessões de upload em segundo plano.
- Acompanhamento do status do upload.
- Redução do risco de timeout no envio de arquivos pesados.

## 13.4 Armazenamento externo

- Armazenamento local quando configurado.
- Armazenamento via WebDAV.
- Integração com Skybox / Nextcloud.
- Streaming de leitura de arquivos remotos.
- Remoção do arquivo remoto quando a mídia é excluída do sistema.

---

# 14. Veículos e logística

## 14.1 Cadastro de veículos

- Cadastro de veículo.
- Listagem de veículos.
- Edição de veículo.
- Exclusão controlada.
- Associação de veículo à equipe.
- Exportação de dados de veículos.

## 14.2 Logs e turnos

- Abertura de turno.
- Encerramento de turno.
- Registro de log por turno.
- Registro de quilometragem.
- Controle da variação de quilometragem.
- Validação de variação máxima prevista no fluxo operacional.
- Histórico de uso do veículo.

## 14.3 Abastecimento

- Registro de abastecimento.
- Vinculação ao turno/log do veículo.
- Upload de nota fiscal.
- Upload de foto do painel.
- Histórico de abastecimentos.

## 14.4 Limpeza de veículos

- Registro de limpeza.
- Histórico de limpeza.
- Alertas de limpeza.
- Ciência do alerta quando aplicável.
- Janela de alerta operacional.
- Janela de alerta administrativa.

---

# 15. Checklists semanais

## 15.1 Checklist de veículo

Itens contemplados no checklist:

- Iluminação.
- Painel.
- Fluidos.
- Vidros.
- Pneus.
- Segurança.
- Itens internos.
- Lataria.
- Assinatura do responsável.
- Observações quando aplicável.

## 15.2 Checklist de drone

Itens contemplados no checklist:

- Hélices.
- Tanque.
- Trem de pouso.
- Câmeras.
- Carregadores.
- Baterias.
- Cabos.
- Correia.
- Quantidades.
- Observações.

## 15.3 Gestão administrativa dos checklists

- Preenchimento semanal pelo responsável.
- Listagem semanal consolidada.
- Consulta administrativa dos checklists.
- Visualização detalhada de checklists de veículos.
- Visualização detalhada de checklists de drones.

---

# 16. Drones, baterias e equipamentos

## 16.1 Drones

- Cadastro de drones urbanos.
- Listagem de drones.
- Edição de drones.
- Controle dos equipamentos disponíveis.
- Associação de drone à execução de OS.
- Uso dos dados do drone em relatórios e históricos.

## 16.2 Importação de drones

- Importação de planilhas de drones.
- Leitura de arquivos de cadastro.
- Normalização assistida dos dados quando aplicável.
- Suporte à integração de normalização pela API Gemini conforme configuração do sistema.

## 16.3 Baterias

- Cadastro de baterias.
- Gestão das baterias como equipamentos especializados.
- Associação ao inventário operacional.
- Uso de informações de bateria nos registros de voo quando disponíveis.

## 16.4 Outros equipamentos

- Cadastro de equipamentos.
- Edição de equipamentos.
- Histórico do equipamento.
- Associação com manutenção e estoque.

---

# 17. Manutenção e estoque

## 17.1 Manutenção de equipamentos

- Registro de manutenção.
- Histórico de manutenções.
- Associação da manutenção ao equipamento.
- Registro de peças utilizadas.
- Acompanhamento de consumo de peças.
- Relatórios de manutenção.

## 17.2 Estoque de peças

- Cadastro de peça.
- Listagem de peças.
- Edição de peça.
- Exclusão de peça.
- Quantidade em estoque.
- Unidade de medida.
- Metadados da peça.
- Associação de consumo da peça à manutenção.
- Histórico de consumo.
- Exportação do estoque.

---

# 18. Logs DJI e rotas KML

## 18.1 Importação de registros de voo DJI

- Importação de planilhas XLSX.
- Importação em lotes.
- Normalização dos registros.
- Deduplicação por fingerprint.
- Armazenamento do lote de importação.

## 18.2 Dados do registro de voo

Podem ser armazenados:

- Período.
- Localização.
- Aeronave.
- Tipo de tarefa.
- Área.
- Quantidade.
- Duração.
- Cultura, quando existente na origem.
- Piloto.
- Equipe.
- Campo.
- Número de série.
- Bateria.

## 18.3 Rotas KML

- Importação de arquivos KML.
- Cálculo de hash SHA-256.
- Código da rota.
- Armazenamento de metadados.
- Extração dos pontos da rota.
- Armazenamento dos pontos da rota.
- Visualização em mapa.
- Download do KML.
- Exclusão controlada.

## 18.4 Vínculo de KML e OS

- Vinculação de KML a registros de voo.
- Vinculação de KML a Ordem de Serviço.
- Associação automática quando existem critérios compatíveis.
- Uso de Place ID quando disponível.
- Associação manual.
- Diagnóstico de rotas sem vínculo.

## 18.5 Relatórios DJI/KML

- Consulta dos registros importados.
- Exportação dos registros.
- Relatórios de logs DJI.
- Visualização das rotas relacionadas às operações.

---

# 19. Mapas, geolocalização e painel operacional

## 19.1 Mapas

- Mapa de relatório.
- Geolocalização de solicitações.
- Visualização geográfica das operações.
- Heatmap.
- Dados geográficos.
- Visualização de trajetos.
- Visualização de rotas KML.

## 19.2 Painel operacional / direção

- Métricas operacionais.
- Mapa de operações.
- Informações meteorológicas quando disponíveis.
- Contexto de campo.
- Apoio à direção e à tomada de decisão operacional.

---

# 20. Relatórios, históricos e exportações

## 20.1 Relatórios de solicitações

- Relatório de solicitações.
- Filtros por período.
- Filtros por status.
- Filtros por UVIS.
- Filtros por região.
- Filtros por prefeitura.
- Filtros por equipe.
- Filtros por piloto.
- Filtros por atributos operacionais.

## 20.2 Relatórios de Ordens de Serviço

- Relatórios de OS urbanas.
- Histórico de execução.
- Formulários de campo.
- Dados de dosagem e aplicação.
- Informações de piloto/equipe.
- Mídias e demais evidências quando aplicável.

## 20.3 Relatório de coleta de imagens

- Consulta das mídias coletadas.
- Relatório de coleta de imagens.
- Tratamento específico para volume de arquivos.

## 20.4 Relatório de retornos automáticos

- Relatório das solicitações de retorno.
- Relatório das solicitações que geraram retorno.
- Relatório de ciclos completos.
- Consulta da OS inicial e etapas sucessoras.

## 20.5 Exportações

- Excel.
- PDF.
- Exportação de agenda.
- Exportação de histórico.
- Exportação de OS.
- Exportação de solicitações.
- Exportação de UVIS.
- Exportação de veículos e logs.
- Exportação de estoque.
- Exportação de logs DJI.
- Geração de trabalhos PDF de maior custo de forma assíncrona quando aplicável.

---

# 21. Clientes urbanos

- Cadastro de clientes urbanos.
- Listagem de clientes urbanos.
- Edição de clientes urbanos.
- Exclusão de clientes urbanos.
- Exportação de clientes urbanos.

---

# 22. Feedback, suporte e melhoria contínua

- Criação de tópicos de feedback.
- Registro de bugs.
- Registro de sugestões.
- Registro de melhorias.
- Criação por unidade ou usuário autorizado.
- Categorias.
- Prioridade.
- Status.
- Roteamento de suporte.
- Comentários internos.
- Comentários visíveis conforme o fluxo.
- Anexos em comentários.
- Moderação.
- Acompanhamento da resolução.

---

# 23. Assistente FAQ

- Assistente FAQ contextual para UVIS.
- Assistente FAQ contextual para administração.
- Respostas determinísticas conforme contexto configurado.
- Apoio à navegação e às dúvidas operacionais do usuário.

---

# 24. Auditoria e rastreabilidade

## 24.1 Auditoria de ações

- Auditoria automática de ações mutáveis relevantes.
- Registro de ações POST.
- Registro de ações PUT.
- Registro de ações PATCH.
- Registro de ações DELETE.

## 24.2 Dados de auditoria

Podem ser registrados:

- Usuário.
- Método HTTP.
- Endpoint.
- Caminho acessado.
- Status da resposta.
- Endereço IP.
- User agent.
- Data e horário.

## 24.3 Presença de usuários

- Registro de login.
- Registro de último acesso.
- Presença limitada dos usuários autenticados.

## 24.4 Rastreabilidade operacional

- Histórico das solicitações.
- Histórico das OS.
- Histórico dos retornos.
- Histórico de veículos.
- Histórico de abastecimentos.
- Histórico de limpezas.
- Histórico de equipamentos.
- Histórico de manutenção.
- Histórico de consumo de peças.
- Histórico de registros de voo.

---

# 25. Portal do Cidadão

O Portal do Cidadão amplia o âmbito Prefeitura para uma área pública de participação e informação, mantendo a página inicial simples e orientada ao envio de relatos, além de disponibilizar dados públicos de saúde e epidemiologia.

## 25.1 Participação cidadã

- Acesso público ao Portal do Cidadão.
- Fluxo de envio de relatos pelo cidadão.
- Manutenção do formulário de relato mesmo quando serviços externos de dados epidemiológicos estiverem indisponíveis.
- Botão para registrar um relato a partir do relatório epidemiológico.
- Integração entre informação epidemiológica e participação cidadã sem fundir os dois fluxos.

---

# 26. Boletim de saúde com API InfoDengue

**Data da atualização:** 16/09/2026  
**Módulo:** Portal do Cidadão  
**Área:** Boletim de saúde, dengue e arboviroses  
**Fonte de dados:** API pública InfoDengue

## 26.1 Objetivo da integração

- Adicionar uma camada de dados epidemiológicos ao Portal do Cidadão.
- Complementar o boletim de saúde existente.
- Manter a home simples e focada no envio de relatos.
- Disponibilizar um caminho para consulta de dados mais detalhados.
- Permitir acompanhamento de dengue, chikungunya e zika.

## 26.2 Resumo epidemiológico na home

Foi adicionado um bloco de dados epidemiológicos antes das notícias oficiais.

O resumo rápido pode apresentar:

- Doença consultada.
- Localidade.
- Semana epidemiológica mais recente.
- Data de início da semana.
- Nível de alerta.
- Casos notificados.
- Casos estimados.
- Incidência por 100 mil habitantes.
- Probabilidade de Rt acima de 1.

Também estão disponíveis:

- Botão **Ver relatório completo**.
- Link **Consultar dados no InfoDengue** para abertura da fonte oficial.

## 26.3 Comportamento quando a API responde corretamente

- Exibição dos dados epidemiológicos no boletim.
- Disponibilização do acesso ao relatório completo.
- Disponibilização do link para a fonte InfoDengue.

## 26.4 Comportamento em falha da API

Quando a API estiver fora do ar, lenta, retornar erro ou retornar dados vazios:

- O Portal do Cidadão continua carregando.
- O bloco de dados epidemiológicos pode deixar de aparecer.
- Notícias e links oficiais continuam disponíveis.
- O envio de relatos continua funcionando.
- O formulário de relato permanece disponível.
- A falha externa não bloqueia o restante do portal.

---

# 27. Relatório epidemiológico público

## 27.1 Acesso

- Rota pública: `/portal-cidadao/boletim-dengue`.
- Acesso sem necessidade de login.
- Painel público de leitura epidemiológica.

## 27.2 Filtros

- Filtro por doença.
- Filtro por ano.
- Doenças disponíveis:
  - Dengue.
  - Chikungunya.
  - Zika.
- Atualização do relatório conforme os filtros selecionados.
- Nova consulta ao backend/API conforme doença e ano selecionados.

## 27.3 Cards de resumo

A página apresenta cards com:

- Localidade.
- Doença selecionada.
- Ano selecionado.
- Última semana epidemiológica disponível.
- Nível atual de alerta.
- Total de casos no período.
- Total de casos estimados.

## 27.4 Série semanal

- Série de casos estimados por semana epidemiológica.
- Visualização em barras horizontais.
- Representação do nível de alerta na visualização.
- Apoio à identificação de crescimento, queda e picos ao longo do ano.

## 27.5 Indicadores complementares

- Incidência atual por 100 mil habitantes.
- Probabilidade de Rt acima de 1.
- Pico do período.
- Semana relacionada ao pico quando disponível no relatório.
- Botão para registrar um relato.

## 27.6 Tabela técnica de semanas epidemiológicas

A tabela apresenta:

- Semana epidemiológica.
- Data de início.
- Nível de alerta.
- Casos notificados.
- Casos estimados.
- Incidência.
- Probabilidade de Rt acima de 1.

---

# 28. Integração técnica com a API InfoDengue

## 28.1 Dados consultáveis na API

- Código IBGE do município.
- Doença.
- Semana epidemiológica inicial.
- Semana epidemiológica final.
- Ano epidemiológico inicial.
- Ano epidemiológico final.
- Formato de retorno JSON ou CSV.

O Portal do Cidadão utiliza JSON para montar as informações na interface.

## 28.2 Parâmetros utilizados

- `geocode`: código IBGE da cidade.
- `disease`: `dengue`, `chikungunya` ou `zika`.
- `format`: `json`.
- `ew_start`: semana epidemiológica inicial.
- `ew_end`: semana epidemiológica final.
- `ey_start`: ano inicial.
- `ey_end`: ano final.

## 28.3 Configuração padrão documentada

- `INFODENGUE_GEOCODE=3550308`.
- `INFODENGUE_CITY=São Paulo`.
- `INFODENGUE_DISEASE=dengue`.
- `INFODENGUE_LOOKBACK_WEEKS=8`.

## 28.4 Normalização e processamento dos dados

- Consulta usando `format=json`.
- Normalização de campos que podem variar entre cidades.
- Tratamento de variações como `SE` / `se`.
- Tratamento de variações como `p_rt1` / `prt1`.
- Tratamento de variações como `p_inc100k` / `inc`.
- Seleção da semana epidemiológica mais recente para o resumo.
- Montagem da série anual para o relatório completo.
- Cálculo do total de casos notificados.
- Cálculo do total de casos estimados.
- Identificação do pico do período.
- Formatação de números no padrão brasileiro.

## 28.5 Cache

- Cache para reduzir chamadas repetidas à API.
- Cache separado para resumo e relatório.
- Tempo de cache documentado: 30 minutos.

## 28.6 Fallback e resiliência

- Fallback seguro em falhas externas.
- O portal continua funcionando sem resposta da API.
- O fluxo de relatos continua independente da integração epidemiológica.

## 28.7 Arquivos relacionados à atualização InfoDengue

### Backend

- `app/modules/portal_cidadao/health_news.py`
- `app/modules/portal_cidadao/routes.py`
- `config.py`

### Templates

- `app/templates/portal_cidadao.html`
- `app/templates/portal_cidadao_boletim_dengue.html`

### Estilo

- `app/static/css/pages/portal_cidadao.css`

### Testes

- `tests/test_portal_cidadao_denuncias.py`

## 28.8 Validações documentadas da atualização

- Suíte focada do Portal do Cidadão executada com sucesso.
- Resultado documentado: 12 testes aprovados.
- Validação de sintaxe do módulo `portal_cidadao` executada.

## 28.9 Observação sobre os dados epidemiológicos

- Os dados vêm do InfoDengue e funcionam como apoio informativo.
- O boletim não substitui a validação técnica da vigilância.
- O boletim não substitui documentos oficiais publicados pela Secretaria de Saúde.
- O relatório público foi pensado para fornecer informações detalhadas sem transformar a página inicial em uma tela técnica pesada.

---

# 29. Integrações relevantes ao âmbito Prefeitura

## 29.1 Google Maps

- Mapas.
- Geocodificação.
- Geocodificação reversa.
- Rotas.
- Visualização geográfica.
- Apoio a Place ID.
- Visualização de KML.

## 29.2 ViaCEP / BrasilAPI

- Consulta de endereço por CEP.
- Busca de CEP por endereço.
- Fallback de consulta quando aplicável.

## 29.3 InfoDengue

- Dados epidemiológicos públicos por município.
- Dengue.
- Chikungunya.
- Zika.
- Semanas epidemiológicas.
- Níveis de alerta.
- Casos notificados.
- Casos estimados.
- Incidência.
- Probabilidade de Rt acima de 1.

## 29.4 WebDAV / Skybox / Nextcloud

- Armazenamento de mídias operacionais.
- Streaming de arquivos.
- Upload de arquivos grandes.
- Exclusão remota controlada.

## 29.5 Dados meteorológicos

- Apoio ao painel operacional e contexto de campo quando o serviço externo correspondente está configurado.

---

# 30. Funcionalidades transversais de interface

- Aplicação web responsiva.
- Uso por navegador.
- Painéis especializados conforme perfil.
- Formulários especializados.
- Filtros de consulta.
- Mensagens de validação.
- Feedback visual de ações.
- Tema claro/escuro quando disponível nas telas correspondentes.
- PWA básica com manifesto e service worker.
- Exportação de dados em arquivos.
- Acesso controlado a mídias e documentos.

---

# 31. Resumo consolidado por área

## Gestão municipal

- Prefeitura.
- Usuários.
- Perfis.
- Permissões.
- Regiões.
- UVIS.
- Equipes.
- Pilotos.
- Credenciais.

## Demanda e planejamento

- Solicitações.
- CEP e endereço.
- Place ID.
- Geolocalização.
- Bloqueio de duplicidade.
- Áreas restritas.
- Aprovação e negação.
- Agenda.
- Rotas do dia.
- Notificações.

## Execução

- Ordem de Serviço urbana.
- Fila por piloto/equipe.
- Formulário operacional.
- Dosagem.
- Drones.
- Clima.
- Assinaturas.
- Imagens e vídeos.
- Conclusão.
- Retorno automático.

## Recursos operacionais

- Veículos.
- Turnos.
- Quilometragem.
- Abastecimento.
- Limpeza.
- Checklists.
- Drones.
- Baterias.
- Equipamentos.
- Manutenção.
- Estoque.

## Dados de voo e geoprocessamento

- Importação DJI.
- Deduplicação de registros.
- KML.
- Vínculo KML/OS.
- Mapas.
- Heatmap.
- Geolocalização.

## Gestão da informação

- Histórico.
- Relatórios.
- Excel.
- PDF.
- Auditoria.
- Feedback.
- Suporte.
- FAQ contextual.

## Participação e informação ao cidadão

- Portal do Cidadão.
- Envio de relatos.
- Boletim de saúde.
- API InfoDengue.
- Resumo epidemiológico na home.
- Relatório epidemiológico público.
- Filtro por dengue, chikungunya e zika.
- Filtro por ano.
- Série semanal.
- Indicadores epidemiológicos.
- Tabela de semanas epidemiológicas.
- Link para fonte oficial.
- Fallback em indisponibilidade externa.

---

# 32. Itens fora do escopo deste documento

Este documento foi propositalmente limitado ao âmbito Prefeitura / operação urbana / UVIS / Portal do Cidadão.

Não foram incluídos como funcionalidades do âmbito Prefeitura os recursos exclusivos da vertical Agro, como:

- Clientes agro.
- Fornecedores agro.
- Orçamentos agro.
- RD de mapeamento agro.
- Contratos agro.
- Ordens de Serviço agro.
- Piloto agro.
- Equipamentos exclusivamente agro.
- Financeiro agro.
- Contas a pagar e a receber agro.
- Bancos agro.
- Caixa diário agro.
- Conciliação financeira agro.
- Fluxo de caixa agro.
- DRE gerencial agro.
- Banco de talentos agro.

---

# 33. Base documental utilizada

Este consolidado foi elaborado a partir de:

- Documentação técnica descritiva do IJA System.
- README / documentação geral de funcionalidades do IJA System.
- Documento **Atualização do Portal do Cidadão: integração com API InfoDengue**, datado de 16/09/2026.

A seção de InfoDengue reflete especificamente a atualização documentada em 16/09/2026, posterior ao snapshot técnico de 25/08/2026 mencionado na documentação técnica original.

---

**Fim do documento**
