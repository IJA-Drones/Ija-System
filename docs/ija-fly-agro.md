# IJA Fly no Agro

O sistema usa duas identidades sobre a mesma infraestrutura de IA e consultas:
Azul nas áreas gerais e IJA Fly no Agro. O contexto é selecionado pelo servidor;
o nome da identidade não concede permissões.

- Rotas `/agro/` e canais Agro usam IJA Fly; pilotos Agro mantêm essa identidade também no chat completo.
- O atalho do chat completo mantém o contexto via `/azul?area=agro`.
- Nome, apresentação, mascote, cores, rótulos acessíveis e guias acompanham a área.
- O IJA Fly mantém as ferramentas existentes de pendências, buscas, períodos e detalhes/conferência de OS e RD. Consultas continuam usando as permissões e vínculos atuais.
- O histórico visual de Azul e IJA Fly fica separado na aba, preservando a vinculação existente à sessão e ao escopo de acesso. Ao mudar de usuário ou de permissões, ambos são descartados.
- O guia e o treinamento do IJA Fly priorizam módulos Agro autorizados. O PDF já publicado continua disponível no mesmo endereço.
- Voz e transcrição continuam compartilhando as regras de acesso, cotas e consentimento. No IJA Fly a chamada começa escutando, sem reproduzir a gravação de apresentação da Azul.

Não há migração de banco, novo usuário de serviço, nova chave de IA nem duplicação de registros. As rotas técnicas `/api/azul/` são mantidas por compatibilidade.
