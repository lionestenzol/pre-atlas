"""Pure-function finance engine for the Finance agent.

All functions are pure: data in, result out. Zero I/O.
Handles transaction summaries, budget variance, cash flow projection, and alerts.
"""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone
from typing import Any


BUDGET_CATEGORIES: list[str] = [
    "housing", "utilities", "software", "groceries", "transport",
    "health", "entertainment", "savings", "business", "other",
]

DEFAULT_THRESHOLDS: dict[str, float] = {
    "runway_critical_months": 1.0,
    "runway_warning_months": 2.0,
    "budget_breach_pct": 1.2,
    "expense_spike_pct": 1.5,
}


def compute_monthly_summary(
    transactions: list[dict[str, Any]],
    month: str,
) -> dict[str, Any]:
    """Compute income, expenses, net, and by-category breakdown for a month.

    Args:
        transactions: List of transaction dicts
        month: YYYY-MM format
    """
    income = 0.0
    expenses = 0.0
    by_category: dict[str, float] = {}

    for txn in transactions:
        txn_date = txn.get("date", "")
        if not txn_date.startswith(month):
            continue

        amount = txn.get("amount", 0)
        category = txn.get("category", "other")

        if amount >= 0:
            income += amount
        else:
            expenses += abs(amount)

        by_category[category] = by_category.get(category, 0) + amount

    return {
        "month": month,
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "net": round(income - expenses, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items())},
        "transaction_count": sum(1 for t in transactions if t.get("date", "").startswith(month)),
    }


def compute_budget_variance(
    budgets: dict[str, dict[str, Any]],
    transactions: list[dict[str, Any]],
    month: str,
) -> list[dict[str, Any]]:
    """Compute budget variance per category for a month."""
    # Sum expenses by category for the month
    spent: dict[str, float] = {}
    for txn in transactions:
        if not txn.get("date", "").startswith(month):
            continue
        amount = txn.get("amount", 0)
        if amount < 0:
            cat = txn.get("category", "other")
            spent[cat] = spent.get(cat, 0) + abs(amount)

    variances: list[dict[str, Any]] = []
    for cat, budget in budgets.items():
        limit = budget.get("monthly_limit", 0)
        cat_spent = spent.get(cat, 0)

        if limit > 0:
            variance_pct = cat_spent / limit
        else:
            variance_pct = 0.0 if cat_spent == 0 else float("inf")

        variances.append({
            "category": cat,
            "monthly_limit": limit,
            "spent": round(cat_spent, 2),
            "remaining": round(max(0, limit - cat_spent), 2),
            "variance_pct": round(variance_pct, 2),
            "over_budget": cat_spent > limit if limit > 0 else False,
        })

    return sorted(variances, key=lambda v: -v["variance_pct"])


def compute_cash_flow_projection(
    transactions: list[dict[str, Any]],
    current_balance: float,
    months_ahead: int = 12,
    now_iso: str = "",
) -> list[dict[str, Any]]:
    """Project cash flow for the next N months based on recurring + historical averages."""
    # Identify recurring transactions
    recurring_income = 0.0
    recurring_expenses = 0.0
    for txn in transactions:
        if not txn.get("recurring", False):
            continue
        amount = txn.get("amount", 0)
        if amount >= 0:
            recurring_income += amount
        else:
            recurring_expenses += abs(amount)

    # Compute historical monthly averages (from all non-recurring)
    monthly_totals: dict[str, dict[str, float]] = {}
    for txn in transactions:
        if txn.get("recurring", False):
            continue
        date = txn.get("date", "")
        if len(date) < 7:
            continue
        month = date[:7]
        if month not in monthly_totals:
            monthly_totals[month] = {"income": 0.0, "expenses": 0.0}
        amount = txn.get("amount", 0)
        if amount >= 0:
            monthly_totals[month]["income"] += amount
        else:
            monthly_totals[month]["expenses"] += abs(amount)

    # Average non-recurring income/expenses
    if monthly_totals:
        months_with_data = len(monthly_totals)
        avg_extra_income = sum(m["income"] for m in monthly_totals.values()) / months_with_data
        avg_extra_expenses = sum(m["expenses"] for m in monthly_totals.values()) / months_with_data
    else:
        avg_extra_income = 0.0
        avg_extra_expenses = 0.0

    monthly_income = recurring_income + avg_extra_income
    monthly_expenses = recurring_expenses + avg_extra_expenses

    # Build projection
    try:
        now = datetime.fromisoformat(now_iso) if now_iso else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        now = datetime.now(timezone.utc)

    projections: list[dict[str, Any]] = []
    running_balance = current_balance

    for i in range(months_ahead):
        month_num = now.month + i
        year = now.year + (month_num - 1) // 12
        month = ((month_num - 1) % 12) + 1
        month_str = f"{year}-{month:02d}"

        running_balance += monthly_income - monthly_expenses

        projections.append({
            "month": month_str,
            "projected_income": round(monthly_income, 2),
            "projected_expenses": round(monthly_expenses, 2),
            "projected_balance": round(running_balance, 2),
        })

    return projections


def compute_runway(balance: float, avg_monthly_burn: float) -> float:
    """Compute months of runway. Returns inf if no burn."""
    if avg_monthly_burn <= 0:
        return 99.0  # No burn = infinite runway (capped)
    return round(balance / avg_monthly_burn, 1)


def detect_alerts(
    ledger: dict[str, Any],
    now_iso: str,
) -> list[dict[str, Any]]:
    """Detect financial alerts based on thresholds."""
    alerts: list[dict[str, Any]] = []
    thresholds = ledger.get("alert_thresholds", DEFAULT_THRESHOLDS)
    transactions = ledger.get("transactions", [])
    budgets = ledger.get("budgets", {})
    balance = ledger.get("balance", 0)

    # Compute current month for budget checks
    try:
        now = datetime.fromisoformat(now_iso)
    except (ValueError, TypeError):
        now = datetime.now(timezone.utc)
    current_month = f"{now.year}-{now.month:02d}"

    # Monthly burn from all expenses this month
    month_expenses = sum(
        abs(t.get("amount", 0))
        for t in transactions
        if t.get("amount", 0) < 0 and t.get("date", "").startswith(current_month)
    )

    # Estimate monthly burn from recurring if no transactions this month
    if month_expenses == 0:
        month_expenses = sum(
            abs(t.get("amount", 0))
            for t in transactions
            if t.get("recurring", False) and t.get("amount", 0) < 0
        )

    # Fallback: use budget total limits as estimated burn
    if month_expenses == 0:
        month_expenses = sum(b.get("monthly_limit", 0) for b in budgets.values())

    runway = compute_runway(balance, month_expenses)

    # Runway alerts
    if runway < thresholds.get("runway_critical_months", 1):
        alerts.append({
            "type": "runway_critical",
            "severity": "HIGH",
            "message": f"Runway at {runway} months — below {thresholds['runway_critical_months']}mo critical threshold",
            "created_at": now_iso,
        })
    elif runway < thresholds.get("runway_warning_months", 2):
        alerts.append({
            "type": "runway_warning",
            "severity": "MEDIUM",
            "message": f"Runway at {runway} months — below {thresholds['runway_warning_months']}mo warning threshold",
            "created_at": now_iso,
        })

    # Budget breach alerts
    breach_pct = thresholds.get("budget_breach_pct", 1.2)
    variances = compute_budget_variance(budgets, transactions, current_month)
    for v in variances:
        if v["over_budget"] and v["variance_pct"] >= breach_pct:
            alerts.append({
                "type": "budget_breach",
                "severity": "HIGH",
                "message": f"{v['category']}: spent ${v['spent']:.0f} vs ${v['monthly_limit']:.0f} limit ({v['variance_pct']:.0%})",
                "created_at": now_iso,
            })

    return alerts


def compute_finance_health_signals(
    ledger: dict[str, Any],
    now_iso: str,
) -> dict[str, Any]:
    """Aggregate finance health signals for compound scoring."""
    transactions = ledger.get("transactions", [])
    budgets = ledger.get("budgets", {})
    balance = ledger.get("balance", 0)

    try:
        now = datetime.fromisoformat(now_iso)
    except (ValueError, TypeError):
        now = datetime.now(timezone.utc)

    current_month = f"{now.year}-{now.month:02d}"

    # Previous month for trend comparison
    prev_month_num = now.month - 1 if now.month > 1 else 12
    prev_year = now.year if now.month > 1 else now.year - 1
    prev_month = f"{prev_year}-{prev_month_num:02d}"

    current_summary = compute_monthly_summary(transactions, current_month)
    prev_summary = compute_monthly_summary(transactions, prev_month)

    # Income trend
    if prev_summary["income"] > 0:
        income_trend = (current_summary["income"] - prev_summary["income"]) / prev_summary["income"]
    else:
        income_trend = 1.0 if current_summary["income"] > 0 else 0.0

    # Budget variance average
    variances = compute_budget_variance(budgets, transactions, current_month)
    active_budgets = [v for v in variances if v["monthly_limit"] > 0]
    avg_variance = (
        sum(v["variance_pct"] for v in active_budgets) / len(active_budgets)
        if active_budgets else 0.0
    )

    # Runway
    monthly_burn = current_summary["expenses"] or sum(b.get("monthly_limit", 0) for b in budgets.values())
    runway = compute_runway(balance, monthly_burn)

    # Alerts
    alerts = detect_alerts(ledger, now_iso)

    # Projection confidence based on data points
    data_points = len(transactions)
    if data_points >= 30:
        projection_confidence = 1.0
    elif data_points >= 10:
        projection_confidence = 0.7
    elif data_points > 0:
        projection_confidence = 0.4
    else:
        projection_confidence = 0.1

    return {
        "runway_months": runway,
        "income_trend": round(income_trend, 2),
        "avg_budget_variance": round(avg_variance, 2),
        "balance": balance,
        "monthly_income": current_summary["income"],
        "monthly_expenses": current_summary["expenses"],
        "alert_count": len(alerts),
        "alerts": alerts,
        "projection_confidence": projection_confidence,
        "transaction_count": data_points,
    }


def add_transaction(
    ledger: dict[str, Any],
    amount: float,
    category: str,
    description: str = "",
    recurring: bool = False,
    date: str = "",
    tags: list[str] | None = None,
    now_iso: str = "",
) -> dict[str, Any]:
    """Return new ledger with transaction added. Immutable — does not mutate input."""
    updated = copy.deepcopy(ledger)

    if not date:
        try:
            date = datetime.fromisoformat(now_iso).strftime("%Y-%m-%d") if now_iso else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    txn_id = f"txn_{hashlib.sha256(f'{date}:{amount}:{category}:{now_iso}'.encode()).hexdigest()[:12]}"

    txn = {
        "id": txn_id,
        "date": date,
        "amount": amount,
        "category": category if category in BUDGET_CATEGORIES else "other",
        "description": description,
        "recurring": recurring,
        "tags": tags or [],
    }

    updated["transactions"].append(txn)
    updated["balance"] = updated.get("balance", 0) + amount
    updated["generated_at"] = now_iso or datetime.now(timezone.utc).isoformat()

    return updated, txn_id
