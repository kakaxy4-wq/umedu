// Пружина на штативе: удлинение растёт вместе с грузом.
(function () {
  LabEngine.scene("spring", function (g, v) {
    var c = v.colors, w = v.w, h = v.h;
    g.fillStyle = c.bg;
    g.fillRect(0, 0, w, h);
    var top = 28, x = Math.max(90, w * 0.38);
    var maxX = (v.cfg.meters[0] && v.cfg.meters[0].max) || 20;
    var stretch = Math.max(0, Math.min(1, (v.out.x || 0) / maxX));
    var len = 36 + stretch * Math.max(70, h - 140);
    g.strokeStyle = c.text;
    g.lineWidth = 4;
    g.beginPath();
    g.moveTo(x - 70, top);
    g.lineTo(x + 36, top);
    g.moveTo(x - 70, top);
    g.lineTo(x - 70, h - 16);
    g.stroke();
    g.strokeStyle = c.ultra;
    g.lineWidth = 2;
    g.beginPath();
    var coils = 14, i;
    g.moveTo(x, top);
    for (i = 0; i <= coils; i++) {
      var yy = top + (len * i) / coils;
      var xx = x + (i % 2 ? 16 : -16);
      if (i === 0 || i === coils) xx = x;
      g.lineTo(xx, yy);
    }
    g.stroke();
    var my = top + len;
    g.fillStyle = c.ultra;
    g.fillRect(x - 22, my, 44, 32);
    g.fillStyle = c.lime;
    g.fillRect(x - 22, my, 44, 6);
    g.fillStyle = c.ink;
    g.font = "600 13px Golos Text, sans-serif";
    g.textAlign = "center";
    g.fillText(Math.round(v.controls.m) + " г", x, my + 20);
    var rx = Math.min(w - 72, x + 78);
    g.strokeStyle = c.muted;
    g.lineWidth = 2;
    g.beginPath();
    g.moveTo(rx, top);
    g.lineTo(rx, h - 20);
    g.stroke();
    g.fillStyle = c.muted;
    g.textAlign = "left";
    g.font = "12px Golos Text, sans-serif";
    for (i = 0; i <= 4; i++) {
      var tick = top + ((h - 40) * i) / 4;
      g.beginPath();
      g.moveTo(rx - 6, tick);
      g.lineTo(rx + 6, tick);
      g.stroke();
      g.fillText(i * 5 + " см", rx + 8, tick + 4);
    }
    g.fillStyle = c.weak;
    g.beginPath();
    g.arc(rx, my + 16, 5, 0, 6.3);
    g.fill();
  });
})();
