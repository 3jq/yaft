import gzip
import os
import sqlite3

from yaft.scheduler.backup import backup_sqlite


async def test_backup_produces_valid_gz(tmp_path):
    src = tmp_path / "f.db"
    con = sqlite3.connect(src)
    con.executescript(
        "CREATE TABLE t(x INTEGER); INSERT INTO t VALUES (1),(2),(3);"
    )
    con.commit()
    con.close()

    out_dir = tmp_path / "backups"
    out = await backup_sqlite(
        db_path=str(src),
        out_dir=str(out_dir),
        keep_dailies=2,
        keep_monthlies=2,
        rclone_remote=None,
    )
    assert os.path.exists(out)

    raw = gzip.decompress(open(out, "rb").read())
    restored = tmp_path / "r.db"
    restored.write_bytes(raw)
    con = sqlite3.connect(restored)
    assert con.execute("SELECT count(*) FROM t").fetchone() == (3,)
    con.close()


async def test_backup_retention_prunes_old_dailies(tmp_path):
    src = tmp_path / "f.db"
    sqlite3.connect(src).close()
    out_dir = tmp_path / "backups"
    out_dir.mkdir()

    # Seed 5 fake older daily backups across two months.
    fake_names = [
        "finance-2026-03-01.sqlite.gz",
        "finance-2026-03-15.sqlite.gz",
        "finance-2026-04-01.sqlite.gz",
        "finance-2026-04-15.sqlite.gz",
        "finance-2026-04-30.sqlite.gz",
    ]
    for n in fake_names:
        (out_dir / n).write_bytes(b"x")

    await backup_sqlite(
        db_path=str(src),
        out_dir=str(out_dir),
        keep_dailies=2,
        keep_monthlies=3,
        rclone_remote=None,
    )

    remaining = sorted(os.listdir(out_dir))
    # keep_monthlies=3 retains the last gzip of March/April/May, plus
    # keep_dailies=2 retains the 2 most recent files.
    assert "finance-2026-03-15.sqlite.gz" in remaining  # March tail
    assert "finance-2026-04-30.sqlite.gz" in remaining  # April tail + recent
    # Earlier March/April files must be pruned.
    assert "finance-2026-03-01.sqlite.gz" not in remaining
    assert "finance-2026-04-01.sqlite.gz" not in remaining
