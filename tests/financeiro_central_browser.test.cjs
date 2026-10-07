const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../app/static/js/financeiro-central.js"), "utf8");

function browser() {
  const search = { value: "", addEventListener: (_, fn) => { search.update = fn; } };
  const filter = { value: "todas", addEventListener: (_, fn) => { filter.update = fn; } };
  const empty = { hidden: true };
  const cards = [
    { dataset: { companySearch: "IJA Gestão 11111111000111 11.111.111/0001-11", companyAvailable: "true" }, hidden: false },
    { dataset: { companySearch: "Oceano Azul 22222222000122 22.222.222/0001-22 OA", companyAvailable: "false" }, hidden: false },
  ];
  vm.runInNewContext(source, { document: {
    getElementById: id => ({ "finance-company-search": search, "finance-company-filter": filter, "finance-company-empty": empty })[id],
    querySelectorAll: () => cards,
  } });
  return { search, filter, empty, cards };
}

test("company search accepts accents and formatted or plain CNPJ", () => {
  const page = browser();
  for (const query of ["gestao", "11111111000111", "11.111.111/0001-11"]) {
    page.search.value = query;
    page.search.update();
    assert.equal(page.cards[0].hidden, false);
    assert.equal(page.cards[1].hidden, true);
    assert.equal(page.empty.hidden, true);
  }
});

test("availability filter hides companies without access and respects the search", () => {
  const page = browser();
  page.filter.value = "disponiveis";
  page.filter.update();
  assert.equal(page.cards[0].hidden, false);
  assert.equal(page.cards[1].hidden, true);
  page.search.value = "oceano";
  page.search.update();
  assert.ok(page.cards.every(card => card.hidden));
  assert.equal(page.empty.hidden, false);
});

test("clearing the search restores companies after an empty result", () => {
  const page = browser();
  page.search.value = "inexistente";
  page.search.update();
  assert.equal(page.empty.hidden, false);
  page.search.value = "";
  page.search.update();
  assert.ok(page.cards.every(card => !card.hidden));
  assert.equal(page.empty.hidden, true);
});
