"""Check that the packages (and pinned versions) in a requirements.txt exist on PyPI.

Uses the PyPI JSON API: https://docs.pypi.org/api/json/
Only the standard library is used (urllib for HTTP, json for parsing).

Usage: python check_requirements.py [path/to/requirements.txt]
"""

import json  # parse the JSON responses from PyPI
import sys  # read the optional command-line argument
import urllib.error  # HTTPError, to detect 404 (not found)
import urllib.request  # send the HTTP requests to PyPI

# Base URL of the PyPI JSON API.
# Project endpoint: https://pypi.org/pypi/<project>/json
# Release endpoint: https://pypi.org/pypi/<project>/<version>/json
PYPI_URL = "https://pypi.org/pypi"

def parse_requirements(path):
    """Read the requirements file and return a list of (name, version) tuples.

    Every line is expected to be a pin like "requests==2.31.0" or "django=1.11".
    """
    requirements = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines
            if not line:
                continue
            # "requests==2.31.0" or "requests=2.31.0" -> ("requests", "2.31.0")
            name, version = line.replace("==", "=").split("=")
            requirements.append((name, version))
    return requirements


def fetch_json(package, version=None):
    """Fetch the PyPI JSON data for a package, or for one version of it.

    fetch_json("requests")           -> https://pypi.org/pypi/requests/json
    fetch_json("requests", "2.31.0") -> https://pypi.org/pypi/requests/2.31.0/json

    Returns the parsed JSON as a dict, or None if PyPI answers 404 (not found).
    Any other HTTP or network error is raised.
    """
    if version:
        url = f"{PYPI_URL}/{package}/{version}/json"
    else:
        url = f"{PYPI_URL}/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    # Use the path from the command line, or requirements.txt in the current directory
    path = sys.argv[1] if len(sys.argv) > 1 else "requirements.txt"
    requirements = parse_requirements(path)

    missing_packages = []  # package names that don't exist on PyPI
    missing_versions = []  # "name==version" where the package exists but the version doesn't
    oldest = None  # oldest pinned release found so far: (upload_time, name, version)

    for name, version in requirements:
        # 1. Does the package exist at all?
        if fetch_json(name) is None:
            missing_packages.append(name)
            continue

        # 2. Does the pinned version exist?
        release = fetch_json(name, version)
        if release is None:
            missing_versions.append(f"{name}=={version}")
            continue

        # 3. Track the oldest release, using the upload_time of the first file under "urls".
        # upload_time is ISO 8601 ("2013-06-13T12:00:00"), so string comparison works.
        # Releases without any uploaded files have no upload_time and are skipped.
        files = release.get("urls") or []
        if files:
            upload_time = files[0]["upload_time"]
            if oldest is None or upload_time < oldest[0]:
                oldest = (upload_time, name, version)

    # Print the summary
    print(f"Checked dependencies: {len(requirements)}")
    print(f"Packages not on PyPI: {len(missing_packages)}")
    print(f"Versions not on PyPI: {len(missing_versions)}")
    if oldest:
        upload_time, name, version = oldest
        # The first 4 characters of the ISO timestamp are the year
        print(f"Oldest pinned release: {name}={version} ({upload_time[:4]})")
    else:
        print("Oldest pinned release: n/a")


if __name__ == "__main__":
    main()
