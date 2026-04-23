import pytest

from src.simulator.models import (
    ACTIVITY_REGISTRY,
    Activity,
    ModelTier,
    Profile,
    Scene,
    Scenario,
)
from src.simulator.engine import AUTOCOMPACT_BUFFER, simulate, simulate_dual
from src.simulator.calibrator import calc_mae


def make_profile(**kwargs) -> Profile:
    defaults = dict(
        name="Test",
        model=ModelTier.SONNET_4,
        system_prompt_tokens=1000,
        system_tools_tokens=500,
        skills_tokens=0,
        mcp_tokens=0,
        plugins_tokens=0,
        memory_tokens=0,
        global_claude_md_lines=0,
        project_claude_md_lines=0,
        cache_hit_rate=0.0,
        ctx_limit=200_000,
        autocompact_threshold=0.90,
    )
    defaults.update(kwargs)
    return Profile(**defaults)


def make_scene(user: int = 200, resp: int = 800, activities=None) -> Scene:
    return Scene(
        user_message_tokens=user,
        assistant_response_tokens=resp,
        activities=activities or [],
    )


# ---------------------------------------------------------------------------
# models.py
# ---------------------------------------------------------------------------

def test_static_overhead_calculation():
    p = make_profile(
        system_prompt_tokens=1000,
        system_tools_tokens=500,
        global_claude_md_lines=10,
        line_token_ratio=10.0,
    )
    assert p.static_overhead == 1000 + 500 + 100  # claude_md = 10 * 10


def test_activity_tokens_added():
    activity = Activity(activity_id="file_read", count=2)
    scene = make_scene(activities=[activity])
    assert scene.tool_input_tokens  == ACTIVITY_REGISTRY["file_read"].input_tokens  * 2
    assert scene.tool_output_tokens == ACTIVITY_REGISTRY["file_read"].output_tokens * 2


# ---------------------------------------------------------------------------
# engine.py
# ---------------------------------------------------------------------------

def test_scene_cost_no_history():
    p = make_profile(system_prompt_tokens=5000, system_tools_tokens=0)
    scenario = Scenario(scenes=[make_scene(user=200, resp=800)])
    result = simulate(p, scenario)
    sr = result.scene_results[0]
    # overhead=5000, user=200, historia=0, tools=0
    assert sr.input_tokens  == 5000 + 200
    assert sr.cached_tokens == 0
    assert sr.output_tokens == 800


def test_history_accumulation():
    p = make_profile(system_prompt_tokens=1000, system_tools_tokens=0, cache_hit_rate=0.0)
    scene = make_scene(user=100, resp=200)
    scenario = Scenario(scenes=[scene, scene])
    result = simulate(p, scenario)
    # Po scenie 1: historia = user(100) + output(200) = 300
    # Scena 2 input = overhead(1000) + user(100) + history(300) = 1400
    assert result.scene_results[1].input_tokens == 1000 + 100 + 300


def test_cache_hit_reduces_cost():
    p_no_cache   = make_profile(cache_hit_rate=0.0,  model=ModelTier.OPUS_4)
    p_with_cache = make_profile(cache_hit_rate=0.70, model=ModelTier.OPUS_4)
    scene    = make_scene(user=100, resp=200)
    scenario = Scenario(scenes=[scene, scene, scene])
    r_no  = simulate(p_no_cache,   scenario)
    r_yes = simulate(p_with_cache, scenario)
    # Od sceny 2 czesc historii trafia w cache (tanszy cache_read)
    assert r_yes.total_cost_usd < r_no.total_cost_usd


def test_autocompact_fires():
    p = make_profile(
        system_prompt_tokens=1000,
        system_tools_tokens=0,
        cache_hit_rate=0.0,
        ctx_limit=10_000,
        autocompact_threshold=0.50,  # prog = 5000 tokenow
    )
    big_scene = make_scene(user=2000, resp=2000)
    scenario  = Scenario(scenes=[big_scene, big_scene, big_scene])
    result    = simulate(p, scenario)
    assert result.autocompact_count >= 1
    fired = [sr for sr in result.scene_results if sr.autocompact_fired]
    assert fired[0].history_tokens == AUTOCOMPACT_BUFFER


def test_two_profiles_delta():
    heavy = make_profile(system_prompt_tokens=10_000, system_tools_tokens=0, model=ModelTier.OPUS_4)
    light = make_profile(system_prompt_tokens=2_000,  system_tools_tokens=0, model=ModelTier.SONNET_4)
    scenario = Scenario(scenes=[make_scene() for _ in range(5)])
    dual = simulate_dual(heavy, light, scenario)
    assert dual.result_a.total_cost_usd > dual.result_b.total_cost_usd
    assert dual.savings_usd > 0
    assert 0.0 <= dual.savings_pct <= 100.0


def test_scene_number_increments():
    scenario = Scenario(scenes=[make_scene() for _ in range(3)])
    result   = simulate(make_profile(), scenario)
    numbers  = [sr.scene_number for sr in result.scene_results]
    assert numbers == [1, 2, 3]


def test_ctx_pct_calculated():
    p = make_profile(ctx_limit=200_000)
    scenario = Scenario(scenes=[make_scene()])
    result   = simulate(p, scenario)
    sr = result.scene_results[0]
    expected_pct = sr.total_ctx_tokens / 200_000 * 100
    assert abs(sr.ctx_pct - expected_pct) < 0.001


def test_empty_scenario():
    result = simulate(make_profile(), Scenario(scenes=[]))
    assert result.scene_results == []
    assert result.total_cost_usd == 0.0
    assert result.autocompact_count == 0


# ---------------------------------------------------------------------------
# calibrator.py
# ---------------------------------------------------------------------------

def test_calibrator_mae():
    pairs = [(1000.0, 900.0), (1200.0, 1100.0), (800.0, 850.0)]
    mae = calc_mae(pairs)
    expected = (100.0 + 100.0 + 50.0) / 3
    assert abs(mae - expected) < 0.001


def test_calibrator_mae_empty():
    assert calc_mae([]) == 0.0


def test_calibrator_mae_perfect():
    pairs = [(500.0, 500.0), (1000.0, 1000.0)]
    assert calc_mae(pairs) == 0.0
