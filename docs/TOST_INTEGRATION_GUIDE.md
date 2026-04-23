# TOST — Przewodnik integracyjny dla CLAUDE ENV Manager

> Dokument opisuje architekturę, API i punkty integracji narzędzia TOST (Token Optimization System Tool) — systemu monitorowania zużycia tokenów w Claude Code.

---

## 1. Czym jest TOST

TOST to lokalne narzędzie Python, które:

1. **Zbiera metryki OTLP** z Claude Code w czasie rzeczywistym (collector HTTP na porcie 4318)
2. **Zapisuje je do SQLite** z automatycznym obliczaniem delt (cumulative → per-message)
3. **Wyświetla dashboard TUI** (Textual) z podziałem na tokeny, koszt, overhead
4. **Symuluje koszty** różnych konfiguracji CC (full vs minimal, duel dwóch profili)
5. **Trenuje context engineering** z Haiku API (curriculum 5 modułów)
6. **Synchronizuje sesje do Notion** (parse JSONL → upsert do Notion DB)

---

## 2. Architektura

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                            │
│  (OTEL_METRICS_EXPORTER=otlp, endpoint=localhost:4318)      │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP POST /v1/metrics (protobuf)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  collector.py — aiohttp server (:4318)                      │
│  Parsuje ExportMetricsServiceRequest → MetricSnapshot       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  store.py — SQLite (tost.db)                                │
│  Tabela: metric_snapshots                                   │
│  Kolumny cumulative + delta (auto-obliczane przy INSERT)     │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         dashboard   simulator    duel
          (TUI)       (TUI)      (TUI)

┌─────────────────────────────────────────────────────────────┐
│  ~/.claude/projects/<encoded-cwd>/*.jsonl                   │
│  ↓ jsonl_scanner.py (parse + aggregate)                     │
│  ↓ notion_sync.py (HTTP → Notion API)                       │
│  → Notion Database (6b9e6206ca1f4097b342d3ecdf11598b)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Moduły i ich rola

| Moduł | Plik | Rola |
|-------|------|------|
| **CLI** | `tost/cli.py` | Dispatcher argparse — subkomendy: `monitor`, `sim`, `duel`, `train`, `sync` |
| **Config** | `tost/config.py` | Loader TOML (`tost.toml`) → dataclasses |
| **Collector** | `tost/collector.py` | Odbiornik OTLP HTTP (aiohttp), parsuje protobuf |
| **Store** | `tost/store.py` | SQLite CRUD + delta computation |
| **Cost** | `tost/cost.py` | Tabele cenowe Anthropic (Opus/Sonnet/Haiku) |
| **Baseline** | `tost/baseline.py` | Overhead: actual vs minimal config |
| **Dashboard** | `tost/dashboard.py` | TUI monitoring na żywo (Textual) |
| **Simulator** | `tost/simulator.py` | Silnik symulacji full vs minimal |
| **Sim Dashboard** | `tost/sim_dashboard.py` | TUI symulatora |
| **Duel** | `tost/duel.py` | Porównanie dwóch profili CC |
| **Duel Dashboard** | `tost/duel_dashboard.py` | TUI trybu duel |
| **Trainer** | `tost/trainer.py` | Curriculum context engineering + Haiku API |
| **Trainer Dashboard** | `tost/trainer_dashboard.py` | TUI trenera |
| **JSONL Scanner** | `tost/jsonl_scanner.py` | Parser plików sesji CC → `SessionAggregate` |
| **Notion Sync** | `tost/notion_sync.py` | Upsert sesji do Notion DB (ciągły lub jednorazowy) |

---

## 4. Konfiguracja wymagana w Claude Code

### 4.1. Zmienne środowiskowe OTEL (w `~/.claude/settings.json`)

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_METRIC_EXPORT_INTERVAL": "5000",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "cumulative"
  }
}
```

**To jest kluczowy punkt integracji z ENV Managerem** — te zmienne muszą być ustawione, aby TOST działał.

### 4.2. Plik konfiguracyjny TOST (`tost.toml`)

```toml
[collector]
host = "0.0.0.0"
port = 4318

[database]
path = "tost.db"

[baseline]
input_tokens_per_message = 3000
output_tokens_per_message = 100

[display]
refresh_interval = 2.0
```

### 4.3. Notion Sync (`.env` lub zmienne systemowe)

```
NOTION_TOKEN=ntn_xxxxx...
NOTION_DATABASE_ID=6b9e6206ca1f4097b342d3ecdf11598b
```

---

## 5. Punkty integracji z ENV Managerem

### 5.1. Zarządzanie zmiennymi OTEL

ENV Manager powinien umieć:

- **Włączyć/wyłączyć TOST** = ustawić/usunąć 6 zmiennych OTEL w `~/.claude/settings.json`
- **Zmienić port collectora** = zmodyfikować `OTEL_EXPORTER_OTLP_ENDPOINT`
- **Zmienić interwał eksportu** = zmodyfikować `OTEL_METRIC_EXPORT_INTERVAL` (ms)
- **Walidacja** = sprawdzić czy wartości są spójne (port w settings.json = port w tost.toml)

### 5.2. Uruchamianie komponentów TOST

| Komponent | Komenda | Tryb |
|-----------|---------|------|
| Monitor (dashboard + collector) | `tost` lub `tost monitor` | Foreground (TUI) |
| Collector only (headless) | `tost monitor --no-tui` | Background daemon |
| Simulator | `tost sim` | Foreground (TUI) |
| Duel | `tost duel` | Foreground (TUI) |
| Trainer | `tost train` | Foreground (TUI) |
| Notion sync (ciągły) | `tost sync -v` | Background daemon |
| Notion sync (jednorazowy) | `tost sync --once -v` | One-shot |

### 5.3. Status / Health check

ENV Manager może sprawdzić czy TOST działa:

```python
# Czy collector nasłuchuje?
import aiohttp
async with aiohttp.ClientSession() as s:
    # Collector nie ma health endpointu — ale można sprawdzić port
    pass

# Czy baza danych istnieje i ma dane?
from tost.store import Store
store = Store("tost.db")
sessions = store.get_all_sessions()  # lista dict
active = store.get_active_session_id()  # str | None
store.close()
```

### 5.4. Odczyt danych z TOST

**Przez Store API (SQLite):**

```python
from tost.store import Store

store = Store("path/to/tost.db")

# Aktualna sesja
session_id = store.get_active_session_id()

# Podsumowanie sesji (tokeny + koszt)
totals = store.get_session_totals(session_id)
# → { session_id, model, input_tokens, output_tokens, 
#     cache_read_tokens, cache_creation_tokens, cost_usd }

# Historia wiadomości (delty)
deltas = store.get_session_deltas(session_id, limit=50)
# → [{ delta_input, delta_output, delta_cache_read, 
#       delta_cache_creation, delta_cost, received_at, ... }]

# Wszystkie sesje
all_sessions = store.get_all_sessions()
store.close()
```

**Przez Cost API:**

```python
from tost.cost import calculate_cost, format_cost, resolve_model

cost = calculate_cost("claude-opus-4", input_tokens=3100, 
                       output_tokens=800, cache_read_tokens=2100, 
                       cache_creation_tokens=1500)
print(format_cost(cost))  # "$0.093"
```

**Przez JSONL Scanner (sesje CC bez OTLP):**

```python
from tost.jsonl_scanner import scan_session_file, scan_all_sessions
from pathlib import Path

# Skanuj wszystkie sesje
root = Path.home() / ".claude" / "projects"
for agg in scan_all_sessions(root):
    print(f"{agg.session_id}: {agg.total_tokens} tok, ${agg.cost_usd:.3f}")
    # agg.session_id, agg.project, agg.primary_model, agg.started_at,
    # agg.last_message_at, agg.message_count, agg.input_tokens, 
    # agg.output_tokens, agg.cache_read_tokens, agg.cache_creation_tokens
```

---

## 6. Schematy baz danych

### 6.1. OTLP Store (`tost.db`)

```sql
CREATE TABLE metric_snapshots (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    session_id            TEXT    NOT NULL,
    model                 TEXT    NOT NULL,
    input_tokens          INTEGER NOT NULL DEFAULT 0,   -- cumulative
    output_tokens         INTEGER NOT NULL DEFAULT 0,   -- cumulative
    cache_read_tokens     INTEGER NOT NULL DEFAULT 0,   -- cumulative
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,   -- cumulative
    cost_usd              REAL    NOT NULL DEFAULT 0.0,  -- cumulative
    delta_input           INTEGER NOT NULL DEFAULT 0,   -- per-message
    delta_output          INTEGER NOT NULL DEFAULT 0,   -- per-message
    delta_cache_read      INTEGER NOT NULL DEFAULT 0,   -- per-message
    delta_cache_creation  INTEGER NOT NULL DEFAULT 0,   -- per-message
    delta_cost            REAL    NOT NULL DEFAULT 0.0   -- per-message
);
-- Indexy: idx_session(session_id), idx_received(received_at)
```

### 6.2. Notion Sync State (`~/.claude/tost_notion.db`)

```sql
CREATE TABLE notion_file_mtimes (
    file_path TEXT PRIMARY KEY,
    mtime     REAL NOT NULL
);

CREATE TABLE notion_pages (
    session_id  TEXT PRIMARY KEY,
    page_id     TEXT NOT NULL,
    last_synced REAL NOT NULL DEFAULT 0
);
```

---

## 7. Tabele cenowe (cost.py)

| Model | Input | Output | Cache Read | Cache Creation |
|-------|-------|--------|------------|----------------|
| claude-opus-4 | $15.00/1M | $75.00/1M | $1.50/1M | $18.75/1M |
| claude-sonnet-4 | $3.00/1M | $15.00/1M | $0.30/1M | $3.75/1M |
| claude-haiku-4 | $0.80/1M | $4.00/1M | $0.08/1M | $1.00/1M |

Funkcja `resolve_model()` matchuje nazwy z suffixami (np. `claude-opus-4-20250514` → `claude-opus-4`).

---

## 8. Metryki OTLP zbierane przez collector

| Metryka | Atrybuty | Wartość |
|---------|----------|---------|
| `claude_code.token.usage` | `session.id`, `model`, `type` (input/output/cacheRead/cacheCreation) | int — cumulative token count |
| `claude_code.cost.usage` | `session.id`, `model` | float — cumulative USD |

Collector parsuje protobuf `ExportMetricsServiceRequest` i tworzy `MetricSnapshot` z zagregowanymi wartościami per `(session_id, model)`.

---

## 9. Simulator — profil komponentów

Simulator modeluje token overhead różnych konfiguracji CC. Kluczowe komponenty i ich koszty tokenowe:

### Komponenty sesji (jednorazowe)

| Komponent | Tokeny | Opis |
|-----------|--------|------|
| System prompt (base) | 4500 | Bazowy prompt CC |
| Skills catalog | 5200 | Lista załadowanych skill'ów |
| Plugin: superpowers | 3800 | Plugin rozszerzony |
| Plugin: vercel | 2400 | Integracja Vercel |
| Plugin: frontend-design | 1200 | Skill frontend |
| Plugin: code-review | 800 | Skill code review |
| Plugin: claude-md-management | 600 | Zarządzanie CLAUDE.md |
| Hooks definitions | 460 | Definicje hooków |

### Komponenty per-message (powtarzane)

| Komponent | Tokeny | Opis |
|-----------|--------|------|
| System prompt (base) | 4500 | Powtórzenie bazowego promptu |
| Auto-memory instructions | 2800 | Instrukcje systemu pamięci |
| Project memory (MEMORY.md) | 1900 | Zawartość pamięci projektu |
| Skills reminder | 1200 | Przypomnienie o skill'ach |
| Deferred tools catalog | 800 | Katalog narzędzi odroczonych |
| Git status context | 500 | Status repozytorium |
| MCP tool descriptions | 350 | Opisy narzędzi MCP |
| Global CLAUDE.md | 20 | Globalne instrukcje |

**Suma per-message overhead (full config):** ~12,070 tokenów  
**Minimal config per-message:** ~4,500 tokenów (sam system prompt)

---

## 10. CLI — pełna specyfikacja

```
tost [command] [options]

Commands:
  monitor (default)   Live dashboard + OTLP collector
  sim                 Cost simulator (full vs minimal)
  duel                Profile comparison
  train               Context engineering trainer
  sync                Notion session sync

Monitor options:
  --config PATH       Path to tost.toml
  --port INT          Collector port (default: 4318)
  --session ID        Track specific session
  --db PATH           SQLite database path
  --no-tui            Run collector without dashboard
  --verbose           Enable debug logging

Sync options:
  --once              Single sync run, then exit
  --interval FLOAT    Sync interval in seconds (default: 60)
  --verbose           Enable debug logging
```

Entry point: `tost.cli:main` (zarejestrowany w `pyproject.toml` jako `[project.scripts]`).

---

## 11. Instalacja i zależności

```toml
# pyproject.toml
requires-python = ">=3.11"
dependencies = [
    "aiohttp>=3.9",
    "protobuf>=4.25",
    "opentelemetry-proto>=1.25",
    "textual>=0.70",
    "python-dotenv>=1.0",
]
```

Instalacja: `pip install -e .` w katalogu projektu.

---

## 12. Pliki konfiguracyjne i ścieżki

| Plik | Ścieżka | Rola |
|------|---------|------|
| Settings CC | `~/.claude/settings.json` | Zmienne OTEL (env section) |
| Config TOST | `<project>/tost.toml` | Port, baza, baseline, refresh |
| Baza OTLP | `<project>/tost.db` | Metryki z collectora |
| Baza Notion state | `~/.claude/tost_notion.db` | Mtime'y + mapowanie session→page |
| Sesje CC (JSONL) | `~/.claude/projects/<encoded-cwd>/*.jsonl` | Surowe logi sesji CC |
| Credentiale Notion | `<project>/.env` | `NOTION_TOKEN`, `NOTION_DATABASE_ID` |

---

## 13. Wzorce integracji dla ENV Managera

### A. Profil "TOST enabled"

ENV Manager tworzy preset zawierający:
1. Zmienne OTEL w `~/.claude/settings.json` → `env` section
2. Autostart collectora (headless) przy uruchomieniu CC
3. Opcjonalny autostart Notion sync

### B. Odczyt metryk w ENV Manager UI

```python
# Szybki odczyt aktualnego zużycia
from tost.store import Store
store = Store("C:/Users/Sławek/Documents/.MD/PARA/SER/10_PROJEKTY/SIDE/PRAWY/tost.db")
totals = store.get_session_totals()
if totals:
    print(f"Sesja: {totals['session_id'][:8]}")
    print(f"Model: {totals['model']}")
    print(f"Input: {totals['input_tokens']:,}")
    print(f"Output: {totals['output_tokens']:,}")
    print(f"Koszt: ${totals['cost_usd']:.3f}")
store.close()
```

### C. Walidacja konfiguracji

```python
# Sprawdź czy settings.json ma wymagane OTEL vars
import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"
settings = json.loads(settings_path.read_text())
env = settings.get("env", {})

REQUIRED_OTEL_VARS = {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_METRIC_EXPORT_INTERVAL": "5000",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "cumulative",
}

missing = {k: v for k, v in REQUIRED_OTEL_VARS.items() if env.get(k) != v}
if missing:
    print(f"Brakujące/niepoprawne zmienne OTEL: {list(missing.keys())}")
else:
    print("TOST: konfiguracja OTEL OK")
```

### D. Programmatic control

```python
# Uruchomienie collectora z poziomu kodu
import asyncio
from tost.store import Store
from tost.collector import run_collector

store = Store("tost.db")
asyncio.run(run_collector(store, host="0.0.0.0", port=4318))

# Uruchomienie Notion sync z poziomu kodu
from tost.notion_sync import NotionConfig, run_sync_loop

cfg = NotionConfig(token="secret_xxx", database_id="6b9e...")
asyncio.run(run_sync_loop(cfg, once=True))
```

---

## 14. Podsumowanie — co ENV Manager musi wiedzieć

| Aspekt | Wartość |
|--------|---------|
| **Język** | Python 3.11+ |
| **Instalacja** | `pip install -e <path>` |
| **Entry point** | `tost` (CLI) lub `python -m tost` |
| **Główna baza** | `tost.db` (SQLite, w katalogu projektu) |
| **Wymagane env vars** | 6 zmiennych OTEL w `~/.claude/settings.json` |
| **Port domyślny** | 4318 (OTLP HTTP) |
| **Notion env** | `NOTION_TOKEN`, `NOTION_DATABASE_ID` |
| **Daemon'y** | Collector (port 4318), Notion sync (co 60s) |
| **TUI framework** | Textual (wymaga terminal) |
| **API do danych** | `tost.store.Store`, `tost.cost`, `tost.jsonl_scanner` |
