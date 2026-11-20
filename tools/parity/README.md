# Parity harness

Runs the same scripts against one Composable instance under two `composapy` builds and compares what a caller can observe: return values, DataFrames, exceptions, and what the notebook and script wrappers write. It was built for the move from `pythonnet` to HTTP (1.0.0): the baseline is 0.13.3, and `report.md` is the result of that comparison.

It is a migration check, not part of the default `tox` run. Use it when a release changes internals as broadly (a new transport, a different contract decoder). Ordinary releases are covered by `tests/offline` and the instance tests.

## What it needs

- A local Composable instance, and `APPLICATION_URI`, `TEST_USERNAME`, and `TEST_PASSWORD` in `tests\.test.env` or `.local.env`. The harness signs in once over a Form session and makes an API token that it passes to each variant in `PARITY_TOKEN`. The token is never written to a file or printed.
- Python 3.11, through the `py` launcher.
- The baseline wheel in `tests\baseline\wheel`, and a candidate wheel in `dist` (`tox -e sync-composapy` builds one).
- A Debug build of the product tree (`Product\CompAnalytics.DataLabService\bin\Debug`). The baseline reads its assemblies from there through `DATALAB_DLL_DIR`.

## Build the environments

From the Composapy folder. Both environments install under the Python 3.11 DataLab pins, so they run the numpy, pandas, and requests versions DataLabs run. The `ipykernel` package lets the wrapper cases run notebooks, and `python-dotenv` is for the runner scripts.

```
py -3.11 -m venv tools\parity\envs\baseline
tools\parity\envs\baseline\Scripts\python.exe -m pip install -c constraints\py311.txt "tests\baseline\wheel\composapy-0.13.3-py3-none-any.whl[deps]" ipykernel python-dotenv

py -3.11 -m venv tools\parity\envs\candidate
tools\parity\envs\candidate\Scripts\python.exe -m pip install -c constraints\py311.txt "dist\composapy-<version>-py3-none-any.whl[deps]" ipykernel python-dotenv
```

After a source change, build a new wheel under a new version (`.devN`) and reinstall it with `pip install --force-reinstall --no-deps`. Copying changed source files into `site-packages` by hand leaves a version number that does not describe what ran.

`envs`, `results`, and `work` are scratch folders. TFS and Git both ignore them.

## Run it

From a folder with no `composapy` folder and no `composapy.ini` (for example `C:\temp`), so that the installed package is the one imported. Run each script with the candidate environment's Python:

```
tools\parity\envs\candidate\Scripts\python.exe tools\parity\run_parity.py
tools\parity\envs\candidate\Scripts\python.exe tools\parity\run_wrappers.py
python tools\parity\compare_results.py
python tools\parity\make_report.py
```

- `run_parity.py` runs every script in `corpus` under both variants and writes `results\<variant>\<script>.json`. It creates a Key and saved QueryViews on the instance first and removes them afterward. Name scripts to run a few (`run_parity.py key_get`), or pass `--only baseline` or `--only candidate` to run one variant.
- `run_wrappers.py` runs the DLNBR test notebooks and scripts, and the cases in `wrapper_corpus`, through the real `script_wrap` and `nb_wrap`.
- `compare_results.py` compares the two result sets and matches each difference to an entry in `classifications.json`. It exits 1 while any difference is unclassified or escalated. Each entry has a script, a record name (`*` for all), one of `fixed`, `visual`, `intentional`, or `escalated`, and a note that names the Decision Log entry when there is one.
- `make_report.py` writes `report.md`, and refuses while any difference is open.

For import time and public names, run `tools\measure_import.py` and `tools\make_baseline_names.py` in the shared DataLab environments with the candidate wheel installed, then `compare_import_time.py` and `compare_names.py`. The Parity and import time task in the solution document gives the exact commands. Run the timing with nothing else running on the machine.

To add a case, put a script in `corpus`. It receives `record(name, value)` and `attempt(name, fn)`, and `runner.py` lists the other helpers.

## Running it for a later release

Several things assume the baseline is the 0.13.3 `pythonnet` build. To compare two later releases:

1. A `make_envs.py` that builds both environments from two wheels. The commands above are done by hand.
2. In `run_parity.py`, `run_wrappers.py`, and `runner.py`, choose the .NET behavior (`DATALAB_DLL_DIR`, and the `int_input`, `list_input`, and `uri_arg` helpers) by whether `pythonnet` is installed in the variant's environment, not by the name `baseline`.
3. In `make_report.py`, take the report title and environment facts from the installed versions, and the import-time and public-names baselines from the baseline release.
4. Keep `classifications.json` per baseline version (for example `classifications-0.13.3.json`), and keep the 0.13.3 `report.md` as the record of the 1.0.0 migration.
