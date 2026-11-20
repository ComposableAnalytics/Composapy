- [Composapy Development Guide](#composapy-development-guide)
  - [What you need](#what-you-need)
  - [Settings files](#settings-files)
  - [Working environment](#working-environment)
  - [Tox](#tox)
    - [Environments](#environments)
    - [Running a subset](#running-a-subset)
    - [Constraints](#constraints)
  - [Tests](#tests)
    - [Windows authentication tests](#windows-authentication-tests)
  - [Formatting and docs](#formatting-and-docs)
  - [Deploying to the DataLabs](#deploying-to-the-datalabs)
    - [Sync Composapy](#sync-composapy)
    - [Sync Project](#sync-project)
    - [TFS sign-in](#tfs-sign-in)
    - [Copying by hand](#copying-by-hand)
  - [Trying a change in a DataLab](#trying-a-change-in-a-datalab)
  - [IDE](#ide)
  - [Source control](#source-control)
    - [Mirroring to GitHub](#mirroring-to-github)
  - [Release checklist](#release-checklist)
  - [Appendix: Installing the older Python versions](#appendix-installing-the-older-python-versions)

# Composapy Development Guide

Composapy is a pure Python package. It talks to a Composable instance over the HTTP services the platform exposes (`*.svc` endpoints), and it carries its own Python versions of the platform's contract objects in `composapy.contracts`. Nothing in it needs .NET, and `pip install composapy` is all a script needs.

The TFS tree (`Composapy\Composapy`, beside the `Product` tree) is the source of truth. The GitHub repository is a mirror (see [Source control](#source-control)).

## What you need

- Python 3.8, 3.9, 3.10, 3.11, 3.12, and 3.13, each reachable through the `py` launcher. `py -0p` lists them. Add each one from [python.org](https://www.python.org/downloads/). For 3.8 to 3.11, see the [appendix](#appendix-installing-the-older-python-versions), because python.org no longer builds installers for their newest releases.
- [tox](https://tox.wiki/en/latest/) 4 or newer: `py -3.13 -m pip install --upgrade tox`.
- A local Composable instance and its `unittestadmin` account. The tests create and delete their own Keys, QueryViews, and DataFlows on it.
- The Team Foundation Server command-line client (`tf.exe`), to deploy to the DataLabs. In a Developer Command Prompt for Visual Studio, `where tf.exe` prints its path.
- For the Windows authentication tests only: an elevated terminal and the IIS Windows Authentication feature (see [Windows authentication tests](#windows-authentication-tests)).

## Settings files

Three files hold local settings. `tests\.test.env` is in TFS, because the C# test suites read the copy that `sync-project` puts in `UnitTests\TestData\composapy`; it holds the account for a local development instance, and it stays out of the GitHub mirror. `tests\.test.local.env` and `.local.env` are in neither. None of the three belongs in a document, a chat, or a log.

`tests\.test.env`:

```
APPLICATION_URI="http://localhost/CompApp/"
TEST_USERNAME="unittestadmin"
TEST_PASSWORD="yourPasswordHere"
```

`tests\.test.local.env`, optional:

```
TEST_API_KEY="yourApiKeyHere"
```

`.local.env`, in the same folder as `pyproject.toml`:

```
TF_EXE_PATH="C:/Path/To/tf.exe"
```

- `APPLICATION_URI` is the address of your instance's application. `TEST_USERNAME` and `TEST_PASSWORD` sign in over a Form session.
- `TEST_API_KEY` is optional. The default test session is a token session. The tests read the key from the shell's environment or from a `.test*.env` file under the folder they run from, such as `tests\.test.local.env`, and never from `.local.env`. When it is absent, the tests sign in with `TEST_USERNAME` and `TEST_PASSWORD`, generate a temporary API token, and print a warning. To keep a token, sign in as `unittestadmin`, open the user's profile page, and use `Generate API Token`.
- The tests load every `.test*.env` file, `.test.env` first. A variable that is already set in the shell, or in a file loaded earlier, is not replaced.
- `TF_EXE_PATH` is read only by the commands that deploy to the DataLabs. Use forward slashes.

## Working environment

tox builds its own environments, so you do not need one to run the tests. For editing and quick test runs, make one on the newest Python:

```
C:\..\Composapy\Composapy> py -3.13 -m venv dev
C:\..\Composapy\Composapy> .\dev\Scripts\activate
(dev) C:\..\Composapy\Composapy> pip install -r requirements.txt -c constraints/py313.txt
(dev) C:\..\Composapy\Composapy> pip install -e . --no-deps
(dev) C:\..\Composapy\Composapy> pytest tests/offline
```

The `(dev)` environment serves your editor and your own test runs. DataLabService does not use it.

## Tox

```
C:\..\Composapy\Composapy> tox
```

runs `black` and then the tests on every Python version. tox builds one wheel and installs it into every environment, so the tests run against the file that gets deployed.

### Environments

| Environment | What it does | Runs by default |
| --- | --- | --- |
| `black` | Formats the source with [Black](https://github.com/psf/black). | yes |
| `py38-test` through `py313-test` | Runs `pytest`, without the Windows authentication tests. | yes |
| `windows-auth` | Runs `tests/test_windows_auth.py` on Python 3.13. | no |
| `docs` | Regenerates `README.md` from `docs\composapy-readme.ipynb` and rebuilds the Sphinx HTML in `docs\sphinx-docs\build`. | no |
| `sync-composapy` | Builds the wheel and deploys it to the DataLabs. | no |
| `sync-project` | Does `sync-composapy`, then deploys the docs, constraints, and test files. | no |

When `requirements.txt`, `setup.cfg`, or a constraints file changes, add `-r` so tox recreates its environments.

### Running a subset

Everything after `--` goes to `pytest`:

```
C:\..\Composapy\Composapy> tox -e py311-test -- tests/offline
C:\..\Composapy\Composapy> tox -e py39-test -- tests/test_api.py -k run
```

### Constraints

The `py38`, `py311`, and `py313` environments install under `constraints\py38.txt`, `py311.txt`, and `py313.txt`. Each is the matching `static\requirements<XY>.txt` from the DataLabService project without its `composapy` line, so those environments test the numpy, pandas, and requests versions the DataLabs install. `py39`, `py310`, and `py312` use the newest versions the package allows. `sync-project` refreshes the three files; commit them when they change.

`pytest` comes from those files too, and its version decides the order: 6.2.5, on `py38` and `py311`, runs the integration test files before `tests/offline`, and newer versions run them after. The tests pass in either order.

## Tests

| Folder or file | What it tests | Needs an instance |
| --- | --- | --- |
| `tests/offline` | The wire codec, contract objects, wrappers, pickles written by 0.13.3, and the tooling in `tools/`. | no |
| `tests/test_*.py` | The public API: `Session`, `DataFlow`, `Key`, and `QueryView`, against the instance. | yes |
| `tests/test_windows_auth.py` | Windows authentication sessions. | yes, with Windows Authentication enabled |

All of `tests` except `offline`, `baseline`, and `wire_captures` is also what the DataLabService C# test suites run, so a change to `conftest.py` or `iis.py` reaches them.

`tools/parity` compares composapy 0.13.3 with the current build by running the same scripts under both against one instance. Its scripts document how to run it.

### Windows authentication tests

`tox -e windows-auth` turns IIS Windows Authentication on for the application, runs the tests, and puts the original settings back, even when a test fails. It changes IIS through `appcmd.exe`, so:

1. Run the terminal as Administrator. `appcmd` cannot read the configuration otherwise, and the run stops before it changes anything.
2. Enable the feature `Internet Information Services` -> `World Wide Web Services` -> `Security` -> `Windows Authentication` (`IIS-WindowsAuthentication`). Without it, IIS accepts the setting but never asks for credentials, and the fixture stops with a message naming the feature.

The default `tox` run never touches IIS.

## Formatting and docs

Run `tox -e black` before every check-in.

`tox -e docs` makes the documentation from two sources:

- `docs\composapy-readme.ipynb` is the source of `README.md`. Edit the notebook; a change to `README.md` is overwritten.
- The Sphinx pages in `docs\sphinx-docs\source` and the docstrings in `composapy` build into `docs\sphinx-docs\build`. The build output is checked in, because Read the Docs publishes it unchanged.

## Deploying to the DataLabs

DataLab environments install from the wheels in `Product\CompAnalytics.DataLabService\static\wheels`, with no internet access. Both commands below work in the TFS tree and need `TF_EXE_PATH`.

### Sync Composapy

```
C:\..\Composapy\Composapy> tox -e sync-composapy
```

1. Removes `build\`, builds the wheel into `dist\` with `python -m build --wheel`, and stops if the wheel holds any file outside `composapy\` and its own `dist-info`.
2. Stops when `static\wheels` already holds a wheel with the same version and different contents. Raise `version` in `setup.cfg`; `1.0.0dev7`, `1.0.0dev8`, and so on serve repeated local builds. A rebuild with unchanged contents does nothing.
3. Removes the old `composapy` wheels from `static\wheels` and from `CompAnalytics.DataLabService.csproj`, through `tf delete` or `tf undo` as each one's state requires, and adds the new wheel the same way.
4. Installs the new wheel into every shared DataLab environment under `PythonDirectory` (`C:\dataLabsArtifacts\python` unless `App.config` says otherwise) that has a `requirements<XY>.txt`. The running DataLabService needs no restart, and the environments are not deleted.

DataLabService builds new environments from `bin\Debug\static\wheels`, which Visual Studio refreshes only when it builds the `CompAnalytics.DataLabService` project. After `sync-composapy`, build that project and restart the service before you run the C# pool and DataLab executor tests. If you do not, `pip` fails with `Could not find a version that satisfies the requirement composapy==<version>`, and the build output keeps every wheel it has ever held, so the failure message lists the stale versions.

### Sync Project

```
C:\..\Composapy\Composapy> tox -e sync-project
```

1. Regenerates `composapy\_wire\operations.json` from the `[ServiceContract]` interfaces in the product tree.
2. Rewrites `constraints\*.txt` from the product tree.
3. Runs Sync Composapy.
4. Copies `composapy-readme.ipynb` and `simple-dataflow.json` into `static`, for every DataLab to hold.
5. Runs `tox -e docs`.
6. Copies `tests` to `Product\UnitTests\TestData\composapy`, leaving out `offline`, `baseline`, and `wire_captures`, and adds the new files to TFS. The copy never deletes, so it lists the files in that folder that `tests` no longer produces; remove each with `tf delete`.

### TFS sign-in

A `TFS30063` error, usually on the `tf info` call, means TFS has lost your sign-in. From `Product\CompAnalytics.DataLabService\static`, run the client by its full path from `TF_EXE_PATH`:

```
PS C:\..\static> & "C:\Path\To\tf.exe" info wheels /prompt
```

Choose your Composable ADO account in the window that opens, then run the tox command again.

### Copying by hand

If a deploy cannot run, these are the product's dependencies on Composapy:

- the wheel in `Product\CompAnalytics.DataLabService\static\wheels`, with its item in `CompAnalytics.DataLabService.csproj`;
- `composapy-readme.ipynb` and `simple-dataflow.json` in `Product\CompAnalytics.DataLabService\static`;
- `tests` in `Product\UnitTests\TestData\composapy`, without `offline`, `baseline`, `wire_captures`, `__pycache__`, and `.pytest_cache`.

## Trying a change in a DataLab

For an edit-and-restart loop against your own source, link one DataLab environment to it. Start DataLabService, open a DataLab, and in its kernel run:

```
import sys
print(sys.executable)
```

This should be the DataLab's virtual environment. Then, in a terminal, with the path it printed:

```
C:\..\python.exe -m pip install -e C:\<path-to>\Composapy\Composapy --no-deps
```

Note that this will overwrite the installation of `composapy` from the shared base virtual environment. Restart the kernel after each edit. `sync-composapy` replaces the editable install with the deployed wheel.

To try the deployed wheel in a new DataLab environment, run `tox -e sync-composapy`. It installs the wheel into each shared environment.

## IDE

Do your Python development in an editor, not in Visual Studio.

**VS Code.** Set the default interpreter to `dev\Scripts\python.exe`. The `python-tox` extension runs a tox environment from the command palette (`ctrl-shift-p`, `tox`). Under `Testing`, choose `pytest` to run and debug tests in the editor.

**PyCharm.** Set the project interpreter to `dev\Scripts\python.exe`, and confirm that `Activate virtualenv` is checked under `Tools` -> `Terminal`.

## Source control

After a change passes the tests:

1. Run `tox -e black` and the default `tox`.
2. Run `tox -e sync-project`, to deploy and to copy the tests.
3. Run the C# suites that cover the change: the DLNBR, DataLab cell-execution, and DLAE pool suites.
4. Check the Composapy tree and the product-tree changes into TFS (`static\wheels`, the requirements files, the `.csproj`, `UnitTests\TestData\composapy`).
5. Mirror the TFS tree to GitHub.

### Mirroring to GitHub

The TFS tree is not a Git working copy. Keep a clone of `https://github.com/ComposableAnalytics/Composapy.git` in its own folder, outside the TFS workspace, and bring it level with the TFS tree after each check-in:

1. Copy the TFS tree's files over the clone, leaving out everything `.gitignore` excludes, and delete clone files that no longer exist in the TFS tree. `.tfignore`, `tests\.test.env`, and `.local.env` stay out.
2. Run `git status` and `git diff --stat`, and confirm that only the files you changed appear.
3. `docs/sphinx-docs/build` is listed in `.gitignore` and tracked, because Read the Docs publishes from it. Stage it with `git add -f docs/sphinx-docs/build`.
4. Commit and push.

The mirror is level when `diff -rq` between the two folders, excluding ignored files, prints nothing.

## Release checklist

1. Set `version` in `setup.cfg`.
2. Run the default `tox` and `tox -e windows-auth`. Both pass.
3. Run `tox -e sync-project`.
4. Run the C# suites listed under [Source control](#source-control), plus the `DataLabCellExecutionTests` and `DataLabCellExecutionWinAuthTests` filters.
5. Check in to TFS, then mirror to GitHub, and tag `v<version>`.
6. Build from the tagged clone and upload:

   ```
   C:\..\Composapy> python -m build --wheel
   C:\..\Composapy> python -m twine upload dist/composapy-<version>*
   ```

   Twine asks for credentials. You need a [PyPI](https://pypi.org/) account with upload rights to the project. With two-factor authentication, use `__token__` as the user name and an API token (it begins `pypi-`) as the password; create one under Account Settings in the browser.
7. Confirm that the PyPI wheel, the wheel in `static\wheels`, and a wheel built from the tag have the same SHA-256 hash (`Get-FileHash`).

## Appendix: Installing the older Python versions

python.org publishes a Windows installer only for the last binary release of each retired Python version. Later patch releases of those versions are source-only, so the newest `3.8.x` or `3.9.x` has no installer to run. Install these releases:

| Python | Install | Release page |
| --- | --- | --- |
| 3.8 | 3.8.10 | https://www.python.org/downloads/release/python-3810/ |
| 3.9 | 3.9.13 | https://www.python.org/downloads/release/python-3913/ |
| 3.10 | 3.10.11 | https://www.python.org/downloads/release/python-31011/ |
| 3.11 | 3.11.9 | https://www.python.org/downloads/release/python-3119/ |

For 3.12 and 3.13, use the newest release whose page lists a `Windows installer (64-bit)`.

1. On the release page, download `Windows installer (64-bit)` from the Files table.
2. Run it. Keep the `py launcher` feature, which is on by default, and leave `Add python.exe to PATH` unticked: tox finds the interpreters through the launcher. A per-user install (`Install Now`, no administrator rights) is enough.
3. Check each one. `py -0p` lists the installed versions, and `py -3.8 --version` prints one.

These versions no longer receive security fixes. Use them only to run Composapy's tests.
