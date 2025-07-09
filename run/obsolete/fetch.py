"""
Debian Metadata Fetcher for Knowledge Graph Construction
Fetches package metadata, security data, and reproducibility information
"""

import logging
import click
import pathlib

from src.onto import DebianMetadataFetcher

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--working-directory", type=click.Path(path_type=pathlib.Path), required=True
)
@click.option("--head", type=click.INT)
def main(working_directory: pathlib.Path, head):
    """Main execution function"""
    fetcher = DebianMetadataFetcher()
    working_directory = working_directory.expanduser()

    # Fetch a sample of packages (adjust the limit as needed)
    package_names = fetcher.fetch_package_list(cwd=working_directory)
    logger.info(f"Found {len(package_names)} packages to process")

    # Build knowledge graph data
    fetcher.fetch_package_info(package_names, cwd=working_directory, head=head)


if __name__ == "__main__":
    main()
