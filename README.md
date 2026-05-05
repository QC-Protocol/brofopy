# brofopy

![CI](https://github.com/martinvonk/brofopy/actions/workflows/ci.yml/badge.svg)
![Docs](https://github.com/martinvonk/brofopy/actions/workflows/docs.yml/badge.svg)

A Python package that reads data from a specific *Bronformat* (source format from the Basisregistratie Ondergrond, BRO) using SciPy, converts it to Pandas DataFrames, and provides a workflow to further convert data into a HydroPandas `ObsCollection`.

## Features

- Read Bronformat files into `pandas.DataFrame` objects via SciPy.
- Convert DataFrames to HydroPandas `ObsCollection` for groundwater analysis.
- Fetch source data using the `brodata` package.

## Installation

```bash
pip install brofopy
```

### Development install

```bash
pip install -e ".[dev]"
```

### Documentation dependencies

```bash
pip install -e ".[docs]"
```

## Quick start

```python
from brofopy import read_bronformat, to_obscollection

df = read_bronformat("path/to/bronformat_file")
obs = to_obscollection(df, meta={})
```

## License

See [LICENSE](LICENSE).
