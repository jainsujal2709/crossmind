/* CrossMind animated background: shooting-star letters + drifting crossword word-strips.
   Included on every page. Pure canvas, no libraries. Respects "reduce motion". */
(function () {
  if (window.__cmBg) return;
  window.__cmBg = true;

  var canvas = document.createElement('canvas');
  canvas.id = 'bg-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:-1;pointer-events:none;';
  (document.body || document.documentElement).insertBefore(canvas, (document.body || document.documentElement).firstChild);
  var ctx = canvas.getContext('2d');

  var COLORS = ['79,70,229', '124,58,237', '6,182,212'];          // indigo, violet, cyan (same as the site theme)
  var LETTERS = 'CROSSMINDABEFGHJKLPQTUVWXYZ';
  var WORDS = ['CROSSMIND', 'LEARN', 'QUIZ', 'CLUE', 'GRID', 'WORD', 'NLP', 'AI', 'SOLVE', 'SCORE', 'CLASS', 'PUZZLE'];
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var W = 0, H = 0, dpr = 1, stars = [], strips = [];

  function rnd(a, b) { return a + Math.random() * (b - a); }
  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
  function dark() { return document.documentElement.dataset.theme === 'dark'; }

  function resetStar(s, initial) {
    var ang = rnd(28, 58) * Math.PI / 180;                          // heading: down and to the right
    s.dx = Math.cos(ang); s.dy = Math.sin(ang);
    s.speed = rnd(2.2, 5.5);                                        // px per 1/60s frame
    s.len = rnd(90, 190);
    s.size = rnd(16, 30);
    s.ch = LETTERS.charAt(Math.floor(Math.random() * LETTERS.length));
    s.col = pick(COLORS);
    if (Math.random() < 0.7) { s.x = rnd(-0.3 * W, W); s.y = -40; }  // enter from the top edge
    else { s.x = -40; s.y = rnd(0, 0.7 * H); }                       // or from the left edge
    if (initial) { var t = Math.random() * (H / s.dy); s.x += s.dx * t; s.y += s.dy * t; }
    s.delay = initial ? 0 : rnd(0, 140);                             // staggered re-entry
  }

  function makeStrip(initial) {
    var used = strips.map(function (t) { return t.word; });
    var free = WORDS.filter(function (w) { return used.indexOf(w) < 0; });
    var word = pick(free.length ? free : WORDS), size = Math.round(rnd(30, 40));
    var wpx = word.length * (size + 3);
    var dirRight = Math.random() < 0.5;
    return {
      word: word, size: size, w: wpx,
      y: rnd(0.04, 0.96) * H,
      x: initial ? rnd(-wpx, W) : (dirRight ? -wpx - 20 : W + 20),
      v: (dirRight ? 1 : -1) * rnd(0.22, 0.5),
      col: pick(COLORS),
      a: rnd(0.07, 0.15)
    };
  }

  function build() {
    var area = W * H;
    var nStars = Math.max(9, Math.min(30, Math.round(area / 48000)));
    var nStrips = Math.max(3, Math.min(8, Math.round(area / 190000)));
    stars = []; strips = [];
    for (var i = 0; i < nStars; i++) { var s = {}; resetStar(s, true); stars.push(s); }
    for (var j = 0; j < nStrips; j++) strips.push(makeStrip(true));
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build();
    if (reduce) draw(0);
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawStrip(p, isDark) {
    var a = isDark ? p.a * 1.6 : p.a;
    ctx.font = '800 ' + Math.round(p.size * 0.55) + 'px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (var i = 0; i < p.word.length; i++) {
      var x = p.x + i * (p.size + 3);
      roundRect(x, p.y, p.size, p.size, 6);
      ctx.fillStyle = 'rgba(' + p.col + ',' + (a * 0.35) + ')';
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = 'rgba(' + p.col + ',' + (a * 1.8) + ')';
      ctx.stroke();
      ctx.fillStyle = 'rgba(' + p.col + ',' + Math.min(1, a * 3.2) + ')';
      ctx.fillText(p.word.charAt(i), x + p.size / 2, p.y + p.size / 2 + 1);
    }
  }

  function drawStar(s, isDark) {
    var a = isDark ? 0.85 : 0.6;
    var tx = s.x - s.dx * s.len, ty = s.y - s.dy * s.len;
    var g = ctx.createLinearGradient(s.x, s.y, tx, ty);
    g.addColorStop(0, 'rgba(' + s.col + ',' + a + ')');
    g.addColorStop(1, 'rgba(' + s.col + ',0)');
    ctx.strokeStyle = g; ctx.lineWidth = 2.5; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(tx, ty); ctx.stroke();

    ctx.font = '800 ' + Math.round(s.size) + 'px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.shadowColor = 'rgba(' + s.col + ',' + (isDark ? 0.95 : 0.6) + ')';
    ctx.shadowBlur = isDark ? 16 : 10;
    ctx.fillStyle = 'rgba(' + s.col + ',' + Math.min(1, a + 0.25) + ')';
    ctx.fillText(s.ch, s.x, s.y);
    ctx.shadowBlur = 0;
  }

  var last = 0;
  function draw(ts) {
    var k = last ? Math.min((ts - last) / 16.667, 3) : 1;          // frame-rate independent movement
    last = ts;
    var isDark = dark();
    ctx.clearRect(0, 0, W, H);

    for (var i = 0; i < strips.length; i++) {
      var p = strips[i];
      if (!reduce) p.x += p.v * k;
      if ((p.v > 0 && p.x > W + 20) || (p.v < 0 && p.x + p.w < -20)) strips[i] = p = makeStrip(false);
      drawStrip(p, isDark);
    }
    if (!reduce) {
      for (var j = 0; j < stars.length; j++) {
        var s = stars[j];
        if (s.delay > 0) { s.delay -= k; continue; }
        s.x += s.dx * s.speed * k; s.y += s.dy * s.speed * k;
        if (s.x - s.dx * s.len > W + 40 || s.y - s.dy * s.len > H + 40) { resetStar(s, false); continue; }
        drawStar(s, isDark);
      }
      requestAnimationFrame(draw);
    }
  }

  var timer;
  window.addEventListener('resize', function () { clearTimeout(timer); timer = setTimeout(resize, 150); });
  resize();
  if (!reduce) requestAnimationFrame(draw);
})();
