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
    metadata_df : pd.DataFrame
        Metadata DataFrame produced by :func:`brofopy.reader.read_bronformat`.
        Should have index (Entity, BROID, SubEntity).
    entity : Literal["GLD", "GAR"], optional
        Entity type to filter for, by default "GLD" (groundwater level data).
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
    >>> oc = to_obscollection(data, metadata)
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

    # Filter metadata for the specified entity
    metadata_df = metadata_df.loc[
        metadata_df.index.get_level_values("Entity") == entity
    ]

    # Get unique BROIDs that are not GMW
    bro_ids = data_df.index.get_level_values("BROID").unique()

    obs_list = []
    for bro_id in bro_ids:
        gmw_id = metadata_df.at[("GLD", bro_id, "Dossier"), "GMWBROID"]
        tube_no = metadata_df.at[("GLD", bro_id, "Dossier"), "TubeNo"]

        x = metadata_df.at[("GMW", gmw_id, "Well"), "XCoordinate"]
        y = metadata_df.at[("GMW", gmw_id, "Well"), "YCoordinate"]
        ground_level = metadata_df.at[("GMW", gmw_id, "Well"), "SurfaceLevel"]

        tube_df = metadata_df.loc[("GMW", gmw_id, "Tube")].query(f"TubeNo == {tube_no}")
        screen_top = tube_df.at[("GMW", gmw_id, "Tube"), "FilterTopLevel"]
        screen_bottom = tube_df.at[("GMW", gmw_id, "Tube"), "FilterBottomLevel"]
        tube_top = tube_df.at[("GMW", gmw_id, "Tube"), "TopLevel"]

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

        # Get metadata for this BROID
        bro_id_metadata = metadata_df.loc[
            (entity, bro_id), :
        ]

        # Extract metadata values
        obs_kwargs = {
            "name": str(bro_id),
            "x": x,
            "y": y,
            "location": str(bro_id),
            "source": "BronFormat",
            "unit": "m",
            "screen_top": screen_top,
            "screen_bottom": screen_bottom,
            "ground_level": ground_level,
            "tube_top": tube_top,
            "metadata_available": False,
            "tube_nr": str(int(tube_no)),
        }

        # Try to extract coordinates from metadata
        if "Point" in bro_id_metadata.index.get_level_values("SubEntity"):
            point_meta = bro_id_metadata.loc[
                (entity, bro_id, "Point"), :
            ]
            if not point_meta.empty:
                if "X" in point_meta.columns:
                    obs_kwargs["x"] = point_meta["X"].iloc[0]
                if "Y" in point_meta.columns:
                    obs_kwargs["y"] = point_meta["Y"].iloc[0]

        # Try to extract tube information
        if "Tube" in bro_id_metadata.index.get_level_values("SubEntity"):
            tube_meta = bro_id_metadata.loc[
                (entity, bro_id, "Tube"), :
            ]
            if not tube_meta.empty:
                if "TubeNr" in tube_meta.columns:
                    obs_kwargs["tube_nr"] = str(int(tube_meta["TubeNr"].iloc[0]))
                if "ScreenTop" in tube_meta.columns:
                    obs_kwargs["screen_top"] = tube_meta["ScreenTop"].iloc[0]
                if "ScreenBottom" in tube_meta.columns:
                    obs_kwargs["screen_bottom"] = tube_meta["ScreenBottom"].iloc[0]

        # Try to extract ground level
        if "Well" in bro_id_metadata.index.get_level_values("SubEntity"):
            well_meta = bro_id_metadata.loc[
                (entity, bro_id, "Well"), :
            ]
            if not well_meta.empty:
                if "GroundLevel" in well_meta.columns:
                    obs_kwargs["ground_level"] = well_meta["GroundLevel"].iloc[0]

        obs = Obs(ts_df, **obs_kwargs)
        obs_list.append(obs)

    return ObsCollection(obs_list, name=name)
