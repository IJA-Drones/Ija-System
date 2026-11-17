# Experimento local: CPU, memória e leitura do Skybox

Branch: `otimizacao-sistema`. Nenhum deploy, reinício ou ajuste de configuração no Render.

## Método e limites

Arquivo real de 17.272.684.320 bytes, servido por HTTP Range em localhost,
conversão completa em subprocesso e falha HTTP 400 injetada uma vez na região
entre 8 e 9 GiB. A contagem inclui HEAD/GET e tentativas de recuperação.
Não são requisições feitas ao Skybox. Tempo local não prevê tempo no Render:
latência, processador, disco e cache do sistema operacional são diferentes.
Uma execução por configuração, sem significância estatística.

Cache HTTP mantido em 512 MiB e bloco HTTP de 4 MiB. O cache GDAL de pixels é
uma configuração separada; os limites não representam a memória total do processo.

| Configuração | Tempo | Requisições | Bytes servidos |
|---|---:|---:|---:|
| Referência: 1 thread, cache GDAL 256 MiB | 454 s | 2.701 | 13.883.686.688 |
| Experimento anterior: 2 threads globais, cache GDAL 512 MiB | 244 s | 7.934 | 13.156.304.465 |
| Leitura remota 1 thread, COG local 2 threads, cache GDAL 512 MiB | 337 s | 2.521 | 13.233.569.568 |

O experimento anterior reduziu o tempo local, mas multiplicou as requisições
por 2,94. Transferiu menos bytes, portanto o problema foi a fragmentação dos
pedidos, não um aumento do volume total. Ambas as configurações recuperaram
a falha injetada. Como threads e cache mudaram juntos, os dois fatores precisam
ser distinguidos; não atribuir todo o efeito exclusivamente às threads.

O GDAL_NUM_THREADS também controla decodificação de TIFF quando a leitura cruza
blocos. Referência: https://gdal.org/en/stable/drivers/raster/gtiff.html

## Alteração em teste

A leitura remota permanece com GDAL_NUM_THREADS=1. A opção de duas threads é
aplicada ao COG gerado a partir do estágio já local. Variáveis optativas:

- ORTHOMOSAIC_RASTER_THREADS: padrão 1, limitado entre 1 e 2.
- ORTHOMOSAIC_RASTER_CACHE_MB: padrão 256, limitado entre 128 e 512.

Os padrões de produção permanecem iguais. Não aumentar simultaneamente os
trabalhos concorrentes para preencher CPU: o serviço compartilha recursos com
requisições web e vídeos.

Reproduzir a partir da raiz do repositório, com espaço para estágio e resultado:

```sh
ORTHOMOSAIC_RASTER_THREADS=2 ORTHOMOSAIC_RASTER_CACHE_MB=512 PYTHONPATH=. \
  .venv/bin/python scripts/benchmark_ortomosaico_http.py \
  /caminho/Result_Ortomosaico_RGB.tif /tmp/mapa-experimento.tif
```

O destino deve ser novo. O script imprime contagem e tempo em JSON e não acessa
Skybox. A falha injetada depende de o arquivo alcançar o intervalo especificado.

## Vídeos

- MP4 já é enviado sem recodificação; outros formatos passam por FFmpeg/libx264,
  preset veryfast, CRF 23, com seleção automática de threads.
- Executor de upload tem padrão de dois trabalhos por processo. Aumentar essa
  concorrência pode competir com o processamento geográfico.
- Reprodução encaminha Range e cabeçalhos condicionais, com streaming limitado
  por blocos. Testes verificam uma única chamada para uma resposta 206.
- Quando o provedor ignora Range e devolve 200, o fallback precisa descartar os
  bytes anteriores ao trecho. Mais CPU não elimina esse custo de rede.
- Corrigida uma leitura de bloco extra após terminar o trecho solicitado, nos
  caminhos Skybox e WebDAV. Testes cobrem intervalo alinhado, intervalo parcial,
  sufixo, fechamento por desconexão e encaminhamento de Range/cache.
- O progresso de upload é persistido a cada bloco de 1 MiB, mesmo quando o
  percentual não muda. Candidato a investigação futura, ainda sem alteração.
- FFmpeg não está disponível no PATH deste ambiente. Não foi medido ganho de
  transcodificação, nem alegado ganho de reprodução em produção.

## Resultado final desta rodada

A configuração separada completou em **337 s (5min37s)**: 25,8% menos tempo,
6,7% menos requisições e 4,7% menos bytes que a referência de 454 s.
Contra as duas threads globais, reduziu 68,2% das requisições, com maior tempo
local (337 s contra 244 s). A prioridade é evitar amplificar pedidos remotos.

A falha injetada ocorreu uma vez e a conversão terminou com sucesso.
Metadados, dimensões, transformação, CRS, tipos e níveis de zoom coincidiram;
25 janelas de 128×128 pixels, distribuídas pelo mapa, foram exatamente iguais
à referência, nas quatro bandas. Não é uma comparação pixel a pixel integral.
Layout COG confirmado. Amostras de recursos: cerca de 1,28 GiB de RSS durante
os pixels e 618–722 MiB durante a etapa local; CPU alcançou cerca de dois núcleos.
Essas leituras pontuais não medem o pico nem garantem o mesmo uso no Render.

A redução de requisições ao retornar a decodificação remota para uma thread,
mantendo o cache de 512 MiB, sustenta que o paralelismo global era o principal
responsável pela fragmentação observada. O ganho isolado do cache exige outra
rodada com cache de 256 MiB e a mesma separação de threads.

Validação: 27 testes existentes de conversão remota/RGB16, sessão de vídeo e
pool de leitura; 10 testes novos de streaming de vídeo; 1 teste de isolamento
de threads; 14 testes JavaScript de uploads e recuperação. Todos passaram.

Recomendação: manter esta configuração optativa para validação controlada
posterior no Render. Não ativada em produção. Não houve push nem deploy.

## Publicação autorizada

Após os testes, publicação autorizada em 17/11/2026. Os padrões passam a duas
threads para o estágio local e cache GDAL de 512 MiB, com leitura remota
sequencial. As variáveis permitem retornar a 1 thread e 256 MiB. As descrições
acima de ausência de deploy referem-se à rodada de benchmark anterior.
