// Схемы: один резистор, последовательное и параллельное соединение.
(function () {
  function bg(g, v) {
    g.fillStyle = v.colors.bg;
    g.fillRect(0, 0, v.w, v.h);
  }
  function font(g, px, col) {
    g.fillStyle = col;
    g.font = "600 " + px + "px Golos Text, sans-serif";
    g.textAlign = "center";
    g.textBaseline = "middle";
  }
  function gap(g, x, y, hw, hh, col) {
    g.fillStyle = col;
    g.fillRect(x - hw, y - hh, hw * 2, hh * 2);
  }
  function gauge(g, x, y, r, letter, value, max, col) {
    g.beginPath();
    g.fillStyle = col.card;
    g.strokeStyle = col.text;
    g.lineWidth = 2;
    g.arc(x, y, r, 0, Math.PI * 2);
    g.fill();
    g.stroke();
    var frac = Math.max(0, Math.min(1, (value || 0) / (max || 1)));
    var ang = -Math.PI + frac * Math.PI;
    g.beginPath();
    g.strokeStyle = col.line;
    g.lineWidth = 2;
    g.arc(x, y, r - 3, -Math.PI, 0);
    g.stroke();
    g.beginPath();
    g.strokeStyle = col.ultra;
    g.moveTo(x, y);
    g.lineTo(x + Math.cos(ang) * (r - 8), y + Math.sin(ang) * (r - 8));
    g.stroke();
    g.beginPath();
    g.fillStyle = col.ultra;
    g.arc(x, y, 2.5, 0, 6.3);
    g.fill();
    font(g, Math.max(11, r * 0.5), col.text);
    g.fillText(letter, x, y + r * 0.62);
  }
  function resistor(g, x, y, vertical, col) {
    g.fillStyle = col.card;
    g.strokeStyle = col.ultra;
    g.lineWidth = 3;
    if (vertical) g.strokeRect(x - 10, y - 28, 20, 56);
    else g.strokeRect(x - 28, y - 10, 56, 20);
    g.fillStyle = col.ultra;
    if (vertical) g.fillRect(x - 8, y - 26, 16, 52);
    else g.fillRect(x - 26, y - 8, 52, 16);
  }
  function battery(g, x, y, col) {
    g.strokeStyle = col.text;
    g.lineWidth = 3;
    g.beginPath();
    g.moveTo(x - 14, y - 16); g.lineTo(x - 14, y + 16);
    g.moveTo(x + 6, y - 8); g.lineTo(x + 6, y + 8);
    g.stroke();
    font(g, 12, col.text);
    g.textAlign = "left";
    g.fillText("+", x - 28, y - 22);
  }
  function swDraw(g, x, y, on, col) {
    g.fillStyle = col.bg;
    g.fillRect(x - 22, y - 20, 44, 32);
    g.strokeStyle = col.text;
    g.lineWidth = 3;
    g.beginPath();
    g.moveTo(x - 16, y);
    if (on) g.lineTo(x + 16, y);
    else g.lineTo(x + 12, y - 14);
    g.stroke();
    g.fillStyle = on ? col.good : col.weak;
    g.beginPath();
    g.arc(x - 16, y, 4, 0, 6.3);
    g.arc(x + 16, y, 4, 0, 6.3);
    g.fill();
  }
  function dots(g, pts, speed, time, col) {
    if (speed < 8) return;
    var seg = [], total = 0, i, dx, dy, len;
    for (i = 0; i < pts.length - 1; i++) {
      dx = pts[i + 1][0] - pts[i][0];
      dy = pts[i + 1][1] - pts[i][1];
      len = Math.hypot(dx, dy);
      seg.push([pts[i][0], pts[i][1], dx, dy, len, total]);
      total += len;
    }
    g.fillStyle = col;
    for (var k = 0; k < 5; k++) {
      var d = (time * speed + k * total / 5) % total, s;
      for (i = 0; i < seg.length; i++) {
        s = seg[i];
        if (d <= s[5] + s[4] || i === seg.length - 1) {
          var t = s[4] ? (d - s[5]) / s[4] : 0;
          g.beginPath();
          g.arc(s[0] + s[2] * t, s[1] + s[3] * t, 4, 0, 6.3);
          g.fill();
          break;
        }
      }
    }
  }
  function stroke(g, pts, col) {
    g.beginPath();
    g.strokeStyle = col;
    g.lineWidth = 3;
    g.lineJoin = "round";
    g.moveTo(pts[0][0], pts[0][1]);
    for (var i = 1; i < pts.length; i++) g.lineTo(pts[i][0], pts[i][1]);
    g.stroke();
  }

  LabEngine.scene("circuit", function (g, v) {
    bg(g, v);
    var c = v.colors;
    var usable = Math.min(v.w - 24, Math.max(260, v.h * 2.05));
    g.save();
    g.translate((v.w - usable) / 2, 0);
    var L = 56, R = usable - 36, T = 46, B = v.h - 36;
    var midY = (T + B) / 2;
    var on = (v.controls.sw || 0) >= 0.5;
    var speed = Math.abs(v.out.I || 0) * 90;
    if (v.cfg.layout === "series") {
      var x1 = L + (R - L) * 0.42, x2 = L + (R - L) * 0.72;
      stroke(g, [[L, midY], [L, T], [R, T], [R, B], [L, B], [L, midY]], c.text);
      battery(g, L, midY, c);
      swDraw(g, L + 70, T, on, c);
      gap(g, (L + R) / 2, T, 26, 26, c.bg);
      gauge(g, (L + R) / 2, T, 22, "A", v.shown.I, 3, c);
      gap(g, x1, B, 32, 16, c.bg);
      resistor(g, x1, B, false, c);
      gap(g, x2, B, 32, 16, c.bg);
      resistor(g, x2, B, false, c);
      gauge(g, x1, B - 48, 20, "V", v.shown.U1, 12, c);
      gauge(g, x2, B - 48, 20, "V", v.shown.U2, 12, c);
      font(g, 12, c.muted);
      g.textAlign = "center";
      g.fillText("R1", x1, B + 18);
      g.fillText("R2", x2, B + 18);
      if (on) dots(g, [[L, midY], [L, T], [R, T], [R, B], [L, B], [L, midY]], speed, v.time, c.lime);
      g.restore();
      return;
    }
    if (v.cfg.layout === "parallel") {
      var xj = L + (R - L) * 0.46;
      stroke(g, [[L, midY], [L, T], [xj, T], [R, T], [R, B], [xj, B], [xj, T]], c.text);
      stroke(g, [[L, midY], [L, B], [xj, B]], c.text);
      battery(g, L, midY, c);
      swDraw(g, L + 64, T, on, c);
      gap(g, (L + xj) / 2, T, 24, 24, c.bg);
      gauge(g, (L + xj) / 2, T, 20, "A", v.shown.I, 6, c);
      var y1 = T + (B - T) * 0.32, y2 = T + (B - T) * 0.68;
      stroke(g, [[xj, T], [xj, B]], c.text);
      stroke(g, [[xj, y1], [R, y1]], c.text);
      stroke(g, [[xj, y2], [R, y2]], c.text);
      gap(g, (xj + R) / 2, y1, 30, 14, c.bg);
      resistor(g, (xj + R) / 2, y1, false, c);
      gap(g, (xj + R) / 2, y2, 30, 14, c.bg);
      resistor(g, (xj + R) / 2, y2, false, c);
      font(g, 12, c.muted);
      g.textAlign = "left";
      g.fillText("I1 " + (v.shown.I1 || 0).toFixed(2).replace(".", ",") + " А", xj + 8, y1 - 22);
      g.fillText("I2 " + (v.shown.I2 || 0).toFixed(2).replace(".", ",") + " А", xj + 8, y2 + 22);
      if (on) dots(g, [[L, midY], [L, T], [R, T], [R, B], [L, B], [L, midY]], speed, v.time, c.lime);
      g.restore();
      return;
    }
    stroke(g, [[L, midY], [L, T], [R, T], [R, B], [L, B], [L, midY]], c.text);
    battery(g, L, midY, c);
    swDraw(g, L + (R - L) * 0.28, T, on, c);
    gap(g, L + (R - L) * 0.58, T, 26, 26, c.bg);
    gauge(g, L + (R - L) * 0.58, T, 24, "A", v.shown.I, 3, c);
    gap(g, R, midY, 16, 34, c.bg);
    resistor(g, R, midY, true, c);
    gauge(g, R - 78, B, 22, "V", v.shown.V, 12, c);
    if (on) dots(g, [[L, midY], [L, T], [R, T], [R, B], [L, B], [L, midY]], speed, v.time, c.lime);
    g.restore();
  });
})();
