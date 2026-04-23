from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .models import SimResult


@dataclass
class CalibrationReport:
    session_id: str
    scene_count: int
    mae_input: float
    mae_output: float
    total_sim_cost: float
    total_real_cost: float
    cost_error_pct: float
    per_scene: list[dict]


def compare_with_tost(
    sim_result: SimResult,
    tost_db_path: str,
    session_id: str,
) -> CalibrationReport:
    """
    Porownuje wynik symulacji z prawdziwymi deltami z bazy TOST.

    Wymaga: tost.db z tabela metric_snapshots (delta_input, delta_output, delta_cost).
    Mapowanie: scena N → delta N (po kolei, zakladamy ze sceny = wiadomosci w sesji).
    """
    conn = sqlite3.connect(tost_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT delta_input, delta_output, delta_cost FROM metric_snapshots "
        "WHERE session_id = ? AND (delta_input > 0 OR delta_output > 0) "
        "ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()

    n = min(len(sim_result.scene_results), len(rows))
    if n == 0:
        raise ValueError("Brak danych do kalibracji")

    per_scene: list[dict] = []
    for i in range(n):
        sr   = sim_result.scene_results[i]
        real = rows[i]
        delta_pct = (
            (sr.input_tokens - real["delta_input"]) / real["delta_input"] * 100
            if real["delta_input"] > 0
            else 0.0
        )
        per_scene.append({
            "scene_number": i + 1,
            "sim_input":    sr.input_tokens,
            "real_input":   real["delta_input"],
            "delta_pct":    delta_pct,
        })

    mae_input = sum(abs(s["sim_input"] - s["real_input"]) for s in per_scene) / n
    total_sim_cost  = sim_result.total_cost_usd
    total_real_cost = sum(r["delta_cost"] for r in rows[:n])
    cost_error_pct  = (
        (total_sim_cost - total_real_cost) / total_real_cost * 100
        if total_real_cost > 0
        else 0.0
    )

    return CalibrationReport(
        session_id=session_id,
        scene_count=n,
        mae_input=mae_input,
        mae_output=0.0,  # TODO: dodac mae_output po rozszerzeniu schematu TOST
        total_sim_cost=total_sim_cost,
        total_real_cost=total_real_cost,
        cost_error_pct=cost_error_pct,
        per_scene=per_scene,
    )


def calc_mae(values: list[tuple[float, float]]) -> float:
    """Pomocnicza — MAE dla par (simulated, real). Przydatna w testach."""
    if not values:
        return 0.0
    return sum(abs(s - r) for s, r in values) / len(values)
