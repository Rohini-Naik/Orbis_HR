#!/usr/bin/env python3
"""Orbis — cross-platform setup.

    Linux / macOS :  ./setup.sh        (or: python3 setup.py)
    Windows       :  setup.bat         (or: py setup.py)

Creates .env, installs backend and frontend dependencies, provisions MySQL,
builds the policy search index, and creates the first administrator.

Written in Python rather than shell so Windows and Unix run the same logic:
the differences (venv layout, how MySQL root authenticates, npm's extension,
which requirements file applies) are handled in one place below.

Safe to re-run — every step detects work already done and skips it.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WINDOWS = os.name == "nt"
VENV = ROOT / "venv"
VENV_BIN = VENV / ("Scripts" if IS_WINDOWS else "bin")
VENV_PY = VENV_BIN / ("python.exe" if IS_WINDOWS else "python")
REQUIREMENTS = ROOT / ("requirements-windows.txt" if IS_WINDOWS else "requirements.txt")

# Windows consoles need VT processing switched on before ANSI codes render.
if IS_WINDOWS:
    os.system("")
BOLD, GREEN, YELLOW, RED, DIM, OFF = (
    "\033[1m", "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"
)


def step(msg: str) -> None:
    print(f"\n{BOLD}==> {msg}{OFF}")


def ok(msg: str) -> None:
    print(f"  {GREEN}\u2713{OFF} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{OFF} {msg}")


def die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"  {RED}\u2717 {msg}{OFF}", file=sys.stderr)
    sys.exit(1)


def run(cmd, **kw):
    """Run a command, raising with a readable message if it fails."""
    return subprocess.run(cmd, check=True, **kw)


def which(name: str) -> str | None:
    return shutil.which(name)


# --------------------------------------------------------------- prerequisites
def check_prerequisites() -> None:
    step("Checking prerequisites")

    if sys.version_info < (3, 11):
        die(f"Python 3.11+ required (running {sys.version.split()[0]}).")
    ok(f"python {sys.version.split()[0]}")

    for tool, hint in (("node", "https://nodejs.org"), ("npm", "ships with Node.js")):
        if not which(tool) and not (IS_WINDOWS and which(f"{tool}.cmd")):
            die(f"{tool} not found. Install Node.js 20+ ({hint}).")
    ok("node / npm found")

    if not which("mysql"):
        die(
            "mysql client not found. Install MySQL 8 and make sure its bin/ "
            "directory is on your PATH."
            + (
                "\n    On Windows the installer usually puts it in:\n"
                "    C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin"
                if IS_WINDOWS
                else ""
            )
        )
    ok("mysql client found")


# ------------------------------------------------------------------ mysql root
_root_cmd: list[str] | None = None


def _env_value(key: str, default: str) -> str:
    """Read a key straight from .env — the bootstrap must target the same
    server the application will use, not whatever a client config points at."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == key and value.strip():
                return value.strip()
    return default


def _diagnose(attempts: list[tuple[str, str]]) -> str:
    """Turn the collected MySQL errors into the one sentence worth acting on."""
    joined = " ".join(error.lower() for _, error in attempts)
    if "can't connect" in joined or "connection refused" in joined:
        return ("the MySQL server is not running. Start it with "
                "`sudo systemctl start mysql` and run setup again.")
    if "access denied" in joined:
        return ("MySQL's root account has a password set. Enter it below, or "
                "reset it: https://dev.mysql.com/doc/refman/8.0/en/resetting-permissions.html")
    if "command not found" in joined or "no such file" in joined:
        return ("the mysql client is not on PATH. On Windows add "
                r"C:\Program Files\MySQL\MySQL Server 8.0\bin")
    return ""


def _prime_sudo() -> bool:
    """Get a sudo session before the silent probes run.

    The probes discard their output so failed attempts do not clutter setup —
    which would also swallow sudo's own password prompt, leaving the user
    staring at a hung screen. Asking here keeps the prompt visible.
    """
    if subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0:
        return True  # already authenticated
    print(f"  {DIM}Administrative access is needed to create the databases.{OFF}")
    print(f"  {DIM}Enter your computer's login password if prompted.{OFF}")
    return subprocess.run(["sudo", "-v"]).returncode == 0


def _confirm_target(cmd: list[str]) -> None:
    """Show which server is about to be modified, and stop if it is not local.

    The bootstrap drops and recreates tables. A misdirected run would do that to
    someone else's database, so a remote target has to be confirmed explicitly.
    """
    try:
        result = subprocess.run(
            cmd + ["-N", "-B", "-e", "SELECT @@hostname, @@port, @@datadir, @@version"],
            capture_output=True, text=True, timeout=30,
        )
        hostname, port, datadir, version = result.stdout.strip().split("\t")
    except Exception:
        return  # cannot introspect; the pinned -h already constrains the target

    print(f"  {DIM}target: {hostname} · port {port} · {version} · {datadir}{OFF}")

    looks_remote = datadir.startswith("/rdsdbdata") or "amazonaws" in hostname.lower()
    if looks_remote:
        print(f"\n  {RED}{BOLD}This looks like a REMOTE managed database, not a local one.{OFF}")
        print(f"  {RED}setup drops and recreates the employees table.{OFF}")
        print(f"  {DIM}A ~/.my.cnf or MYSQL_HOST entry may be redirecting the connection.{OFF}\n")
        if input("  Type 'yes' to modify this server anyway: ").strip().lower() != "yes":
            die("Aborted — no changes were made.")


def mysql_root() -> list[str]:
    """Work out how to reach MySQL as root on this machine, once.

    Linux/macOS installs normally use socket auth, so `sudo mysql` works with
    no password. Windows sets a root password at install time, so we prompt.
    """
    global _root_cmd
    if _root_cmd is not None:
        return _root_cmd

    # Probe with the privileges bootstrap actually needs. Connecting is not
    # enough: an unprivileged `root` can pass `SELECT 1` and then fail on the
    # first CREATE DATABASE.
    probe = (
        "CREATE DATABASE IF NOT EXISTS orbis_setup_probe; "
        "DROP DATABASE orbis_setup_probe; "
        "CREATE USER IF NOT EXISTS 'orbis_setup_probe'@'localhost'; "
        "DROP USER 'orbis_setup_probe'@'localhost';"
    )

    attempts: list[tuple[str, str]] = []

    def works(cmd: list[str]) -> bool:
        """Try one way in. Failures are recorded rather than discarded — when
        every route fails, the MySQL error is the only thing that explains why."""
        try:
            result = subprocess.run(
                cmd + ["-e", probe],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60,
            )
            if result.returncode == 0:
                return True
            message = result.stderr.decode(errors="ignore").strip().splitlines()
            attempts.append((" ".join(cmd), message[-1] if message else "failed"))
        except Exception as exc:
            attempts.append((" ".join(cmd), f"{type(exc).__name__}: {exc}"))
        return False

    # Always pin host and port to the values the application itself uses.
    # A ~/.my.cnf can silently redirect a bare `mysql` to an entirely different
    # server — a remote one — and the bootstrap scripts are destructive, so the
    # target must never be inherited from client configuration.
    host = _env_value("MYSQL_HOST", "localhost")
    port = _env_value("MYSQL_PORT", "3306")

    # Without sudo first: on many Linux installs MySQL's root uses socket auth,
    # which only works as the system root.
    if works(["mysql", "--no-defaults", "-u", "root", "-h", host, "-P", port]):
        _root_cmd = ["mysql", "--no-defaults", "-u", "root", "-h", host, "-P", port]
        ok("MySQL admin access via: mysql -u root")
        _confirm_target(_root_cmd)
        return _root_cmd

    if not IS_WINDOWS and which("sudo") and _prime_sudo():
        for cmd in (
            ["sudo", "mysql", "--no-defaults", "-h", host, "-P", port],
            ["sudo", "mysql", "--no-defaults"],  # socket auth takes no -h
            # `--no-defaults` also suppresses the config that tells the client
            # where the server's socket lives, so on some installs it cannot
            # connect at all. Allowing defaults is a last resort — the target
            # check below still refuses an unexpected remote server.
            ["sudo", "mysql"],
        ):
            if works(cmd):
                _root_cmd = cmd
                ok(f"MySQL admin access via: {' '.join(cmd)}")
                _confirm_target(cmd)
                return _root_cmd

    # Fall back to prompting for the root password.
    print()
    print(f"  {YELLOW}Could not reach MySQL as an administrator automatically.{OFF}")
    print(f"  {DIM}What each attempt reported:{OFF}")
    for cmd, error in attempts:
        print(f"    {DIM}${OFF} {cmd}")
        print(f"      {RED}{error[:150]}{OFF}")
    print()
    hint = _diagnose(attempts)
    if hint:
        print(f"  {BOLD}Most likely: {hint}{OFF}\n")
    print(f"  {DIM}Otherwise, enter your MySQL server's own root password — the one")
    print(f"  set when MySQL was installed. It is NOT your computer login. Press")
    print(f"  Enter to try a blank password.{OFF}")
    print(f"  {DIM}For a full check, run: bash scripts/diagnose_mysql.sh{OFF}")
    print()
    import getpass

    for attempt in range(3):
        password = getpass.getpass("  MySQL root password: ")
        cmd = ["mysql", "-u", "root", f"-p{password}"]
        if works(cmd):
            _root_cmd = cmd
            ok("MySQL admin access via: mysql -u root -p")
            return _root_cmd
        warn("That did not work." + (" Try again." if attempt < 2 else ""))

    die(
        "Could not get administrative access to MySQL.\n"
        "    On Linux this usually works:  sudo mysql < scripts/bootstrap_local_mysql.sql\n"
        "    Make sure the server is running: sudo systemctl start mysql"
    )


def run_sql_file(path: Path, db_password: str, extra: list[str] | None = None) -> None:
    """Feed a bootstrap script to MySQL, substituting the password placeholder."""
    sql = path.read_text(encoding="utf-8").replace(
        "__SET_A_STRONG_PASSWORD__", db_password
    )
    proc = subprocess.run(
        mysql_root() + (extra or []),
        input=sql.encode("utf-8"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        die(f"{path.name} failed:\n{proc.stderr.decode(errors='ignore')[:800]}")


# ------------------------------------------------------------------------ .env
def configure_env() -> dict[str, str]:
    step("Configuring .env")
    env_path = ROOT / ".env"

    if env_path.exists():
        ok(".env already exists — leaving it untouched")
    else:
        alphabet = string.ascii_letters + string.digits
        db_password = "".join(secrets.choice(alphabet) for _ in range(24))
        text = (ROOT / ".env.example").read_text(encoding="utf-8").replace(
            "__GENERATED__", db_password
        )
        env_path.write_text(text, encoding="utf-8")
        if not IS_WINDOWS:
            env_path.chmod(0o600)
        ok("created .env with a generated database password")

        print()
        print("  An API key is required for the AI to answer anything.")
        print(f"  {DIM}Groq is the default provider — the free tier is enough.{OFF}")
        print(f"  {DIM}Create a key at https://console.groq.com/keys{OFF}")
        print()
        key = input("  Paste your Groq API key (Enter to skip): ").strip()
        if key:
            env_path.write_text(
                re.sub(
                    r"^GROQ_API_KEY=.*$",
                    f"GROQ_API_KEY={key}",
                    env_path.read_text(encoding="utf-8"),
                    flags=re.MULTILINE,
                ),
                encoding="utf-8",
            )
            ok("key saved")
        else:
            warn("no key yet — add GROQ_API_KEY to .env before using the chat")

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()

    # Mirror the few settings the browser needs; the domain is only an input hint.
    frontend_env = ROOT / "Frontend" / ".env"
    if not frontend_env.exists():
        frontend_env.write_text(
            "VITE_API_BASE_URL=http://localhost:8000\n"
            f"VITE_COMPANY_EMAIL_DOMAIN={values.get('COMPANY_EMAIL_DOMAIN', 'company.com')}\n",
            encoding="utf-8",
        )
        ok("created Frontend/.env")

    return values


# ------------------------------------------------------------------ python env
def install_backend() -> None:
    step("Installing backend dependencies (a few minutes the first time)")

    if not VENV_PY.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
        ok("created venv/")

    pip = [str(VENV_PY), "-m", "pip", "install", "--quiet"]
    run(pip + ["--upgrade", "pip"])

    if IS_WINDOWS:
        # The Windows requirements deliberately exclude torch: the default PyPI
        # wheel pulls a large CUDA payload, so install the CPU build first.
        try:
            run([str(VENV_PY), "-c", "import torch"], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            ok("torch already installed")
        except subprocess.CalledProcessError:
            print(f"  {DIM}Installing CPU-only torch (~200 MB)…{OFF}")
            run(pip + ["torch", "--index-url", "https://download.pytorch.org/whl/cpu"])
            ok("torch (CPU build) installed")

    run(pip + ["-r", str(REQUIREMENTS)])
    ok(f"python packages installed from {REQUIREMENTS.name}")


# ----------------------------------------------------------------------- mysql
def provision_mysql(env: dict[str, str]) -> None:
    step("Provisioning MySQL")
    db_password = env.get("MYSQL_PASSWORD", "")
    if not db_password or db_password == "__GENERATED__":
        die("MYSQL_PASSWORD is not set in .env — delete .env and re-run setup.")

    mysql_root()  # resolve credentials once, up front

    run_sql_file(ROOT / "scripts" / "bootstrap_local_mysql.sql", db_password)
    ok("orbis_hr database + employees table")
    run_sql_file(ROOT / "scripts" / "bootstrap_app_mysql.sql", db_password)
    ok("orbis_app database + user")
    run_sql_file(ROOT / "scripts" / "bootstrap_hr_admin_mysql.sql", db_password)
    ok("orbis_hr_admin user")

    step("Loading employee records")
    run([str(VENV_PY), "-m", "app.provision", "load-employees"], cwd=ROOT)


def backfill(env: dict[str, str]) -> None:
    """The CSV ships with company addresses; this fills in any that are missing
    (and is what mints them for employees added later)."""
    step("Checking company email addresses")
    run([str(VENV_PY), "-m", "app.provision", "backfill-emails"], cwd=ROOT)


# ----------------------------------------------------------------- search index
def build_index() -> None:
    step("Building the policy search index")
    chroma = ROOT / "data" / "chroma"
    if chroma.exists() and any(chroma.iterdir()):
        ok("index already present (rebuild: python -m rag_engine.maintenance)")
        return
    print(f"  {DIM}Downloads the embedding model (~440 MB) the first time.{OFF}")
    run([str(VENV_PY), "-m", "rag_engine.maintenance"], cwd=ROOT)


# --------------------------------------------------------------------- frontend
def install_frontend() -> None:
    step("Installing frontend dependencies")
    npm = which("npm") or (which("npm.cmd") if IS_WINDOWS else None)
    if npm is None:
        die("npm not found on PATH.")
    run([npm, "install", "--silent"], cwd=ROOT / "Frontend", shell=IS_WINDOWS)
    ok("npm packages installed")


# ------------------------------------------------------------------ first admin
def create_admin() -> None:
    step("Creating the first HR administrator")
    listing = subprocess.run(
        [str(VENV_PY), "-m", "app.provision", "list-admins"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if "@" in listing.stdout:
        ok("an administrator already exists")
        print(listing.stdout.rstrip())
        return

    suggested = subprocess.run(
        [str(VENV_PY), "-c",
         "import mysql.connector;from rag_engine import settings;"
         "c=mysql.connector.connect(**settings.get_mysql_config());cur=c.cursor();"
         "cur.execute(\"SELECT Email FROM employees WHERE Department='HR' AND Email IS NOT NULL LIMIT 1\");"
         "r=cur.fetchone();print(r[0] if r else '')"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip()

    print("  Pick the company email this admin will sign in with.")
    if suggested:
        print(f"  {DIM}An HR employee you could use: {suggested}{OFF}")
    print()
    email = input(f"  Admin email [{suggested}]: ").strip() or suggested
    if not email:
        warn("skipped — create one later with: "
             "python -m app.provision create-admin --email you@orbis.com")
        return
    subprocess.run([str(VENV_PY), "-m", "app.provision", "create-admin",
                    "--email", email], cwd=ROOT)


def main() -> None:
    print(f"{BOLD}Orbis setup{OFF}  {DIM}({'Windows' if IS_WINDOWS else 'Unix'}){OFF}")
    check_prerequisites()
    env = configure_env()
    install_backend()
    provision_mysql(env)
    backfill(env)
    build_index()
    install_frontend()
    create_admin()

    start = "start.bat" if IS_WINDOWS else "./start.sh"
    print(f"""
{GREEN}{BOLD}Setup complete.{OFF}

  Start the app with:   {BOLD}{start}{OFF}
  Then open:            {BOLD}http://localhost:5173{OFF}

  {DIM}Sign in with the admin address you just created.
  New hires added under "Employees" get an invitation link printed in the
  backend terminal (EMAIL_BACKEND=console).{OFF}
""")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        die(f"Command failed: {' '.join(str(c) for c in exc.cmd)}")
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
