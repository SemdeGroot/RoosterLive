import os
import sys
import subprocess
import time
import signal
from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parent

CELERY_STATE_DIR = PROJECT_ROOT / ".celery"
CELERY_STATE_DIR.mkdir(exist_ok=True)
CELERYBEAT_SCHEDULE = str(CELERY_STATE_DIR / "celerybeat-schedule")

# Gebruik exact dezelfde Python/venv waarmee je dit script start
PY = sys.executable

# Probeer celerey entrypoint in venv te vinden (Windows/Linux)
if os.name == "nt":
    CELERY_BIN = Path(PY).with_name("celery.exe")
else:
    CELERY_BIN = Path(PY).with_name("celery")

if not CELERY_BIN.exists():
    # fallback: roep "python -m celery" aan
    CELERY_CMD = [PY, "-m", "celery"]
else:
    CELERY_CMD = [str(CELERY_BIN)]

env = os.environ.copy()
# Zet default envs als ze nog niet staan
env.setdefault("REDIS_URL", "redis://127.0.0.1:6379/1")
env.setdefault("CELERY_BROKER_URL", "redis://127.0.0.1:6379/2")
env.setdefault("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/3")
env.setdefault("PYTHONUNBUFFERED", "1")

print("🔧 Starting Redis, Postgres and Pgbouncer via docker compose...")
subprocess.run(
    [
        "docker",
        "compose",
        "-f",
        "deploy/docker-compose.dev.yml",
        "up",
        "-d",
        "--remove-orphans",
        "redis",
        "db",
        "pgbouncer",
    ],
    check=True,
)

# Wacht even tot Redis gezond is
time.sleep(3)

print("🚀 Starting Django development server...")
django_proc = subprocess.Popen(
    [PY, "manage.py", "runserver", "0.0.0.0:8000"],
    cwd=str(PROJECT_ROOT),
    env=env,
)

# Op Windows prefork geeft ellende -> solo pool + 1 concurrency
print("⚙️ Starting Celery worker...")
worker_proc = subprocess.Popen(
    CELERY_CMD
    + [
        "-A", "rooster_site",
        "worker",
        "-l", "info",
        "-Q", "mail,default,push",
        "-Ofair",
        "--concurrency=1",
        "--pool=solo",
    ],
    cwd=str(PROJECT_ROOT),
    env=env,
)

print("⏱️ Starting Celery beat...")
beat_proc = subprocess.Popen(
    CELERY_CMD
    + [
        "-A", "rooster_site",
        "beat",
        "-l", "info",
        "--pidfile=",
        f"--schedule={CELERYBEAT_SCHEDULE}",
    ],
    cwd=str(PROJECT_ROOT),
    env=env,
)

def shutdown(*_):
    print("\n🛑 Stopping development processes...")
    for p in (beat_proc, worker_proc, django_proc):
        try:
            p.terminate()
        except Exception:
            pass
    # stop alleen redis; andere services draaien we niet in deze compose
    subprocess.run(["docker", "compose", "-f", "deploy/docker-compose.dev.yml", "down"], check=False)
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

print("\n✅ Development environment running:")
print("   - Django: http://127.0.0.1:8000")
print("   - Redis:  redis://127.0.0.1:6379")
print("   - Celery: worker \n")
print("   - Celery: beat\n")
print("Press Ctrl+C to stop.\n")

# Houdt script in leven
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    shutdown()