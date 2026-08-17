#!/usr/bin/env python3
"""Create a fixed futures cache snapshot ending at a chosen trading day."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from ctypes import sizeof
from pathlib import Path

from xqsim.data.data_manager import DATA_HEADER_LENGTH, DataHeader


def load_calendar(source: Path) -> tuple[list[int], dict[int, int]]:
    calendar_path = source / "meta" / "index" / "DateIndex.csv"
    with calendar_path.open(newline="", encoding="utf-8") as reader:
        rows = csv.DictReader(reader)
        dates = [int(row["TradingDay"]) for row in rows]
    if not dates or dates != sorted(dates) or len(dates) != len(set(dates)):
        raise RuntimeError(f"invalid calendar: {calendar_path}")
    return dates, {date: di for di, date in enumerate(dates)}


def resolve_cutoff(dates: list[int], requested: int) -> int:
    eligible = [date for date in dates if date <= requested]
    if not eligible:
        raise ValueError(f"cutoff {requested} precedes the cache calendar")
    return eligible[-1]


def read_header(path: Path) -> tuple[DataHeader, bytes]:
    with path.open("rb") as reader:
        block = reader.read(DATA_HEADER_LENGTH)
    if len(block) != DATA_HEADER_LENGTH:
        raise RuntimeError(f"short data header: {path}")
    header = DataHeader()
    header.decode(block)
    return header, block


def header_int(header: DataHeader, name: str) -> int:
    value = getattr(header, name)
    return int(value.decode("utf-8"))


def truncate_matrix(
    source: Path,
    target: Path,
    cutoff: int,
    di_mapping: dict[int, int],
) -> str:
    header, block = read_header(source)
    begin = header_int(header, "begin_trading_day")
    end = header_int(header, "end_trading_day")
    original_rows = header_int(header, "di_size")
    row_size = (
        header_int(header, "ti_size")
        * header_int(header, "ii_size")
        * header_int(header, "type_size")
    )
    expected_size = DATA_HEADER_LENGTH + original_rows * row_size
    if source.stat().st_size != expected_size:
        raise RuntimeError(
            f"matrix size mismatch: {source} "
            f"({source.stat().st_size} != {expected_size})"
        )
    if begin not in di_mapping or end not in di_mapping:
        raise RuntimeError(f"matrix dates not present in calendar: {source}")
    if begin > cutoff:
        return "skipped"
    target.parent.mkdir(parents=True, exist_ok=True)
    if end <= cutoff:
        shutil.copy2(source, target)
        return "copied"

    rows = di_mapping[cutoff] - di_mapping[begin] + 1
    payload_size = rows * row_size
    header.end_trading_day = str(cutoff).encode("utf-8")
    header.di_size = str(rows).encode("utf-8")
    header.last_trading_day = str(cutoff).encode("utf-8")
    encoded = header.encode()
    if len(encoded) != sizeof(DataHeader):
        raise RuntimeError("unexpected DataHeader encoding size")

    with source.open("rb") as reader, target.open("wb") as writer:
        reader.seek(DATA_HEADER_LENGTH)
        writer.write(encoded)
        writer.write(block[len(encoded):])
        remaining = payload_size
        while remaining:
            chunk = reader.read(min(8 * 1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError(f"short matrix payload: {source}")
            writer.write(chunk)
            remaining -= len(chunk)
    shutil.copystat(source, target)
    return "truncated"


def path_trading_day(path: Path, source: Path) -> int | None:
    relative = path.relative_to(source)
    for part in relative.parts:
        if len(part) == 8 and part.isdigit():
            return int(part)
    return None


def verify_snapshot(target: Path, cutoff: int) -> None:
    matrix_count = 0
    for path in target.rglob("*.dat"):
        header, _ = read_header(path)
        end = header_int(header, "end_trading_day")
        rows = header_int(header, "di_size")
        row_size = (
            header_int(header, "ti_size")
            * header_int(header, "ii_size")
            * header_int(header, "type_size")
        )
        if end > cutoff:
            raise RuntimeError(f"matrix exceeds cutoff: {path} ({end})")
        if path.stat().st_size != DATA_HEADER_LENGTH + rows * row_size:
            raise RuntimeError(f"snapshot matrix size mismatch: {path}")
        matrix_count += 1
    if matrix_count == 0:
        raise RuntimeError("snapshot contains no matrix files")

    for path in target.rglob("*.datlz4"):
        day = path_trading_day(path, target)
        if day is None or day > cutoff:
            raise RuntimeError(f"compressed daily file exceeds cutoff: {path}")
        header, _ = read_header(path)
        begin = header_int(header, "begin_trading_day")
        end = header_int(header, "end_trading_day")
        if begin != day or end != day:
            raise RuntimeError(
                f"compressed daily header mismatch: {path} ({begin} -- {end})"
            )


def create_snapshot(source: Path, target: Path, requested_cutoff: int) -> None:
    source = source.resolve()
    target = target.resolve()
    if not source.is_dir():
        raise FileNotFoundError(source)
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    if source == target or source in target.parents:
        raise ValueError(f"unsafe snapshot target: {target}")

    dates, di_mapping = load_calendar(source)
    cutoff = resolve_cutoff(dates, requested_cutoff)
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    if temporary.exists() or temporary.is_symlink():
        raise FileExistsError(temporary)

    counts = {"copied": 0, "truncated": 0, "skipped": 0}
    try:
        temporary.mkdir(parents=True)
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            destination = temporary / relative
            if path.is_dir():
                day = path_trading_day(path, source)
                if day is not None and day > cutoff:
                    continue
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if path.name.endswith(".datlz4"):
                day = path_trading_day(path, source)
                if day is None:
                    raise RuntimeError(f"daily file has no date directory: {path}")
                if day > cutoff:
                    counts["skipped"] += 1
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                counts["copied"] += 1
            elif path.name.endswith(".dat"):
                result = truncate_matrix(path, destination, cutoff, di_mapping)
                counts[result] += 1
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                counts["copied"] += 1

        verify_snapshot(temporary, cutoff)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    print(f"snapshot: {source} -> {target}")
    print(f"requested cutoff: {requested_cutoff}; trading-day cutoff: {cutoff}")
    print(
        "files copied: {copied}; matrices truncated: {truncated}; "
        "files skipped: {skipped}".format(**counts)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--cutoff", type=int, required=True, help="YYYYMMDD")
    args = parser.parse_args()
    create_snapshot(args.source, args.target, args.cutoff)


if __name__ == "__main__":
    main()
