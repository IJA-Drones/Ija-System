"""One Brasília time interval shared by cache, GPS recovery and the UI."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

BRAZIL = ZoneInfo("America/Sao_Paulo")
MAX_DAYS = 15


@dataclass(frozen=True)
class TrackingPeriod:
    start: datetime
    end: datetime  # Exclusive; the last minute chosen in the UI is inclusive.

    @property
    def day(self):
        return self.start.date()

    def payload(self):
        return {"start": self.start.strftime("%Y-%m-%dT%H:%M"),
                "end": (self.end - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M"),
                "start_at": self.start.isoformat(), "end_before": self.end.isoformat(),
                "max_days": MAX_DAYS}

    def utc_bounds(self):
        return tuple(value.astimezone(timezone.utc).replace(tzinfo=None) for value in (self.start, self.end))


def parse_tracking_period(values, now=None):
    now = now or datetime.now(BRAZIL)
    raw_start, raw_end = values.get("start"), values.get("end")
    if raw_start or raw_end:
        if not raw_start or not raw_end:
            raise ValueError("Informe o início e o fim do período.")
        try:
            start, finish = (datetime.fromisoformat(value) for value in (raw_start, raw_end))
        except (ValueError, TypeError):
            raise ValueError("Informe datas e horários válidos para o período.") from None
        start = start.replace(tzinfo=BRAZIL) if start.tzinfo is None else start.astimezone(BRAZIL)
        finish = finish.replace(tzinfo=BRAZIL) if finish.tzinfo is None else finish.astimezone(BRAZIL)
        start = start.replace(second=0, microsecond=0)
        end = finish.replace(second=0, microsecond=0) + timedelta(minutes=1)
    else:
        try:
            day = datetime.strptime(values.get("date", ""), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            day = now.date()
        start = datetime.combine(day, time.min, BRAZIL)
        end = datetime.combine(day + timedelta(days=1), time.min, BRAZIL)
    if end <= start:
        raise ValueError("O fim do período deve ser igual ou posterior ao início.")
    if end - start > timedelta(days=MAX_DAYS):
        raise ValueError(f"Selecione um período de até {MAX_DAYS} dias.")
    if start.date() > now.date() or end > datetime.combine(now.date() + timedelta(days=1), time.min, BRAZIL):
        raise ValueError("O período não pode incluir dias futuros.")
    return TrackingPeriod(start, end)
