"""Run the parity corpus under the baseline and the candidate against the local instance.

Run it with the CANDIDATE environment's Python, from any folder that has no composapy.ini or composapy folder:

    tools\\parity\\envs\\candidate\\Scripts\\python.exe tools\\parity\\run_parity.py [--only baseline|candidate] [script ...]

It signs in over a Form session with TEST_USERNAME and TEST_PASSWORD (tests/.test.env, .local.env) once, makes an API
token, and hands it to each variant's process in the PARITY_TOKEN environment variable. The token is never written to a
file or printed. Each variant runs the whole corpus in one process of its own virtual environment (the baseline also
gets DATALAB_DLL_DIR, as a DataLab process does) and writes tools/parity/results/<variant>/<script>.json.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent.parent
CORPUS = HERE / "corpus"
RESULTS = HERE / "results"
ENVS = HERE / "envs"
WORK = (
    HERE / "work"
)  # the same current directory for both variants, so relative paths resolve alike
DLL_DIR = (
    ROOT.parent.parent / "Product" / "CompAnalytics.DataLabService" / "bin" / "Debug"
)


def make_session():
    from composapy.auth import AuthMode
    from composapy.session import Session

    username, password = os.environ.get("TEST_USERNAME"), os.environ.get(
        "TEST_PASSWORD"
    )
    if not username or not password:
        sys.exit(
            "TEST_USERNAME and TEST_PASSWORD are needed to make an API token (tests/.test.env or .local.env)."
        )
    session = Session(auth_mode=AuthMode.FORM, credentials=(username, password))
    session.register()
    return session


def make_token(session):
    users = session.services["UserService"]
    user = users.GetCurrentUser()
    return users.GenerateUserToken(
        user.Id,
        user.UserName,
        "parity harness",
        datetime.now(timezone.utc) + timedelta(days=1),
    )


def run_variant(variant, token, scripts, fixtures_file):
    python = ENVS / variant / "Scripts" / "python.exe"
    if not python.exists():
        sys.exit(
            f"{python} does not exist; create the environments first (see tools/parity/README.md)."
        )
    ini_dir = WORK / f"ini-{variant}"  # where register(save=True) writes composapy.ini
    shutil.rmtree(
        ini_dir, ignore_errors=True
    )  # so an earlier run's saved configuration cannot change this one
    ini_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "PARITY_TOKEN": token,
        "PARITY_FIXTURES": str(fixtures_file),
        "COMPOSAPY_INI_DIR": str(ini_dir),
    }
    if variant == "baseline":
        env["DATALAB_DLL_DIR"] = str(DLL_DIR)
    else:
        env.pop("DATALAB_DLL_DIR", None)
    WORK.mkdir(
        exist_ok=True
    )  # empty, so nothing in it can shadow the installed package
    subprocess.run(
        [
            str(python),
            str(HERE / "runner.py"),
            variant,
            str(RESULTS / variant),
            str(CORPUS),
            *scripts,
        ],
        env=env,
        cwd=str(WORK),
        check=True,
    )


def main(argv):
    args = argv[1:]
    only = None
    if "--only" in args:
        only = args[args.index("--only") + 1]
        args = [a for a in args if a not in ("--only", only)]
    for env_file in (ROOT / "tests" / ".test.env", ROOT / ".local.env"):
        load_dotenv(env_file)
    if not os.environ.get("APPLICATION_URI"):
        sys.exit("APPLICATION_URI is not set (tests/.test.env or .local.env).")
    import fixtures

    session = make_session()
    token = make_token(session)
    WORK.mkdir(exist_ok=True)
    fixtures_file = WORK / "fixtures.json"
    created = fixtures.create(session)
    try:
        fixtures_file.write_text(json.dumps(created), encoding="utf-8")
        for variant in ("baseline", "candidate"):
            if only in (None, variant):
                run_variant(variant, token, args, fixtures_file)
    finally:
        fixtures.delete(session, created)
        fixtures_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main(sys.argv)
