"""
Debian Metadata Fetcher for Knowledge Graph Construction
Fetches package metadata, security data, and reproducibility information
"""

import requests
from bs4 import BeautifulSoup
import re

from onto import DebianMetadataFetcher
import logging
import click
import pathlib

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_debian_maintainers(item, version=None):
    package = item["package"]
    url = f"https://tracker.debian.org/pkg/{package}"
    if version:
        url += f"?version={version}"

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch page: {str(e)}"}

    soup = BeautifulSoup(response.text, "html.parser")
    maintainers_header = soup.find(
        "h2", text=re.compile(r"Maintainers?", re.IGNORECASE)
    )

    if not maintainers_header:
        return {
            "error": "Maintainers section not found - package may not exist or page structure changed"
        }

    results = {"maintainer": None, "uploaders": []}
    ul = maintainers_header.find_next("ul")

    if not ul:
        return {"error": "Maintainers list not found"}

    # Process maintainer
    maintainer_li = ul.find("li")
    if maintainer_li and "maintainer" in maintainer_li.text.lower():
        maintainer_text = maintainer_li.get_text(strip=True).replace("Maintainer:", "")
        email_match = re.search(r"<([^>]+@[^>]+)>", maintainer_text)
        name = re.split(r"<[^>]+>", maintainer_text)[0].strip()

        if email_match:
            results["maintainer"] = {"name": name, "email": email_match.group(1)}

    # Process uploaders
    for li in ul.find_all("li"):
        if "uploaders" in li.text.lower():
            for a in li.find_all("a", href=re.compile(r"^mailto:")):
                email = a["href"].replace("mailto:", "")
                name = a.get_text(strip=True)
                results["uploaders"].append({"name": name, "email": email})

    return results


@click.command()
@click.option(
    "--working-directory", type=click.Path(path_type=pathlib.Path), required=True
)
@click.option("--head", type=click.INT)
def main(working_directory: pathlib.Path, head):
    """Main execution function"""
    _ = DebianMetadataFetcher()
    working_directory = working_directory.expanduser()

    # package_names = fetcher.get_package_info(
    #     cwd=working_directory, condition={"suite": "bookworm"}
    # )
    # logger.info(f"Found {len(package_names)} packages to process")
    #
    # package_names = package_names[:2]

    package_names = [{"package": "plr"}]
    for p in package_names:
        _ = get_debian_maintainers(p)


if __name__ == "__main__":
    main()
