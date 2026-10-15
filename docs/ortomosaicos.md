# Visualizador de ortomosaicos

## Acesso e uso

O menu **Ortomosaicos** (`/ortomosaicos`) é exclusivo dos perfis `diretor` e `dev`. A restrição é obrigatória no servidor em todas as rotas, inclusive consultas, reprocessamento e leitura parcial do arquivo. A Central TI não pode conceder essa funcionalidade a outros perfis. DIRETOR e DEV mantêm o alcance global de prefeituras já existente no sistema; cada levantamento pertence obrigatoriamente a uma prefeitura, escolhida no envio.

Envie um GeoTIFF RGB de 8 bits (três bandas ou quatro com transparência), com sistema de coordenadas e transformação geográfica válidos. Não há teto de tamanho ou de pixels imposto pela aplicação por padrão; não aceita MDS, bandas multiespectrais ou TIF sem georreferenciamento. `ORTHOMOSAIC_MAX_UPLOAD_MB=0` e `ORTHOMOSAIC_MAX_PIXELS=0` significam sem limite. Um valor positivo explícito no ambiente permite impor um teto operacional e prevalece sobre o padrão. O formulário e o servidor usam a mesma configuração, incluindo a validação de pixels no subprocesso.

Uploads continuam sendo feitos em uma única requisição, sem retomada automática. Para arquivos grandes no site, conferir limites de corpo e tempo do proxy/hospedagem e espaço temporário disponível (original, cópia de trabalho e COG). Aumentar o limite da aplicação não altera os limites do provedor. O envio ao Skybox usa fluxo de arquivo, sem carregar o TIF inteiro na memória.

O visualizador permite zoom, enquadramento, tela cheia, coordenadas WGS 84, Google Satélite, mapa de ruas OpenStreetMap, controle de opacidade e visibilidade da imagem. O painel de camadas pode ser recolhido. Medições e curvas de nível não fazem parte desta primeira entrega. As medidas de pixel da cópia projetada são em Web Mercator, não uma medição topográfica de precisão no solo.

## Fundo Google Satélite

O satélite é a opção inicial e usa a Map Tiles API oficial pelo OpenLayers. A imagem do Google fica por baixo do GeoTIFF, sem alterar o arquivo ou suas coordenadas. O seletor permite alternar entre Google Satélite, ruas e sem fundo. Falhas de autenticação, conexão ou carregamento voltam ao mapa de ruas com um aviso persistente separado do estado do ortomosaico.

Reutiliza a mesma chave de **navegador** dos demais mapas do sistema: `Maps_KEY_FRONT` / `KEY_API_GOOGLE_MAPS`, autorizada também para a Map Tiles API. Não exige uma chave ou variável separada e nunca usa a chave de servidor `Maps_KEY_BACK`. A chave do navegador aparece no HTML e nas requisições ao Google: aplicar restrições de API e de sites autorizados, incluindo os endereços locais usados nos testes. A API precisa estar habilitada em um projeto com faturamento ativo; o consumo segue as cotas e preços do Google. Uma chave que funciona na Maps JavaScript API não garante acesso à Map Tiles API.

Os tiles são solicitados diretamente pelo navegador, sem gravá-los no Skybox. O OpenLayers administra sessões, renovação e créditos dos fornecedores por área visualizada; o logo oficial Google Maps fica visível enquanto o satélite é exibido, inclusive em tela cheia. Essa integração não exige nova migração de banco.

Referências: [configuração da API](https://developers.google.com/maps/documentation/tile/get-api-key), [atribuição](https://developers.google.com/maps/documentation/tile/policies).

## Armazenamento e processamento

O original é validado em um subprocesso, com limite de tempo, e gravado no Skybox antes de confirmar o cadastro. O banco mantém nome, prefeitura, usuário, hash SHA-256, tamanho, metadados geográficos, estado e referência privada dos arquivos. O prefixo é `SKYBOX_BASE_DIR/ortomosaicos/<namespace-do-banco>/prefeitura-<id>/<uuid>/`; testes e produção ficam em namespaces distintos. Arquivos não são publicados em `/static` nem retornados como links remotos ao navegador.

O processamento baixa o original para uma pasta temporária, confere tamanho e hash, reprojeta para EPSG:3857 e gera um Cloud Optimized GeoTIFF com blocos e níveis de zoom. A cópia é enviada ao Skybox. Antes de marcar como disponível, o sistema exige uma resposta real HTTP 206 para uma leitura parcial. O navegador consulta uma rota autenticada do IJA, que encaminha as faixas de bytes ao Skybox e mantém as credenciais no servidor. O tráfego passa pela aplicação: dimensionar conexões e banda antes de ampliar o uso.

Estados: `pendente`, `processando`, `pronto` e `falha`. A fila é persistida no banco. Um executor local processa um arquivo por vez; vários processos disputam a execução por uma atualização condicional no banco. Uma tarefa interrompida pode ser retomada após o vencimento da reserva de processamento, pela consulta da página ou pelo comando abaixo. A conversão tem timeout configurável em `ORTHOMOSAIC_PROCESS_TIMEOUT_SECONDS` (padrão de uma hora); a reserva inclui esse tempo mais 30 minutos para transferências (90 minutos por padrão). Não há promessa de processamento ilimitado: recursos, encerramento de processos e tempo disponível na hospedagem continuam relevantes. O token de processamento evita que uma tentativa antiga substitua o resultado de uma nova tentativa. Falhas permitem **Processar novamente** na tela.

Para retomar pendências por um trabalhador/agendador externo:

```bash
flask --app app:create_app main processar-ortomosaicos --limite 5
```

`ORTHOMOSAIC_BACKGROUND_ENABLED=0` desativa apenas o disparo automático por threads; o comando continua disponível. O banco mantém o original recuperável no Skybox, mas a execução não é um serviço externo de filas: sem páginas abertas ou agendador, pendências de um processo encerrado aguardam o próximo disparo. Não há limpeza automática de arquivos de tentativas abandonadas durante encerramento abrupto; planejar retenção conforme o volume de uso.

## Implantação

Instalar as dependências de `requirements.txt` (inclui Rasterio 1.5.2) e aplicar `flask --app app:create_app db upgrade`. A migração `c8d3e70a192f`, após `b7f2c9d41e60`, cria somente a tabela `ortomosaicos`. Não altera prefeituras, contas ou OS existentes. O serviço precisa de acesso ao Skybox, permissão para executar o subprocesso Python e espaço temporário para original e cópia otimizada. A conversão não ocorre dentro da requisição de navegação, mas o envio inicial ao Skybox ocorre antes da resposta do upload; configurar timeout e limite do proxy de acordo com o tamanho admitido.

Bibliotecas do navegador são servidas localmente em `app/static/vendor`: OpenLayers 10.10.0 e GeoTIFF.js 3.1.0-beta.0, dependência utilizada pela distribuição OpenLayers. As licenças estão nas respectivas pastas. GeoTIFF.js deve ser carregado antes de `ol.js`. Não habilitar `convertToRGB` para o COG RGBA produzido aqui: a leitura RGB descarta a quarta banda de transparência.

## Validação

`tests/test_ortomosaicos.py` usa bancos descartáveis e armazenamento simulado: restrição dos perfis, autenticação, CSRF, validação de arquivo e prefeitura, conversão real de raster, conferência de integridade, recuperação de tarefa expirada, leitura parcial privada e migração reversível. O arquivo Base PCTI foi usado para conferir visualmente a renderização RGBA no navegador e testar o fluxo real no banco de testes/Skybox.
