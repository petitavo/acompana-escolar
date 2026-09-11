"""Única implementación de reconstrucción, calidad y referencia personal v1."""

from datetime import datetime, timedelta, time, date, timezone
from zoneinfo import ZoneInfo
from statistics import median
from sqlalchemy import select
from .db import *
from .config import FEATURE_VERSION
from .cases import add_reason

FEATURES = {
    "interactive_minutes": ("min", 15),
    "night_interactive_minutes": ("min", 15),
    "interactive_session_count": ("eventos", 5),
    "keyguard_hidden_count": ("eventos", 5),
}


def union(spans):
    merged = []
    for start, end in sorted(spans):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def overlap(spans, start, end):
    return sum(
        (b - a).total_seconds()
        for a, b in union(
            [(max(a, start), min(b, end)) for a, b in spans if b > start and a < end]
        )
    )


def reconstruct(events, windows):
    opened = None
    intervals = []
    discarded = []
    seen = set()
    for e in sorted(events, key=lambda e: (utc(e["occurred_at"]), e["id"])):
        at = utc(e["occurred_at"])
        kind = e["event_type"]
        key = (at, kind)
        if e.get("clock_flag"):
            discarded.append({"id": e["id"], "reason": "clock_flag"})
            continue
        if key in seen:
            discarded.append({"id": e["id"], "reason": "duplicate_state_event"})
            continue
        seen.add(key)
        if kind in ("DEVICE_STARTUP", "DEVICE_SHUTDOWN"):
            if opened:
                discarded.append({"id": opened["id"], "reason": "reboot_without_pair"})
                opened = None
        elif kind == "SCREEN_INTERACTIVE":
            if opened:
                discarded.append({"id": e["id"], "reason": "already_interactive"})
            else:
                opened = e
        elif kind == "SCREEN_NON_INTERACTIVE":
            if not opened:
                discarded.append({"id": e["id"], "reason": "missing_start"})
                continue
            start = utc(opened["occurred_at"])
            if overlap(windows, start, at) + 0.001 >= (at - start).total_seconds():
                intervals.append(
                    {
                        "start": start.isoformat(),
                        "end": at.isoformat(),
                        "events": [opened["id"], e["id"]],
                    }
                )
            else:
                discarded.append(
                    {
                        "id": opened["id"],
                        "reason": "unverified_gap",
                        "end_event": e["id"],
                    }
                )
            opened = None
    if opened:
        discarded.append({"id": opened["id"], "reason": "missing_end"})
    return intervals, discarded


def build_day(events, captures, day, zone="America/Lima", keyguard=True, cutoff=None):
    local = ZoneInfo(zone)
    d = date.fromisoformat(day)
    start = datetime.combine(d, time.min, local).astimezone(timezone.utc)
    end = datetime.combine(d + timedelta(days=1), time.min, local).astimezone(
        timezone.utc
    )
    night_start = datetime.combine(d, time(22), local).astimezone(timezone.utc)
    night_end = datetime.combine(d + timedelta(days=1), time(6), local).astimezone(
        timezone.utc
    )
    windows = union(
        [
            (utc(c["start_at"]), utc(c["end_at"]))
            for c in captures
            if c["detail"]["success"]
            and c["detail"]["permission_before"]
            and c["detail"]["permission_after"]
        ]
    )
    intervals, discarded = reconstruct(events, windows)
    spans = [(utc(i["start"]), utc(i["end"])) for i in intervals]
    incomplete = any(
        x["reason"]
        in ("missing_start", "missing_end", "unverified_gap", "reboot_without_pair")
        for x in discarded
    )
    failures = any(
        not c["detail"]["permission_before"] or not c["detail"]["permission_after"]
        for c in captures
        if utc(c["end_at"]) > start and utc(c["start_at"]) < night_end
    )
    quality = {}
    values = {}
    for name, (unit, _) in FEATURES.items():
        a, b = (
            (night_start, night_end)
            if name == "night_interactive_minutes"
            else (start, end)
        )
        coverage = overlap(windows, a, b) / (b - a).total_seconds()
        supported = keyguard if name == "keyguard_hidden_count" else True
        closed = cutoff is None or utc(cutoff) >= b
        eligible = (
            supported
            and closed
            and coverage >= 0.8
            and not failures
            and (not incomplete or name == "keyguard_hidden_count")
        )
        state = (
            "unsupported"
            if not supported
            else (
                "missing"
                if coverage == 0 or not closed
                else ("observed" if eligible else "partial")
            )
        )
        if state in ("missing", "unsupported"):
            value = None
        elif name.endswith("minutes"):
            value = round(overlap(spans, a, b) / 60, 3)
        elif name == "interactive_session_count":
            value = sum(a <= utc(i["start"]) < b for i in intervals)
        else:
            value = sum(
                a <= utc(e["occurred_at"]) < b
                and e["event_type"] == "KEYGUARD_HIDDEN"
                and not e.get("clock_flag")
                for e in events
            )
        values[name] = {
            "value": value,
            "unit": unit,
            "state": state,
            "eligible": eligible,
            "operational_coverage": round(coverage, 4),
            "window_start": a.isoformat(),
            "window_end": b.isoformat(),
        }
    return {
        "features": values,
        "lineage": {
            "intervals": intervals,
            "discarded": discarded,
            "capture_ids": [c["id"] for c in captures],
            "event_ids": [e["id"] for e in events],
        },
        "successful_queries": sum(c["detail"]["success"] for c in captures),
        "version": FEATURE_VERSION,
        "timezone": zone,
        "permission_evidence": "query_snapshots; no garantiza observación continua del fabricante",
    }


def deviation(days, cutoff, definitions=None):
    end = date.fromisoformat(cutoff)
    current_start = end - timedelta(days=7)
    reference_start = current_start - timedelta(days=28)
    result = {}
    eligible = False
    for name, (_, floor) in (definitions or FEATURES).items():
        ref = [
            x["features"][name]["value"]
            for day, x in days.items()
            if reference_start <= date.fromisoformat(day) < current_start
            and name in x["features"] and x["features"][name]["eligible"]
        ]
        cur = [
            x["features"][name]["value"]
            for day, x in days.items()
            if current_start <= date.fromisoformat(day) < end
            and name in x["features"] and x["features"][name]["eligible"]
        ]
        item = {
            "reference_days": len(ref),
            "current_days": len(cur),
            "state": "insufficient",
            "floor": floor,
        }
        if len(ref) >= 14 and len(cur) >= 5:
            baseline = median(ref)
            actual = median(cur)
            mad = median(abs(x - baseline) for x in ref)
            delta = actual - baseline
            item.update(
                state="available",
                baseline=baseline,
                current=actual,
                mad=mad,
                delta=delta,
                robust_deviation=delta / max(1.4826 * mad, floor),
                percent_change=100 * delta / baseline if baseline > 0 else None,
            )
            eligible = True
        result[name] = item
    return {
        "eligible": eligible,
        "features": result,
        "reference_start": str(reference_start),
        "reference_end": str(current_start),
        "current_start": str(current_start),
        "current_end": str(end),
        "candidate": any(
            abs(v.get("robust_deviation", 0)) >= 3 for v in result.values()
        ),
        "notice": "Cambio observado; parámetros de ingeniería, sin significado diagnóstico.",
    }


def process_device(db, device, start_day, end_day, version=FEATURE_VERSION):
    start = date.fromisoformat(start_day)
    end = date.fromisoformat(end_day)
    if end < start or (end - start).days > 90:
        raise ValueError("Rango de reproceso inválido; máximo 90 días")
    authorized = list(
        db.scalars(select(Interval).where(Interval.device_id == device.id))
    )

    def allowed(at):
        return any(
            utc(i.start_at) <= utc(at) and (i.end_at is None or utc(at) < utc(i.end_at))
            for i in authorized
        )

    raw = [
        public(r)
        for r in db.scalars(
            select(RawEvent)
            .where(RawEvent.device_id == device.id)
            .order_by(RawEvent.occurred_at)
        )
        if allowed(r.occurred_at)
    ]
    captures = [
        public(c)
        for c in db.scalars(select(Capture).where(Capture.device_id == device.id))
    ]
    latest = {}
    for row in db.scalars(
        select(Feature)
        .where(Feature.device_id == device.id)
        .order_by(Feature.created_at)
    ):
        latest[row.day] = row.detail
    for n in range((end - start).days + 1):
        day = start + timedelta(days=n)
        lo = datetime.combine(
            day, time.min, ZoneInfo(device.detail.get("timezone", "America/Lima"))
        ).astimezone(timezone.utc)
        hi = lo + timedelta(hours=32)
        # Only evidence available now, bounded around this local day; never fill an unobserved period.
        selected = [
            e for e in raw if lo - timedelta(days=1) <= utc(e["occurred_at"]) < hi
        ]
        selected_c = [
            c
            for c in captures
            if utc(c["end_at"]) > lo - timedelta(days=1) and utc(c["start_at"]) < hi
        ]
        value = build_day(
            selected,
            selected_c,
            str(day),
            device.detail.get("timezone", "America/Lima"),
            device.detail.get("keyguard_available", True),
            now(),
        )
        row = Feature(device_id=device.id, day=str(day), version=version, detail=value)
        db.add(row)
        latest[str(day)] = value
    db.flush()
    cutoff = str(end + timedelta(days=1))
    exists = db.scalar(
        select(Evaluation).where(
            Evaluation.participant_id == device.participant_id,
            Evaluation.cutoff == cutoff,
            Evaluation.version == version,
        )
    )
    if exists and MODE == "REAL":
        result = deviation(latest, cutoff)
        if exists.detail != result:
            exists.detail = result
            db.flush()
            persist_case(db, device.participant_id, exists)
    if not exists:
        result = deviation(latest, cutoff)
        evaluation = Evaluation(
            participant_id=device.participant_id,
            cutoff=cutoff,
            version=version,
            detail=result,
        )
        db.add(evaluation)
        db.flush()
        persist_case(db, device.participant_id, evaluation)
    return {"days": (end - start).days + 1, "version": version, "cutoff": cutoff}


def persist_case(db, pid, evaluation):
    rows = list(
        db.scalars(
            select(Evaluation)
            .where(
                Evaluation.participant_id == pid,
                Evaluation.cutoff <= evaluation.cutoff,
                Evaluation.version == evaluation.version,
            )
            .order_by(Evaluation.cutoff.desc())
            .limit(3)
        )
    )
    consecutive = len(rows) == 3 and all(
        (
            date.fromisoformat(rows[i].cutoff) - date.fromisoformat(rows[i + 1].cutoff)
        ).days
        == 1
        for i in (0, 1)
    )
    if consecutive and all(r.detail["candidate"] for r in rows):
        add_reason(
            db,
            pid,
            "behavior_change",
            {"evaluation_id": evaluation.id, **evaluation.detail},
        )
    elif MODE != "REAL" and consecutive and all(
        all(
            v["state"] == "available" and abs(v["robust_deviation"]) < 2
            for v in r.detail["features"].values()
        )
        for r in rows
    ):
        for case in db.scalars(
            select(Case).where(Case.participant_id == pid, Case.state != "closed")
        ):
            for reason in db.scalars(
                select(Reason).where(
                    Reason.case_id == case.id,
                    Reason.kind == "behavior_change",
                    Reason.active == True,
                )
            ):
                reason.active = False
                db.add(
                    CaseEvent(
                        case_id=case.id,
                        actor="worker",
                        kind="behavior_reason_resolved",
                        detail={"evaluation_id": evaluation.id},
                    )
                )
            db.flush()
            if case.state == "new" and not db.scalar(
                select(Reason).where(Reason.case_id == case.id, Reason.active == True)
            ):
                case.state = "closed"
                case.version += 1
                db.add(
                    CaseEvent(
                        case_id=case.id,
                        actor="worker",
                        kind="transition",
                        detail={
                            "state": "closed",
                            "reason": "Tres evaluaciones completas bajo umbral; solo motivo conductual",
                        },
                    )
                )
