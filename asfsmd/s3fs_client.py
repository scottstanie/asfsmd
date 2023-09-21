"""Asfsmd client based on s3fs."""

import os
import zipfile
import contextlib
import logging
from typing import Optional

import requests
from concurrent.futures import ThreadPoolExecutor

import s3fs
from .common import AbstractClient, Auth, Url

# import earthaccess


COLLECTION_CONCEPT_ID_S1A = "C1214470488-ASF"
COLLECTION_CONCEPT_ID_S1B = "C1327985661-ASF"
# CMR_AUTH = earthaccess.login()
# FS = earthaccess.get_s3fs_session("ASF")
# earthaccess.get_s3_credentials()
# FS = s3fs.S3FileSystem(
#     # key=s3_credentials["accessKeyId"],
#     # secret=s3_credentials["secretAccessKey"],
#     # token=s3_credentials["sessionToken"],
#     key=os.environ["AWS_ACCESS_KEY_ID"],
#     secret=os.environ["AWS_SECRET_ACCESS_KEY"],
#     token=os.environ["AWS_SESSION_TOKEN"],
# )

_log = logging.getLogger(__name__)


class S3FSClient(AbstractClient):
    """S3Fs based asfsmd client."""

    def __init__(self, auth: Auth, block_size: Optional[int] = None):
        """Initialize the s3fs based client."""
        self._fs = s3fs.S3FileSystem(
            # key=os.environ["ACCESS_KEY_ID"],
            # secret=os.environ["SECRET_ACCESS_KEY"],
            # token=os.environ["SESSION_TOKEN"],
            key=os.environ["accessKeyId"],
            secret=os.environ["secretAccessKey"],
            token=os.environ["sessionToken"],
        )

    @contextlib.contextmanager
    def open_zip_archive(self, url: Url) -> zipfile.ZipFile:
        """Context manager for the remote zip archive."""
        with self._fs.open(url, "rb") as fd:
            with zipfile.ZipFile(fd) as zf:
                yield zf


Client = S3FSClient


def _get_cmr_concept_id(safe_name: str) -> str:
    sat = "A" if safe_name.startswith("S1A") else "B"
    return (
        COLLECTION_CONCEPT_ID_S1A if sat == "A" else COLLECTION_CONCEPT_ID_S1B
    )


def _get_edl_token() -> dict[str, str]:
    # return CMR_AUTH.token['access_token']
    return os.environ["CMR_TOKEN"]


def _get_s3_url(safe_name: str) -> str | None:
    cmr_collection_id = _get_cmr_concept_id(safe_name)
    cmr_query_url = f"https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id={cmr_collection_id}&producer_granule_id={safe_name}"
    resp = requests.get(
        cmr_query_url, headers={"Authorization": f"Bearer {_get_edl_token()}"}
    )
    resp.raise_for_status()
    js = resp.json()
    
    try:
        s3_url = js["feed"]["entry"][0]["links"]
    except IndexError:
        _log.error(f"Could not find links for {safe_name} in CMR")
        return None

    try:
        # Get the one which starts with "s3://"
        s3_url = [
            link["href"] for link in s3_url if link["href"].startswith("s3://")
        ][0]
    except IndexError:
        _log.error(f"Could not S3 link for {safe_name} in CMR")
        return None

    return s3_url


def _get_url_stac(safe_name):
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


def get_s3_direct_urls(
    safe_names: list[str], max_workers: int = 3
) -> str | None:
    """Get the concept urls for a list of SAFE granules."""

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        urls = list(executor.map(_get_s3_url, safe_names))
    return [u for u in urls if u is not None]
