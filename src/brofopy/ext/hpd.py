"""HydroPandas extension for brofopy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pandas as pd
from hydropandas import GroundwaterObs, ObsCollection, WaterQualityObs

if TYPE_CHECKING:
    from brofopy.bronformat import BronFormat


def to_obscollection(
    bronformat: "BronFormat",
    entity: Literal["GLD", "GAR"] = "GLD",
    name: str = "",
) -> ObsCollection:
    """Convert brofopy BronFormat data to a HydroPandas ObsCollection.

    Parameters
    ----------
    bronformat : BronFormat
        A BronFormat object with entity data.
    entity : Literal["GLD", "GAR"], optional
        The entity type to convert (e.g., "GLD" for groundwater, "GAR"
        for water quality). By default "GLD".
    name : str, optional
        Name for the ObsCollection, by default "".

    Returns
    -------
    ObsCollection
        A HydroPandas ``ObsCollection`` built from the data.

    Examples
    --------
    >>> from brofopy import read_bronformat
    >>> bf = read_bronformat("path/to/file.bron2")
    >>> oc = to_obscollection(bf, entity="GLD", name="MyCollection")
    """
    entity_data = getattr(bronformat, entity, None)

    if entity_data is None:
        return ObsCollection(name=name)

    # Get metadata and data for this entity
    # We need to access GMW data as well for coordinates
    gmw_data = getattr(bronformat, "GMW", None)

    # Create GroundwaterObs object
    if entity == "GLD":
        Obs = GroundwaterObs
    elif entity == "GAR":
        Obs = WaterQualityObs
    else:
        raise ValueError(f"Unsupported entity type: {entity}")

    obs_list = []
    for bro_id, data in entity_data.items():
        # Get GMWBROID and TubeNo from Dossier sub-entity
        dossier = data.get("Dossier", {})
        gmw_id = str(dossier.get("GMWBROID", ""))
        tube_no = int(dossier.get("TubeNo", 0))

        # Get coordinates from GMW data
        x = y = ground_level = tube_top = screen_top = screen_bottom = 0.0
        if gmw_data and gmw_id in gmw_data:
            gmw_entry = gmw_data[gmw_id]
            well = gmw_entry.get("Well", {})
            x = float(well.get("XCoordinate", 0.0))
            y = float(well.get("YCoordinate", 0.0))
            ground_level = float(well.get("SurfaceLevel", 0.0))

            # Find tube data matching TubeNo
            tube = gmw_entry.get("Tube", {})
            if isinstance(tube, dict):
                screen_top = float(tube.get("FilterTopLevel", 0.0))
                screen_bottom = float(tube.get("FilterBottomLevel", 0.0))
                tube_top = float(tube.get("TopLevel", 0.0))

        # Create DataFrame from Source/Measurements
        source = data.get("Source", {})
        ts_list = source.get("Measurements", [])
        if ts_list:
            ts_df = pd.DataFrame(ts_list)
            if "DateTime" in ts_df.columns:
                ts_df = ts_df.set_index("DateTime")["RawValue"]
                ts_df = ts_df.to_frame(name="RawValue")
            else:
                ts_df = pd.DataFrame(columns=["RawValue"])
                ts_df.index.name = "DateTime"
        else:
            ts_df = pd.DataFrame(columns=["RawValue"])
            ts_df.index.name = "DateTime"

        # Extract metadata values
        obs_kwargs = {
            "name": str(bro_id),
            "x": x,
            "y": y,
            "location": str(bro_id),
            "source": "BronFormat",
            "unit": "",
            "screen_top": screen_top,
            "screen_bottom": screen_bottom,
            "ground_level": ground_level,
            "tube_top": tube_top,
            "metadata_available": False,
            "tube_nr": str(int(tube_no)),
        }

        obs = Obs(ts_df, **obs_kwargs)
        obs_list.append(obs)

    return ObsCollection(obs_list, name=name)
