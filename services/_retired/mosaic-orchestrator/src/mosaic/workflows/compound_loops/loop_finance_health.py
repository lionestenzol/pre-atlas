"""Loop 10: Finance Health — transaction-based financial tracking.

Reads the financial ledger, computes budget variance, cash flow projection,
and alerts. Emits richer finance signals than the simple runway-based scoring.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult
from .finance_engine import compute_finance_health_signals, compute_cash_flow_projection


def compute_finance_health(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute finance health signals from the financial ledger."""
    ledger = snapshot.financial_ledger

    if "error" in ledger:
        return LoopResult(
            fired=False,
            input_summary="financial_ledger.json not available",
            output_summary="Skipped — no financial ledger data",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_finance_health_signals(ledger, now_iso)

    # Build signal delta
    signal_delta: dict[str, Any] = {
        "finance_health": {
            "runway_months": signals["runway_months"],
            "income_trend": signals["income_trend"],
            "avg_budget_variance": signals["avg_budget_variance"],
            "balance": signals["balance"],
            "projection_confidence": signals["projection_confidence"],
            "alert_count": signals["alert_count"],
        },
    }

    # Emit alerts for analyst decisions
    if signals["alerts"]:
        signal_delta["finance_alerts"] = signals["alerts"]

    # Generate cash flow projection
    projections = compute_cash_flow_projection(
        ledger.get("transactions", []),
        ledger.get("balance", 0),
        months_ahead=6,
        now_iso=now_iso,
    )
    if projections:
        # Check if any month goes negative
        negative_months = [p for p in projections if p["projected_balance"] < 0]
        if negative_months:
            signal_delta["cashflow_warning"] = (
                f"Balance projected negative by {negative_months[0]['month']}"
            )

    # Build summaries
    input_summary = (
        f"Balance: ${signals['balance']:.0f}, "
        f"{signals['transaction_count']} transactions, "
        f"runway: {signals['runway_months']}mo"
    )

    output_parts = [f"Runway: {signals['runway_months']}mo"]
    if signals["income_trend"] != 0:
        direction = "up" if signals["income_trend"] > 0 else "down"
        output_parts.append(f"Income trend: {direction} {abs(signals['income_trend']):.0%}")
    if signals["alert_count"] > 0:
        output_parts.append(f"{signals['alert_count']} alerts")
    output_parts.append(f"Confidence: {signals['projection_confidence']:.0%}")

    return LoopResult(
        fired=True,
        input_summary=input_summary,
        output_summary=" | ".join(output_parts),
        signal_delta=signal_delta,
        confidence=signals["projection_confidence"],
    )
