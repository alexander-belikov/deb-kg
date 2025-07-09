"""
Debian Metadata Fetcher for Knowledge Graph Construction
Fetches package metadata, security data, and reproducibility information
"""

import requests
from bs4 import BeautifulSoup
import re

from tqdm import tqdm
from src.onto import DebianMetadataFetcher
import logging
import click
import pathlib
from src.util import crawl_directories
from suthing import FileHandle
from urllib.parse import unquote, urlparse, parse_qs


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_maintainers(soup):
    tags = ["maintainer", "uploaders"]
    results = {}

    for li in soup.find_all("li", class_="list-group-item"):
        key_span = li.find("span", class_="list-item-key")
        for tag in tags:
            if key_span and key_span.get_text(strip=True).lower().startswith(tag):
                name_tag = li.find("a", href=True)
                doc = {}
                if name_tag:
                    name = name_tag.text.strip()
                    parsed_url = urlparse(name_tag["href"])
                    query = parse_qs(parsed_url.query)
                    email_encoded = query.get("login", [""])[0]
                    doc["name"] = name
                    doc["email"] = unquote(email_encoded)

                    if tag in results:
                        results[tag] += [doc]
                    else:
                        results[tag] = [doc]

    return results


def extract_email_from_href(href):
    """Extract email from qa.debian.org developer link"""
    match = re.search(r"login=([^&#]+)", href)
    if match:
        return unquote(match.group(1))
    return None


def get_debian_maintainers(package_name, version=None):
    url = f"https://tracker.debian.org/pkg/{package_name}"
    if version:
        url += f"?version={version}"

    try:
        response = requests.get(
            url, headers={"User-Agent": "Debian Maintainer Scraper/1.0"}
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return extract_maintainers(soup)
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch page: {str(e)}"}
    except Exception as e:
        return {"error": f"Processing error: {str(e)}"}


@click.command()
@click.option(
    "--working-directory", type=click.Path(path_type=pathlib.Path), required=True
)
@click.option("--head", type=click.INT)
def main(working_directory: pathlib.Path, head):
    """Main execution function"""

    working_directory = working_directory.expanduser()
    output_directory = working_directory / "pack_main"
    output_directory.mkdir(parents=True, exist_ok=True)

    fetcher = DebianMetadataFetcher()

    package_names = fetcher.get_package_info(
        cwd=working_directory, condition={"suite": "bookworm"}
    )

    logger.info(f"Found {len(package_names)} packages to process")

    files = sorted(
        crawl_directories(
            output_directory,
            suffixes=tuple([".json"]),
        )
    )

    present_package_names = [f.stem for f in files]

    logger.info(f"about to discard {len(present_package_names)} packages")

    package_names = [x for x in package_names if x["name"] not in present_package_names]

    logger.info(f"Finally {len(package_names)} packages to process")

    pnames = package_names if head is None else package_names[:head]

    for p in tqdm(pnames, desc="Fetching pages", colour="green"):
        name = p["name"]
        info = get_debian_maintainers(name)
        r = {**p, **info}
        FileHandle.dump(r, output_directory / f"{name}.json")


if __name__ == "__main__":
    main()
