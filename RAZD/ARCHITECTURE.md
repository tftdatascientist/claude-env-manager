<!-- ARCHITECTURE v1.0 -->

## Overview
<!-- SECTION:overview -->
RAZD to trójwarstwowy moduł PySide6 wpięty w Claude Env Manager. Warstwa Tracker zbiera niskopoziomowe sygnały aktywności (aktywne okno, URL z przeglądarki, idle/active) przez polling co 2s. Strumień zdarzeń JSON trafia do Claude Code Agenta (claude-agent-sdk, persistent session), który kategoryzuje aktywność, buduje bazę wiedzy o procesach i URLach, a gdy napotka coś nieznanego — wystawia pytanie do usera przez dialog Qt. Warstwa UI to dwie zakładki: Time Tracking (oś czasu, kategorie, statystyki dzień/tydzień) i Focus Timer (timer 30-120min, whitelist appek, ping przy ucieczce z fokusu).
<!-- /SECTION:overview -->

## Components
<!-- SECTION:components -->
- Tracker: psutil (lista procesów), pywin32 (GetForegroundWindow + GetLastInputInfo dla idle), uiautomation (extract URL z address bar Chrome/Edge)
- Event stream: JSON lines do agenta, schema {ts, event_type, process, window_title, url?, idle_seconds}
- Claude Code Agent: claude-agent-sdk Python, persistent ClaudeSDKClient z system promptem trackingu, tools = [save_category, ask_user, query_knowledge]
- Knowledge base: lokalny SQLite (events, processes, categories, url_mappings, user_decisions)
- UI: PySide6 widget RazdMainWindow z QTabWidget, wpięty do CEM przez plugin pattern
- TimeTrackingTab: oś czasu (QGraphicsView lub custom), agregacja godzin per kategoria, eksport CSV
- FocusTimerTab: QListWidget whitelist + QSpinBox czas (30/60/90/120) + QTimer + QSystemTrayIcon do alertów
- Question dialog: Qt modal pytający o nieznany proces/URL, odpowiedź zasila bazę wiedzy
<!-- /SECTION:components -->

## Data Flow
<!-- SECTION:data_flow -->
[Tracker poll 2s] → [event JSON] → [Claude Code Agent persistent session]
                                                  ↓
                                           [Knowledge SQLite ← zapis kategoryzacji]
                                                  ↓
                                           [PySide6 TimeTrackingTab — update osi czasu]

[Agent napotyka nieznany proces] → [QDialog pytanie do usera] → [odpowiedź] → [agent → SQLite]

[FocusTimer start] → [whitelist appek] → [QTimer countdown 30-120min]
                                              ↓
                          [Tracker wykrywa app spoza whitelisty]
                                              ↓
                          [QSystemTrayIcon ping + modal dialog: wracaj lub zatrzymaj]
<!-- /SECTION:data_flow -->

## External Deps
<!-- SECTION:external_deps -->
<!-- /SECTION:external_deps -->

## Decisions
<!-- SECTION:decisions -->
- [x] AI engine = Claude Code przez claude-agent-sdk, nie bezpośredni Claude API | 2026-04-29 | spójność z preferencjami usera (CC robi maks roboty), pełne agentic capabilities, tool use bez własnego harnessa
- [x] knowledge base lokalny SQLite, nie Notion | 2026-04-29 | zero latencji sieci, działa offline; eksport do Notion można dorobić w fazie 2
- [x] tracking polling co 2s, nie event-driven (SetWinEventHook) | 2026-04-29 | prostsze, deterministyczne, niskie zużycie CPU; event hooks na fazę 2 jeśli potrzeba
- [x] PySide6 moduł CEM, nie oddzielna app | 2026-04-29 | jeden install, jedno menu, spójność stacku z CEM
- [x] Windows-only na MVP | 2026-04-29 | pywin32 + uiautomation są Windows-specific; Linux/Mac na fazę 2 z innymi API
<!-- /SECTION:decisions -->

## Constraints
<!-- SECTION:constraints -->
- Windows 10/11 only (pywin32, uiautomation API)
- Wymaga zainstalowanego Claude Code SDK + aktywnej subskrypcji/API key
- Claude Code Agent musi być uruchamiany w QThread (nie blokować UI)
- URL extraction tylko z Chrome/Edge na MVP (Firefox UI Automation jest mniej stabilne)
- Privacy: URLs filtrujemy z tokenów/haseł przed zapisem do bazy
- Wszystkie operacje SQLite przez QThreadPool (Qt + SQLite + threading wymaga ostrożności)
<!-- /SECTION:constraints -->
