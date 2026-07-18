"""Minimal steward UI shell for Case History / Official Case Record / Save and Print.

Not a full React app — a lightweight FastAPI-served workspace that wires the
existing case APIs so reopen, history, and Save and Print are usable in-browser.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Steward UI"])


_PAGE_CSS = """
:root {
  --ink: #1c2430;
  --muted: #5c6b7a;
  --line: #d7dde5;
  --panel: #f3f6f9;
  --accent: #0f5c4c;
  --accent-soft: #e6f2ef;
  --warn: #8a4b00;
  --white: #fff;
  --sidebar-w: 280px;
  --font: "Source Serif 4", "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  --ui: "IBM Plex Sans", "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  font-family: var(--ui);
  background:
    radial-gradient(1200px 500px at 10% -10%, #e8f1ee 0%, transparent 55%),
    linear-gradient(180deg, #eef2f6 0%, #f8fafc 40%, #f3f6f9 100%);
  min-height: 100vh;
}
a { color: var(--accent); text-decoration: none; }
.layout { display: grid; grid-template-columns: var(--sidebar-w) 1fr; min-height: 100vh; }
.sidebar {
  background: var(--panel);
  border-right: 1px solid var(--line);
  padding: 1rem 0.85rem 2rem;
  overflow: auto;
}
.brand {
  font-family: var(--font);
  font-size: 1.55rem;
  letter-spacing: -0.02em;
  margin: 0.2rem 0 0.15rem;
}
.sidebar-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin: 0.75rem 0 0.5rem;
}
.case-item, .hist-item {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  border-radius: 8px;
  background: transparent;
  padding: 0.65rem 0.7rem;
  margin: 0 0 0.25rem;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.case-item:hover, .hist-item:hover, .case-item.active {
  background: var(--accent-soft);
}
.case-title { font-weight: 600; font-size: 0.95rem; }
.case-meta, .hist-meta { color: var(--muted); font-size: 0.78rem; margin-top: 0.2rem; }
.main { padding: 1.25rem 1.5rem 2.5rem; }
.hero-brand {
  font-family: var(--font);
  font-size: clamp(2rem, 4vw, 2.8rem);
  margin: 0;
}
.lede { color: var(--muted); max-width: 36rem; }
.card-free { margin-top: 1.25rem; max-width: 44rem; }
textarea, input, select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0.7rem 0.8rem;
  font: inherit;
  background: var(--white);
}
textarea { min-height: 110px; resize: vertical; }
.row { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-top: 0.7rem; }
button.btn {
  border: 0;
  border-radius: 8px;
  padding: 0.65rem 1rem;
  background: var(--accent);
  color: var(--white);
  font: inherit;
  cursor: pointer;
}
button.btn.secondary { background: #2c3a4a; }
button.btn.ghost {
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--line);
}
.status { margin-top: 0.8rem; color: var(--muted); font-size: 0.9rem; white-space: pre-wrap; }
.panel {
  margin-top: 1rem;
  padding: 0.9rem 0;
  border-top: 1px solid var(--line);
}
.panel h2 { font-family: var(--font); font-size: 1.2rem; margin: 0 0 0.5rem; }
.icon { display: inline-block; width: 0.7rem; height: 0.7rem; border-radius: 50%; margin-right: 0.35rem; background: var(--accent); }
.icon.report { background: #245b8a; }
.icon.grievance { background: #6b4a9e; }
.icon.printed { background: #8a4b00; }
.icon.upload { background: #3d6b3d; }
.icon.decision { background: #9a3b3b; }
.icon.step { background: #555; }
.chat-log {
  max-height: 280px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0.75rem;
  background: var(--white);
  margin-bottom: 0.75rem;
  white-space: pre-wrap;
  font-size: 0.92rem;
}
.artifact-group { margin: 0.75rem 0; }
.artifact-group h3 {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  margin: 0 0 0.35rem;
}
.artifact-item {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--white);
  padding: 0.55rem 0.7rem;
  margin: 0 0 0.35rem;
  cursor: pointer;
  font: inherit;
}
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(20, 28, 36, 0.45);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 40;
  padding: 1rem;
}
.modal-backdrop.open { display: flex; }
.modal {
  width: min(720px, 100%);
  max-height: 90vh;
  overflow: auto;
  background: var(--white);
  border-radius: 12px;
  padding: 1.1rem 1.2rem 1.2rem;
  box-shadow: 0 16px 40px rgba(20, 28, 36, 0.18);
}
.modal h2 { font-family: var(--font); margin: 0 0 0.4rem; }
.modal .readonly {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0.8rem;
  background: #f8fafc;
  white-space: pre-wrap;
  max-height: 45vh;
  overflow: auto;
}
.field-grid { display: grid; gap: 0.55rem; }
.field-grid label { font-size: 0.82rem; color: var(--muted); display: block; }
.primary-actions { margin-top: 0.85rem; }
"""


def _shell(title: str, body: str, script: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap" rel="stylesheet"/>
  <style>{_PAGE_CSS}</style>
</head>
<body>
{body}
<script>
{script}
</script>
</body>
</html>"""


@router.get("/ui", response_class=HTMLResponse)
def steward_home():
    body = """
<div class="layout">
  <aside class="sidebar" aria-label="Case History">
    <div class="brand">GrievanceHub</div>
    <div class="sidebar-label">Case History</div>
    <div id="case-list"></div>
    <div class="row" style="margin-top:0.8rem">
      <button class="btn ghost" id="prev-page" type="button">Prev</button>
      <button class="btn ghost" id="next-page" type="button">Next</button>
    </div>
    <div class="case-meta" id="list-meta"></div>
  </aside>
  <main class="main">
    <h1 class="hero-brand">GrievanceHub</h1>
    <p class="lede">Open a saved case from Case History, or start a new case. The workspace opens into continuous AI conversation — analysis reports and grievances are optional steward actions.</p>
    <div class="card-free">
      <label for="new-q"><strong>New Case</strong></label>
      <textarea id="new-q" placeholder="Describe the dispute…"></textarea>
      <div class="row">
        <input id="new-name" placeholder="Steward / grievant name (optional)"/>
        <button class="btn" id="create-case" type="button">New Case</button>
      </div>
      <div class="status" id="home-status"></div>
    </div>
  </main>
</div>
"""
    script = """
let offset = 0;
const limit = 25;
async function loadCases() {
  const res = await fetch(`/cases/saved?limit=${limit}&offset=${offset}&order=newest_first`);
  const data = await res.json();
  const list = document.getElementById('case-list');
  list.innerHTML = '';
  (data.cases || []).forEach(c => {
    const btn = document.createElement('button');
    btn.className = 'case-item';
    btn.type = 'button';
    btn.innerHTML = `<div class="case-title">${escapeHtml(c.title || c.issue_summary || 'Untitled case')}</div>
      <div class="case-meta">${escapeHtml(c.grievant_or_class || c.case_number || '')}
      · ${escapeHtml(c.current_step_type || 'step unknown')}
      · ${escapeHtml(c.workspace_status || '')}
      · ${escapeHtml((c.last_activity_at || '').slice(0,10))}</div>`;
    btn.onclick = () => openCase(c);
    list.appendChild(btn);
  });
  document.getElementById('list-meta').textContent =
    `Showing ${data.count || 0} of ${data.total || 0} (summary only)`;
  document.getElementById('prev-page').disabled = offset <= 0;
  document.getElementById('next-page').disabled = !data.has_more;
}
async function openCase(c) {
  const terminal = ['closed', 'settled', 'archived'];
  const path = terminal.includes(c.workspace_status)
    ? `/cases/saved/${c.case_uuid}/reopen`
    : `/cases/saved/${c.case_uuid}/open`;
  const res = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({source: 'manual_ui'})
  });
  if (!res.ok) {
    document.getElementById('home-status').textContent = 'Failed to open case';
    return;
  }
  window.location.href = `/ui/cases/${c.case_uuid}`;
}
document.getElementById('create-case').onclick = async () => {
  const question = document.getElementById('new-q').value.trim();
  if (!question) return;
  const res = await fetch('/cases/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      question,
      user_name: document.getElementById('new-name').value.trim() || null
    })
  });
  const data = await res.json();
  if (!res.ok) {
    document.getElementById('home-status').textContent = JSON.stringify(data);
    return;
  }
  const createdUuid = (data.case && data.case.case_uuid) || data.case_uuid;
  if (!createdUuid) {
    document.getElementById('home-status').textContent = 'Case created but UUID missing from response';
    return;
  }
  window.location.href = `/ui/cases/${createdUuid}`;
};
document.getElementById('prev-page').onclick = () => { offset = Math.max(0, offset - limit); loadCases(); };
document.getElementById('next-page').onclick = () => { offset += limit; loadCases(); };
function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
loadCases();
"""
    return HTMLResponse(_shell("GrievanceHub — Case History", body, script))


@router.get("/ui/cases/{case_uuid}", response_class=HTMLResponse)
def steward_case_workspace(case_uuid: str):
    body = f"""
<div class="layout">
  <aside class="sidebar" aria-label="Official Case Record">
    <div class="brand"><a href="/ui">GrievanceHub</a></div>
    <div class="sidebar-label">Official Case Record</div>
    <div id="history-list"></div>
  </aside>
  <main class="main">
    <h1 class="hero-brand" id="case-title">Case</h1>
    <p class="lede" id="case-lede">Loading restored workspace…</p>
    <div class="panel">
      <h2>Case Overview</h2>
      <p class="case-meta">Automatically maintained from Case Memory.</p>
      <div id="overview-structured" class="case-meta"></div>
    </div>
    <div class="panel">
      <h2>AI Conversation</h2>
      <p class="case-meta">Primary working area. Chat does not generate reports or grievances.</p>
      <div class="chat-log" id="chat-log">Loading conversation…</div>
      <textarea id="chat" placeholder="Ask a follow-up, challenge a conclusion, or discuss strategy…"></textarea>
      <div class="row primary-actions">
        <button class="btn" id="send" type="button">Send</button>
        <button class="btn secondary" id="generate-analysis" type="button">Generate Analysis Report</button>
        <button class="btn secondary" id="generate-grievance" type="button">Generate Grievance</button>
        <a class="btn ghost" href="/ui">Dashboard</a>
      </div>
      <div class="status" id="status"></div>
    </div>
    <div class="panel">
      <h2>File Upload</h2>
      <p class="case-meta">Upload evidence or management responses without leaving the workspace.</p>
      <input id="upload-file" type="file"/>
      <div class="row">
        <button class="btn ghost" id="upload-btn" type="button">Upload to case</button>
      </div>
    </div>
    <div class="panel">
      <h2>Artifacts</h2>
      <p class="case-meta">Document library — separate from the Official Case Record timeline.</p>
      <div id="artifacts"></div>
    </div>
    <div class="panel">
      <h2>Jump to context</h2>
      <p class="case-meta">Historical view only — does not change current Case Memory.</p>
      <pre class="status" id="history-context">Select an Official Case Record item.</pre>
    </div>
  </main>
</div>
<div class="modal-backdrop" id="analysis-modal" aria-hidden="true">
  <div class="modal" role="dialog" aria-labelledby="analysis-title">
    <h2 id="analysis-title">Analysis Report Review</h2>
    <p class="case-meta">Read-only. To change the analysis, cancel, continue chatting, then generate a new version.</p>
    <div class="readonly" id="analysis-preview"></div>
    <div class="row">
      <button class="btn" id="analysis-save" type="button">Save</button>
      <button class="btn secondary" id="analysis-save-print" type="button">Save and Print</button>
      <button class="btn ghost" id="analysis-cancel" type="button">Cancel</button>
    </div>
  </div>
</div>
<div class="modal-backdrop" id="grievance-modal" aria-hidden="true">
  <div class="modal" role="dialog" aria-labelledby="grievance-title">
    <h2 id="grievance-title">Grievance Review</h2>
    <p class="case-meta">Editable working draft. Cancel discards this preview without creating an official artifact.</p>
    <div class="field-grid" id="grievance-fields"></div>
    <div class="row">
      <button class="btn" id="grievance-save" type="button">Save</button>
      <button class="btn secondary" id="grievance-save-print" type="button">Save and Print</button>
      <button class="btn ghost" id="grievance-cancel" type="button">Cancel</button>
    </div>
  </div>
</div>
"""
    script = f"""
const caseUuid = {case_uuid!r};
let workspace = null;
let analysisPreview = null;
let grievanceDraft = null;
const grievanceFieldIds = [
  'grievant_name', 'grievant_name_or_class', 'facts_what_happened',
  'facts_date_time_location', 'violation_articles_citations', 'corrective_action_requested'
];
function escapeHtml(s) {{
  return String(s || '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
}}
function openModal(id) {{
  document.getElementById(id).classList.add('open');
  document.getElementById(id).setAttribute('aria-hidden', 'false');
}}
function closeModal(id) {{
  document.getElementById(id).classList.remove('open');
  document.getElementById(id).setAttribute('aria-hidden', 'true');
}}
async function loadWorkspace() {{
  const res = await fetch(`/cases/${{caseUuid}}/workspace`);
  workspace = await res.json();
  if (!res.ok) {{
    document.getElementById('status').textContent = 'Failed to load workspace';
    return;
  }}
  document.getElementById('case-title').textContent = workspace.title || 'Case workspace';
  document.getElementById('case-lede').textContent =
    (workspace.case_memory_restored_first ? 'Case Memory restored. ' : '') +
    (workspace.initial_question || '');
  const ov = workspace.case_overview || {{}};
  document.getElementById('overview-structured').innerHTML =
    `<div><strong>Status:</strong> ${{escapeHtml(ov.current_status || '')}} · ` +
    `<strong>Step:</strong> ${{escapeHtml(ov.current_step || '')}} · ` +
    `<strong>Workflow:</strong> ${{escapeHtml(ov.explicit_workflow_state || '')}}</div>` +
    `<div style="margin-top:8px"><strong>AI Recommendation</strong> ` +
    `(not a steward decision): ${{escapeHtml(ov.current_recommendation || 'None')}}</div>` +
    `<div style="margin-top:8px"><strong>Steward Decision</strong>: ` +
    `${{escapeHtml((ov.steward_decision && (ov.steward_decision.decision_summary || ov.steward_decision.outcome_type)) || 'None recorded')}}</div>`;
  await Promise.all([loadHistory(), loadChat(), loadArtifacts()]);
}}
async function loadChat() {{
  const res = await fetch(`/cases/${{caseUuid}}/messages?limit=100&order=oldest_first`);
  const data = await res.json();
  const log = document.getElementById('chat-log');
  const msgs = data.messages || data.items || [];
  if (!msgs.length) {{
    log.textContent = 'No messages yet. Start the conversation.';
    return;
  }}
  log.textContent = msgs.map(m => `${{(m.role || '').toUpperCase()}}: ${{m.content || ''}}`).join('\\n\\n');
  log.scrollTop = log.scrollHeight;
}}
async function loadArtifacts() {{
  const [artRes, assetRes] = await Promise.all([
    fetch(`/cases/${{caseUuid}}/artifacts`),
    fetch(`/cases/${{caseUuid}}/assets`)
  ]);
  const artData = artRes.ok ? await artRes.json() : {{groups: {{}}, artifacts: []}};
  const assetData = assetRes.ok ? await assetRes.json() : {{assets: []}};
  const root = document.getElementById('artifacts');
  const groups = artData.groups || {{}};
  const analysis = groups.analysis_reports || [];
  const grievances = groups.grievances || [];
  const assets = assetData.assets || assetData.items || [];
  const isMgmt = a => {{
    const meta = a.asset_metadata || {{}};
    return meta.management_response || meta.document_role === 'management_response';
  }};
  const management = assets.filter(isMgmt);
  const evidence = assets.filter(a => (a.asset_category || '') === 'uploaded_document' && !isMgmt(a));
  const other = assets.filter(a => (a.asset_category || '') !== 'uploaded_document');
  function renderGroup(title, items, kind) {{
    let html = `<div class="artifact-group"><h3>${{escapeHtml(title)}}</h3>`;
    if (!items.length) return html + `<div class="case-meta">None yet.</div></div>`;
    items.forEach(item => {{
      if (kind === 'artifact') {{
        const flags = [
          item.printed ? 'printed' : 'saved',
          item.artifact_type === 'analysis_report' ? 'immutable' : 'saved version',
          item.is_latest_official ? 'latest official' : ''
        ].filter(Boolean).join(' · ');
        html += `<button type="button" class="artifact-item" data-uuid="${{escapeHtml(item.artifact_uuid)}}">
          <strong>${{escapeHtml(item.version_label || item.title || 'Artifact')}}</strong>
          <div class="case-meta">${{escapeHtml(flags)}}</div></button>`;
      }} else {{
        html += `<div class="artifact-item"><strong>${{escapeHtml(item.original_filename || item.filename || item.asset_uuid)}}</strong>
          <div class="case-meta">${{escapeHtml(item.category || 'asset')}}</div></div>`;
      }}
    }});
    return html + '</div>';
  }}
  root.innerHTML =
    renderGroup('Analysis Reports', analysis, 'artifact') +
    renderGroup('Grievances', grievances, 'artifact') +
    renderGroup('Management Responses', management, 'asset') +
    renderGroup('Evidence', evidence, 'asset') +
    renderGroup('Other saved case documents', other, 'asset');
  root.querySelectorAll('button.artifact-item').forEach(btn => {{
    btn.onclick = async () => {{
      const res = await fetch(`/cases/${{caseUuid}}/artifacts/${{btn.dataset.uuid}}`);
      document.getElementById('status').textContent = JSON.stringify(await res.json(), null, 2);
    }};
  }});
}}
async function jumpToContext(eventId) {{
  document.getElementById('history-context').textContent = 'Loading context…';
  const res = await fetch(`/cases/${{caseUuid}}/history/${{eventId}}/context`);
  document.getElementById('history-context').textContent = JSON.stringify(await res.json(), null, 2);
}}
async function loadHistory() {{
  const res = await fetch(`/cases/saved/${{caseUuid}}/history?order=oldest_first&limit=100`);
  const data = await res.json();
  const list = document.getElementById('history-list');
  list.innerHTML = '';
  (data.events || []).forEach(ev => {{
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'hist-item';
    const label = ev.display_label ? ` · ${{escapeHtml(ev.display_label)}}` : '';
    btn.innerHTML = `<span class="icon ${{ev.icon || 'case'}}"></span>
      <strong>${{escapeHtml(ev.title)}}</strong>
      <div class="hist-meta">${{escapeHtml(ev.record_class || '')}}${{label}} · ${{escapeHtml((ev.event_timestamp || '').slice(0,19))}}</div>`;
    if (ev.clickable) btn.onclick = () => jumpToContext(ev.event_id);
    else {{ btn.disabled = true; btn.style.opacity = '0.85'; }}
    list.appendChild(btn);
  }});
}}
document.getElementById('send').onclick = async () => {{
  const message = document.getElementById('chat').value.trim();
  if (!message) return;
  document.getElementById('status').textContent = 'Sending…';
  const res = await fetch(`/cases/${{caseUuid}}/interactions`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ message, source: 'manual_ui' }})
  }});
  const data = await res.json();
  document.getElementById('status').textContent = res.ok
    ? ((data.assistant_message && data.assistant_message.content) || data.message || 'Sent')
    : JSON.stringify(data);
  document.getElementById('chat').value = '';
  await loadWorkspace();
}};
document.getElementById('upload-btn').onclick = async () => {{
  const fileInput = document.getElementById('upload-file');
  if (!fileInput.files || !fileInput.files[0]) {{
    document.getElementById('status').textContent = 'Choose a file first.';
    return;
  }}
  const form = new FormData();
  form.append('file', fileInput.files[0]);
  form.append('category', 'uploaded_document');
  form.append('source', 'manual_ui');
  document.getElementById('status').textContent = 'Uploading…';
  const res = await fetch(`/cases/${{caseUuid}}/assets`, {{ method: 'POST', body: form }});
  const data = await res.json();
  document.getElementById('status').textContent = res.ok
    ? `Uploaded ${{(data.asset && (data.asset.original_filename || data.asset.asset_uuid)) || 'file'}}`
    : JSON.stringify(data);
  fileInput.value = '';
  await loadWorkspace();
}};
document.getElementById('generate-analysis').onclick = async () => {{
  document.getElementById('status').textContent = 'Generating analysis preview…';
  const res = await fetch(`/cases/${{caseUuid}}/reports/generate`, {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{}})
  }});
  const data = await res.json();
  if (!res.ok) {{
    document.getElementById('status').textContent = JSON.stringify(data);
    return;
  }}
  analysisPreview = data.preview || data.analysis_preview || null;
  document.getElementById('analysis-preview').textContent = JSON.stringify(
    (analysisPreview && (analysisPreview.report_data || analysisPreview.report_summary))
      || analysisPreview
      || {{}},
    null,
    2
  );
  openModal('analysis-modal');
  document.getElementById('status').textContent = data.message || 'Temporary preview ready (not saved).';
}};
async function saveAnalysis(preparePdf) {{
  if (!analysisPreview) {{
    document.getElementById('status').textContent = 'No analysis preview to save. Generate first.';
    return;
  }}
  const res = await fetch(`/cases/${{caseUuid}}/reports/save-and-print`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ preview: analysisPreview, prepare_pdf: preparePdf }})
  }});
  const data = await res.json();
  document.getElementById('status').textContent = JSON.stringify(data, null, 2);
  if (preparePdf && data.print_ready && data.export_path) window.open(data.export_path, '_blank');
  closeModal('analysis-modal');
  analysisPreview = null;
  await loadWorkspace();
}}
document.getElementById('analysis-save').onclick = () => saveAnalysis(false);
document.getElementById('analysis-save-print').onclick = () => saveAnalysis(true);
document.getElementById('analysis-cancel').onclick = () => {{
  closeModal('analysis-modal');
  analysisPreview = null;
  document.getElementById('status').textContent =
    'Analysis preview discarded. No version, artifact, or Official Case Record event created.';
}};
function renderGrievanceFields(values) {{
  const root = document.getElementById('grievance-fields');
  root.innerHTML = '';
  grievanceFieldIds.forEach(id => {{
    const wrap = document.createElement('div');
    const label = document.createElement('label');
    label.textContent = id;
    const ta = document.createElement('textarea');
    ta.id = `gf-${{id}}`;
    ta.value = values[id] || '';
    wrap.appendChild(label);
    wrap.appendChild(ta);
    root.appendChild(wrap);
  }});
}}
function collectGrievanceFields() {{
  const values = {{}};
  grievanceFieldIds.forEach(id => {{ values[id] = document.getElementById(`gf-${{id}}`).value; }});
  return values;
}}
document.getElementById('generate-grievance').onclick = async () => {{
  document.getElementById('status').textContent = 'Generating grievance draft…';
  const res = await fetch(`/cases/${{caseUuid}}/actions`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ action: 'generate_grievance' }})
  }});
  const data = await res.json();
  if (!res.ok || data.status === 'prerequisites_not_met') {{
    document.getElementById('status').textContent = JSON.stringify(data);
    return;
  }}
  grievanceDraft = data.grievance_generation || {{}};
  renderGrievanceFields(grievanceDraft.field_values || {{}});
  openModal('grievance-modal');
  document.getElementById('status').textContent = data.message || 'Editable grievance draft ready.';
}};
async function saveGrievance(preparePdf) {{
  const fieldValues = collectGrievanceFields();
  const res = await fetch(`/cases/${{caseUuid}}/grievances/save-and-print`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{
      template_id: (grievanceDraft && grievanceDraft.template_id) || 'local_300_form_79_1',
      template_version: '1',
      grievance_step: (grievanceDraft && grievanceDraft.step_type)
        || (workspace && workspace.step_progression && workspace.step_progression.current_step_type)
        || 'step_1_initial',
      field_values: fieldValues,
      draft_status: 'ready_for_steward_review',
      prepare_pdf: preparePdf
    }})
  }});
  const data = await res.json();
  document.getElementById('status').textContent = JSON.stringify(data, null, 2);
  if (preparePdf && data.print_ready && data.export_path) window.open(data.export_path, '_blank');
  closeModal('grievance-modal');
  grievanceDraft = null;
  await loadWorkspace();
}}
document.getElementById('grievance-save').onclick = () => saveGrievance(false);
document.getElementById('grievance-save-print').onclick = () => saveGrievance(true);
document.getElementById('grievance-cancel').onclick = () => {{
  closeModal('grievance-modal');
  grievanceDraft = null;
  document.getElementById('status').textContent =
    'Grievance draft discarded. No artifact, version, or Official Case Record event created.';
}};
loadWorkspace();
"""
    return HTMLResponse(
        _shell(f"GrievanceHub — Case {case_uuid}", body, script)
    )
