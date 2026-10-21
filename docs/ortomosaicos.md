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

O original é validado em um subprocesso, sem limite de duração, e gravado no Skybox antes de confirmar o cadastro. O banco mantém nome, prefeitura, usuário, hash SHA-256, tamanho, metadados geográficos, estado e referência privada dos arquivos. O prefixo é `SKYBOX_BASE_DIR/ortomosaicos/<namespace-do-banco>/prefeitura-<id>/<uuid>/`; testes e produção ficam em namespaces distintos. Arquivos não são publicados em `/static` nem retornados como links remotos ao navegador.

O processamento baixa o original para uma pasta temporária, confere tamanho e hash, reprojeta para EPSG:3857 e gera um Cloud Optimized GeoTIFF com blocos e níveis de zoom. A cópia é enviada ao Skybox. Antes de marcar como disponível, o sistema exige uma resposta real HTTP 206 para uma leitura parcial. O navegador consulta uma rota autenticada do IJA, que encaminha as faixas de bytes ao Skybox e mantém as credenciais no servidor. O tráfego passa pela aplicação: dimensionar conexões e banda antes de ampliar o uso.

Estados: `pendente`, `processando`, `pronto` e `falha`. A fila é persistida no banco. Um executor local processa um arquivo por vez; vários processos disputam a execução por uma atualização condicional no banco. Uma tarefa interrompida pode ser retomada após o vencimento da reserva de processamento, pela consulta da página ou pelo comando abaixo. A validação, a conversão RGB e a geração de curvas não têm prazo máximo de execução. A antiga configuração `ORTHOMOSAIC_PROCESS_TIMEOUT_SECONDS` não é mais utilizada. Enquanto o trabalhador está ativo, uma thread renova a reserva de cinco minutos a cada 30 segundos, inclusive durante download e upload. Essa reserva detecta um trabalhador encerrado; seu vencimento permite uma nova tentativa, sem marcar falha apenas pelo tempo decorrido. Se o banco ficar indisponível, a renovação é tentada novamente; uma indisponibilidade maior que a reserva pode permitir outra tentativa, mas somente o token vigente pode publicar. Recursos, encerramento de processos e limites externos da hospedagem continuam relevantes. Falhas reais de integridade, processamento ou armazenamento continuam sendo informadas; os uploads dos levantamentos ao Skybox usam `timeout=None`, inclusive para a escrita no socket, que no Requests também é afetada pelo timeout de conexão. Em desconexões ou respostas HTTP transitórias (408, 429, 500, 502, 503, 504), o envio é repetido até três vezes, com pausas de 2 e 4 segundos, reabrindo o arquivo desde o início no mesmo caminho privado da tentativa. Durante essas tentativas o resultado convertido é mantido localmente, sem repetir a conversão. Esgotadas as tentativas, a falha informa que o envio ao Skybox não foi concluído. Erros permanentes, como autenticação, falta de espaço e certificado inválido, não entram nessa repetição. Os demais usos do Skybox, a preparação de pastas e as leituras mantêm seus limites de conexão/inatividade. Sem timeout no PUT, uma conexão travada pode exigir intervenção; o sistema não consegue impedir limites ou interrupções impostos pelo próprio armazenamento/proxy. O token de processamento evita que uma tentativa antiga substitua o resultado de uma nova tentativa. Falhas permitem **Processar novamente** na tela.

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

## DEM e curvas de nível

A mesma biblioteca aceita o tipo **DEM / curvas de nível**, apenas para DIRETOR e DEV. O upload exige GeoTIFF de uma banda numérica, georreferenciamento válido e elevações em metros (confirmadas no formulário; unidades explicitamente incompatíveis são rejeitadas). O tipo RGB continua com a validação anterior. A migração `d9e4f81b203a`, após `c8d3e70a192f`, adiciona tipo, intervalo, resolução e referências privadas dos dois resultados; registros existentes ficam como `rgb`.

Fluxo: enviar DEM → escolher intervalo vertical e resolução horizontal → acompanhar Na fila/Processando → abrir curvas no mapa ou baixar JPEG. Padrões da interface: intervalo 1 m e grade 2 m. Intervalo aceito: 0,25–1.000 m; resolução: 0,25–100 m. Resolução é espaçamento da grade, não precisão altimétrica. Se o processamento falhar, é possível ajustar esses parâmetros e tentar novamente sem reenviar o original.

O subprocesso usa Rasterio/GDAL para ler máscaras e reprojetar/re-amostrar em grade métrica com interpolação bilinear; ContourPy extrai isolinhas lineares. Preserva o CRS projetado em metros quando disponível; caso contrário usa uma zona UTM local. A resolução efetiva nunca é menor que a estimativa da resolução nativa. O sistema registra a grade efetiva, CRS de cálculo, intervalo, contagem e amplitude de cotas da grade processada. O referencial vertical é o do arquivo original, sem conversão de datum. Não há classificação de solo, suavização nem remoção automática de vegetação/construções: MDS continua sendo superfície, não MDT. Resultados não são necessariamente idênticos aos de outro algoritmo/configuração no QGIS.

Limites de trabalho desta versão: 4 milhões de células na grade, 500 cotas, 30.000 linhas e 1 milhão de vértices. Ao exceder, o trabalho falha com orientação para ajustar parâmetros, sem simplificar silenciosamente. A aplicação não impõe novo teto de MB ao original; continuam valendo espaço temporário, memória e limites externos do servidor, sem prazo máximo de processamento imposto pela aplicação. Jobs compartilham o worker durável dos ortomosaicos e a CLI `flask --app app:create_app main processar-ortomosaicos --limite 5`.

Resultados no Skybox, na pasta privada do levantamento e namespace do banco:

- `curvas.geojson`: linhas WGS 84 com atributos `cota` (metros) e `mestra` (a cada cinco intervalos), servidas por rota autenticada. Nesta versão a camada é carregada inteira, respeitando os limites de complexidade; não usa tiles vetoriais.
- `curvas.jpg`: JPEG de 3080 × 2200 pixels, fundo claro, cotas nas curvas mestras selecionadas, grade de coordenadas, indicação de norte da grade e escala no CRS de cálculo. Sem imagens do Google incorporadas. Usa as mesmas linhas do GeoJSON. Aparência fixa; controles do visualizador não alteram o JPEG.

Os dois resultados são publicados juntos somente após processamento e uploads concluídos. Em falha parcial, o worker remove o resultado incompleto que criou. Rotas de saída verificam perfil, prefeitura, tipo e estado pronto; respostas privadas/no-store, sem URLs ou credenciais do Skybox no navegador. Hash e tamanho do original são conferidos antes de processar. Cada tentativa usa nomes próprios e um token de posse para impedir que jobs antigos publiquem sobre tentativas novas.

No mapa: zoom/enquadramento, visibilidade, opacidade, cor, espessura, cotas, clique para consultar altitude e opção de sobrepor a um ortomosaico RGB pronto da mesma prefeitura. Sem fundo, mapa de ruas e Google Satélite continuam disponíveis. O seletor de referência não garante que os levantamentos cubram a mesma área.

Validação: `python -m pytest tests/test_dem_contours.py tests/test_ortomosaicos.py tests/test_central_ti_permissions.py -q`. O DEM de exemplo `Result_MDS_DEM.tif` foi validado com intervalo 1 m e grade 2 m; limites e cotas são derivados da grade processada, não das estatísticas completas do TIFF original.

## Carregamento e reaproveitamento das referências

O visualizador mantém em memória as duas imagens RGB usadas mais recentemente, compartilhando a mesma camada entre visualização principal e referência das curvas. Desligar/ligar a referência ou voltar ao RGB reaproveita os blocos e tiles enquanto permanecerem no cache da página. Trocar o filtro remove as imagens que deixaram de constar na lista autorizada. Fechar/recarregar a página elimina esse reaproveitamento; não há cache persistente em disco nem publicação dos arquivos.

A leitura parcial usa blocos de 256 KiB e cache de 64 blocos (16 MiB de dados comprimidos por fonte), além do cache de renderização do OpenLayers configurado para 128 tiles por camada. Continua recusando o download integral como resposta a uma leitura parcial. As URLs locais incluem uma versão derivada da referência privada do COG; um novo resultado invalida a imagem anterior, sem expor seu caminho. Erros também permitem uma nova tentativa ao selecionar novamente.

No servidor, somente as leituras GET/HEAD do COG optam por uma Session HTTP reutilizável por thread. Configuração/credenciais ou processo diferentes fecham/substituem a sessão anterior; cookies não são reaproveitados entre chamadas. As autorizações de perfil e prefeitura continuam sendo verificadas antes de cada acesso, e as respostas continuam `private, no-store`. Outros acessos ao Skybox mantêm o transporte anterior. Não requer migração nem reprocessamento dos arquivos existentes.

O seletor mostra carregamento, conclusão das leituras ou falha; metadados carregados sozinhos não anunciam a imagem como pronta. Se os limites da referência não interceptam os limites do DEM, informa que a referência não cobre a área. A disponibilidade do Skybox, a rede e o nível de zoom ainda afetam a primeira abertura.

Validação de desempenho local em 16/10/2026: COG RGBA real Base PCTI de 43.285.787 bytes, enquadramento inicial e atraso simulado de 120 ms por leitura remota. Código anterior: 5 leituras, 655.360 bytes, janela de transferência de 0,692 s. Código ajustado: 3 leituras, 786.432 bytes, 0,417 s. Blocos maiores reduzem viagens de rede, podendo transferir bytes extras. Desligar/ligar a referência carregada não gerou leituras adicionais na versão ajustada. Esses números medem esse cenário local, não o tempo total garantido no site. Uma amostra somente leitura no Skybox real também confirmou menor latência com conexão reutilizada (aproximadamente 120–150 ms após a primeira chamada, contra 220–370 ms com conexões novas).

Testes adicionais: `node --test tests/ortomosaicos_raster.test.cjs` e `python -m pytest tests/test_skybox_read_pool.py tests/test_ortomosaicos.py -q`.

## Estimativa de água para vigilância

No levantamento disponível, **Estimar água** abre um painel para cadastrar piscinas,
caixas d’água e outros reservatórios. A estimativa exige identificação, origem das
medidas (estimadas, campo ou fabricante) e localização dentro dos limites do
levantamento. Funciona tanto com RGB quanto com DEM e referência RGB.

Métodos:

- **Área desenhada × profundidade:** desenhar um contorno simples da área interna.
  O servidor valida o polígono e calcula sua área em uma projeção UTM local, em
  metros quadrados, sem usar a área distorcida do mapa Web Mercator.
- **Retangular:** comprimento e largura internos, em metros.
- **Cilíndrico:** diâmetro interno, em metros.
- **Capacidade conhecida:** capacidade em litros e percentual opcional do volume
  ocupado. Esse percentual não representa a altura em recipientes afunilados.

Os três métodos geométricos usam área × profundidade média × 1.000 para litros.
Exigem a profundidade média até o nível máximo; a profundidade média atual da água
é opcional. Pressupõem paredes verticais e profundidade média sobre toda a área.
Se houver degraus, paredes inclinadas ou fundo parcialmente seco, utilizar
medições/modelagem apropriadas ou capacidade conhecida. O DEM não fornece
automaticamente profundidade, fundo submerso nem capacidade de caixas tampadas.
Não há cálculo de dosagem ou recomendação de produto.

Capacidade total e água presente são resultados separados. Campo atual em branco
significa **não informada**; zero significa vazio. Profundidade atual maior que a
máxima, percentuais fora de 0–100, números não finitos e contornos que se cruzam são
rejeitados. A interface recalcula antes de salvar; o servidor recalcula novamente
e ignora resultados/áreas enviados pelo cliente.

As estimativas ficam no banco por levantamento, com geometria WGS 84, parâmetros,
origem, observações, versão do cálculo, usuário criador e data. A lista permite
consultar, editar, localizar no mapa e excluir com confirmação. Não há histórico
de revisões nesta primeira versão. Troca de levantamento e saída da página
protegem rascunhos não salvos; fechar o painel mantém o rascunho na página.
As rotas usam os mesmos perfis DIRETOR/DEV, verificação de acesso à prefeitura e
proteção CSRF do módulo. Os arquivos originais e o processamento DEM permanecem
independentes dessas estimativas.

Aplicar a migração `b84f20d19a6e` (após `a73e5c9b204f`) com
`flask --app app:create_app db upgrade` no ambiente de implantação. Ela cria apenas
`ortomosaico_estimativas_agua`; não é necessário reenviar ou reprocessar rasters.

Validação: `python -m pytest tests/test_ortomosaicos_agua.py tests/test_ortomosaicos.py tests/test_dem_contours.py -q`.
