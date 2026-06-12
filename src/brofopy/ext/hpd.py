"""HydroPandas extension for brofopy."""

from __future__ import annotations

from typing import Literal

import pandas as pd
from hydropandas import GroundwaterObs, ObsCollection, WaterQualityObs


def to_obscollection(
    data_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    entity: Literal["GLD", "GAR"],
    name: str,
) -> ObsCollection:
    """Convert brofopy DataFrames to a HydroPandas ObsCollection.

    Parameters
    ----------
    data_df : pd.DataFrame
        Data DataFrame produced by :func:`brofopy.reader.read_bronformat`.
        Should have DateTime and RawValue columns with index (Entity, BROID).
    entity : Literal["GLD", "GAR"]
        The entity type to convert (e.g., "GLD" for groundwater, "GAR
        for water quality).
    metadata_df : pd.DataFrame
        Metadata DataFrame produced by :func:`brofopy.reader.read_bronformat`.
        Should have index (Entity, BROID, SubEntity).
    name : str, optional
        Name for the ObsCollection, by default "".

    Returns
    -------
    ObsCollection
        A HydroPandas ``ObsCollection`` built from *data_df* and *metadata_df*.

    Examples
    --------
    >>> from brofopy.reader import read_bronformat
    >>> metadata, data = read_bronformat("path/to/file.bron2")
    >>> oc = to_obscollection(data, metadata, entity="GLD")
    """
    # Create GroundwaterObs object
    if entity == "GLD":
        Obs = GroundwaterObs
    elif entity == "GAR":
        Obs = WaterQualityObs
    else:
        raise ValueError(f"Unsupported entity type: {entity}")

    if data_df.empty:
        return ObsCollection(name=name)

    # Filter unique BROIDs for the specified entity
    bro_ids = (
        metadata_df.loc[metadata_df.index.get_level_values("Entity") == entity]
        .index.get_level_values("BROID")
        .unique()
    )

    obs_list = []
    for bro_id in bro_ids:
        gmw_id = str(metadata_df.loc[(entity, bro_id, "Dossier"), "GMWBROID"].squeeze())
        tube_no = float(
            metadata_df.loc[(entity, bro_id, "Dossier"), "TubeNo"].squeeze()
        )

        x = float(metadata_df.loc[("GMW", gmw_id, "Well"), "XCoordinate"].squeeze())
        y = float(metadata_df.loc[("GMW", gmw_id, "Well"), "YCoordinate"].squeeze())
        ground_level = float(
            metadata_df.loc[("GMW", gmw_id, "Well"), "SurfaceLevel"].squeeze()
        )
        tube_df = metadata_df.loc[("GMW", gmw_id, "Tube")].query(f"TubeNo == {tube_no}")
        screen_top = float(tube_df.loc[("GMW", gmw_id, "Tube"), "FilterTopLevel"])
        screen_bottom = float(tube_df.loc[("GMW", gmw_id, "Tube"), "FilterBottomLevel"])
        tube_top = float(tube_df.loc[("GMW", gmw_id, "Tube"), "TopLevel"])

        # Get time series data for this BROID
        ts_data = data_df.loc[(entity, bro_id)]
        if isinstance(ts_data, pd.Series):
            ts_data = ts_data.to_frame().T

        # Pivot to have DateTime as index and RawValue as column
        if len(ts_data) > 0:
            ts_df = ts_data.set_index("DateTime")["RawValue"]
            ts_df = ts_df.to_frame(name="RawValue")
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
