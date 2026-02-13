"""
Stress test de timezone/horário.

Valida:
1. Cálculo de "agora" em vários timezones (datetime.now(ZoneInfo(...)))
2. Próxima execução em cron em diferentes fusos (São Paulo, Lisboa, Tóquio, UTC)
3. Comparação de timestamps em UTC (time.time() vs next_run_at_ms)
4. Consistência entre timezones e conversão para UTC

Requer: tzdata (pip install tzdata) no Windows para ZoneInfo funcionar.
Execute com: uv run pytest tests/test_timezone_stress.py -v
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

# Skip se ZoneInfo não suportar os timezones (Windows sem tzdata)
try:
    ZoneInfo("UTC")
    _TZDATA_AVAILABLE = True
except Exception:
    _TZDATA_AVAILABLE = False

# croniter pode não estar no projeto; import condicional
try:
    import croniter
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False


# Timezones para testes
TIMEZONES = [
    "America/Sao_Paulo",
    "Europe/Lisbon",
    "Asia/Tokyo",
    "UTC",
    "America/New_York",
    "Europe/London",
]

pytestmark = pytest.mark.skipif(not _TZDATA_AVAILABLE, reason="tzdata necessário (pip install tzdata) no Windows")


def test_datetime_now_multiple_timezones():
    """Valida que datetime.now(ZoneInfo(...)) retorna horários consistentes em cada fuso."""
    base_utc = datetime.now(ZoneInfo("UTC"))
    base_ts = base_utc.timestamp()

    for tz_name in TIMEZONES:
        tz = ZoneInfo(tz_name)
        now_local = datetime.now(tz)
        now_utc = now_local.astimezone(ZoneInfo("UTC"))
        # A diferença deve ser pequena (menos de 2 segundos)
        diff = abs(now_utc.timestamp() - base_ts)
        assert diff < 2.0, f"{tz_name}: diff={diff}s"


def test_time_time_utc_consistency():
    """Valida que time.time() está alinhado com datetime UTC."""
    t1 = time.time()
    dt_utc = datetime.now(ZoneInfo("UTC"))
    t2 = time.time()
    ts = dt_utc.timestamp()
    assert t1 <= ts <= t2 or abs(ts - (t1 + t2) / 2) < 2.0


def test_cron_next_run_sao_paulo():
    """Valida próxima execução em cron no fuso de São Paulo."""
    if not HAS_CRONITER:
        pytest.skip("croniter não instalado")

    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime.now(tz)
    cron = croniter.croniter("0 * * * *", now)  # Todo minuto na hora cheia
    next_run = cron.get_next(datetime)
    next_utc = next_run.astimezone(ZoneInfo("UTC"))
    next_ts = next_utc.timestamp()

    now_utc = datetime.now(ZoneInfo("UTC"))
    assert next_ts > now_utc.timestamp(), "Próxima execução deve ser no futuro"


def test_cron_next_run_lisbon():
    """Valida próxima execução em cron no fuso de Lisboa."""
    if not HAS_CRONITER:
        pytest.skip("croniter não instalado")

    tz = ZoneInfo("Europe/Lisbon")
    now = datetime.now(tz)
    cron = croniter.croniter("30 8 * * *", now)  # 8:30 todo dia
    next_run = cron.get_next(datetime)
    next_utc = next_run.astimezone(ZoneInfo("UTC"))
    assert next_utc.timestamp() > time.time()


def test_cron_next_run_tokyo():
    """Valida próxima execução em cron no fuso de Tóquio."""
    if not HAS_CRONITER:
        pytest.skip("croniter não instalado")

    tz = ZoneInfo("Asia/Tokyo")
    now = datetime.now(tz)
    cron = croniter.croniter("0 9 * * 1-5", now)  # 9h dias úteis
    next_run = cron.get_next(datetime)
    next_utc = next_run.astimezone(ZoneInfo("UTC"))
    assert next_utc.timestamp() > time.time()


def test_timestamp_comparison_utc():
    """Compara time.time() com next_run_at em ms (simulando backend)."""
    if not HAS_CRONITER:
        pytest.skip("croniter não instalado")

    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime.now(tz)
    cron = croniter.croniter("0 * * * *", now)
    next_run = cron.get_next(datetime)
    next_run_ms = int(next_run.astimezone(ZoneInfo("UTC")).timestamp() * 1000)
    now_ms = int(time.time() * 1000)

    assert next_run_ms > now_ms


def test_stress_multiple_cron_expressions():
    """Stress: várias expressões cron em vários timezones."""
    if not HAS_CRONITER:
        pytest.skip("croniter não instalado")

    expressions = ["0 * * * *", "*/5 * * * *", "0 0 * * *", "0 12 * * 0"]
    for tz_name in TIMEZONES:
        for expr in expressions:
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
            cron = croniter.croniter(expr, now)
            next_run = cron.get_next(datetime)
            next_utc = next_run.astimezone(ZoneInfo("UTC"))
            assert next_utc.timestamp() > time.time() - 3600  # não deve ser muito no passado


def test_stress_1000_timezone_conversions():
    """Stress: 1000 conversões de timezone sem erro."""
    base = datetime.now(ZoneInfo("UTC"))
    for _ in range(1000):
        for tz_name in TIMEZONES:
            tz = ZoneInfo(tz_name)
            local = base.astimezone(tz)
            back = local.astimezone(ZoneInfo("UTC"))
            assert abs(back.timestamp() - base.timestamp()) < 0.001
