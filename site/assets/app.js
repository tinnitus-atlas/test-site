// Table filter on index pages and site-wide search on the home page. No dependencies.
(function () {
  var filter = document.querySelector("[data-filter-table]");
  if (filter) {
    var rows = Array.prototype.slice.call(document.querySelectorAll(filter.getAttribute("data-filter-table") + " tbody tr"));
    filter.addEventListener("input", function () {
      var q = filter.value.trim().toLowerCase();
      rows.forEach(function (r) { r.hidden = q && r.textContent.toLowerCase().indexOf(q) === -1; });
    });
  }
  var search = document.getElementById("site-search");
  if (search) {
    var out = document.getElementById("search-results"), index = null;
    function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
    function run() {
      var q = search.value.trim().toLowerCase();
      if (!q || !index) { out.innerHTML = ""; return; }
      var hits = index.filter(function (r) { return (r.name + " " + r.tldr + " " + r.kind).toLowerCase().indexOf(q) !== -1; }).slice(0, 20);
      out.innerHTML = hits.length ? hits.map(function (r) {
        return '<li><a href="' + esc(r.url) + '">' + esc(r.name) + '</a> <span class="meta">' + esc(r.kind_label) + '</span><br><span class="meta">' + esc(r.tldr) + "</span></li>";
      }).join("") : '<li class="meta">No matches.</li>';
    }
    fetch(search.getAttribute("data-index")).then(function (r) { return r.json(); }).then(function (j) { index = j.records; run(); });
    search.addEventListener("input", run);
  }
})();
