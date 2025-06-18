#!/usr/bin/env python3
"""
Two-step Debian package dependency fetcher:
1. Download cache
2. Parse cache separately
"""

import requests
import gzip
import pathlib
import click
from tqdm import tqdm
import logging
from suthing import FileHandle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_packages_file(
    mirror: str, suite: str, component: str, arch: str, cache_dir: pathlib.Path
):
    """Download Packages.gz file"""
    url = f"{mirror}/dists/{suite}/{component}/binary-{arch}/Packages.gz"
    filename = f"{suite}_{component}_{arch}_Packages.gz"
    output_path = cache_dir / filename

    if output_path.exists():
        logger.info(f"Already exists: {filename}")
        return output_path

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Downloaded {filename}")
        return output_path

    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return None


def parse_packages_file(packages_file: pathlib.Path, head: int = None):
    """Parse Packages.gz file"""
    packages = {}
    current_package = {}

    with gzip.open(packages_file, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                if current_package and "Package" in current_package:
                    pkg_name = current_package["Package"]
                    packages[pkg_name] = parse_package_data(current_package)
                    if head and len(packages) >= head:
                        break
                current_package = {}
                continue

            if ":" in line and not line.startswith(" "):
                key, value = line.split(":", 1)
                current_package[key.strip()] = value.strip()
            elif line.startswith(" ") and current_package:
                last_key = list(current_package.keys())[-1]
                current_package[last_key] += " " + line.strip()

    return packages


def parse_package_data(pkg_data: dict):
    """Extract package info and dependencies"""
    dependencies = {}
    dep_fields = [
        "Depends",
        "Pre-Depends",
        "Recommends",
        "Suggests",
        "Conflicts",
        "Breaks",
    ]

    for field in dep_fields:
        if field in pkg_data:
            deps = []
            aliases = []
            for dep in pkg_data[field].split(","):
                dep = dep.strip()
                if dep and not dep.startswith("${"):
                    parts = dep.split("|")
                    main_dep = parts[0].strip()
                    name_version = main_dep.split("(")
                    name = name_version[0].strip()
                    version = (
                        name_version[1].strip(")") if len(name_version) > 1 else None
                    )
                    item = {"name": name}
                    if version is not None:
                        item.update({"version": version})
                    deps.append(item)
                    if len(parts) > 1:
                        for alias in parts[1:]:
                            aliases.append({"source": name, "target": alias.strip()})
            dependencies[field.lower()] = deps
            if aliases:
                dependencies[field.lower() + "_aliases"] = aliases

    maintainer_info = pkg_data.get("Maintainer", "")
    maintainer_name = (
        maintainer_info.split("<")[0].strip()
        if "<" in maintainer_info
        else maintainer_info
    )
    maintainer_email = (
        maintainer_info.split("<")[1].strip(">") if "<" in maintainer_info else ""
    )

    return {
        "name": pkg_data["Package"],
        "version": pkg_data.get("Version", ""),
        "dependencies": dependencies,
        "description": pkg_data.get("Description", "").split("\n")[0],
        "maintainer": {"name": maintainer_name, "email": maintainer_email},
    }


@click.group()
def cli():
    """Debian package dependency fetcher"""
    pass


@cli.command()
@click.option(
    "--cache-dir", type=click.Path(path_type=pathlib.Path), default="./debian_cache"
)
@click.option("--suite", default="bookworm")
@click.option("--components", default="main,contrib,non-free")
@click.option("--arch", default="amd64")
@click.option("--mirror", default="http://deb.debian.org/debian")
def download(cache_dir, suite, components, arch, mirror):
    """Download Packages.gz files"""
    cache_dir = cache_dir.expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)

    components_list = [c.strip() for c in components.split(",")]

    for component in tqdm(components_list, desc="Downloading"):
        download_packages_file(mirror, suite, component, arch, cache_dir)

    logger.info(f"Cache stored in {cache_dir}")


@cli.command()
@click.option("--cache-dir", type=click.Path(path_type=pathlib.Path))
@click.option("--output-dir", type=click.Path(path_type=pathlib.Path))
@click.option("--head", type=click.INT, help="Number of packages to parse")
def parse(cache_dir, output_dir, head):
    """Parse downloaded cache for dependencies"""
    cache_dir = cache_dir.expanduser()
    output_dir = output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    packages_files = list(cache_dir.glob("*_Packages.gz"))

    if not packages_files:
        logger.error(f"No cache files found in {cache_dir}")
        return

    all_packages = []
    total_packages = 0

    with tqdm(
        total=sum(len(parse_packages_file(f, head)) for f in packages_files),
        desc="Processing packages",
    ) as pbar:
        for packages_file in packages_files:
            packages_data = parse_packages_file(packages_file, head)
            for pkg_name, pkg_data in packages_data.items():
                all_packages += [pkg_data]
                total_packages += 1
                pbar.update(1)

    FileHandle.dump(all_packages, output_dir / "package.meta.json.gz")

    found = len(all_packages)
    logger.info(f"Processed {found} packages → {output_dir}")


if __name__ == "__main__":
    cli()
