// Shared interface features: consent prompt, session expiry, confirmation dialogs, copy, loading indicator,
// scroll progress, password toggles, footer, floating contact button and UTM capture.
const UI = (() => {
  const S = window.SITE || { owner: {} };
  const O = S.owner || {};
  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const el = (tag, attrs = {}, html = '') => { const e = document.createElement(tag); Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v)); e.innerHTML = html; return e; };
  const isHttp = u => /^https?:\/\//i.test(u || '');

  // ---------- loading indicator (appears only if a request takes longer than 0.3 s) ----------
  let pending = 0, spinTimer, spinner;
  function busy(d) {
    pending = Math.max(0, pending + d);
    spinner = spinner || document.body.appendChild(el('div', { class: 'spinner', role: 'status', 'aria-label': 'Loading', hidden: '' }));
    clearTimeout(spinTimer);
    if (pending > 0) spinTimer = setTimeout(() => { spinner.hidden = false; }, 300);
    else spinner.hidden = true;
  }

  // ---------- copy to clipboard ----------
  async function copy(text, what) {
    try { await navigator.clipboard.writeText(text); }
    catch (e) {
      const t = el('textarea', { style: 'position:fixed;opacity:0' }); t.value = text; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); } catch (_) {} t.remove();
    }
    toast((what || 'Text') + ' copied.');
  }

  // ---------- modal helper (focus trap, Esc to close) ----------
  function modal(inner, { label, onClose, dismissible = true } = {}) {
    const back = el('div', { class: 'modal-back' });
    const box = el('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': label || 'Dialog', tabindex: '-1' }, inner);
    back.appendChild(box); document.body.appendChild(back);
    const prev = document.activeElement;
    const close = v => { back.remove(); document.removeEventListener('keydown', key, true); prev && prev.focus && prev.focus(); onClose && onClose(v); };
    function key(e) {
      if (e.key === 'Escape' && dismissible) { e.stopPropagation(); close(false); }
      if (e.key === 'Tab') {
        const f = [...box.querySelectorAll('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])')].filter(x => x.offsetParent !== null);
        if (!f.length) return;
        if (!box.contains(document.activeElement)) { e.preventDefault(); f[0].focus(); }
        else if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    }
    document.addEventListener('keydown', key, true);
    if (dismissible) back.addEventListener('mousedown', e => { if (e.target === back) close(false); });
    return { box, close };
  }

  // ---------- confirmation dialog (replaces the browser's confirm box) ----------
  function confirmDialog(message, { okText = 'Confirm', cancelText = 'Cancel', danger = false } = {}) {
    return new Promise(resolve => {
      const m = modal(`<p class="modal-text">${esc(message)}</p><div class="modal-actions"><button class="btn alt" data-x="0">${esc(cancelText)}</button><button class="btn ${danger ? 'bad' : 'primary'}" data-x="1">${esc(okText)}</button></div>`,
        { label: 'Confirmation', onClose: v => resolve(!!v) });
      m.box.querySelectorAll('[data-x]').forEach(b => b.onclick = () => m.close(b.dataset.x === '1'));
      m.box.querySelector('[data-x="0"]').focus();
    });
  }

  // ---------- consent prompt (privacy policy, terms, cookies) ----------
  const needsConsent = () => { try { const c = JSON.parse(localStorage.cm_consent || 'null'); return !c || c.v !== S.policyVersion; } catch (e) { return true; } };
  function consentGate() {
    if (document.body.hasAttribute('data-no-consent') || !needsConsent()) return;
    const body = `<h2>Before you continue</h2>
      <p>CrossMind stores a sign-in cookie, your theme and this choice in your browser, and your browser keeps copies of our style and script files so pages load faster. We do not use advertising or tracking cookies.</p>
      <p>To use CrossMind, please read and accept the <a href="/privacy.html" target="_blank" rel="noopener">Privacy Policy</a> and the <a href="/terms.html" target="_blank" rel="noopener">Terms and Conditions</a>.</p>
      <div class="modal-actions"><button class="btn alt" data-x="no">Decline</button><button class="btn primary" data-x="yes">Allow and continue</button></div>`;
    const m = modal(body, { label: 'Privacy policy, terms and cookies', dismissible: false });
    const kids = [...document.body.children].filter(e => !e.classList.contains('modal-back'));
    kids.forEach(e => { e.inert = true; });
    document.documentElement.classList.add('locked');
    m.box.querySelector('[data-x="yes"]').focus();
    m.box.onclick = e => {
      const x = e.target.dataset && e.target.dataset.x;
      if (x === 'yes') {
        localStorage.cm_consent = JSON.stringify({ v: S.policyVersion, at: new Date().toISOString() });
        kids.forEach(k => { k.inert = false; }); document.documentElement.classList.remove('locked'); m.close(true);
      } else if (x === 'no') {
        m.box.innerHTML = `<h2>Access needs your agreement</h2><p>CrossMind cannot be used unless you accept the Privacy Policy, Terms and Conditions and the use of cookies described above.</p><div class="modal-actions"><button class="btn primary" data-x="back">Review again</button></div>`;
        m.box.querySelector('[data-x="back"]').onclick = () => { m.close(true); kids.forEach(k => { k.inert = false; }); document.documentElement.classList.remove('locked'); consentGate(); };
        m.box.querySelector('[data-x="back"]').focus();
      }
    };
  }

  // ---------- session expiry ----------
  let warned = false;
  function sessionWatch() {
    const exp = +localStorage.exp;
    if (!exp) return;
    const left = exp - Date.now();
    if (left <= 0) {
      if (/index\.html$|\/$/.test(location.pathname)) { Session.clear(); return; }
      logout('Your session has ended. Please sign in again.');
    } else if (left < 5 * 60 * 1000 && !warned && !/index\.html$|\/$/.test(location.pathname)) {
      warned = true; toast('Your session ends in less than 5 minutes. Save your work.');
    }
  }

  // ---------- password show/hide ----------
  function passwordToggles(root = document) {
    root.querySelectorAll('input[type=password]:not([data-pw])').forEach(inp => {
      inp.dataset.pw = '1';
      const wrap = el('span', { class: 'pw-wrap' }); inp.parentNode.insertBefore(wrap, inp); wrap.appendChild(inp);
      const b = el('button', { type: 'button', class: 'pw-toggle', 'aria-label': 'Show password', 'aria-pressed': 'false' }, 'Show');
      b.onclick = () => { const show = inp.type === 'password'; inp.type = show ? 'text' : 'password'; b.textContent = show ? 'Hide' : 'Show'; b.setAttribute('aria-pressed', show); b.setAttribute('aria-label', show ? 'Hide password' : 'Show password'); };
      wrap.appendChild(b);
    });
  }

  // ---------- scroll progress bar ----------
  function progressBar() {
    const bar = document.body.appendChild(el('div', { class: 'progress', 'aria-hidden': 'true' }));
    let tick = false;
    const upd = () => { const h = document.documentElement; const max = h.scrollHeight - h.clientHeight; bar.style.width = (max > 0 ? Math.min(100, h.scrollTop / max * 100) : 0) + '%'; tick = false; };
    addEventListener('scroll', () => { if (!tick) { tick = true; requestAnimationFrame(upd); } }, { passive: true });
    addEventListener('hashchange', upd);
  }

  // ---------- footer ----------
  function footer() {
    const f = document.getElementById('site-footer'); if (!f) return;
    const contact = [O.name && esc(O.name), O.email && `<a href="mailto:${esc(O.email)}">${esc(O.email)}</a>`, O.phone && `<a href="tel:${esc(O.phone.replace(/[^+\d]/g, ''))}">${esc(O.phone)}</a>`].filter(Boolean).join(' &middot; ');
    f.innerHTML = `<div class="footer-links"><a href="/privacy.html">Privacy Policy</a><a href="/terms.html">Terms and Conditions</a><a href="/faq.html">FAQ</a></div>
      ${contact ? `<div class="footer-contact">Contact: ${contact}</div>` : ''}
      <div class="footer-meta">&copy; ${new Date().getFullYear()} ${esc(S.name || 'CrossMind')}. Last updated ${esc(S.updated || '')}.</div>`;
  }

  // ---------- floating contact button ----------
  function contactButton() {
    if (!O.email && !O.phone) return;
    const b = document.body.appendChild(el('button', { class: 'fab', type: 'button', 'aria-haspopup': 'dialog' }, 'Contact'));
    b.onclick = () => {
      const row = (label, val, href, copyIt) => val ? `<div class="crow"><span class="mu">${label}</span><span class="cval">${href ? `<a href="${esc(href)}"${/^https/.test(href) ? ' target="_blank" rel="noopener"' : ''}>${esc(val)}</a>` : esc(val)}</span>${copyIt ? `<button class="btn alt sm" data-copy="${esc(val)}" data-what="${label}">Copy</button>` : ''}</div>` : '';
      const m = modal(`<h2>Contact</h2>${O.name ? `<p><b>${esc(O.name)}</b>${O.role ? `<br><span class="mu">${esc(O.role)}</span>` : ''}${O.organisation ? `<br><span class="mu">${esc(O.organisation)}</span>` : ''}</p>` : ''}
        ${row('Email', O.email, O.email && 'mailto:' + O.email, true)}${row('Phone', O.phone, O.phone && 'tel:' + O.phone.replace(/[^+\d]/g, ''), true)}${row('Location', O.location)}
        ${row('GitHub', isHttp(O.github) ? O.github : '', O.github)}${row('LinkedIn', isHttp(O.linkedin) ? O.linkedin : '', O.linkedin)}
        <div class="modal-actions"><button class="btn primary" data-close>Close</button></div>`, { label: 'Contact details' });
      m.box.querySelectorAll('[data-copy]').forEach(c => c.onclick = () => copy(c.dataset.copy, c.dataset.what));
      m.box.querySelector('[data-close]').onclick = () => m.close();
      m.box.querySelector('[data-close]').focus();
    };
  }

  // ---------- UTM capture (first visit in this browser tab) ----------
  function captureUtm() {
    const p = new URLSearchParams(location.search), found = {};
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'].forEach(k => { const v = (p.get(k) || '').slice(0, 80); if (v) found[k] = v; });
    if (Object.keys(found).length && !sessionStorage.cm_utm) sessionStorage.cm_utm = JSON.stringify(found);
  }
  const utm = () => { try { return JSON.parse(sessionStorage.cm_utm || '{}'); } catch (e) { return {}; } };

  function init() {
    captureUtm();
    consentGate();
    progressBar();
    footer();
    contactButton();
    passwordToggles();
    new MutationObserver(() => passwordToggles()).observe(document.body, { childList: true, subtree: true });
    if (sessionStorage.cm_msg) { toast(sessionStorage.cm_msg); sessionStorage.removeItem('cm_msg'); }
    sessionWatch(); setInterval(sessionWatch, 30000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) sessionWatch(); });
    $$('[data-theme-btn]').forEach(b => b.setAttribute('aria-pressed', document.documentElement.dataset.theme === 'dark'));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  return { busy, copy, modal, confirmDialog, utm, esc };
})();
const confirmDialog = UI.confirmDialog;
