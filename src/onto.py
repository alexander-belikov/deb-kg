import time
from dataclasses import dataclass
from typing import List, Optional, Set
import logging
import requests
from suthing import FileHandle
from tqdm import tqdm

from src.util import crawl_directories

logger = logging.getLogger(__name__)


@dataclass
class Package:
    name: str
    version: str
    architecture: str
    maintainer: str
    description: str
    section: str
    priority: str
    dependencies: List[str]
    recommends: List[str]
    suggests: List[str]
    homepage: Optional[str]
    source_package: Optional[str]
    license: Optional[str]


@dataclass
class Maintainer:
    name: str
    email: str
    packages: Set[str]


@dataclass
class CVE:
    cve_id: str
    description: str
    severity: str
    affected_packages: List[str]
    published_date: str


@dataclass
class ReproducibilityStatus:
    package: str
    version: str
    architecture: str
    status: str
    build_date: str
    issues: List[str]


class DebianMetadataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "DebianKnowledgeGraph/1.0 (Research Project)"}
        )

        # API endpoints
        self.udd_api_base = "http://udd.progval.net"
        self.sources_api_base = "https://sources.debian.org/api"
        self.security_tracker_base = "https://security-tracker.debian.org"
        self.reproducible_builds_base = "https://tests.reproducible-builds.org"

        # Data storage
        self.packages = {}
        self.maintainers = {}
        self.cves = {}
        self.reproducibility_data = {}

    def fetch_package_list(self, cwd) -> list[dict]:
        """Fetch a list of source packages using Debian Sources API"""
        logger.info("Fetching package list using sources.debian.org API")

        url = f"{self.sources_api_base}/list/"

        try:
            packages = FileHandle.load(cwd / "packages_names.json")
        except Exception as e:
            logger.warning(f"Failed to load packages: {e}")
            try:
                response = self.session.get(url, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    packages = data.get("packages", [])
                    if packages:
                        FileHandle.dump(packages, cwd / "packages_names.json")
                else:
                    logger.warning(
                        f"Failed to fetch source packages: {response.status_code}"
                    )
            except Exception as e:
                packages = []
                logger.error(f"Exception fetching source package list: {e}")

        return packages

    def fetch_package_metadata(
        self, package_name: str, distribution: str = "sid"
    ) -> Optional[Package]:
        """Fetch detailed metadata for a single package using sources.debian.org"""
        url = f"{self.sources_api_base}/src/{package_name}/"

        try:
            response = self.session.get(url, timeout=20)
            if response.status_code != 200:
                logger.warning(f"No metadata found for {package_name}")
                return None

            data = response.json()
            return data
        except Exception as e:
            logger.error(f"Error fetching metadata for {package_name}: {e}")

        return None

    def fetch_package_info(self, package_names: List[dict], cwd, head=None):
        """Build knowledge graph data structure"""
        package_cwd = cwd / "package"
        package_cwd.mkdir(parents=True, exist_ok=True)

        files = sorted(
            crawl_directories(
                package_cwd,
                suffixes=tuple([".json"]),
            )
        )

        package_names_str = [item["name"] for item in package_names]
        present_package_names = [f.stem for f in files]

        package_names_str = [
            x for x in package_names_str if x not in present_package_names
        ]

        pnames = package_names_str if head is None else package_names_str[:head]
        for package_name in tqdm(pnames, desc="Fetching packages", colour="green"):
            data = self.fetch_package_metadata(package_name)
            FileHandle.dump(data, package_cwd / f"{package_name}.json")
            time.sleep(0.2)

    def get_package_info(self, cwd, condition):
        """Build knowledge graph data structure"""
        package_cwd = cwd / "package"
        package_cwd.mkdir(parents=True, exist_ok=True)

        files = sorted(
            crawl_directories(
                package_cwd,
                suffixes=tuple([".json"]),
            )
        )

        agg = []

        for f in files:
            data = FileHandle.load(f)
            if data is None:
                logger.error(f"empty file {f}")
                continue
            versions = data.pop("versions")
            for v in versions:
                if any(x == condition["suite"] for x in v["suites"]):
                    agg += [
                        {
                            "name": data["package"],
                            "version": v["version"],
                            "suite": condition["suite"],
                        }
                    ]

        return agg
