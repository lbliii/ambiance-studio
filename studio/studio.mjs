const app = document.getElementById('app');
const parts = location.pathname.split('/').filter(Boolean);
const query = new URLSearchParams(location.search);
const labels = {score: 'Score', effects: 'Effects only', silent: 'Silent picture'};
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (key.startsWith('aria-')) node.setAttribute(key, String(value));
    else if (key === 'class') node.className = value;
    else if (value !== false && value != null) node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) if (child != null) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}
async function get(url) {
  const response = await fetch(url, {cache: 'no-store'});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'The studio could not load this result.');
  return result;
}
function duration(seconds) { return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`; }
function feedbackTime(row) { const seconds=n=>`${Number(n.toFixed(3))}s`; return row.time?.kind==='range' ? `${seconds(row.time.start_seconds)}–${seconds(row.time.end_seconds)}` : seconds(row.seconds); }
function link(text, href, cls = '') { return el('a', {href, class: cls}, text); }
function mediaURL(project, delivery, role) { return `/media/${project}/${delivery}/${role}`; }
function entries(data) { return data.entries || data.editions || {}; }
function pair(data, view = query.get('view'), role = query.get('role')) {
  view ??= data.default?.view || 'authored'; role ??= data.default?.role || data.default_role;
  return Object.entries(entries(data)).find(([, entry]) => (entry.view || 'authored') === view && entry.role === role);
}
function entryLabel(entry) { return `${entry.view === 'authored' || !entry.view ? '' : entry.view+' · '}${labels[entry.role]}`; }
function exactURL(project, data, entry) {
  const values = new URLSearchParams({role: entry.role});
  if (data.schema_version === 2) values.set('view', entry.view);
  return `/projects/${project}/deliveries/${data.id}?${values}`;
}
function posterURL(project, data, key) { return mediaURL(project, data.id, 'poster')+(data.schema_version === 2 ? '?entry='+encodeURIComponent(key) : ''); }
function metadata(edition) {
  return el('div', {class: 'metadata'}, el('span', {}, `${edition.duration_seconds} seconds`), el('span', {}, `${edition.width} × ${edition.height}`), el('span', {}, `${edition.fps} fps`));
}
function video(project, data, role, muted = false) {
  const entry = entries(data)[role];
  if (!entry?.available) return el('div', {class: 'error'}, 'This movie is missing or has changed. Choose an intact version from the history below.');
  const player = el('video', {controls: true, playsinline: true, preload: 'metadata', muted,
    poster: entry.poster ? posterURL(project, data, role) : null,
    src: mediaURL(project, data.id, role), 'aria-label': `${data.title} — ${entryLabel(entry)}`});
  player.muted = muted;
  return player;
}
async function home() {
  const {projects} = await get('/api/projects');
  const cards = projects.map(project => {
    const data = project.current?.delivery;
    const selected = data && pair(data, null, null); const entry = selected?.[1];
    const cover = data?.poster ? el('img', {src: mediaURL(project.id, data.id, 'poster'), alt: '', loading: 'lazy'}) : el('div', {class: 'no-cover'}, project.title);
    const state = !project.available ? 'Project location unavailable' : project.current?.error ? 'Current version needs attention' : data ? (project.current.ok ? 'Current review' : 'Files need attention') : 'No review movie selected';
    return el('article', {class: 'card'}, el('a', {class: 'cover', href: project.url, 'aria-label': `Open ${project.title}`}, cover),
      el('div', {class: 'card-body'}, el('p', {class: 'eyebrow'}, state), el('h2', {}, project.title),
        el('p', {class: 'muted'}, data ? `${data.title}${entry ? ' · '+entry.duration_seconds+' seconds' : ''}` : 'Scene, versions, and production notes'),
        link(data ? 'Watch current version' : 'Open project', project.url, 'button '+(data ? 'primary' : ''))));
  });
  app.replaceChildren(el('div', {class: 'intro'}, el('p', {class: 'eyebrow'}, 'Your local library'), el('h1', {}, 'Films in progress'),
    el('p', {}, 'The current review, with every earlier version close at hand.')),
    cards.length ? el('div', {class: 'cards'}, cards) : el('div', {class: 'empty'}, el('h2', {}, 'Your studio is ready.'), el('p', {}, 'Register an existing project to bring its movies here.'), el('code', {}, './ambiance studio register /path/to/project')));
}
function history(project, overview, selected) {
  return el('section', {class: 'side-section'}, el('h2', {}, 'Previous versions'),
    overview.history.length ? el('ul', {class: 'history'}, overview.history.map(item => el('li', {},
      link(item.title, `/projects/${project}/deliveries/${item.id}`),
      item.id === overview.current.selection?.delivery ? el('span', {class: 'pill'}, 'Current review') : null,
      el('p', {}, item.notes || (item.error ? item.error : Object.values(entries(item)).map(entryLabel).join(' · '))),
      item.id !== selected?.id && selected ? link('Compare with this version', exactURL(project, selected, pair(selected)?.[1] || pair(selected, null, null)[1])+'&compare='+item.id) : null))) : el('p', {class: 'muted'}, 'Registered movies will appear here.'));
}
function feedbackPanel(project, data, key, player, notes) {
  const entry = entries(data)[key]; const role = entry.role; const list = el('div');
  async function post(suffix, body) {
    const response = await fetch(`/api/projects/${project}/feedback${suffix}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const result = await response.json(); if (!response.ok) throw Error(result.error); return result.feedback;
  }
  function replace(row) { const i = notes.findIndex(n => n.id === row.id); if (i >= 0) notes[i] = row; else notes.unshift(row); showNotes(); }
  function showNotes() {
    list.replaceChildren(...notes.map(row => {
      const seek = row.seconds == null ? el('small', {}, row.subject?.kind === 'delivery' ? 'Whole delivery' : entryLabel(row)) :
        el('button', {onclick: () => { if ((row.view || 'authored') === entry.view && row.role === role && player.tagName === 'VIDEO') player.currentTime = row.seconds; else location.href = exactURL(project, data, {...row, view: row.view || 'authored'})+'&time='+row.seconds; }}, `${feedbackTime(row)} · ${entryLabel(row)}`);
      const reason = el('input', {placeholder: 'What changed, or why reopen?', required: true, 'aria-label': 'Disposition reason'});
      const target = el('input', {placeholder: 'Delivery ID that addresses this', 'aria-label': 'Resolution delivery'});
      const outcome = el('select', {'aria-label': 'Resolution outcome'}, el('option', {value: 'addressed'}, 'Addressed in a delivery'), el('option', {value: 'withdrawn'}, 'Withdrawn'));
      const status = el('p', {role: 'status'});
      const form = el('form', {onsubmit: async event => {
        event.preventDefault();
        try {
          const resolution = {outcome: outcome.value, note: reason.value};
          if (outcome.value === 'addressed') resolution.delivery = target.value;
          replace(await post(`/${row.id}/${row.state === 'resolved' ? 'reopen' : 'resolve'}`, {reporter: name.value, note: reason.value, expected: row.head, resolution: row.state === 'resolved' ? null : resolution}));
        } catch (error) { status.textContent = error.message; }
      }}, reason, row.state === 'resolved' ? null : [outcome, target], el('button', {type: 'submit'}, row.state === 'resolved' ? 'Reopen' : 'Record resolution'), status);
      return el('article', {class: 'feedback-note'}, seek, el('span', {class: 'pill'}, row.state || 'open'), el('p', {}, row.note),
        el('small', {class: 'muted'}, `Reported by ${row.reporter || row.observer}${row.observer ? ' · Observer: '+row.observer : ''}`),
        row.integrity?.ok === false ? el('p', {class: 'warning'}, row.integrity.errors.join('; ')) : null,
        el('details', {}, el('summary', {}, 'Disposition'), el('p', {class: 'caption'}, 'Records work addressing this note. Movie reviews remain separate.'), form));
    }));
  }
  const note = el('textarea', {placeholder: 'What would you change, or like to keep?', 'aria-label': 'Movie feedback', required: true, maxlength: 10000});
  const name = el('input', {value: 'Local viewer', 'aria-label': 'Reporter name', maxlength: 200, required: true});
  const scope = el('select', {'aria-label': 'Feedback scope'}, el('option', {value: 'delivery'}, 'Whole delivery'), el('option', {value: 'entry'}, 'This movie'), el('option', {value: 'point'}, 'This movie at current time'), el('option', {value: 'range'}, 'Time range in this movie'));
  const start = el('input', {type: 'number', min: 0, step: .01, placeholder: 'Range start (seconds)', 'aria-label': 'Range start'});
  const end = el('input', {type: 'number', min: 0, step: .01, placeholder: 'Range end (seconds)', 'aria-label': 'Range end'});
  const range = el('div', {hidden: true}, start, end); scope.addEventListener('change', () => { range.hidden = scope.value !== 'range'; });
  const status = el('p', {role: 'status', class: 'caption'}); const save = el('button', {type: 'submit'}, 'Save note');
  let requestId = crypto.randomUUID(), pendingBody = null;
  for (const field of [note, name, scope, start, end]) field.addEventListener('input', () => { requestId = crypto.randomUUID(); pendingBody = null; });
  const form = el('form', {onsubmit: async event => {
    event.preventDefault(); save.disabled = true;
    try {
      const body = {delivery: data.id, scope: scope.value === 'delivery' ? 'delivery' : 'entry', note: note.value, reporter: name.value, request_id: requestId};
      if (body.scope === 'entry') Object.assign(body, {view: entry.view, role});
      if (scope.value === 'point') {
        if (player.tagName !== 'VIDEO') throw Error('An intact movie is required for timed feedback.');
        body.seconds = Math.min(player.currentTime || 0, entry.duration_seconds - .001);
      }
      if (scope.value === 'range') { if (!start.value || !end.value) throw Error('Supply both range boundaries.'); body.start = Number(start.value); body.end = Number(end.value); }
      pendingBody ||= body;
      replace(await post('', pendingBody)); requestId = crypto.randomUUID(); pendingBody = null; note.value = ''; status.textContent = `Saved against ${data.title}.`;
    } catch (error) { status.textContent = error.message; }
    finally { save.disabled = false; }
  }}, note, scope, range, el('label', {}, 'Reported by', name), save, status);
  showNotes();
  return el('section', {class: 'side-section'}, el('h2', {}, 'Review notes'), el('p', {class: 'caption'}, 'Notes stay with this exact delivery or movie.'), form, list);
}

function productionPanel(project, overview, data = null) {
  const open = overview.open_checks.filter(item => item.criteria.length || item.reasons.length);
  return el('details', {}, el('summary', {}, 'Production and checks'),
    el('p', {class: 'caption'}, Object.values(overview.working).some(item => item.matches_selected === false) ? 'Working inputs have changes beyond this movie.' : Object.values(overview.working).some(item => item.matches_selected === true) ? 'Working inputs match the selected movie snapshots.' : 'No working-input comparison is recorded.'),
    Object.entries(data?.entry_checks || overview.entry_checks || {}).map(([key, state]) => el('details', {}, el('summary', {}, `${key}: ${state.release_ready ? 'Release ready' : 'Review pending'}`),
      state.error ? el('p', {class: 'warning'}, state.error) : null, state.open_checks.map(item => el('p', {class: 'caption'}, `${item.gate}: ${item.state}${item.reasons.length ? ' · '+item.reasons.join('; ') : ''}`)))),
    overview.runs.map(run => el('p', {}, `${run.id}: ${run.effective_state || run.state}${run.stage ? ' · '+run.stage : ''}`, run.error ? el('span', {class: 'warning'}, ' — '+run.error) : null)),
    open.map(item => el('details', {}, el('summary', {}, `${item.gate}: ${item.state}`),
      item.reasons.map(reason => el('p', {class: 'caption'}, reason)),
      item.criteria.map(check => el('p', {class: 'caption'}, `${check.id}: ${check.result}${check.note ? ' — '+check.note : ''}`)))),
    overview.next_work?.items.length ? el('div', {}, el('h3', {}, 'Next work'), overview.next_work.items.map(item => el('p', {}, item.reason, item.decision ? ' · '+item.decision : ''))) : null,
    overview.errors.map(error => el('p', {class: 'warning'}, error)));
}
async function compare(project, data, otherId, overview, paired = false) {
  const other = paired ? data : await get(`/api/projects/${project}/deliveries/${otherId}`);
  const chosen=pair(data); if (!chosen) throw Error('This version does not contain the requested format and soundtrack.');
  const [key, entry]=chosen; const matching=paired ? Object.entries(entries(other)).find(([, e])=>e.view!==entry.view && e.role===entry.role) : pair(other, entry.view, entry.role);
  const left = video(project, data, key), right = video(project, other, matching?.[0], true);
  const play = el('button', {}, 'Play both');
  const slider = el('input', {type: 'range', min: 0, max: Math.min(entry.duration_seconds, matching?.[1].duration_seconds || 0), step: .033, value: 0, 'aria-label': 'Comparison time'});
  play.addEventListener('click', async () => {
    if (left.tagName !== 'VIDEO' || right.tagName !== 'VIDEO') return;
    if (!left.paused) { left.pause(); right.pause(); play.textContent = 'Play both'; }
    else { right.currentTime = left.currentTime; await Promise.all([left.play(), right.play()]); play.textContent = 'Pause both'; }
  });
  slider.addEventListener('input', () => { for (const item of [left, right]) if (item.tagName === 'VIDEO') item.currentTime = Number(slider.value); });
  left.addEventListener('timeupdate', () => {
    slider.value = left.currentTime;
    if (right.tagName === 'VIDEO' && Math.abs(left.currentTime - right.currentTime) > .15) right.currentTime = left.currentTime;
    if (left.currentTime >= Number(slider.max)-.02) { if(loop.checked){left.currentTime=0;if(right.tagName==='VIDEO')right.currentTime=0;left.play().catch(()=>{});}else{left.pause(); if (right.tagName === 'VIDEO') right.pause(); play.textContent = 'Play both';} }
  });
  const loop = el('input', {type: 'checkbox', 'aria-label': 'Loop comparison'});
  left.addEventListener('play', () => { if (right.tagName === 'VIDEO') { right.currentTime = left.currentTime; right.play().catch(()=>left.pause()); } });
  left.addEventListener('pause', () => { if (right.tagName === 'VIDEO') right.pause(); });
  left.addEventListener('seeking', () => { if (right.tagName === 'VIDEO') right.currentTime = left.currentTime; });
  if (right.tagName === 'VIDEO') { right.controls=false; right.addEventListener('volumechange', () => { if(!right.muted)right.muted=true; }); }
  left.addEventListener('ended', () => { if(loop.checked){left.currentTime=0;left.play().catch(()=>{});} });
  const playbackStatus = el('p', {role:'status', class:'caption'}); let lastTime=0, advanced=performance.now();
  const syncTimer=setInterval(()=>{if(!left.isConnected){clearInterval(syncTimer);return;}const now=performance.now();
    if(left.paused||left.currentTime!==lastTime)advanced=now;lastTime=left.currentTime;
    if(!left.paused&&right.tagName==='VIDEO'&&Math.abs(right.currentTime-left.currentTime)>.15)right.currentTime=left.currentTime;
    playbackStatus.textContent=!left.paused&&now-advanced>2000?'Playback is waiting for the first movie. Check its play or sound controls.':'';
  },250);
  app.replaceChildren(el('div', {class: 'project-head'}, el('div', {}, el('p', {class: 'eyebrow'}, paired ? 'Paired formats' : 'Version comparison'), el('h1', {}, overview.title)), link('Back to movie', `/projects/${project}/deliveries/${data.id}`, 'button')),
    el('p', {class: 'caption'}, `${entryLabel(entry)} · Sound plays from the left movie. This comparison follows playback time; use a paired scene proof to check exact synchronization.`),
    el('div', {class: 'comparison'}, el('section', {}, el('h2', {}, data.title), left), el('section', {}, el('h2', {}, other.title), right)),
    el('div', {class: 'compare-controls'}, play, slider, el('label', {}, loop, 'Loop comparison')), playbackStatus);
}
async function projectPage(project) {
  const overview = await get(`/api/projects/${project}`);
  const selectedId = parts[2] === 'deliveries' ? parts[3] : overview.current.selection?.delivery;
  const data = selectedId && (parts[2] === 'deliveries' || overview.current.delivery) ? await get(`/api/projects/${project}/deliveries/${selectedId}`) : null;
  if (data && query.get('paired')) return compare(project, data, data.id, overview, true);
  if (data && query.get('compare')) return compare(project, data, query.get('compare'), overview);
  const heading = el('div', {class: 'project-head'}, el('div', {}, el('p', {class: 'eyebrow'}, selectedId === overview.current.selection?.delivery ? 'Current review' : data ? 'Earlier version' : 'Project'), el('h1', {}, overview.title)),
    link('Open working scene', `/editor/?project=${project}`, 'button'));
  if (!data) {
    app.replaceChildren(heading, el('div', {class: 'empty'}, el('h2', {}, 'No current movie selected'), el('p', {}, overview.current.error || 'Choose a completed delivery through the CLI to make it the current review.')), history(project, overview), productionPanel(project, overview)); return;
  }
  const chosen = pair(data);
  if (!chosen) {
    app.replaceChildren(heading, el('div', {class: 'error'}, 'This delivery does not contain the requested format and soundtrack.'),
      el('div', {class: 'actions'}, Object.values(entries(data)).map(entry => link(entryLabel(entry), exactURL(project, data, entry), 'button')))); return;
  }
  const [key, entry] = chosen; const role = entry.role; const player = video(project, data, key);
  const seek = Number(query.get('time'));
  if (seek > 0 && seek < entry.duration_seconds) player.addEventListener('loadedmetadata', () => { player.currentTime = seek; }, {once: true});
  const isCurrent = overview.current.selection?.delivery === data.id;
  function switchPair(view, soundtrack) {
    const selected = pair(data, view, soundtrack); if (!selected) return;
    const url = new URL(location.href); url.searchParams.set('view', view); url.searchParams.set('role', soundtrack);
    const time = player.tagName === 'VIDEO' ? player.currentTime : 0;
    if (player.tagName === 'VIDEO') player.pause();
    url.searchParams.delete('time');
    if (time > 0 && time < selected[1].duration_seconds) url.searchParams.set('time', String(time));
    location.href = url;
  }
  const viewControls = data.schema_version === 2 ? el('div', {class: 'roles', role: 'group', 'aria-label': 'Output format'},
    [...new Set(Object.values(entries(data)).map(item => item.view))].map(view => el('button', {
      disabled: !pair(data, view, role), 'aria-pressed': view === entry.view, onclick: () => switchPair(view, role)}, view[0].toUpperCase()+view.slice(1)))) : null;
  const controls = el('div', {class: 'roles', role: 'group', 'aria-label': 'Soundtrack'}, Object.entries(labels).map(([soundtrack, label]) => el('button', {
    disabled: !pair(data, entry.view, soundtrack), 'aria-pressed': soundtrack === role, onclick: () => switchPair(entry.view, soundtrack)}, label)));
  const files = el('details', {}, el('summary', {}, 'Movie files and evidence'), el('ul', {class: 'files'},
    Object.entries(entries(data)).map(([id, value]) => el('li', {}, link(`Download ${entryLabel(value)}`, mediaURL(project, data.id, id)+'?download=1'),
      ' · ', link('Decode report', `/files/${project}/${data.id}/${id}`),
      value.poster ? [' · ', link('Cover', posterURL(project, data, id)+(data.schema_version === 2 ? '&' : '?')+'download=1')] : null))));
  const copy = el('button', {onclick: async () => {
    const url = location.origin+exactURL(project, data, entry);
    try { await navigator.clipboard.writeText(url); copy.textContent = 'Exact version link copied'; }
    catch { copy.replaceWith(el('input', {value: url, readonly: true, 'aria-label': 'Exact version link'})); }
  }}, 'Copy exact version link');
  const state = entry.technical_evidence_current ? 'Technically checked · Human review is separate' : 'Technical evidence needs attention';
  const releaseSelected = overview.release.selection?.delivery === data.id && overview.release.release?.approved;
  app.replaceChildren(heading, el('div', {id: 'update'}), el('div', {class: 'watch-layout'},
    el('section', {}, el('div', {class: 'screen'}, player), viewControls, controls, metadata(entry), el('p', {class: 'caption'}, state),
      el('div', {class: 'actions'}, copy, data.schema_version === 2 ? link('Watch paired formats', exactURL(project,data,entry)+'&paired=1', 'button') : null, !isCurrent ? link('Watch current version', `/projects/${project}`, 'button') : null), files),
    el('aside', {}, el('section', {class: 'side-section'}, el('p', {class: 'eyebrow'}, releaseSelected ? 'Approved release' : 'Review movie'),
      el('h2', {}, data.title), el('p', {class: 'muted'}, data.notes || 'No change note was recorded.'),
      data.issues.length ? el('div', {class: 'notice warning'}, 'Some registered inputs have changed or are missing. Intact movies remain available.', data.issues.map(issue => el('p', {class: 'caption'}, `${issue.path}: ${issue.error}`))) : null),
      history(project, overview, data), feedbackPanel(project, data, key, player, data.feedback || []), productionPanel(project, overview, data))));
  const token = overview.current.selection?.payload_sha256;
  setInterval(async () => {
    try {
      const fresh = await get(`/api/projects/${project}/current`);
      document.getElementById('connection').textContent = fresh.runs.some(run => run.effective_state === 'running') ? 'An iteration is in progress' : 'Local studio · Connected';
      if (fresh.selection?.payload_sha256 !== token) document.getElementById('update').replaceChildren(el('div', {class: 'notice'}, 'The current review has changed. ', link('Open current version', `/projects/${project}`, 'button primary')));
    } catch { document.getElementById('connection').textContent = 'Studio disconnected · Reopen with ambiance studio open'; }
  }, 5000);
}
get('/api/runtime').then(data => { document.getElementById('runtime').textContent = `Version ${data.version} · ${data.code_root} · Projects: ${data.registry}`; }).catch(() => {});
(parts[0] === 'projects' ? projectPage(parts[1]) : home()).catch(error => app.replaceChildren(el('div', {class: 'empty'}, el('h1', {}, 'This view needs attention'), el('p', {class: 'error'}, error.message), link('Return to all films', '/', 'button'))));
