<!-- CLAUDE v1.1 -->

# system-start

Pliki CLAUDE,ARCHITECTURE,PLAN,CONVENTIONS . Zmiany w tych plikach są kontrolowane przez skrypt pythona deterministyczne a subagenci ingerują tylko w przypadku awarii. Wszystkie pozycje są zmapowane w notion i kontrolowane 2 razy na okno a jedyny edytowalny plik w trakcie pracy to PLAN.md. Po zakończeniu rundy. PLAN.md jest czyszczony z wykonanych zadań i innych wpisów. Informację które chciały się zapisać do pozostałych MD są przetwarzane i po rundzie i segregowane w opodwiednie miejsca, Po wygenerowaniu szablonu.md urchomiony jest plan mode na tej podstawie jest poprawiany szablon następnie .Jedyne zmiany sa w PLAN.md za cały proces odpowiada SKILL za zmiany w plikach python  według decyzjii Agenta ze SKILL

## Imports
<!-- SECTION:imports -->
@ARCHITECTURE.md
@PLAN.md
@CONVENTIONS.md
<!-- /SECTION:imports -->

## Project
<!-- SECTION:project -->
- name: System do zarządzania przebiegiem pracy z w projektem Claude Code
- type: other
- client: własny
- stack: Dobierz
<!-- /SECTION:project -->

## Off Limits
<!-- SECTION:off_limits -->
- nie edytuj CLAUDE.md, ARCHITECTURE.md ani CONVENTIONS.md ręcznie w trakcie sesji
- nie pomijaj walidacji pythonowego skryptu kontrolnego przy zmianach plików MD
- nie zapisuj informacji poza PLAN.md podczas aktywnej rundy
<!-- /SECTION:off_limits -->

## Specifics
<!-- SECTION:specifics -->
- PLAN.md to jedyny plik edytowalny w trakcie rundy – wszystkie inne zmiany przechodzą przez skrypt Python
- po zakończeniu rundy PLAN.md jest czyszczony; informacje segregowane do odpowiednich MD przez SKILL
- subagenci ingerują tylko przy awarii skryptu deterministycznego, nie jako domyślny przepływ
- szablon.md generowany jest przed uruchomieniem plan mode – kolejność ma znaczenie
<!-- /SECTION:specifics -->
