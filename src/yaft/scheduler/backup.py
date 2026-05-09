from __future__ import annotations

import asyncio
import datetime as dt
import gzip
import os
import sqlite3

from yaft.logging_setup import log


async def _rclone_copy(src: str, remote: str) -> tuple[int, bytes]:
    """Run `rclone copy <src> <remote>` with no shell. argv list only."""
    spawn = asyncio.create_subprocess_exec
    proc = await spawn(
        "rclone", "copy", src, remote,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    return proc.returncode or 0, err or b""


async def backup_sqlite(
    *,
    db_path: str,
    out_dir: str,
    keep_dailies: int = 30,
    keep_monthlies: int = 12,
    rclone_remote: str | None = None,
) -> str:
    """Online SQLite backup -> gzip -> optional rclone push, with retention.

    Uses sqlite3.Connection.backup() so writers can stay active during the copy.
    Retention: keep the last `keep_dailies` files plus the last gzipped file of
    each of the most recent `keep_monthlies` calendar months.
    """
    os.makedirs(out_dir, exist_ok=True)
    today = dt.date.today()
    stamp = today.strftime("%Y-%m-%d")
    raw = os.path.join(out_dir, f"finance-{stamp}.sqlite")
    gz = raw + ".gz"

    def _backup_sync() -> None:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(raw)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        with open(raw, "rb") as f_in, gzip.open(gz, "wb") as f_out:
            f_out.write(f_in.read())
        os.remove(raw)

    await asyncio.to_thread(_backup_sync)

    files = sorted(
        f for f in os.listdir(out_dir)
        if f.startswith("finance-") and f.endswith(".sqlite.gz")
    )
    by_month: dict[str, list[str]] = {}
    for f in files:
        ym = f[len("finance-"):len("finance-") + 7]
        by_month.setdefault(ym, []).append(f)
    keep = set(files[-keep_dailies:])
    for ym in sorted(by_month.keys())[-keep_monthlies:]:
        keep.add(by_month[ym][-1])
    for f in files:
        if f not in keep:
            try:
                os.remove(os.path.join(out_dir, f))
            except OSError:
                pass

    if rclone_remote:
        rc, err = await _rclone_copy(gz, rclone_remote)
        if rc != 0:
            log.warning(
                "scheduler.backup.rclone_failed",
                error=err.decode("utf-8", "ignore"),
            )

    log.info("scheduler.backup.done", path=gz, kept=len(keep))
    return gz
