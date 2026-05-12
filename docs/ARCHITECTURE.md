# Architektura CEM — szczegółowy opis modułów

## Zakladki glownego okna (QTabWidget, Ctrl+1..6)

| Zakladka | Klasa | Plik |
|----------|-------|------|
| Resources | `EditorPanel` | `src/ui/editor_panel.py` |
| Projects | `HistoryPanel` | `src/ui/history_panel.py` |
| Active Projects | `ActiveProjectsPanel` | `src/ui/active_projects_panel.py` |
| Websites | `WebsiteProjectsPanel` | `src/ui/website_projects_panel.py` |
| Hidden | `HiddenProjectsPanel` | `src/ui/hidden_projects_panel.py` |
| Simulator | `SimulatorPanel` | `src/ui/simulator/simulator_panel.py` |
| Sesje CC | `CCLauncherPanel` | `src/ui/cc_launcher_panel.py` |

## CCLauncherPanel — zakładki slotu (`ProjectSlotWidget`)

Każdy z 4 slotów zawiera wewnętrzny `QTabWidget` z zakładkami:

| Indeks | Nazwa | Zawartość |
|--------|-------|-----------|
| 0 | Config | Ścieżka + parametry CC + prompt startowy (splitter poziomy: lewa = config, prawa = statystyki) |
| 1 | Monitor | `_MonitorView` — lista slotów po lewej, szczegóły po prawej (SSS: bufor, plain: ostatnia wiadomość) |
| 2 | Historia | Sesje CC, transkrypt |
| 3 | ZADANIA | Generator zadań do PLAN.md przez CC subprocess (`_build_plan`) |
| 4 | Prompt Score | `_PromptScorePanel` |
| 5 | PLAN.md | PCC view (Widok / Edytor) |
| 6+ | CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md, Logi, Full Converter | |

### Config — parametry uruchomienia CC

Sekcja "Parametry uruchomienia CC" zawiera:
- **Ścieżka projektu** — edytowalne pole + przycisk Browse
- **Model / Effort / Uprawnienia** — combo boxy
- **Tryb sesji** — radio: Nowa / Wznów (`--resume`) / Kontynuuj (`--continue`)
- **Opcje** — checkboxy: Verbose (`--verbose`) / Bez aktualizacji (`--no-update-check`)
- **Przed CC** — komenda PowerShell/bash uruchamiana przed `cc` (np. aktywacja venv)
- **Flagi CC** — dowolne dodatkowe flagi CLI (np. `--add-dir`, `--output-format`)
- **Prompt startowy** — tekst wklejany do terminala CC po załadowaniu

Flagi z checkboxów/radio są kompilowane do `SlotConfig.cc_flags` w `get_config()`.
Pole `cc_flags` trafia do `launch-request.json` jako `"ccFlags"` i jest odczytywane przez cc-panel.

### Monitor — `_MonitorView`

Widok podzielony na lewą (lista slotów) i prawą (szczegóły):
- **Lista slotów** (lewa, 170px) — przyciski T1–T4 z fazą CC i skrótem SSS meta; kliknięcie przełącza slot
- **Szczegóły** (prawa) — stack z 3 stronami:
  - **SSS** (idx 0): meta (runda/sesja/next/done) + bufor wpisów z podziałem na Aktywne / Rozdzielone
  - **Plain CC** (idx 1): metryki (model/koszt/ctx%) + pole ostatniej wiadomości
  - **Pusty slot** (idx 2)
- Odświeżanie: przy każdym `_on_snapshot`, `_on_sss_detected`, zmianie slotu

### ZADANIA — generator zadań przez CC

Układ splitter poziomy:
- **Lewa** — pole opisu zamierzenia + wybór modelu + przyciski Generuj/Stop/status
- **Prawa górna** — edytowalna lista zadań `- [ ] ...` + przycisk "Zapisz do PLAN.md"
- **Prawa dolna** — log CC (surowy output)

Pipeline generowania:
1. Prompt = system prompt + CLAUDE.md + PLAN.md + ARCHITECTURE.md + opis zamierzenia
2. Prompt zapisywany do pliku tymczasowego (obejście ograniczenia stdin w QProcess)
3. CC uruchamiane przez `cmd /c "type prompt.txt | claude -p --output-format stream-json"`
4. Stream parsowany live — linie `- [ ] ...` wyświetlane na bieżąco
5. Zapis do PLAN.md: `write_section(text, "next", ...)` (PCC v2) lub append `## Next` (plain)

**Ograniczenie:** `claude -p` wisi gdy uruchamiany jako subprocess aktywnej sesji CC
(blokada auth socketu). Obejście: plik tymczasowy + izolacja `CC_PANEL_TERMINAL_ID` z env.

### SlotConfig — pola persystowane

| Pole | Typ | Opis |
|------|-----|------|
| `project_path` | str | Ścieżka katalogu projektu |
| `model` | str | Model CC CLI |
| `effort` | str | Poziom wysiłku |
| `permission_mode` | str | Klucz trybu uprawnień |
| `pre_command` | str | Komenda przed CC (terminal) |
| `cc_flags` | str | Skompilowane flagi CC (tryb sesji + checkboxy + ręczne) |
| `vibe_prompt` | str | Prompt startowy wklejany po uruchomieniu CC |

### cc-panel — integracja z `launch-request.json`

Pola zapisywane do `~/.claude/cc-panel/launch-request.json`:

| Pole JSON | Źródło w CM | Obsługa w cc-panel |
|-----------|-------------|-------------------|
| `slotId` | numer slotu | wybór terminala |
| `projectPath` | `project_path` | cwd terminala |
| `terminalCount` | globalna liczba terminali | liczba spawniętych terminali |
| `model` | `model` | `--model X` w komendzie CC |
| `permissionFlag` | `permission_mode` | flaga uprawnień |
| `preCommand` | `pre_command` | `sendText(preCommand)` przed CC (t=300ms) |
| `ccFlags` | `cc_flags` | dołączane do komendy CC po model/perm |
| `vibePrompt` | `vibe_prompt` | `sendText(prompt)` po załadowaniu CC (t=+3s) |

## Struktura katalogów

```
claude-env-manager/
  main.py                    # entry point; globalny dark stylesheet QApplication
  launcher.pyw               # launcher bez okna konsoli
  create_shortcut.py
  src/
    scanner/
      discovery.py           # discover_all() — skanuje 6 poziomow zasobow
      indexer.py             # build_tree() — buduje TreeNode hierarchy
    models/
      resource.py            # Resource, ResourceType, ResourceScope
      project.py             # Project
      history.py             # HistoryEntry
    simulator/
      models.py              # Profile, Scene, Activity, Scenario, SimResult, DualSimResult,
                             # ACTIVITY_REGISTRY, PRICING, ModelTier
      engine.py              # simulate(), simulate_dual(), AUTOCOMPACT_BUFFER
      calibrator.py          # CalibrationReport, compare_with_tost(), calc_mae()
      storage.py             # SimulatorStorage — load/save simulator_data.json
      preset_scenes.py       # PresetScene, PRESET_SCENES (10 scen), PRESET_BY_KEY
      preset_data.py         # PRESET_PROFILES (5), PRESET_SCENARIOS (10), _make_scenarios()
    ui/
      main_window.py         # MainWindow — menu, splitter, 6 zakladek, sygnaly
      status_bar.py          # StatusBar (niebieski pasek dolny)
      tree_panel.py          # TreePanel — QTreeView zasobow CC
      editor_panel.py        # EditorPanel — podglad tresci zasobu
      history_panel.py       # HistoryPanel — drzewo projektow/watkow/wiadomosci
      active_projects_panel.py
      website_projects_panel.py
      hidden_projects_panel.py
      projektant_panel.py    # ProjectantPanel — PLAN.md (diff+sekcje) / PCC (sekcje semantyczne)
                             #   DiffView, PlanView, PlanSectionsPanel, PccView, PccSectionsPanel
      ai_project_wizard.py   # AIProjectWizardDialog — kreator projektu przez AI
      simulator/
        simulator_panel.py   # SimulatorPanel — glowny orkiestrator zakładki
        profile_editor.py    # ProfileEditor (QDialog)
        scene_builder.py     # SceneBuilder — przyciski aktywnosci
        results_view.py      # ResultsView — tabela wynikow
        context_widget.py    # ContextWidget — breakdown /context
    watchers/                # (stub — monitorowanie plikow przez watchdog)
    utils/
      paths.py               # centralne sciezki (Path.home() based)
      parsers.py             # read_text, parse_json, extract_frontmatter, detect_file_format
      security.py            # mask_dict, mask_value
      colors.py              # kolory kategorii drzewa, reset_colors()
      aliases.py             # aliasy nazw projektow
      relocations.py         # relokacje przeniesionych projektow
      active_projects.py     # lista pinowanych projektow
      website_projects.py    # lista projektow-stron WWW
      hidden_projects.py     # lista ukrytych projektow
      project_groups.py      # grupy projektow (ProjectGroup)
      plan_parser.py         # PlanData, get_section, read_plan, write_plan (PCC v2.0)
      tost.py                # launchers dla zewnetrznego narzedzia TOST
    workflow.py              # WorkflowRunner (QThread) — clean_plan, git_push, round_end
    projektant/
      template_parser.py     # Parser PCC v2.0: read/write_section, parse_dict/list, plan_*
      templates/             # Szablony MD: PLAN.md, CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md
    cc_launcher/
      launcher_config.py     # LauncherConfig, SlotConfig, load/save
      session_manager.py     # prepare_and_launch, open_vscode_window, terminate_vscode_session
      session_history.py     # SessionHistorySummary, get_session_history, fmt_duration
      project_stats.py       # ProjectStats, get_project_stats, fmt_size
    watchers/
      session_watcher.py     # SessionWatcher, TerminalSnapshot, read_transcript_tail
  planist/                   # Moduł PLANist — generator i walidator PLAN.md
    src/
      context_reader.py      # ProjectContext, read_context() — odczyt CLAUDE/ARCH/CONV/PLAN
      importance_scorer.py   # ImportanceScore, score() — ocena wagi projektu (0–1.0, granularność)
      plan_writer.py         # PlanWriter API: write_section, set_next/current, append_done/log
      planner.py             # generate_plan() — orchestracja: kontekst → prompt → cc --print → zapis
      validator.py           # validate_plan() — walidacja PCC v2.0, exit 0/1
      pcc_unpack.py          # unpack_payload() — JSON payload Wizarda → 4 pliki MD
      cli.py                 # Typer CLI: planist run / validate / unpack
      planist_runner.py      # PlanistRunner (QObject) + _PlanistWorker (QThread) — integracja CEM
      planist_panel.py       # PlanistPanel (PySide6) — widget do osadzenia w CEM
    templates/
      plan_template.md       # Szablon PLAN.md PCC v2.0
    tests/
      test_planner.py        # 15 testów: ContextReader, ImportanceScorer, PlanWriter
      test_validator.py      # 8 testów: validator.py
      test_pcc_unpack.py     # 7 testów: pcc_unpack.py
      test_runner_logic.py   # 8 testów: _generate_wrapper, _validate_wrapper
  tests/
    test_scanner.py
    test_parsers.py
    test_models.py
    test_simulator_engine.py  # 13 przypadkow: overhead, historia, cache, autocompact, MAE
```

## Pliki JSON w katalogu projektu

| Plik | Zawiera | Uwagi |
|------|---------|-------|
| `simulator_data.json` | Profile, sceny, scenariusze symulatora | Usun aby zresetowac do presetow |
| `colors_config.json` | Nadpisania kolorow kategorii drzewa | |
| `aliases.json` | Aliasy nazw projektow `{path: name}` | |
| `relocations.json` | Relokacje `{old_path: new_path}` | |
| `active_projects.json` | Pinowane projekty `[path, ...]` | |
| `website_projects.json` | Projekty-strony WWW `[path, ...]` | |
| `hidden_projects.json` | Ukryte projekty `[path, ...]` | |
| `project_groups.json` | Grupy projektow `[{main, members}]` | |

## Token Simulator v2 — architektura modułów

**Backend (`src/simulator/`):**
- `models.py` — dataclassy: `Profile`, `Scene`, `Activity`, `Scenario`, `SceneResult`, `SimResult`, `DualSimResult`; stala `ACTIVITY_REGISTRY` (20 aktywnosci), `PRICING` (3 modele)
- `engine.py` — `simulate()`, `simulate_dual()`, `AUTOCOMPACT_BUFFER=33_000`
- `calibrator.py` — `CalibrationReport`, `compare_with_tost()`, `calc_mae()`
- `storage.py` — `SimulatorStorage.load()/save()`; zapisuje sceny ze scenariuszy + biblioteki
- `preset_scenes.py` — 10 wbudowanych scen (`PresetScene`, `PRESET_SCENES`, `PRESET_BY_KEY`)
- `preset_data.py` — 5 profili (`PRESET_PROFILES`) + 10 scenariuszy (`PRESET_SCENARIOS`); ladowane przy pustym JSON

**UI (`src/ui/simulator/`):**
- `simulator_panel.py` — orkiestrator; animacja krokowa 1s/scena; przycisk Stop zatrzymuje i pokazuje wyniki natychmiast
- `profile_editor.py` — dialog edycji profilu (QDialog z QScrollArea)
- `scene_builder.py` — przyciski aktywnosci: LPM +1, PPM reset
- `results_view.py` — tabela wynikow; `show_step()` dla animacji, `show_dual()` dla finalnych wynikow
- `context_widget.py` — widget `/context` z paskiem postępu i breakdownem kategorii

**Presety:**
- 5 profili: Bare minimum (Haiku) / Light (Sonnet) / Standard (Sonnet) / Power (Opus) / Heavy Opus
- 10 scenariuszy: Typowy dzien / Bugfix / Feature E2E / Research / Refaktor / MCP+AI / Micro-tasks / Dluga sesja / Code review / Setup projektu

**Kluczowa zasada storage:** `save()` zbiera sceny ze scenariuszy ORAZ z biblioteki przed zapisem — dzieki temu `scene_ids` w JSON maja swoje definicje przy ponownym wczytaniu.

**Presety sa zawsze dostepne:** `_load_data` scala presety z tym co jest w JSON (wersja z JSON ma pierwszenstwo dla presetow o tym samym ID, wlasne scenariusze uzytkownika dochodza na koniec).
