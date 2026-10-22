#### Preamble ####
# Purpose: Download a file from Harvard Dataverse and check it arrived intact.
#          Used by:
#            #3  scripts/01-download_election_data.py: CES 2024, CES 2022, and possibly the MIT Election Lab
#                results (also on Dataverse)
# Author: Sean Murphy
# Date: 22 October 2026
# Pre-requisites: none (uses only Python's standard library)

import hashlib
import urllib.request
from pathlib import Path

DATAVERSE_FILE_URL = "https://dataverse.harvard.edu/api/access/datafile/{file_id}"
CHUNK_BYTES = 1024 * 1024  # read and write 1 MB at a time, so a large file never has to fit in memory
# Dataverse refuses requests that use Python's default name ("Python-urllib"), so say who we are.
USER_AGENT = "senate-forecast-2026 (University of Toronto course project)"


def md5_of(path):
    """The MD5 checksum of a file: a short fingerprint that changes if even one byte of the file is different."""
    checksum = hashlib.md5()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(CHUNK_BYTES)
            if not chunk:
                break
            checksum.update(chunk)
    return checksum.hexdigest()


def download_dataverse_file(file_id, expected_md5, in_path):
    """Download Dataverse file `file_id` to `path`, unless it is already there, and check its MD5 checksum.

    The file ID and checksum are listed on the dataset's Dataverse page. If the file at `path` already has the
    right checksum, nothing is downloaded, so the script can be rerun freely. The download goes to a temporary
    ".part" file first, renamed only once the checksum matches, so a broken download never looks complete."""

    # tell user what is being downloaded (or checked if it exists)
    path = Path(in_path)
    print(f'\nPreparing to download {path.name}')

    if path.exists() and md5_of(path) == expected_md5:
        print(f"{path} is already downloaded and intact; skipping.", flush=True)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    # saves parts of the download while in progress
    partial_path = path.with_name(path.name + ".part")
    # .format works the same as f-strings
    url = DATAVERSE_FILE_URL.format(file_id=file_id)
    print(f"Downloading {url} to {path}", flush=True)

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response, open(partial_path, "wb") as output:
        total_bytes = int(response.headers.get("Content-Length", 0))
        downloaded_bytes = 0
        next_report_percent = 10
        while True:
            chunk = response.read(CHUNK_BYTES)
            if not chunk:
                break
            output.write(chunk)
            downloaded_bytes += len(chunk)
            # Progress every 10%, so a long download is visibly still running. One chunk can pass more than one
            # 10% mark on a small file, so report every mark it passed.
            while total_bytes and downloaded_bytes / total_bytes * 100 >= next_report_percent:
                print(f"  {next_report_percent}% ({downloaded_bytes / 1e6:,.0f} of {total_bytes / 1e6:,.0f} MB)", flush=True)
                next_report_percent += 10

    actual_md5 = md5_of(partial_path)
    if actual_md5 != expected_md5:
        partial_path.unlink()  # delete the broken download
        raise ValueError(f"Checksum mismatch for {path.name}: expected {expected_md5}, got {actual_md5}. Try again.")
    partial_path.rename(path)
    print(f"Done: {path} ({path.stat().st_size / 1e6:,.1f} MB, checksum OK).", flush=True)
