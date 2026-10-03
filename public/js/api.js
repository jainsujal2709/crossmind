const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

function toast(m) {
  let t = $('#toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = m;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3500);
}

const rawBase = (window.CROSSMIND_API_URL || '__BACKEND_URL__').replace(/\/$/, '');
const API_BASE = (rawBase === '__BACKEND_URL__' || !rawBase) ? '' : rawBase;

const API = {
  async f(p, o = {}) {
    const h = {};
    if (localStorage.ct) {
      h['Authorization'] = 'Bearer ' + localStorage.ct;
    }
    let b = o.body;
    if (o.json) {
      h['Content-Type'] = 'application/json';
      b = JSON.stringify(o.json);
    }
    const r = await fetch(API_BASE + '/api' + p, {
      method: o.method || 'GET',
      headers: h,
      body: b
    });
    const d = await r.json().catch(() => ({}));
    if (r.status === 401 && !p.startsWith('/auth')) {
      localStorage.clear();
      location = '/index.html';
    }
    if (!r.ok) {
      if (typeof d.detail === 'string') throw new Error(d.detail);
      if (r.status >= 500) throw new Error('Server error (' + r.status + '). The backend may be misconfigured - open /api/health to check.');
      throw new Error('Please check your input.');
    }
    return d;
  }
};

function theme() {
  const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = t;
  localStorage.th = t;
}
document.documentElement.dataset.theme = localStorage.th || 'light';

function renderAppNav(isAdmin = false) {
  const role = localStorage.role || 'student';
  const name = localStorage.name || 'User';

  let navItems = '';
  if (isAdmin || role === 'admin') {
    navItems = `<a href="/admin.html">Platform Statistics</a><a href="/app.html#dashboard">App View</a>`;
  } else if (role === 'teacher') {
    navItems = `
      <a href="#dashboard">Teacher Dashboard</a>
      <a href="#classrooms">My Classrooms</a>
      <a href="#create-quiz">Create Quiz</a>
      <a href="#create-crossword">Generate Crossword</a>
    `;
  } else {
    // Student
    navItems = `
      <a href="#dashboard">Student Dashboard</a>
      <a href="#join-classroom">Join Classroom</a>
      <a href="#performance">My Performance</a>
      <a href="#create-crossword">Generate Crossword</a>
      <a href="#history">History</a>
    `;
  }

  const existingNav = $('nav');
  if (existingNav) existingNav.remove();

  const navHtml = `
    <nav class="glass-nav">
      <a class="brand" href="/app.html#dashboard">CROSSMIND</a>
      <div class="nav-links">
        ${navItems}
        <span class="tag ${role === 'teacher' ? 'completed' : 'active'}" style="margin-left: 10px;">${role.toUpperCase()}: ${name}</span>
        <button class="btn alt" onclick="theme()" aria-label="Toggle theme">◐ Theme</button>
        <button class="btn alt" onclick="localStorage.clear();location='/index.html'">Logout</button>
      </div>
    </nav>
    <div id="toast" role="status"></div>
  `;
  document.body.insertAdjacentHTML('afterbegin', navHtml);

  if (!localStorage.ct) {
    location = '/index.html';
  }
}
