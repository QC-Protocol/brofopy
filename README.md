# brofopy

![CI](https://github.com/martinvonk/brofopy/actions/workflows/ci.yml/badge.svg)
![Docs](https://github.com/martinvonk/brofopy/actions/workflows/docs.yml/badge.svg)

BroFoPy is a Python package that reads data from the *BronFormat*. The Bronformat is an alternative dataformat for the [Basisregistratie Ondergrond, BRO](https://basisregistratieondergrond.nl/). BroFoPy uses [SciPy](https://github.com/scipy/scipy) to convert the BronFormat into a [Pandas]([https://pandas.pydata.org/docs/index.html](https://github.com/pandas-dev/pandas)) `DataFrame`, and provides a workflow to further convert data into a [HydroPandas](https://github.com/ArtesiaWater/hydropandas) `ObsCollection`.

This Python package was developed by [Artesia](https://artesia-water.nl). on behalf of the [Omgevingsdienst Zuidoost-Brabant](https://odzob.nl/). Some of the Python routines were first developed by [TAUW](https://github.com/QC-Protocol/BronDatamodel). The Python pacakge is maintained by [Trefoil Hydrology](mailto:jos.von.asmuth@3hydro.nl). 

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
