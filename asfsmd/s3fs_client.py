"""Asfsmd client based on s3fs."""

import zipfile
import contextlib
from typing import Optional

import s3fs

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
