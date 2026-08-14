"""brofopy version information."""

from importlib import import_module, metadata
from platform import python_version

from packaging.requirements import Requirement

__version__ = "0.0.1"


def get_versions(optional: bool = False) -> dict[str, str]:
    """Get version of dependencies.

    Parameters
    ----------
    optional: bool, optional
        Add the version of optional dependencies if installed.

    Returns
    -------
    dict[str, str]
        Dictionary with the version of the dependencies.

    """
    version_dict = {
        "python": python_version(),
        "brofopy": __version__,
    }

    requirements = metadata.requires("brofopy")
    if requirements:
        deps = [Requirement(x).name for x in requirements if "extra" not in x]
        for dep in deps:
            version_dict[dep] = metadata.version(dep)
    if optional and requirements:
        optional_deps = [Requirement(x).name for x in requirements if "extra" in x]
        for dep in optional_deps:
            try:
                import_module(dep)
                version_dict[dep] = metadata.version(dep)
            except ModuleNotFoundError:
                version_dict[dep] = "not installed"

    return version_dict


def show_versions(optional: bool = False) -> None:
    """Print the version of dependencies.

    Parameters
    ----------
    optional: bool, optional
        Print the version of optional dependencies if installed

    """
    version_dict = get_versions(optional=optional)

    max_len_key = max(len(key) for key in version_dict) + 1
    msg = ""
    for key, value in version_dict.items():
        leftside = f"{key.capitalize()}"
        msg += f"{leftside:<{max_len_key}}: {value}\n"

    print(msg)
