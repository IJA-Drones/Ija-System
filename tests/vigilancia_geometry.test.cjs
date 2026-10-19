const assert = require('node:assert/strict');
const test = require('node:test');
const {polygonFromPoints, pointsFromPolygon} = require('../app/static/js/vigilancia-planejamento-mapa.js');
const square = [{lng:-36.7,lat:-8.35},{lng:-36.699,lat:-8.35},{lng:-36.699,lat:-8.349},{lng:-36.7,lat:-8.349}];
test('GeoJSON usa longitude/latitude e fecha o contorno, sem alterar os pontos', () => {
  const geometry = polygonFromPoints(square);
  assert.deepEqual(geometry.coordinates[0][0], [-36.7,-8.35]);
  assert.deepEqual(geometry.coordinates[0][4], geometry.coordinates[0][0]);
  assert.deepEqual(pointsFromPolygon(geometry), square);
  assert.equal(square.length, 4);
});
test('recusa área incompleta, cruzada, repetida ou com coordenada inválida', () => {
  for (const points of [[],square.slice(0,2),[square[0],square[2],square[1],square[3]],
    [square[0],square[1],square[0]],square.map(p=>({...p,lat:NaN})),square.map(p=>({...p,lng:181})),
    [{lng:1,lat:1},{lng:2,lat:2},{lng:3,lat:3}]]) assert.throws(()=>polygonFromPoints(points));
});
