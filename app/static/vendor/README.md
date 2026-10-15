# Bibliotecas do visualizador de ortomosaicos

- OpenLayers 10.10.0: `https://cdn.jsdelivr.net/npm/ol@10.10.0/dist/ol.js` e `ol.css`; licença em `openlayers/LICENSE`.
- GeoTIFF.js 3.1.0-beta.0: `https://cdn.jsdelivr.net/npm/geotiff@3.1.0-beta.0/dist-browser/geotiff.js`; versão da dependência declarada por OpenLayers 10.10.0; licença em `geotiff/LICENSE`.

Arquivos distribuídos sem modificações. GeoTIFF.js deve ser carregado primeiro, pois a distribuição completa do OpenLayers utiliza o objeto global `GeoTIFF`.
