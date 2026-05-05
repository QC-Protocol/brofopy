# brofopy

![CI](https://github.com/martinvonk/brofopy/actions/workflows/ci.yml/badge.svg)
![Docs](https://github.com/martinvonk/brofopy/actions/workflows/docs.yml/badge.svg)

BroFoPy is a Python package that reads data from the *BronFormat*. The Bronformat is an alternative dataformat for the [Basisregistratie Ondergrond, BRO](https://basisregistratieondergrond.nl/). BroFoPy uses [SciPy](https://github.com/scipy/scipy) to convert the BronFormat into a [Pandas]([https://pandas.pydata.org/docs/index.html](https://github.com/pandas-dev/pandas)) `DataFrame`, and provides a workflow to further convert data into a [HydroPandas](https://github.com/ArtesiaWater/hydropandas) `ObsCollection`.

## Installation

```bash
pip install brofopy
```

### Development install

```bash
pip install -e ".[dev]"
```

## License

See [LICENSE](LICENSE).
