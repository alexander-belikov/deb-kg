#!/usr/bin/env python3
"""
Scrape Debian BTS for bugs by suite and component
"""

import debianbts
import click
import pathlib
import logging
from suthing import FileHandle
from tqdm import tqdm
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_bug_log(bug_log):
    """Parse bug log to extract date, status, and severity"""
    date = None
    status = None
    severity = None

    for entry in bug_log:
        header = entry.get("header", "")
        body = entry.get("body", "")

        # Extract date from header
        date_match = re.search(r"Date: (.+)", header)
        if date_match:
            date_str = date_match.group(1)
            try:
                date = datetime.strptime(
                    date_str, "%a, %d %b %Y %H:%M:%S %z"
                ).isoformat()
            except ValueError:
                pass

        # Extract status and severity from body
        status_match = re.search(r"Status: (.+)", body)
        if status_match:
            status = status_match.group(1).strip()

        severity_match = re.search(r"Severity: (.+)", body)
        if severity_match:
            severity = severity_match.group(1).strip()

    return {"date": date, "status": status, "severity": severity}


def convert_datetime_to_iso(bug_report):
    """Convert datetime objects in bug report to ISO format"""
    for key, value in bug_report.items():
        if isinstance(value, datetime):
            bug_report[key] = value.isoformat()
    return bug_report


@click.command()
@click.option("--input-dir", type=click.Path(path_type=pathlib.Path))
@click.option("--head", type=click.INT, help="Number of packages to process")
def scrape(input_dir, head):
    """Scrape Debian BTS for bugs by suite and component"""
    all_packages = FileHandle.load(input_dir / "package.meta.json.gz")
    if head:
        all_packages = all_packages[:head]

    bug_logs = []
    package_bugs = []

    for package in tqdm(all_packages, desc="Processing packages", colour="green"):
        name = package["name"]
        bug_ids = debianbts.get_bugs(package=name, status="open")
        package_bugs += [{"package": package, "bugs": bug_ids}]
        bug_reports = debianbts.get_status(bug_ids)
        bug_logs += [
            convert_datetime_to_iso(bug_report.__dict__) for bug_report in bug_reports
        ]
        # for bug_id in bug_ids:
        #     bug_log = debianbts.get_bug_log(bug_id)
        #     parsed_log = parse_bug_log(bug_log)
        #     bug_logs += [{"id": bug_id, **parsed_log, **bug_report.__dict__}]

    FileHandle.dump(bug_logs, input_dir / "bugs.json.gz")
    logger.info(f"Results written to {input_dir / 'bugs.json.gz'}")


if __name__ == "__main__":
    scrape()
