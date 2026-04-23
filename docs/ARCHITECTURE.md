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
      tost.py                # launchers dla zewnetrznego narzedzia TOST
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
