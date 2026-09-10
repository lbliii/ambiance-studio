const app = document.getElementById('app');
const parts = location.pathname.split('/').filter(Boolean);
const query = new URLSearchParams(location.search);
const labels = {score: 'Score', effects: 'Effects only', silent: 'Silent picture'};
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
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
function link(text, href, cls = '') { return el('a', {href, class: cls}, text); }
function mediaURL(project, delivery, role) { return `/media/${project}/${delivery}/${role}`; }
function metadata(edition) {
  return el('div', {class: 'metadata'}, el('span', {}, `${edition.duration_seconds} seconds`), el('span', {}, `${edition.width} × ${edition.height}`), el('span', {}, `${edition.fps} fps`));
}
function video(project, data, role, muted = false) {
  const entry = data.editions?.[role];
  if (!entry?.available) return el('div', {class: 'error'}, 'This movie is missing or has changed. Choose an intact version from the history below.');
  const player = el('video', {controls: true, playsinline: true, preload: 'metadata', muted,
    poster: data.poster ? mediaURL(project, data.id, 'poster') : null,
    src: mediaURL(project, data.id, role), 'aria-label': `${data.title} — ${labels[role]}`});
  player.muted = muted;
  return player;
}
async function home() {
  const {projects} = await get('/api/projects');
  const cards = projects.map(project => {
    const data = project.current?.delivery;
    const entry = data?.editions?.[data.default_role];
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
      el('p', {}, item.notes || (item.error ? item.error : Object.keys(item.editions || {}).map(role => labels[role]).join(' · '))),
      item.id !== selected?.id && selected ? link('Compare with this version', `/projects/${project}/deliveries/${selected.id}?compare=${item.id}&role=${query.get('role') || selected.default_role}`) : null))) : el('p', {class: 'muted'}, 'Registered movies will appear here.'));
}
function feedbackPanel(project, data, role, player, notes) {
  const list = el('div');
  function showNotes(rows) {
    list.replaceChildren(...rows.map(row => el('article', {class: 'feedback-note'},
      el('button', {onclick: () => { if (row.role === role && player.tagName === 'VIDEO') player.currentTime = row.seconds; else location.href = `/projects/${project}/deliveries/${data.id}?role=${row.role}&time=${row.seconds}`; }}, `${duration(row.seconds)} · ${labels[row.role]}`),
      el('p', {}, row.note), el('small', {class: 'muted'}, row.observer))));
  }
  showNotes(notes);
  const note = el('textarea', {placeholder: 'What would you change, or like to keep?', 'aria-label': 'Movie feedback', required: true, maxlength: 10000});
  const name = el('input', {value: 'Local viewer', 'aria-label': 'Your name', maxlength: 200, required: true});
  const status = el('p', {role: 'status', class: 'caption'});
  const save = el('button', {type: 'submit'}, 'Save note at current time');
  const form = el('form', {onsubmit: async event => {
    event.preventDefault(); save.disabled = true;
    try {
      const seconds = player.tagName === 'VIDEO' ? Math.min(player.currentTime || 0, data.editions[role].duration_seconds - .001) : 0;
      const response = await fetch(`/api/projects/${project}/feedback`, {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({delivery: data.id, role, seconds, note: note.value, observer: name.value})});
      const result = await response.json();
      if (!response.ok) throw Error(result.error);
      notes.unshift(result.feedback); showNotes(notes); note.value = '';
      status.textContent = `Saved against ${data.title} at ${duration(seconds)}.`;
    } catch (error) { status.textContent = error.message; }
    finally { save.disabled = false; }
  }}, note, el('details', {}, el('summary', {}, 'Observer'), el('label', {}, 'Your name', name)), save, status);
  return el('section', {class: 'side-section'}, el('h2', {}, 'Review notes'), el('p', {class: 'caption'}, 'Notes stay with this exact movie and soundtrack.'), form, list);
}
function productionPanel(project, overview) {
  const open = overview.open_checks.filter(item => item.criteria.length || item.reasons.length);
  return el('details', {}, el('summary', {}, 'Production and checks'),
    el('p', {class: 'caption'}, Object.values(overview.working).some(item => item.matches_selected === false) ? 'Working inputs have changes beyond this movie.' : Object.values(overview.working).some(item => item.matches_selected === true) ? 'Working inputs match the selected movie snapshots.' : 'No working-input comparison is recorded.'),
    overview.runs.map(run => el('p', {}, `${run.id}: ${run.state}${run.stage ? ' · '+run.stage : ''}`, run.error ? el('span', {class: 'warning'}, ' — '+run.error) : null)),
    open.map(item => el('details', {}, el('summary', {}, `${item.gate}: ${item.state}`),
      item.reasons.map(reason => el('p', {class: 'caption'}, reason)),
      item.criteria.map(check => el('p', {class: 'caption'}, `${check.id}: ${check.result}${check.note ? ' — '+check.note : ''}`)))),
    overview.ready_work.length ? el('div', {}, el('h3', {}, 'Available next work'), overview.ready_work.map(item => el('p', {}, item.action))) : null,
    overview.errors.map(error => el('p', {class: 'warning'}, error)));
}
async function compare(project, data, otherId, overview) {
  const other = await get(`/api/projects/${project}/deliveries/${otherId}`);
  const role = query.get('role') || data.default_role;
  const left = video(project, data, role), right = video(project, other, role, true);
  const play = el('button', {}, 'Play both');
  const slider = el('input', {type: 'range', min: 0, max: Math.min(data.editions[role]?.duration_seconds || 0, other.editions[role]?.duration_seconds || 0), step: .033, value: 0, 'aria-label': 'Comparison time'});
  play.addEventListener('click', async () => {
    if (left.tagName !== 'VIDEO' || right.tagName !== 'VIDEO') return;
    if (!left.paused) { left.pause(); right.pause(); play.textContent = 'Play both'; }
    else { right.currentTime = left.currentTime; await Promise.all([left.play(), right.play()]); play.textContent = 'Pause both'; }
  });
  slider.addEventListener('input', () => { for (const item of [left, right]) if (item.tagName === 'VIDEO') item.currentTime = Number(slider.value); });
  left.addEventListener('timeupdate', () => {
    slider.value = left.currentTime;
    if (right.tagName === 'VIDEO' && Math.abs(left.currentTime - right.currentTime) > .15) right.currentTime = left.currentTime;
    if (left.currentTime >= Number(slider.max)) { left.pause(); right.pause(); play.textContent = 'Play both'; }
  });
  app.replaceChildren(el('div', {class: 'project-head'}, el('div', {}, el('p', {class: 'eyebrow'}, 'Version comparison'), el('h1', {}, overview.title)), link('Back to movie', `/projects/${project}/deliveries/${data.id}`, 'button')),
    el('p', {class: 'caption'}, `${labels[role]} · Sound plays from the left movie. Both views use the same position in seconds.`),
    el('div', {class: 'comparison'}, el('section', {}, el('h2', {}, data.title), left), el('section', {}, el('h2', {}, other.title), right)),
    el('div', {class: 'compare-controls'}, play, slider));
}
async function projectPage(project) {
  const overview = await get(`/api/projects/${project}`);
  const selectedId = parts[2] === 'deliveries' ? parts[3] : overview.current.selection?.delivery;
  const data = selectedId && (parts[2] === 'deliveries' || overview.current.delivery) ? await get(`/api/projects/${project}/deliveries/${selectedId}`) : null;
  if (data && query.get('compare')) return compare(project, data, query.get('compare'), overview);
  const heading = el('div', {class: 'project-head'}, el('div', {}, el('p', {class: 'eyebrow'}, selectedId === overview.current.selection?.delivery ? 'Current review' : data ? 'Earlier version' : 'Project'), el('h1', {}, overview.title)),
    link('Open working scene', `/editor/?project=${project}`, 'button'));
  if (!data) {
    app.replaceChildren(heading, el('div', {class: 'empty'}, el('h2', {}, 'No current movie selected'), el('p', {}, overview.current.error || 'Choose a completed delivery through the CLI to make it the current review.')), history(project, overview), productionPanel(project, overview)); return;
  }
  let role = query.get('role') || data.default_role;
  if (!data.editions[role]) role = data.default_role;
  const entry = data.editions[role]; const player = video(project, data, role);
  const seek = Number(query.get('time'));
  if (seek > 0 && seek < entry.duration_seconds) player.addEventListener('loadedmetadata', () => { player.currentTime = seek; }, {once: true});
  const isCurrent = overview.current.selection?.delivery === data.id;
  const controls = el('div', {class: 'roles'}, Object.entries(labels).map(([key, label]) => el('button', {disabled: !data.editions[key], 'aria-pressed': key === role,
    onclick: () => { const url = new URL(location.href); url.searchParams.set('role', key); url.searchParams.delete('time'); location.href = url; }}, label)));
  const files = el('details', {}, el('summary', {}, 'Movie files and evidence'), el('ul', {class: 'files'},
    Object.entries(data.editions).map(([key, value]) => el('li', {}, link(`Download ${labels[key].toLowerCase()}`, mediaURL(project, data.id, key)+'?download=1'),
      ' · ', link('Decode report', `/files/${project}/${data.id}/${key}`))),
    data.poster ? el('li', {}, link('Download cover', mediaURL(project, data.id, 'poster')+'?download=1')) : null));
  const copy = el('button', {onclick: async () => {
    const url = `${location.origin}/projects/${project}/deliveries/${data.id}?role=${role}`;
    try { await navigator.clipboard.writeText(url); copy.textContent = 'Exact version link copied'; }
    catch { copy.replaceWith(el('input', {value: url, readonly: true, 'aria-label': 'Exact version link'})); }
  }}, 'Copy exact version link');
  const state = entry.technical_evidence_current ? 'Technically checked · Human review is separate' : 'Technical evidence needs attention';
  const releaseSelected = overview.release.selection?.delivery === data.id && overview.release.release?.approved;
  app.replaceChildren(heading, el('div', {id: 'update'}), el('div', {class: 'watch-layout'},
    el('section', {}, el('div', {class: 'screen'}, player), controls, metadata(entry), el('p', {class: 'caption'}, state),
      el('div', {class: 'actions'}, copy, !isCurrent ? link('Watch current version', `/projects/${project}`, 'button') : null), files),
    el('aside', {}, el('section', {class: 'side-section'}, el('p', {class: 'eyebrow'}, releaseSelected ? 'Approved release' : 'Review movie'),
      el('h2', {}, data.title), el('p', {class: 'muted'}, data.notes || 'No change note was recorded.'),
      data.issues.length ? el('div', {class: 'notice warning'}, 'Some registered inputs have changed or are missing. Intact movies remain available.', data.issues.map(issue => el('p', {class: 'caption'}, `${issue.path}: ${issue.error}`))) : null),
      history(project, overview, data), feedbackPanel(project, data, role, player, data.feedback || []), productionPanel(project, overview))));
  const token = overview.current.selection?.payload_sha256;
  setInterval(async () => {
    try {
      const fresh = await get(`/api/projects/${project}/current`);
      document.getElementById('connection').textContent = fresh.runs.some(run => run.state === 'running') ? 'An iteration is in progress' : 'Local studio · Connected';
      if (fresh.selection?.payload_sha256 !== token) document.getElementById('update').replaceChildren(el('div', {class: 'notice'}, 'The current review has changed. ', link('Open current version', `/projects/${project}`, 'button primary')));
    } catch { document.getElementById('connection').textContent = 'Studio disconnected · Reopen with ambiance studio open'; }
  }, 5000);
}
get('/api/runtime').then(data => { document.getElementById('runtime').textContent = `Version ${data.version} · ${data.code_root} · Projects: ${data.registry}`; }).catch(() => {});
(parts[0] === 'projects' ? projectPage(parts[1]) : home()).catch(error => app.replaceChildren(el('div', {class: 'empty'}, el('h1', {}, 'This view needs attention'), el('p', {class: 'error'}, error.message), link('Return to all films', '/', 'button'))));
