"""Protocol module for extracting and comparing HDF5 file structures."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h5py


@dataclass
class DatasetInfo:
    """Information about an HDF5 dataset."""

    shape: tuple
    dtype: str
    size: int

    def __repr__(self) -> str:
        return f"Dataset(shape={self.shape}, dtype={self.dtype})"


@dataclass
class GroupInfo:
    """Information about an HDF5 group."""

    datasets: dict[str, DatasetInfo] = field(default_factory=dict)
    groups: dict[str, "GroupInfo"] = field(default_factory=dict)

    def __repr__(self) -> str:
        parts = []
        if self.datasets:
            parts.append(f"datasets={list(self.datasets.keys())}")
        if self.groups:
            parts.append(f"groups={list(self.groups.keys())}")
        return f"Group({', '.join(parts)})"


@dataclass
class HDF5Structure:
    """Complete structure of an HDF5 file.

    This class provides a clean way to extract, compare, and display HDF5 file
    structures using Python dataclasses.

    Attributes
    ----------
    groups : dict[str, GroupInfo]
        Top-level groups in the file.
    datasets : dict[str, DatasetInfo]
        Top-level datasets in the file.

    Example
    -------
    >>> struct1 = HDF5Structure.from_file('file1.hdf5')
    >>> struct2 = HDF5Structure.from_file('file2.hdf5')
    >>>
    >>> # Compare structures
    >>> if struct1 == struct2:
    ...     print("Structures match!")
    >>>
    >>> # Access groups and datasets
    >>> print(f"Groups: {list(struct1.groups.keys())}")
    >>> print(f"Datasets: {list(struct1.datasets.keys())}")
    >>>
    >>> # Get all groups/datasets as flat lists
    >>> all_groups = struct1.get_all_groups()
    >>> all_datasets = struct1.get_all_datasets()
    >>>
    >>> # Print structure
    >>> struct1.print()
    """

    groups: dict[str, GroupInfo] = field(default_factory=dict)
    datasets: dict[str, DatasetInfo] = field(default_factory=dict)

    @classmethod
    def from_file(cls, filepath: str | Path) -> "HDF5Structure":
        """Create an HDF5Structure from a file path.

        Parameters
        ----------
        filepath : str or Path
            Path to the HDF5 file.

        Returns
        -------
        HDF5Structure
            The structure of the HDF5 file.
        """
        filepath = Path(filepath)

        def build_structure(name: str, obj: h5py.Group | h5py.Dataset) -> GroupInfo:
            """Recursively build GroupInfo structure from HDF5 object."""
            if isinstance(obj, h5py.Group) and (
                name.startswith("#refs#") or name.startswith("#subsystem#")
            ):
                return GroupInfo()

            if isinstance(obj, h5py.Dataset):
                return GroupInfo(
                    datasets={
                        name: DatasetInfo(
                            shape=obj.shape, dtype=str(obj.dtype), size=obj.size
                        )
                    }
                )

            group_info = GroupInfo()
            for item_name, item_obj in obj.items():
                if isinstance(item_obj, h5py.Group):
                    group_info.groups[item_name] = build_structure(item_name, item_obj)
                elif isinstance(item_obj, h5py.Dataset):
                    group_info.datasets[item_name] = DatasetInfo(
                        shape=item_obj.shape,
                        dtype=str(item_obj.dtype),
                        size=item_obj.size,
                    )
            return group_info

        with h5py.File(filepath, "r") as f:
            groups = {}
            datasets = {}
            for name, obj in f.items():
                if not (name.startswith("#refs#") or name.startswith("#subsystem#")):
                    if isinstance(obj, h5py.Group):
                        groups[name] = build_structure(name, obj)
                    elif isinstance(obj, h5py.Dataset):
                        datasets[name] = DatasetInfo(
                            shape=obj.shape, dtype=str(obj.dtype), size=obj.size
                        )
            return cls(groups=groups, datasets=datasets)

    def to_dict(self) -> dict[str, Any]:
        """Convert to nested dictionary format.

        Returns
        -------
        dict
            Nested dictionary representation of the structure.
        """
        result: dict[str, Any] = {}
        for name, group in self.groups.items():
            result[name] = self._group_to_dict(group)
        for name, ds in self.datasets.items():
            result[name] = {
                "type": "dataset",
                "shape": ds.shape,
                "dtype": ds.dtype,
                "size": ds.size,
            }
        return result

    def _group_to_dict(self, group: GroupInfo) -> dict[str, Any]:
        """Recursively convert GroupInfo to dict."""
        result: dict[str, Any] = {"type": "group"}
        if group.datasets:
            result["datasets"] = {
                name: {
                    "type": "dataset",
                    "shape": ds.shape,
                    "dtype": ds.dtype,
                    "size": ds.size,
                }
                for name, ds in group.datasets.items()
            }
        if group.groups:
            result["groups"] = {
                name: self._group_to_dict(grp) for name, grp in group.groups.items()
            }
        return result

    def get_all_groups(self) -> list[str]:
        """Get a flat list of all group paths.

        Returns
        -------
        list
            All group paths in the structure.
        """
        groups = ["/"]

        def collect_groups(group: GroupInfo, path: str = "") -> None:
            for name, subgroup in group.groups.items():
                full_path = f"{path}/{name}" if path else name
                groups.append(full_path)
                collect_groups(subgroup, full_path)

        for name, group in self.groups.items():
            groups.append(name)
            collect_groups(group, name)

        return groups

    def get_all_datasets(self) -> list[tuple[str, tuple, str]]:
        """Get a flat list of all datasets with their info.

        Returns
        -------
        list
            List of (path, shape, dtype) tuples for each dataset.
        """
        datasets: list[tuple[str, tuple, str]] = []

        def collect_datasets(group: GroupInfo, path: str = "") -> None:
            for name, ds in group.datasets.items():
                full_path = f"{path}/{name}" if path else name
                datasets.append((full_path, ds.shape, ds.dtype))
            for name, subgroup in group.groups.items():
                full_path = f"{path}/{name}" if path else name
                collect_datasets(subgroup, full_path)

        for name, ds in self.datasets.items():
            datasets.append((name, ds.shape, ds.dtype))
        for name, group in self.groups.items():
            collect_datasets(group, name)

        return datasets

    def print(self, indent: int = 0) -> None:
        """Pretty print the structure.

        Parameters
        ----------
        indent : int, default 0
            Starting indentation level.
        """
        prefix = "  " * indent

        for name, info in self.datasets.items():
            print(f"{prefix}{name}: {info.shape} {info.dtype}")
        for name, info in self.groups.items():
            print(f"{prefix}{name}/ (group)")
            self._print_group_info(info, indent + 1)

    def _print_group_info(self, group: GroupInfo, indent: int) -> None:
        """Helper to print a GroupInfo recursively."""
        prefix = "  " * indent
        for ds_name, ds_info in group.datasets.items():
            print(f"{prefix}  {ds_name}: {ds_info.shape} {ds_info.dtype}")
        for grp_name, grp_info in group.groups.items():
            print(f"{prefix}  {grp_name}/ (group)")
            self._print_group_info(grp_info, indent + 1)


# Backward compatibility alias
get_hdf5_structure = HDF5Structure.from_file


# Example usage
if __name__ == "__main__":
    testdata_path = Path(__file__).parent.parent.parent / "tests/data/"

    for file in testdata_path.glob("*.hdf5"):
        print(f"\n{'=' * 60}")
        print(f"File: {file.name}")
        print("=" * 60)

        structure = HDF5Structure.from_file(file)
        structure.print()
