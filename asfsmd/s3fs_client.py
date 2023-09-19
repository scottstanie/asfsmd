"""Asfsmd client based on s3fs."""

import zipfile
import contextlib
from typing import Optional

import requests
from concurrent.futures import ThreadPoolExecutor

from .common import AbstractClient, Auth, Url

import earthaccess


class S3FSClient(AbstractClient):
    """S3Fs based asfsmd client."""

    def __init__(self, auth: Auth, block_size: Optional[int] = None):
        """Initialize the s3fs based client."""
        earthaccess.login()
        self._fs = earthaccess.get_s3fs_session("ASF")

    @contextlib.contextmanager
    def open_zip_archive(self, url: Url) -> zipfile.ZipFile:
        """Context manager for the remote zip archive."""
        with self._fs.open(url, "rb") as fd:
            with zipfile.ZipFile(fd) as zf:
                yield zf


Client = S3FSClient


def get_s3_direct_urls(
    safe_names: list[str], max_workers: int = 5
) -> str | None:
    """Get the concept urls for a list of SAFE granules."""

    def _get_url(safe_name):
        try:
            item_url = "https://cmr.earthdata.nasa.gov/stac/ASF/collections/SENTINEL-1{sat}_SLC.v1/items/{safe_name}-SLC"
            # example:
            # https://cmr.earthdata.nasa.gov/stac/ASF/collections/SENTINEL-1A_SLC.v1/items/S1A_IW_SLC__1SDV_20150302T000329_20150302T000356_004845_006086_51B0-SLC
            sat = "A" if safe_name.startswith("S1A") else "B"
            resp = requests.get(item_url.format(safe_name=safe_name, sat=sat))
            resp.raise_for_status()
            js = resp.json()

            # Get the "Concept" url which has the S2 bucked
            # example: "https://cmr.earthdata.nasa.gov/search/concepts/G1345380784-ASF.json"
            concept_url = [
                link["href"]
                for link in js["links"]
                if link["href"].endswith("-ASF.json")
            ][-1]

            # Now using the concept url, get the S3 bucket in one of the links.
            # It will be the one that starts with "s3://"
            resp = requests.get(concept_url)
            resp.raise_for_status()
            js = resp.json()
            s3_url = [
                link["href"]
                for link in js["links"]
                if link["href"].startswith("s3://")
            ][0]
            return s3_url
        except Exception as e:
            print(f"{safe_name} failed: {e}")
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        urls = list(executor.map(_get_url, safe_names))
    return urls
