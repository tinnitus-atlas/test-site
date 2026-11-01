// Small force-directed graph explorer. Reads /api/v1/graph.json. No dependencies.
(function () {
  var svg = document.getElementById("graph");
  if (!svg) return;
  var NS = "http://www.w3.org/2000/svg";
  var colours = ["--k1", "--k2", "--k3", "--k4", "--k5", "--k6", "--k7", "--k8"];
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888"; }
  fetch(svg.getAttribute("data-src")).then(function (r) { return r.json(); }).then(draw);

  function draw(data) {
    var W = svg.clientWidth || 800, H = svg.clientHeight || 500;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var kinds = [], byId = {};
    data.nodes.forEach(function (n, i) {
      if (kinds.indexOf(n.kind_label) === -1) kinds.push(n.kind_label);
      var a = (i / data.nodes.length) * Math.PI * 2;
      n.x = W / 2 + Math.cos(a) * W / 4; n.y = H / 2 + Math.sin(a) * H / 4; n.vx = 0; n.vy = 0;
      n.colour = cssVar(colours[kinds.indexOf(n.kind_label) % colours.length]);
      byId[n.id] = n;
    });
    var links = data.edges.filter(function (e) { return byId[e.source] && byId[e.target]; })
      .map(function (e) { return { s: byId[e.source], t: byId[e.target], label: e.label }; });
    var legend = document.getElementById("graph-legend");
    if (legend) kinds.forEach(function (k, i) {
      var span = document.createElement("span"), dot = document.createElement("i");
      dot.style.background = cssVar(colours[i % colours.length]);  // set through script so the security policy allows it
      span.appendChild(dot); span.appendChild(document.createTextNode(k));
      legend.appendChild(span);
    });

    var gLinks = document.createElementNS(NS, "g"), gNodes = document.createElementNS(NS, "g");
    svg.appendChild(gLinks); svg.appendChild(gNodes);
    links.forEach(function (l) {
      l.el = document.createElementNS(NS, "line");
      var t = document.createElementNS(NS, "title"); t.textContent = l.s.name + " " + l.label + " " + l.t.name;
      l.el.appendChild(t); gLinks.appendChild(l.el);
    });
    var dragging = null;
    data.nodes.forEach(function (n) {
      var g = document.createElementNS(NS, "g"), c = document.createElementNS(NS, "circle"), tx = document.createElementNS(NS, "text"), ti = document.createElementNS(NS, "title");
      c.setAttribute("r", 7 + Math.min(n.degree, 8)); c.setAttribute("fill", n.colour);
      ti.textContent = n.name + " (" + n.kind_label + ")"; c.appendChild(ti);
      tx.textContent = n.name.length > 28 ? n.name.slice(0, 27) + "…" : n.name; tx.setAttribute("dx", 12); tx.setAttribute("dy", 4);
      g.appendChild(c); g.appendChild(tx); gNodes.appendChild(g); n.el = g;
      var moved = false;
      c.addEventListener("pointerdown", function (ev) { dragging = n; moved = false; c.setPointerCapture(ev.pointerId); });
      c.addEventListener("pointermove", function (ev) {
        if (dragging !== n) return; moved = true;
        var p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY;
        var q = p.matrixTransform(svg.getScreenCTM().inverse()); n.x = q.x; n.y = q.y; n.vx = n.vy = 0; alpha = Math.max(alpha, 0.3);
      });
      c.addEventListener("pointerup", function () { dragging = null; if (!moved) window.location.href = n.url; });
    });

    var alpha = 1;
    function tick() {
      var nodes = data.nodes, i, j;
      for (i = 0; i < nodes.length; i++) for (j = i + 1; j < nodes.length; j++) {
        var a = nodes[i], b = nodes[j], dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy + 0.01, f = 2200 / d2, d = Math.sqrt(d2);
        a.vx -= f * dx / d; a.vy -= f * dy / d; b.vx += f * dx / d; b.vy += f * dy / d;
      }
      links.forEach(function (l) {
        var dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 110) * 0.02;
        l.s.vx += f * dx / d; l.s.vy += f * dy / d; l.t.vx -= f * dx / d; l.t.vy -= f * dy / d;
      });
      nodes.forEach(function (n) {
        n.vx += (W / 2 - n.x) * 0.004; n.vy += (H / 2 - n.y) * 0.004;
        if (n !== dragging) { n.x += n.vx * alpha; n.y += n.vy * alpha; }
        n.vx *= 0.6; n.vy *= 0.6;
        n.x = Math.max(16, Math.min(W - 120, n.x)); n.y = Math.max(16, Math.min(H - 16, n.y));
        n.el.setAttribute("transform", "translate(" + n.x + "," + n.y + ")");
      });
      links.forEach(function (l) {
        l.el.setAttribute("x1", l.s.x); l.el.setAttribute("y1", l.s.y); l.el.setAttribute("x2", l.t.x); l.el.setAttribute("y2", l.t.y);
      });
      alpha *= 0.985;
      if (alpha > 0.02 || dragging) requestAnimationFrame(tick); else setTimeout(function () { if (alpha > 0.02) requestAnimationFrame(tick); }, 200);
    }
    svg.addEventListener("pointermove", function () { if (dragging && alpha <= 0.02) { alpha = 0.3; requestAnimationFrame(tick); } });
    requestAnimationFrame(tick);
  }
})();
