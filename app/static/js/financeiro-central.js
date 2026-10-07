(() => {
  "use strict";
  const search = document.getElementById("finance-company-search");
  const filter = document.getElementById("finance-company-filter");
  const empty = document.getElementById("finance-company-empty");
  if (!search || !filter || !empty) return;
  const cards = [...document.querySelectorAll("[data-company-search]")];
  const normalize = value => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[./-]/g, "");

  function updateCompanies() {
    const query = normalize(search.value.trim());
    let visible = 0;
    for (const card of cards) {
      const matchesSearch = normalize(card.dataset.companySearch).includes(query);
      const matchesFilter = filter.value !== "disponiveis" || card.dataset.companyAvailable === "true";
      card.hidden = !(matchesSearch && matchesFilter);
      if (!card.hidden) visible += 1;
    }
    empty.hidden = visible > 0;
  }
  search.addEventListener("input", updateCompanies);
  filter.addEventListener("change", updateCompanies);
})();
