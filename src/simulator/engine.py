from __future__ import annotations

from .models import (
    PRICING,
    Activity,
    DualSimResult,
    Profile,
    SceneResult,
    Scenario,
    SimResult,
)

AUTOCOMPACT_BUFFER = 33_000


def simulate(profile: Profile, scenario: Scenario) -> SimResult:
    history_tokens = 0
    cumulative_cost = 0.0
    scene_results: list[SceneResult] = []
    autocompact_count = 0
    total_in = total_out = total_cached = 0

    rates = PRICING[profile.model]

    for i, scene in enumerate(scenario.scenes, 1):
        tool_in  = scene.tool_input_tokens
        tool_out = scene.tool_output_tokens

        cached_history   = int(history_tokens * profile.cache_hit_rate)
        uncached_history = history_tokens - cached_history

        input_tokens  = (
            profile.static_overhead
            + scene.user_message_tokens
            + uncached_history
            + tool_in
        )
        cached_tokens = cached_history
        output_tokens = scene.assistant_response_tokens + tool_out

        total_ctx = (
            profile.static_overhead
            + history_tokens
            + input_tokens
            + output_tokens
        )

        autocompact_fired = False
        if total_ctx > profile.autocompact_token_threshold:
            history_tokens = AUTOCOMPACT_BUFFER
            autocompact_fired = True
            autocompact_count += 1
        else:
            history_tokens += (
                scene.user_message_tokens
                + output_tokens
                + tool_in
                + tool_out
            )

        cost = (
            input_tokens  * rates["input"]      / 1_000_000
            + cached_tokens * rates["cache_read"] / 1_000_000
            + output_tokens * rates["output"]     / 1_000_000
        )
        cumulative_cost += cost
        total_in     += input_tokens
        total_out    += output_tokens
        total_cached += cached_tokens

        scene_results.append(SceneResult(
            scene=scene,
            scene_number=i,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_ctx_tokens=total_ctx,
            history_tokens=history_tokens,
            cost_usd=cost,
            cumulative_cost_usd=cumulative_cost,
            autocompact_fired=autocompact_fired,
            ctx_pct=total_ctx / profile.ctx_limit * 100,
        ))

    return SimResult(
        profile=profile,
        scenario=scenario,
        scene_results=scene_results,
        total_cost_usd=cumulative_cost,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cached_tokens=total_cached,
        autocompact_count=autocompact_count,
    )


def simulate_dual(profile_a: Profile, profile_b: Profile, scenario: Scenario) -> DualSimResult:
    return DualSimResult(
        result_a=simulate(profile_a, scenario),
        result_b=simulate(profile_b, scenario),
    )
