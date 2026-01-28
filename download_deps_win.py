#!/usr/bin/env python3

import argparse
import os
import urllib.request
from typing import Union

import nltk
from huggingface_hub import snapshot_download


def get_urls(use_china_mirrors=False) -> list[Union[str, list[str]]]:
    if use_china_mirrors:
        return [
            "https://repo.huaweicloud.com/repository/maven/org/apache/tika/tika-server-standard/3.2.3/tika-server-standard-3.2.3.jar",
            "https://repo.huaweicloud.com/repository/maven/org/apache/tika/tika-server-standard/3.2.3/tika-server-standard-3.2.3.jar.md5",
            "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
            ["https://registry.npmmirror.com/-/binary/chrome-for-testing/121.0.6167.85/win64/chrome-win64.zip", "chrome-win64-121-0-6167-85.zip"],
            ["https://registry.npmmirror.com/-/binary/chrome-for-testing/121.0.6167.85/win64/chromedriver-win64.zip", "chromedriver-win64-121-0-6167-85.zip"],
        ]
    else:
        return [
            "https://repo1.maven.org/maven2/org/apache/tika/tika-server-standard/3.2.3/tika-server-standard-3.2.3.jar",
            "https://repo1.maven.org/maven2/org/apache/tika/tika-server-standard/3.2.3/tika-server-standard-3.2.3.jar.md5",
            "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
            ["https://storage.googleapis.com/chrome-for-testing-public/121.0.6167.85/win64/chrome-win64.zip", "chrome-win64-121-0-6167-85.zip"],
            ["https://storage.googleapis.com/chrome-for-testing-public/121.0.6167.85/win64/chromedriver-win64.zip", "chromedriver-win64-121-0-6167-85.zip"],
        ]


repos = [
    "InfiniFlow/text_concat_xgb_v1.0",
    "InfiniFlow/deepdoc",
]


def download_model(repository_id):
    local_directory = os.path.abspath(os.path.join("huggingface.co", repository_id))
    os.makedirs(local_directory, exist_ok=True)
    snapshot_download(repo_id=repository_id, local_dir=local_directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download dependencies with optional China mirror support for Windows")
    parser.add_argument("--china-mirrors", action="store_true", help="Use China-accessible mirrors for downloads")
    args = parser.parse_args()

    urls = get_urls(args.china_mirrors)

    for url in urls:
        download_url = url[0] if isinstance(url, list) else url
        filename = url[1] if isinstance(url, list) else url.split("/")[-1]
        print(f"Downloading {filename} from {download_url}...")
        if not os.path.exists(filename):
            try:
                urllib.request.urlretrieve(download_url, filename)
            except Exception as e:
                print(f"Error downloading {filename}: {e}")

    local_dir = os.path.abspath("nltk_data")
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
        
    for data in ["wordnet", "punkt", "punkt_tab"]:
        print(f"Downloading nltk {data}...")
        try:
            nltk.download(data, download_dir=local_dir)
        except Exception as e:
            print(f"Error downloading nltk {data}: {e}")

    for repo_id in repos:
        print(f"Downloading huggingface repo {repo_id}...")
        try:
            download_model(repo_id)
        except Exception as e:
            print(f"Error downloading repo {repo_id}: {e}")
