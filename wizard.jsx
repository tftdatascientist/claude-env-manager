import React, { useState, useEffect } from 'react';
import {
  Sparkles, Loader2, Check, AlertCircle, FileText, GitBranch,
  ListTree, Wrench, RefreshCw, ChevronDown, ChevronRight,
  Trash2, Terminal, ArrowRight, Copy, Clipboard, ClipboardCheck,
} from 'lucide-react';

const MODEL = 'claude-sonnet-4-20250514';

const AVAILABLE_TAGS = [
  'fullstack', 'chatbot', 'api', 'automation', 'frontend', 'backend',
  'ai', 'learning', 'client-B2B', 'n8n', 'flowise', 'wordpress', 'voice',
];

const SECTIONS = {
  metadata: {
    title: 'CLAUDE.md',
    subtitle: 'Metadane projektu',
    Icon: FileText,
    fields: [
      { key: 'one_liner', label: 'One-liner', type: 'text' },
      { key: 'stack', label: 'Stack', type: 'textarea', mono: true, rows: 4 },
      { key: 'run_command', label: 'Run command', type: 'textarea', mono: true, rows: 4 },
      { key: 'coding_rules', label: 'Coding rules', type: 'textarea', rows: 5 },
      { key: 'key_files_table', label: 'Key files (markdown table)', type: 'textarea', mono: true, rows: 5 },
    ],
  },
  architecture: {
    title: 'ARCHITECTURE.md',
    subtitle: 'Struktura i moduły',
    Icon: ListTree,
    fields: [
      { key: 'directory_tree', label: 'Directory tree', type: 'textarea', mono: true, rows: 7 },
      { key: 'modules_table', label: 'Modules table', type: 'textarea', mono: true, rows: 5 },
      { key: 'data_flow', label: 'Data flow', type: 'textarea', rows: 3 },
      { key: 'architectural_decisions', label: 'Architectural decisions', type: 'textarea', rows: 4 },
      { key: 'external_dependencies_table', label: 'External dependencies (markdown table)', type: 'textarea', mono: true, rows: 4 },
    ],
  },
  conventions: {
    title: 'CONVENTIONS.md',
    subtitle: 'Nazewnictwo i styl',
    Icon: Wrench,
    fields: [
      { key: 'naming_conventions', label: 'Naming conventions', type: 'textarea', rows: 4 },
      { key: 'code_structure_rules', label: 'Code structure', type: 'textarea', rows: 3 },
      { key: 'formatting_rules', label: 'Formatting', type: 'textarea', rows: 3 },
      { key: 'testing_rules', label: 'Testing', type: 'textarea', rows: 3 },
      { key: 'git_conventions', label: 'Git conventions', type: 'textarea', rows: 3 },
    ],
  },
  plan: {
    title: 'PLAN.md',
    subtitle: 'Cel i pierwsze kroki',
    Icon: GitBranch,
    fields: [
      { key: 'initial_goal', label: 'Initial goal', type: 'text' },
      { key: 'initial_steps', label: 'Initial steps (markdown checklist)', type: 'textarea', mono: true, rows: 5 },
      { key: 'initial_decisions', label: 'Initial decisions', type: 'textarea', rows: 4 },
    ],
  },
};

const STORAGE_DRAFT_KEY = 'cc_wizard_draft_v1';
const STORAGE_PREFS_KEY = 'cc_wizard_prefs_v1';
const GLOW_SHADOW = { boxShadow: '0 0 40px rgba(163, 230, 53, 0.18)' };

const POLISH_MAP = {
  ą:'a', ć:'c', ę:'e', ł:'l', ń:'n', ó:'o', ś:'s', ź:'z', ż:'z',
  Ą:'a', Ć:'c', Ę:'e', Ł:'l', Ń:'n', Ó:'o', Ś:'s', Ź:'z', Ż:'z',
};

function slugify(title) {
  if (!title) return '';
  let s = title.split('').map(ch => POLISH_MAP[ch] ?? ch).join('');
  s = s.toLowerCase();
  s = s.replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  return s || 'project';
}

// ─── Clipboard: try modern API, fall back to execCommand on textarea ───

async function copyToClipboard(text) {
  // Strategy 1: modern async API
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) { /* fall through */ }
  }
  // Strategy 2: hidden textarea + execCommand (works even in restrictive iframes)
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    ta.style.pointerEvents = 'none';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch (e) {
    return false;
  }
}

// ─── JSON sanitization (from v0.3) ───

function tryParseWithSanitization(candidate) {
  try { return JSON.parse(candidate); } catch (e) { /* */ }
  let fixed = '';
  let inString = false;
  let escape = false;
  for (let i = 0; i < candidate.length; i++) {
    const ch = candidate[i];
    if (escape) { fixed += ch; escape = false; continue; }
    if (ch === '\\') { fixed += ch; escape = true; continue; }
    if (ch === '"') { inString = !inString; fixed += ch; continue; }
    if (inString) {
      if (ch === '\n') { fixed += '\\n'; continue; }
      if (ch === '\r') { fixed += '\\r'; continue; }
      if (ch === '\t') { fixed += '\\t'; continue; }
    }
    fixed += ch;
  }
  try { return JSON.parse(fixed); } catch (e) { /* */ }
  return JSON.parse(fixed.replace(/,(\s*[}\]])/g, '$1'));
}

function extractJson(text) {
  if (!text || typeof text !== 'string') throw new Error('Pusta odpowiedź modelu');
  const t = text.trim();
  if (t.startsWith('{') && t.endsWith('}')) {
    try { return tryParseWithSanitization(t); } catch (e) { /* */ }
  }
  const jsonFence = t.match(/```json\s*\n?([\s\S]*?)```/i);
  if (jsonFence) {
    try { return tryParseWithSanitization(jsonFence[1].trim()); } catch (e) { /* */ }
  }
  const fences = [...t.matchAll(/```(?:[a-zA-Z]+)?\s*\n?([\s\S]*?)```/g)];
  for (const m of fences) {
    const inner = m[1].trim();
    if (inner.startsWith('{') && inner.endsWith('}')) {
      try { return tryParseWithSanitization(inner); } catch (e) { /* */ }
    }
  }
  const firstBrace = t.indexOf('{');
  const lastBrace = t.lastIndexOf('}');
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    const slice = t.slice(firstBrace, lastBrace + 1);
    try { return tryParseWithSanitization(slice); } catch (e) { /* */ }
  }
  const preview = t.slice(0, 400).replace(/\n/g, ' ⏎ ');
  throw new Error(`Nie znaleziono prawidłowego JSON. Preview (400): "${preview}${t.length > 400 ? '...' : ''}"`);
}

// ─── Claude API ───

async function callClaude(prompt, { maxTokens = 4000 } = {}) {
  const body = { model: MODEL, max_tokens: maxTokens, messages: [{ role: 'user', content: prompt }] };
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`API ${res.status}: ${errText.slice(0, 200)}`);
  }
  const data = await res.json();
  if (data.stop_reason === 'max_tokens') {
    throw new Error(`Odpowiedź ucięta (limit ${maxTokens} tokenów). Zmniejsz opis lub regen sekcji.`);
  }
  return data;
}

function collectTextBlocks(data) {
  return (data.content || []).filter(b => b.type === 'text').map(b => b.text || '').join('\n');
}

// ─── Prompts (unchanged) ───

const JSON_RULES = `
KRYTYCZNE ZASADY ODPOWIEDZI:
1. Odpowiedz JEDNYM obiektem JSON. Nic poza nim.
2. NIE owijaj w \`\`\`json fences — surowy obiekt {...}.
3. Wartości stringów MUSZĄ mieć escape'owane \\n.
4. Bloki kodu wewnątrz wartości używają potrójnych backtików.
5. Wszystkie wartości to stringi.
6. Bądź ZWIĘZŁY. Każda wartość max 600 znaków.

PRZYKŁAD: {"name": "X", "code": "\`\`\`bash\\nnpm install\\n\`\`\`"}`;

function promptMetadata(desc) {
  return `Konfigurujesz nowy projekt Claude Code.

OPIS:
${desc}

Wygeneruj wartości pól (po polsku):

- "project_title": krótki tytuł (max 60 znaków)
- "tags": tablica 1-3 tagów Z LISTY: ${JSON.stringify(AVAILABLE_TAGS)}
- "one_liner": jedno zdanie (max 140 znaków)
- "stack": język + framework + biblioteki, prosty markdown
- "run_command": jak uruchomić, blok kodu
- "coding_rules": 3-5 zasad jako markdown lista
- "key_files_table": markdown tabela "Plik | Rola" z 3-5 wierszami

${JSON_RULES}`;
}

function promptArchitecture(desc, metadata) {
  return `Generujesz ARCHITECTURE.md.

OPIS:
${desc}

KONTEKST:
Stack: ${metadata.stack || '(brak)'}
One-liner: ${metadata.one_liner || '(brak)'}

Wygeneruj wartości pól (po polsku, ZWIĘZŁE):

- "directory_tree": ASCII tree, max 15 linii
- "modules_table": markdown tabela "Moduł | Plik(i) | Odpowiedzialność", 3-5 wierszy
- "data_flow": 2-3 zdania
- "architectural_decisions": 3-4 punkty z uzasadnieniem
- "external_dependencies_table": markdown tabela "Lib/API | Cel | Wersja", 3-5 wierszy

${JSON_RULES}`;
}

function promptConventions(desc, metadata) {
  return `Generujesz CONVENTIONS.md.

OPIS:
${desc}

STACK:
${metadata.stack || '(brak)'}

Wygeneruj wartości pól (po polsku, dopasuj do języka):

- "naming_conventions": 4 punkty (pliki, klasy, funkcje, zmienne)
- "code_structure_rules": 2-3 punkty
- "formatting_rules": 2-3 punkty
- "testing_rules": 2-3 punkty
- "git_conventions": 2 punkty

${JSON_RULES}`;
}

function promptPlan(desc, metadata) {
  return `Generujesz PLAN.md.

OPIS:
${desc}

ONE-LINER:
${metadata.one_liner || '(brak)'}

Wygeneruj wartości pól (po polsku):

- "initial_goal": jedno konkretne zdanie
- "initial_steps": markdown checklist 3-5 kroków "- [ ] krok"
- "initial_decisions": 2-3 punkty już-podjętych decyzji

${JSON_RULES}`;
}

function promptSingleField(desc, fieldKey, metadata, allFields) {
  return `Regenerujesz pojedyncze pole.

OPIS:
${desc}

KONTEKST:
${JSON.stringify({ ...metadata, ...allFields }, null, 2).slice(0, 1500)}

Regeneruj TYLKO pole "${fieldKey}".

${JSON_RULES}

Twoja odpowiedź:
{"${fieldKey}": "<nowa wartość>"}`;
}

// ─── COMPONENT ───

export default function ProjectWizard() {
  const [phase, setPhase] = useState('describe');
  const [description, setDescription] = useState('');
  const [projectTitle, setProjectTitle] = useState('');
  const [slug, setSlug] = useState('');
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false);
  const [tags, setTags] = useState([]);
  const [fields, setFields] = useState({});
  const [expanded, setExpanded] = useState({ metadata: true });
  const [generating, setGenerating] = useState(null);
  const [regeneratingField, setRegeneratingField] = useState(null);
  const [progress, setProgress] = useState({ done: 0, total: 4 });
  const [error, setError] = useState(null);
  const [logToNotion, setLogToNotion] = useState(true);
  const [draftLoaded, setDraftLoaded] = useState(false);

  // Export phase state
  const [exportedPayload, setExportedPayload] = useState(null);  // JSON string
  const [copyStatus, setCopyStatus] = useState(null);  // 'ok' | 'fail' | null

  useEffect(() => {
    (async () => {
      try {
        const r = await window.storage.get(STORAGE_DRAFT_KEY);
        if (r?.value) {
          const d = JSON.parse(r.value);
          setDescription(d.description || '');
          setProjectTitle(d.projectTitle || '');
          setSlug(d.slug || '');
          setSlugManuallyEdited(!!d.slugManuallyEdited);
          setTags(d.tags || []);
          setFields(d.fields || {});
          if (d.projectTitle && Object.keys(d.fields || {}).length > 0) {
            setPhase('wizard');
          }
        }
      } catch (e) { /* */ }
      try {
        const p = await window.storage.get(STORAGE_PREFS_KEY);
        if (p?.value) {
          const prefs = JSON.parse(p.value);
          if (typeof prefs.logToNotion === 'boolean') setLogToNotion(prefs.logToNotion);
        }
      } catch (e) { /* */ }
      setDraftLoaded(true);
    })();
  }, []);

  useEffect(() => {
    if (!draftLoaded) return;
    const timer = setTimeout(() => {
      const draft = { description, projectTitle, slug, slugManuallyEdited, tags, fields };
      window.storage.set(STORAGE_DRAFT_KEY, JSON.stringify(draft)).catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
  }, [description, projectTitle, slug, slugManuallyEdited, tags, fields, draftLoaded]);

  useEffect(() => {
    if (!draftLoaded) return;
    window.storage.set(STORAGE_PREFS_KEY, JSON.stringify({ logToNotion })).catch(() => {});
  }, [logToNotion, draftLoaded]);

  useEffect(() => {
    if (!slugManuallyEdited) setSlug(slugify(projectTitle));
  }, [projectTitle, slugManuallyEdited]);

  async function callAndParse(prompt, label, opts = {}) {
    const firstTokens = opts.maxTokens || 4000;
    try {
      const data = await callClaude(prompt, { maxTokens: firstTokens });
      return extractJson(collectTextBlocks(data));
    } catch (firstErr) {
      try {
        const retryPrompt = prompt + `\n\nTwoja poprzednia odpowiedź była niepoprawna. Wygeneruj ZWIĘZŁY, kompletny JSON.`;
        const data = await callClaude(retryPrompt, { maxTokens: firstTokens + 2000 });
        return extractJson(collectTextBlocks(data));
      } catch (retryErr) {
        throw new Error(`${label}: ${retryErr.message}`);
      }
    }
  }

  async function generateAll() {
    setError(null);
    setGenerating('all');
    setProgress({ done: 0, total: 4 });
    try {
      const meta = await callAndParse(promptMetadata(description), 'metadane');
      const newFields = {
        one_liner: meta.one_liner || '',
        stack: meta.stack || '',
        run_command: meta.run_command || '',
        coding_rules: meta.coding_rules || '',
        key_files_table: meta.key_files_table || '',
      };
      setProjectTitle(meta.project_title || '');
      setTags(Array.isArray(meta.tags) ? meta.tags.filter(t => AVAILABLE_TAGS.includes(t)) : []);
      setFields(f => ({ ...f, ...newFields }));
      setProgress({ done: 1, total: 4 });

      const [arch, conv, plan] = await Promise.all([
        callAndParse(promptArchitecture(description, newFields), 'architecture'),
        callAndParse(promptConventions(description, newFields), 'conventions'),
        callAndParse(promptPlan(description, newFields), 'plan'),
      ]);

      setFields(f => ({
        ...f, ...newFields,
        directory_tree: arch.directory_tree || '',
        modules_table: arch.modules_table || '',
        data_flow: arch.data_flow || '',
        architectural_decisions: arch.architectural_decisions || '',
        external_dependencies_table: arch.external_dependencies_table || '',
        naming_conventions: conv.naming_conventions || '',
        code_structure_rules: conv.code_structure_rules || '',
        formatting_rules: conv.formatting_rules || '',
        testing_rules: conv.testing_rules || '',
        git_conventions: conv.git_conventions || '',
        initial_goal: plan.initial_goal || '',
        initial_steps: plan.initial_steps || '',
        initial_decisions: plan.initial_decisions || '',
      }));
      setProgress({ done: 4, total: 4 });
      setPhase('wizard');
      setExpanded({ metadata: true });
    } catch (e) {
      setError(`Generowanie: ${e.message}`);
    } finally {
      setGenerating(null);
    }
  }

  async function regenerateSection(sectionKey) {
    setError(null);
    setGenerating(sectionKey);
    try {
      const meta = { one_liner: fields.one_liner, stack: fields.stack };
      let prompt;
      if (sectionKey === 'metadata') prompt = promptMetadata(description);
      else if (sectionKey === 'architecture') prompt = promptArchitecture(description, meta);
      else if (sectionKey === 'conventions') prompt = promptConventions(description, meta);
      else if (sectionKey === 'plan') prompt = promptPlan(description, meta);
      else throw new Error('Unknown section');

      const parsed = await callAndParse(prompt, sectionKey);

      if (sectionKey === 'metadata') {
        setProjectTitle(parsed.project_title || projectTitle);
        setTags(Array.isArray(parsed.tags) ? parsed.tags.filter(t => AVAILABLE_TAGS.includes(t)) : tags);
      }

      setFields(f => {
        const next = { ...f };
        for (const field of SECTIONS[sectionKey].fields) {
          if (parsed[field.key] !== undefined) next[field.key] = parsed[field.key];
        }
        return next;
      });
    } catch (e) {
      setError(`Regeneracja ${sectionKey}: ${e.message}`);
    } finally {
      setGenerating(null);
    }
  }

  async function regenerateField(fieldKey) {
    setError(null);
    setRegeneratingField(fieldKey);
    try {
      const parsed = await callAndParse(
        promptSingleField(description, fieldKey, { projectTitle, tags }, fields),
        `pole ${fieldKey}`,
        { maxTokens: 2000 }
      );
      if (parsed[fieldKey] !== undefined) {
        setFields(f => ({ ...f, [fieldKey]: parsed[fieldKey] }));
      }
    } catch (e) {
      setError(`Regeneracja pola: ${e.message}`);
    } finally {
      setRegeneratingField(null);
    }
  }

  async function sendToLauncher() {
    setError(null);
    const payload = {
      project_title: projectTitle,
      slug: slug,
      tags: tags,
      save_to_notion: logToNotion,
      fields: fields,
    };
    const jsonStr = JSON.stringify(payload, null, 2);
    const ok = await copyToClipboard(jsonStr);
    setExportedPayload(jsonStr);
    setCopyStatus(ok ? 'ok' : 'fail');
    setPhase('export');
    // Don't clear draft yet — user might want to retry copy
  }

  async function recopyPayload() {
    if (!exportedPayload) return;
    const ok = await copyToClipboard(exportedPayload);
    setCopyStatus(ok ? 'ok' : 'fail');
  }

  function finishAndReset() {
    // Called after user confirms "już uruchomiłem cc-paste"
    setPhase('describe');
    setDescription('');
    setProjectTitle('');
    setSlug('');
    setSlugManuallyEdited(false);
    setTags([]);
    setFields({});
    setExportedPayload(null);
    setCopyStatus(null);
    setError(null);
    window.storage.delete(STORAGE_DRAFT_KEY).catch(() => {});
  }

  function resetAll() {
    try {
      if (!confirm('Skasować obecny draft i zacząć od nowa?')) return;
    } catch (e) { /* */ }
    finishAndReset();
  }

  function backToWizard() {
    // From export phase back to wizard to edit
    setPhase('wizard');
  }

  function toggleTag(tag) {
    setTags(t => t.includes(tag) ? t.filter(x => x !== tag) : [...t, tag]);
  }

  function toggleExpanded(key) {
    setExpanded(e => ({ ...e, [key]: !e[key] }));
  }

  const allFieldsFilled = Object.keys(SECTIONS).every(sec =>
    SECTIONS[sec].fields.every(f => (fields[f.key] || '').trim().length > 0)
  );
  const canSend = projectTitle.trim() && slug.trim() && allFieldsFilled;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-sans">
      <header className="border-b border-neutral-800 px-8 py-5 flex items-center justify-between sticky top-0 bg-neutral-950 z-10">
        <div className="flex items-center gap-3">
          <Clipboard className="w-5 h-5 text-lime-400" />
          <div>
            <div className="text-sm font-mono text-lime-400 tracking-tight">cc_project_wizard</div>
            <div className="text-xs text-neutral-500">Generuj → kopiuj do schowka → cc-paste.bat</div>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-neutral-500">
          {phase === 'wizard' && (
            <button onClick={resetAll} className="flex items-center gap-1.5 hover:text-red-400 transition">
              <Trash2 className="w-3.5 h-3.5" /> Reset
            </button>
          )}
          <span className="font-mono">v0.6</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-8 py-12">
        {error && (
          <div className="mb-6 rounded-lg border border-red-900 bg-red-950 px-5 py-3 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-red-300">Błąd</div>
              <div className="text-sm text-red-400 mt-0.5 font-mono break-all">{error}</div>
            </div>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-300 text-xs">×</button>
          </div>
        )}

        {phase === 'describe' && (
          <div>
            <div className="mb-10">
              <div className="text-xs font-mono text-lime-400 mb-3 tracking-widest">// 01 — DESCRIBE</div>
              <h1 className="text-4xl font-bold tracking-tight leading-tight mb-3 text-neutral-50">
                Opisz projekt, a wizard wypełni szablon.
              </h1>
              <p className="text-neutral-400 text-lg leading-relaxed">
                Kilka zdań o tym co budujesz, w jakim stacku, dla kogo.
                Wizard wygeneruje 4 pliki <span className="font-mono text-lime-400">CLAUDE.md</span>,
                <span className="font-mono text-lime-400"> ARCHITECTURE.md</span>,
                <span className="font-mono text-lime-400"> CONVENTIONS.md</span>,
                <span className="font-mono text-lime-400"> PLAN.md</span> i skopiuje do schowka.
              </p>
            </div>

            <div className="relative">
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder={`Np.:\n\nChatbot dla agencji nieruchomości w Warszawie. Osadzony na WordPressie przez widget Typebot. Logika w n8n (Code nodes w JS), embeddings przez OpenAI, sesje trzymane w Redis Upstash. Klient B2B, 2-tygodniowy sprint.`}
                rows={10}
                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-5 py-4 text-neutral-100 placeholder-neutral-600 font-mono text-sm leading-relaxed focus:outline-none focus:border-lime-600 transition resize-none"
              />
              <div className="absolute bottom-3 right-4 text-xs font-mono text-neutral-600">
                {description.length} znaków
              </div>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <div className="text-xs text-neutral-500">Minimum ~30 znaków żeby zaczął się sensowny output.</div>
              <button
                onClick={generateAll}
                disabled={description.trim().length < 30 || generating === 'all'}
                style={generating !== 'all' && description.trim().length >= 30 ? GLOW_SHADOW : {}}
                className="group flex items-center gap-2 bg-lime-400 hover:bg-lime-300 disabled:bg-neutral-800 disabled:text-neutral-600 text-neutral-950 font-semibold px-6 py-3 rounded-lg transition"
              >
                {generating === 'all' ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /><span>Generowanie ({progress.done}/{progress.total})...</span></>
                ) : (
                  <><Sparkles className="w-4 h-4" /><span>Generuj szablon</span><ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition" /></>
                )}
              </button>
            </div>
          </div>
        )}

        {phase === 'wizard' && (
          <div>
            <div className="mb-8">
              <div className="text-xs font-mono text-lime-400 mb-3 tracking-widest">// 02 — REVIEW & EDIT</div>
              <h1 className="text-3xl font-bold tracking-tight mb-2 text-neutral-50">Przejrzyj i popraw.</h1>
              <p className="text-neutral-400 text-sm">
                Każde pole jest edytowalne. Regeneruj sekcję lub pojedyncze pole.
              </p>
            </div>

            <div className="mb-6 bg-neutral-900 border border-neutral-800 rounded-lg p-5 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-mono text-neutral-500 mb-1.5 tracking-wide uppercase">Project title</label>
                  <input
                    value={projectTitle}
                    onChange={e => setProjectTitle(e.target.value)}
                    placeholder="np. Chatbot nieruchomości Warszawa"
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-neutral-100 focus:outline-none focus:border-lime-600 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-neutral-500 mb-1.5 tracking-wide uppercase flex items-center justify-between">
                    <span>Slug</span>
                    <span className="text-neutral-700 normal-case">
                      {slugManuallyEdited ? 'edytowany ręcznie' : 'auto z tytułu'}
                    </span>
                  </label>
                  <input
                    value={slug}
                    onChange={e => { setSlug(e.target.value); setSlugManuallyEdited(true); }}
                    placeholder="auto_generated_from_title"
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-lime-300 font-mono text-sm focus:outline-none focus:border-lime-600 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-neutral-500 mb-2 tracking-wide uppercase">Project tags</label>
                <div className="flex flex-wrap gap-1.5">
                  {AVAILABLE_TAGS.map(tag => (
                    <button
                      key={tag}
                      onClick={() => toggleTag(tag)}
                      className={`font-mono text-xs px-2.5 py-1 rounded border transition ${
                        tags.includes(tag)
                          ? 'bg-lime-900 border-lime-600 text-lime-300'
                          : 'bg-neutral-950 border-neutral-800 text-neutral-500 hover:border-neutral-700 hover:text-neutral-400'
                      }`}
                    >{tag}</button>
                  ))}
                </div>
              </div>
            </div>

            {Object.entries(SECTIONS).map(([sectionKey, section]) => {
              const isOpen = expanded[sectionKey];
              const isGenerating = generating === sectionKey;
              const { Icon } = section;
              return (
                <div key={sectionKey} className="mb-3 bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
                  <div className="flex items-center">
                    <button
                      onClick={() => toggleExpanded(sectionKey)}
                      className="flex-1 flex items-center gap-3 px-5 py-4 hover:bg-neutral-800 transition text-left"
                    >
                      {isOpen ? <ChevronDown className="w-4 h-4 text-neutral-500" /> : <ChevronRight className="w-4 h-4 text-neutral-500" />}
                      <Icon className="w-4 h-4 text-lime-500" />
                      <div className="flex-1">
                        <div className="font-mono text-sm text-neutral-200">{section.title}</div>
                        <div className="text-xs text-neutral-500">{section.subtitle}</div>
                      </div>
                    </button>
                    <button
                      onClick={() => regenerateSection(sectionKey)}
                      disabled={isGenerating || generating === 'all'}
                      className="flex items-center gap-1.5 text-xs font-mono text-neutral-500 hover:text-lime-400 disabled:opacity-30 px-4 py-4 border-l border-neutral-800 transition"
                    >
                      {isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                      <span className="hidden sm:inline">regen sekcji</span>
                    </button>
                  </div>

                  {isOpen && (
                    <div className="border-t border-neutral-800 p-5 space-y-4">
                      {section.fields.map(field => (
                        <FieldEditor
                          key={field.key}
                          field={field}
                          value={fields[field.key] || ''}
                          onChange={v => setFields(f => ({ ...f, [field.key]: v }))}
                          onRegenerate={() => regenerateField(field.key)}
                          regenerating={regeneratingField === field.key}
                          disabled={generating === 'all' || generating === sectionKey}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            <div className="mt-8 bg-neutral-900 border border-neutral-800 rounded-lg p-5">
              <div className="text-xs font-mono text-lime-400 mb-4 tracking-widest">// 03 — COPY & PASTE</div>

              <div className="flex items-start gap-3 mb-4">
                <input
                  id="logNotion"
                  type="checkbox"
                  checked={logToNotion}
                  onChange={e => setLogToNotion(e.target.checked)}
                  className="mt-1 accent-lime-500"
                />
                <label htmlFor="logNotion" className="text-sm">
                  <div className="text-neutral-300">Loguj do Notion</div>
                  <div className="text-xs text-neutral-500 mt-0.5">
                    Launcher zapisze wpis w bazie <span className="font-mono text-lime-400">🚀 CC_Launch_Queue</span> ze statusem <span className="font-mono text-lime-400">Provisioned</span> jako historia projektów.
                  </div>
                </label>
              </div>

              {!canSend && (
                <div className="text-xs text-amber-400 font-mono mb-4">
                  ⚠ Uzupełnij wszystkie pola przed wysłaniem.
                </div>
              )}

              <div className="flex items-center justify-between gap-4">
                <div className="text-xs text-neutral-500 font-mono">
                  target: <span className="text-lime-400">system clipboard</span>
                </div>
                <button
                  onClick={sendToLauncher}
                  disabled={!canSend}
                  style={canSend ? GLOW_SHADOW : {}}
                  className="flex items-center gap-2 bg-lime-400 hover:bg-lime-300 disabled:bg-neutral-800 disabled:text-neutral-600 text-neutral-950 font-semibold px-6 py-3 rounded-lg transition"
                >
                  <Copy className="w-4 h-4" />
                  <span>Wyślij do launchera</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {phase === 'export' && exportedPayload && (
          <div>
            <div className="mb-8 text-center">
              <div className={`inline-flex items-center justify-center w-16 h-16 rounded-full border mb-6 ${
                copyStatus === 'ok'
                  ? 'bg-lime-900 border-lime-600'
                  : 'bg-amber-900 border-amber-600'
              }`}>
                {copyStatus === 'ok'
                  ? <ClipboardCheck className="w-8 h-8 text-lime-400" />
                  : <AlertCircle className="w-8 h-8 text-amber-400" />
                }
              </div>
              <h1 className="text-3xl font-bold tracking-tight mb-3 text-neutral-50">
                {copyStatus === 'ok' ? 'Skopiowano do schowka.' : 'Nie udało się skopiować automatycznie.'}
              </h1>
              <p className="text-neutral-400 max-w-xl mx-auto">
                {copyStatus === 'ok' ? (
                  <>Teraz <span className="font-mono text-lime-400">dwuklik cc-paste.bat</span> na pulpicie — launcher odczyta schowek i utworzy projekt.</>
                ) : (
                  <>Zaznacz JSON poniżej i skopiuj ręcznie (Ctrl+A, Ctrl+C), potem dwuklik <span className="font-mono text-lime-400">cc-paste.bat</span>.</>
                )}
              </p>
            </div>

            {/* JSON preview / fallback manual copy */}
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden mb-6">
              <div className="flex items-center justify-between px-4 py-2 border-b border-neutral-800 bg-neutral-950">
                <span className="text-xs font-mono text-neutral-500 uppercase tracking-wide">
                  Payload (do schowka)
                </span>
                <button
                  onClick={recopyPayload}
                  className="flex items-center gap-1.5 text-xs font-mono text-neutral-400 hover:text-lime-400 transition"
                >
                  {copyStatus === 'ok' ? <ClipboardCheck className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copyStatus === 'ok' ? 'skopiowano' : 'kopiuj ponownie'}</span>
                </button>
              </div>
              <textarea
                value={exportedPayload}
                readOnly
                rows={14}
                onClick={e => e.target.select()}
                className="w-full bg-neutral-950 text-neutral-300 font-mono text-xs leading-relaxed px-4 py-3 focus:outline-none resize-y"
              />
            </div>

            {/* Next step card */}
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-5 mb-6">
              <div className="text-xs font-mono text-lime-400 mb-3 tracking-widest">// NEXT — NA PULPICIE</div>
              <div className="bg-neutral-950 border border-neutral-800 rounded-md px-4 py-3 font-mono text-sm text-lime-300 flex items-center gap-3">
                <Terminal className="w-4 h-4 text-neutral-600" />
                <span>cc-paste.bat</span>
              </div>
              <p className="text-xs text-neutral-500 mt-3">
                Launcher otworzy terminal, odczyta schowek, wygeneruje folder projektu, otworzy VS Code i uruchomi Claude Code.
              </p>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between gap-3">
              <button
                onClick={backToWizard}
                className="flex items-center gap-2 text-neutral-400 hover:text-neutral-200 font-medium px-4 py-2 transition"
              >
                ← Wróć i popraw
              </button>
              <button
                onClick={finishAndReset}
                className="flex items-center gap-2 bg-lime-400 hover:bg-lime-300 text-neutral-950 font-semibold px-5 py-2.5 rounded-lg transition"
              >
                <Sparkles className="w-4 h-4" />
                <span>Uruchomiłem — następny projekt</span>
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function FieldEditor({ field, value, onChange, onRegenerate, regenerating, disabled }) {
  const monoClass = field.mono ? "font-mono" : "";
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs font-mono text-neutral-500 tracking-wide uppercase">{field.label}</label>
        <button
          onClick={onRegenerate}
          disabled={regenerating || disabled}
          className="text-xs font-mono text-neutral-600 hover:text-lime-400 disabled:opacity-30 flex items-center gap-1 transition"
        >
          {regenerating ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          <span>regen</span>
        </button>
      </div>
      {field.type === 'text' ? (
        <input
          value={value}
          onChange={e => onChange(e.target.value)}
          disabled={disabled}
          className={`w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-lime-600 transition ${monoClass}`}
        />
      ) : (
        <textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          rows={field.rows || 4}
          disabled={disabled}
          className={`w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-lime-600 transition resize-y leading-relaxed ${monoClass}`}
        />
      )}
    </div>
  );
}