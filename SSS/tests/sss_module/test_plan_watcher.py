from src.cm.sss_module.core.plan_watcher import _parse_plan


def test_parse_plan_extracts_sections():
    text = """
## Meta
<!-- SECTION:meta -->
- status: active
- goal: MVP
<!-- /SECTION:meta -->

## Next
<!-- SECTION:next -->
- [ ] task A
<!-- /SECTION:next -->
"""
    sections = _parse_plan(text)
    assert "meta" in sections
    assert "next" in sections
    assert "status: active" in sections["meta"]
    assert "task A" in sections["next"]


def test_parse_plan_empty_section():
    text = "<!-- SECTION:done --><!-- /SECTION:done -->"
    sections = _parse_plan(text)
    assert sections["done"] == ""


def test_parse_plan_unknown_sections_ignored():
    text = "<!-- SECTION:current -->content<!-- /SECTION:current -->"
    sections = _parse_plan(text)
    assert sections["current"] == "content"
