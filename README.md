# brofopy

![CI](https://github.com/martinvonk/brofopy/actions/workflows/ci.yaml/badge.svg)
![Docs](https://github.com/martinvonk/brofopy/actions/workflows/docs.yaml/badge.svg)

BroFoPy is a Python package that reads data from the *BronFormat*. The Bronformat is an alternative
dataformat for the [Basisregistratie Ondergrond, BRO](https://basisregistratieondergrond.nl/).
BroFoPy converts the *.bron* files into a custom BronFormat class and provides a workflow to
convert the data into a [Pandas](https://github.com/pandas-dev/pandas) `DataFrame` or a
[HydroPandas](https://github.com/ArtesiaWater/hydropandas) `ObsCollection`.

This Python package was developed by [Artesia](https://artesia-water.nl) on behalf of the
[Omgevingsdienst Zuidoost-Brabant](https://odzob.nl/). Some of the Python routines were first
developed by [TAUW](https://github.com/QC-Protocol/BronDatamodel). The Python pacakge is
maintained by [Trefoil Hydrology](mailto:jos.von.asmuth@3hydro.nl).

## Installation

```bash
pip install git+https://github.com/QC-Protocol/brofopy.git
```

### Development install

Clone the repository and install the package in development mode with the following command:

```bash
pip install -e .[dev]
```

## License

See [LICENSE](LICENSE).
