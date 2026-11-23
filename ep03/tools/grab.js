// pasted into the ElevenLabs sound-effects page: captures the WAV blob of a library row and POSTs it to the local receiver
if (!window.__hooked) {
  window.__hooked = true;
  const orig = URL.createObjectURL.bind(URL);
  URL.createObjectURL = (b) => {
    try {
      if (b instanceof Blob && b.size > 2000) {
        const n = (window.__name || 'snd') + '.wav';
        fetch('http://127.0.0.1:8765/' + encodeURIComponent(n), {method: 'POST', body: b})
          .then(r => window.__last = 'sent ' + n + ' ' + b.size + ' ' + r.status).catch(e => window.__last = 'err ' + e);
      }
    } catch (e) {}
    return orig(b);
  };
  const oc = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () { if (this.download || /^blob:/.test(this.href)) return; return oc.call(this); };
}
window.rows = () => [...document.querySelectorAll('button[aria-label="播放"]')].map(p => {
  let r = p; for (let i = 0; i < 8 && r; i++) { if (r.querySelectorAll('button').length >= 4) break; r = r.parentElement; }
  const t = r.textContent; const d = parseFloat((t.match(/(\d+(?:\.\d+)?)s/) || [0, 0])[1]);
  return {r, t, d};
});
window.pickWav = () => { const it = [...document.querySelectorAll('[role=menuitem], [role=option], button, div')].filter(e => e.childElementCount <= 2 && /^\s*WAV/.test(e.textContent)); if (!it.length) return 'nowav'; it[it.length - 1].click(); return 'wav'; };
window.grabFirst = async (name, minDur, excl) => {
  const bad = excl || /music|scream|sci-?fi|fantasy|cartoon|game|horror|spaceship|anime|robot|alien|magic|siren|explosion/i;
  const row = rows().find(x => x.d >= minDur && !bad.test(x.t));
  if (!row) return name + ': none';
  window.__name = name; window.__last = '';
  for (let k = 0; k < 3; k++) {
    document.body.click(); await new Promise(r => setTimeout(r, 500));
    [...row.r.querySelectorAll('button')][2].click(); await new Promise(r => setTimeout(r, 1500));
    if (pickWav() === 'wav') { for (let t = 0; t < 30 && !window.__last; t++) await new Promise(r => setTimeout(r, 500)); if (window.__last) return name + ' (' + row.d + 's): ' + row.t.slice(0, 110); }
  }
  return name + ': failed';
};
'ready'
