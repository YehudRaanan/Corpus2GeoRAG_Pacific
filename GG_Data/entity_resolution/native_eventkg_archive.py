"""Download the official EventKG archive and filter its native metadata to corpus QIDs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import logging
import re
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from attach_source_page_ids import save_json, sha256
from native_corpus_graphs import OUTPUT

LOG = logging.getLogger(__name__)
URL = "https://zenodo.org/records/10424118/files/eventkg_v3_2_output.tar.gz?download=1"
SIZE = 7_807_417_165
MD5 = "99d8e0fdba68cea788773855ba4dc7ff"
QID_RE = re.compile(rb"<http://www\.wikidata\.org/entity/(Q[0-9]+)>")
SOURCES = {
    "events.nq",
    "entities.nq",
    "types.nq",
    "types_dbpedia.nq",
    "types_wikidata.nq",
    "preferred_labels.nq",
}


def check_range(
    status: int, header: str | None, start: int, end: int, total: int
) -> None:
    if status != 206 or header != f"bytes {start}-{end}/{total}":
        raise ValueError(f"Unexpected archive range: {status} {header}")


def download(output: Path) -> None:
    folder = output / "eventkg_archive"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "eventkg_v3_2_output.tar.gz"
    if archive.exists():
        raise FileExistsError(
            f"Archive already exists: {archive}; verify rather than overwrite"
        )
    chunk = 128 * 1024 * 1024
    intervals = [(i, min(i + chunk - 1, SIZE - 1)) for i in range(0, SIZE, chunk)]
    started = time.monotonic()

    def fetch(interval: tuple[int, int]) -> Path:
        start, end = interval
        path = folder / f"range_{start:012d}.bin"
        if path.exists():
            if path.stat().st_size != end - start + 1:
                raise ValueError(f"Incomplete saved archive range: {path}")
            return path
        with requests.get(
            URL,
            headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"},
            stream=True,
            timeout=(30, 90),
        ) as response:
            check_range(
                response.status_code,
                response.headers.get("Content-Range"),
                start,
                end,
                SIZE,
            )
            with path.open("xb") as stream:
                for block in response.iter_content(1024 * 1024):
                    stream.write(block)
        if path.stat().st_size != end - start + 1:
            raise ValueError(f"Short archive range: {path}")
        return path

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(fetch, interval) for interval in intervals]
        completed = 0
        for future in as_completed(jobs):
            path = future.result()
            completed += path.stat().st_size
            LOG.info(
                "Archive download %.1f%% (%s/%s bytes), %.1f elapsed seconds",
                100 * completed / SIZE,
                completed,
                SIZE,
                time.monotonic() - started,
            )
    digest = hashlib.md5()
    strong = hashlib.sha256()
    with archive.open("xb") as target:
        for start, _ in intervals:
            with (folder / f"range_{start:012d}.bin").open("rb") as source:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    digest.update(block)
                    strong.update(block)
                    target.write(block)
    if digest.hexdigest() != MD5 or archive.stat().st_size != SIZE:
        raise ValueError("EventKG archive does not match the published size/MD5")
    save_json(
        folder / "download_manifest.json",
        {
            "url": URL,
            "release": "3.2",
            "bytes": SIZE,
            "published_md5": MD5,
            "verified_md5": digest.hexdigest(),
            "sha256": strong.hexdigest(),
            "elapsed_seconds": time.monotonic() - started,
            "workers": 4,
            "range_bytes": chunk,
        },
    )
    LOG.info("Archive downloaded and checksum verified")


def matching_qids(lines: list[bytes], qids: set[bytes]) -> set[bytes]:
    return {
        qid for line in lines if b"owl#sameAs>" in line for qid in QID_RE.findall(line)
    } & qids


def filter_archive(output: Path) -> None:
    folder = output / "eventkg_archive"
    archive = folder / "eventkg_v3_2_output.tar.gz"
    # The verified download manifest is required; do not claim coverage of an incomplete archive.
    from attach_source_page_ids import read_json

    manifest = read_json(folder / "download_manifest.json")
    if (
        manifest["verified_md5"] != MD5
        or archive.stat().st_size != SIZE
        or sha256(archive) != manifest["sha256"]
    ):
        raise ValueError("Missing verified official archive")
    qids = {
        qid.encode("ascii")
        for qid in pd.read_parquet(output / "title_qid_mapping.parquet").qid.dropna()
    }
    selected = folder / "corpus"
    selected.mkdir(exist_ok=True)
    resources: dict[bytes, set[bytes]] = {}
    stats = {
        "source": manifest,
        "corpus_qids": len(qids),
        "members": [],
        "metadata_sources": sorted(SOURCES),
        "completed": False,
        "title_qid_mapping_sha256": sha256(output / "title_qid_mapping.parquet"),
    }
    for phase in [1, 2]:
        with tarfile.open(archive, "r|gz", bufsize=4 * 1024 * 1024) as tar:
            for member in tar:
                name = Path(member.name).name
                if phase == 1:
                    stats["members"].append({"name": member.name, "bytes": member.size})
                wanted = {"events.nq", "entities.nq"} if phase == 1 else SOURCES
                if name not in wanted:
                    continue
                LOG.info(
                    "Archive filter phase %s: %s (%s bytes)", phase, name, member.size
                )
                count = 0
                source = tar.extractfile(member)
                if source is None:
                    raise ValueError(f"Missing archive member data: {member.name}")
                if phase == 1:
                    with source:
                        for line in source:
                            if b"owl#sameAs>" not in line:
                                continue
                            found = matching_qids([line], qids)
                            if found:
                                subject = line.split(b" ", 1)[0]
                                resources.setdefault(subject, set()).update(found)
                                count += 1
                    LOG.info(
                        "Archive identity scan matched %s QID assertions in %s",
                        count,
                        name,
                    )
                else:
                    with source, gzip.open(selected / (name + ".gz"), "xb") as target:
                        for line in source:
                            if line.split(b" ", 1)[0] in resources:
                                target.write(line)
                                count += 1
                    LOG.info("Archive filter saved %s assertions from %s", count, name)
        if phase == 1:
            with (selected / "resource_qids.tsv").open("x", encoding="ascii") as stream:
                for resource, ids in sorted(resources.items()):
                    for qid in sorted(ids):
                        stream.write(qid.decode() + "\t" + resource.decode() + "\n")
            LOG.info("Archive QID scan: %s resources", len(resources))
    present = {Path(x["name"]).name for x in stats["members"]}
    if not SOURCES <= present:
        raise ValueError(
            f"Missing official archive metadata members: {SOURCES - present}"
        )
    stats.update(
        completed=True,
        matched_resources=len(resources),
        found_qids=len(set().union(*resources.values())) if resources else 0,
        output_sha256={path.name: sha256(path) for path in sorted(selected.iterdir())},
    )
    save_json(folder / "filter_manifest.json", stats)
    LOG.info("Full archive corpus filtering complete: %s resources", len(resources))


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("stage", choices=["download", "filter"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    {"download": download, "filter": filter_archive}[args.stage](args.output)


if __name__ == "__main__":
    main()
