const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

function toast(m) {
  let t = $('#toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast';
    t.setAttribute('role', 'status');
    document.body.appendChild(t);
  }
  t.textContent = m;
  t.style.display = 'block';
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.style.display = 'none', 4000);
}

const rawBase = (window.CROSSMIND_API_URL || '__BACKEND_URL__').replace(/\/$/, '');
const API_BASE = (rawBase === '__BACKEND_URL__' || !rawBase) ? '' : rawBase;

// The sign-in itself lives in an HttpOnly cookie that scripts cannot read.
// Only the display name, role and the expiry time are kept here, so the page can show the right menu and sign out on time.
const Session = {
  set(d) { localStorage.name = d.name; localStorage.role = d.role; localStorage.exp = d.expires_at; },
  valid() { return !!localStorage.exp && Date.now() < +localStorage.exp; },
  clear() { ['name', 'role', 'exp'].forEach(k => localStorage.removeItem(k)); }
};
async function logout(message) {
  try { await fetch(API_BASE + '/api/auth/logout', { method: 'POST', headers: { 'X-Requested-With': 'CrossMind' } }); } catch (e) {}
  Session.clear();
  if (message) sessionStorage.cm_msg = message;
  location = '/index.html';
}

// Upload limit comes from the server (it differs between hosts).
window.UPLOAD_MAX_MB = 4;
const configReady = fetch(API_BASE + '/api/config').then(r => r.json()).then(c => { window.UPLOAD_MAX_MB = c.max_upload_mb || 4; }).catch(() => {});

// Returns an error message if the selected files together are over the upload limit.
function tooBig(files) {
  const total = [...files].reduce((n, f) => n + f.size, 0);
  const limit = window.UPLOAD_MAX_MB * 1024 * 1024;
  return total > limit ? 'Your files total ' + (total / 1048576).toFixed(1) + ' MB. The limit is ' + window.UPLOAD_MAX_MB + ' MB per upload. Please remove some files or split them into smaller uploads.' : '';
}

const API = {
  async f(p, o = {}) {
    const h = { 'X-Requested-With': 'CrossMind' };
    let b = o.body;
    if (o.json) {
      h['Content-Type'] = 'application/json';
      b = JSON.stringify(o.json);
    }
    window.UI && UI.busy(1);
    let r;
    try {
      r = await fetch(API_BASE + '/api' + p, { method: o.method || 'GET', headers: h, body: b, credentials: 'same-origin' });
    } catch (e) {
      throw new Error('Could not reach the server. Check your connection and try again.');
    } finally {
      window.UI && UI.busy(-1);
    }
    const d = await r.json().catch(() => ({}));
    if (r.status === 401 && !p.startsWith('/auth')) {
      Session.clear();
      sessionStorage.cm_msg = 'Your session has ended. Please sign in again.';
      location = '/index.html';
    }
    if (!r.ok) {
      if (r.status === 413) throw new Error(typeof d.detail === 'string' ? d.detail : 'The upload is too large. The limit is ' + window.UPLOAD_MAX_MB + ' MB.');
      if (r.status === 429) throw new Error(typeof d.detail === 'string' ? d.detail : 'Too many requests. Please wait a moment.');
      if (r.status === 504 || r.status === 408) throw new Error('The server took too long. Try a smaller file or fewer pages.');
      if (typeof d.detail === 'string') throw new Error(d.detail);
      if (Array.isArray(d.detail)) throw new Error(d.detail.map(x => (x.msg || '').replace(/^Value error, /, '')).filter(Boolean).join(' ') || 'Please check your input.');
      if (r.status >= 500) throw new Error('Server error (' + r.status + '). Please try again in a moment.');
      throw new Error('Please check your input.');
    }
    return d;
  }
};

function theme() {
  const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = t;
  localStorage.th = t;
  $$('[data-theme-btn]').forEach(b => b.setAttribute('aria-pressed', t === 'dark'));
}
document.documentElement.dataset.theme = localStorage.th || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

function toggleMenu(force) {
  const nav = $('nav.glass-nav'); if (!nav) return;
  const open = force === undefined ? !nav.classList.contains('open') : force;
  nav.classList.toggle('open', open);
  const b = $('.menu-btn'); if (b) b.setAttribute('aria-expanded', open);
}

function renderAppNav(isAdmin = false) {
  const role = localStorage.role || 'student';
  const name = localStorage.name || 'User';
  if (!Session.valid()) {
    if (localStorage.exp) sessionStorage.cm_msg = 'Your session has ended. Please sign in again.';
    Session.clear(); location = '/index.html'; return;
  }

  let navItems = '';
  if (isAdmin || role === 'admin') {
    navItems = `<a href="/admin.html">Platform Statistics</a><a href="/app.html#dashboard">App View</a>`;
  } else if (role === 'teacher') {
    navItems = `
      <a href="#dashboard">Teacher Dashboard</a>
      <a href="#classrooms">My Classrooms</a>
      <a href="#create-quiz">Create Quiz</a>
      <a href="#create-crossword">Generate Crossword</a>
      <a href="#history">History</a>
    `;
  } else {
    navItems = `
      <a href="#dashboard">Student Dashboard</a>
      <a href="#join-classroom">Join Classroom</a>
      <a href="#performance">My Performance</a>
    `;
  }

  const existingNav = $('nav');
  if (existingNav) existingNav.remove();
  const safeName = String(name).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const navHtml = `
    <nav class="glass-nav">
      <a class="brand" href="/app.html#dashboard"><img src="/logo.svg" width="28" height="28" alt=""><span>CrossMind</span></a>
      <button class="menu-btn" aria-label="Menu" aria-expanded="false" aria-controls="navlinks" onclick="toggleMenu()"><i></i><i></i><i></i></button>
      <div class="nav-links" id="navlinks" onclick="if (event.target.closest('a')) toggleMenu(false)">
        ${navItems}
        <span class="tag ${role === 'teacher' ? 'completed' : 'active'}">${role.toUpperCase()}: ${safeName}</span>
        <button class="btn alt" data-theme-btn onclick="theme()" aria-label="Toggle dark mode" aria-pressed="${document.documentElement.dataset.theme === 'dark'}">Theme</button>
        <button class="btn alt" onclick="logout()">Logout</button>
      </div>
    </nav>
    <div id="toast" role="status"></div>
  `;
  document.body.insertAdjacentHTML('afterbegin', navHtml);
}
