# ============================================================
# SLA Penalty Calculator — KB Tender RFB IN-KBL-543730-NC-RFB §5.1B
#
# Monthly target schedule (hours):
#   Month 1→50, 2→55, 3→100, 4→125, 5→100, 6→125,
#   7→100, 8→125, 9→100, 10→125, 11→100
#
# Penalty table (applied to that month's payment):
#   Shortfall < 5%   → 0% deduction
#   5% ≤ shortfall < 10%  → 2% deduction
#   10% ≤ shortfall < 20% → 4% deduction
#   shortfall ≥ 20%  → 5% deduction
# ============================================================

# Monthly target hours per KB tender delivery schedule
MONTHLY_SCHEDULE: dict[int, float] = {
    1: 50, 2: 55, 3: 100, 4: 125, 5: 100,
    6: 125, 7: 100, 8: 125, 9: 100, 10: 125, 11: 100,
}

# Penalty brackets: (shortfall_threshold_pct, deduction_pct)
# Evaluated in order — first matching bracket wins
_PENALTY_BRACKETS = [
    (5.0,  0.0),   # < 5% shortfall → no penalty
    (10.0, 2.0),   # 5–10% → 2%
    (20.0, 4.0),   # 10–20% → 4%
    (100.0, 5.0),  # > 20% → 5%
]


def target_hours(month: int) -> float:
    """Return the contracted target hours for a given month (1-based)."""
    return MONTHLY_SCHEDULE.get(month, 0.0)


def sla_penalty_pct(shortfall_pct: float) -> float:
    """
    Return the deduction percentage for a given shortfall percentage.
    shortfall_pct = (target - delivered) / target * 100
    Negative shortfall (over-delivery) → 0% penalty.
    """
    if shortfall_pct <= 0:
        return 0.0
    for threshold, deduction in _PENALTY_BRACKETS:
        if shortfall_pct < threshold:
            return deduction
    return _PENALTY_BRACKETS[-1][1]


def compute_sla(month: int, delivered_hours: float) -> dict:
    """
    Compute full SLA result for a month.

    Returns:
        month              : int
        target_hours       : float
        delivered_hours    : float
        shortfall_hours    : float  (negative = over-delivery)
        shortfall_pct      : float
        penalty_pct        : float  (deduction applied to that month's payment)
        status             : str    ("✅ On track" | "⚠️ Minor shortfall" | "❌ Penalty applies")
    """
    target = target_hours(month)
    shortfall_h = max(0.0, target - delivered_hours)
    shortfall_pct = (shortfall_h / target * 100) if target > 0 else 0.0
    penalty = sla_penalty_pct(shortfall_pct)

    if penalty == 0.0:
        status = "✅ On track" if shortfall_pct < 5.0 else "✅ No penalty (<5% shortfall)"
    elif penalty <= 2.0:
        status = "⚠️ 2% deduction (5–10% shortfall)"
    elif penalty <= 4.0:
        status = "⚠️ 4% deduction (10–20% shortfall)"
    else:
        status = "❌ 5% deduction (>20% shortfall)"

    return {
        "month":           month,
        "target_hours":    round(target, 2),
        "delivered_hours": round(delivered_hours, 2),
        "shortfall_hours": round(shortfall_h, 2),
        "shortfall_pct":   round(shortfall_pct, 2),
        "penalty_pct":     penalty,
        "status":          status,
    }


def compute_sla_multi(monthly_delivered: dict[int, float]) -> list[dict]:
    """
    Compute SLA for multiple months.
    monthly_delivered: {month_number: hours_delivered}
    Returns list of compute_sla() dicts, one per month.
    """
    return [compute_sla(m, monthly_delivered.get(m, 0.0))
            for m in sorted(monthly_delivered)]


def format_sla_report(sla_rows: list[dict]) -> str:
    """Format SLA results as a human-readable text table."""
    lines = [
        "KB Tender §5.1B — Monthly SLA Report",
        "=" * 70,
        f"{'Month':<8} {'Target':>8} {'Delivered':>10} {'Shortfall':>10} {'Shortfall%':>11} {'Penalty':>8}  Status",
        "-" * 70,
    ]
    for r in sla_rows:
        lines.append(
            f"Month {r['month']:<2} {r['target_hours']:>8.1f} {r['delivered_hours']:>10.1f} "
            f"{r['shortfall_hours']:>10.1f} {r['shortfall_pct']:>10.1f}% "
            f"{r['penalty_pct']:>7.0f}%  {r['status']}"
        )
    lines.append("-" * 70)
    total_target    = sum(r["target_hours"]    for r in sla_rows)
    total_delivered = sum(r["delivered_hours"] for r in sla_rows)
    total_shortfall = sum(r["shortfall_hours"] for r in sla_rows)
    lines.append(
        f"{'TOTAL':<8} {total_target:>8.1f} {total_delivered:>10.1f} "
        f"{total_shortfall:>10.1f}"
    )
    return "\n".join(lines)
