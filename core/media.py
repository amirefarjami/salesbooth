"""CHIZ Booth — screensaver playlist (attract-mode slides).

The seller uploads pictures and videos from the panel; each item can be
limited to a time-of-day window («فقط عصرها») and a picture also carries
how many seconds it stays up. A video simply plays for its own length:
on upload it is decoded to a JPEG frame sequence (ffmpeg) at a fixed rate,
so the kiosk player needs no codec at all — it just blits frame N.

Rows live in the `media` table; files live under data/media/ (git-ignored).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MediaItem:
    id: int | None
    kind: str                     # 'image' | 'video'
    path: str                     # data/ relative image file
    poster: str | None = None     # data/ relative thumbnail (video: 1st frame)
    frames_dir: str | None = None  # data/ relative folder of 0001.jpg …
    fps: float = 12.0
    frame_count: int = 0
    duration_s: int = 8
    start_time: str | None = None
    end_time: str | None = None
    sort_order: int = 0
    active: bool = True
    created_at: str = ""

    @property
    def seconds(self) -> float:
        """How long the slide stays up. A video's frames decide it."""
        if self.kind == "video" and self.frame_count and self.fps > 0:
            return self.frame_count / self.fps
        return max(1, int(self.duration_s))

    @property
    def thumb(self) -> str | None:
        return self.poster or self.path

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "MediaItem":
        return cls(
            id=row["id"], kind=row["kind"], path=row["path"],
            poster=row["poster"], frames_dir=row["frames_dir"],
            fps=float(row["fps"] or 12), frame_count=int(row["frame_count"] or 0),
            duration_s=int(row["duration_s"] or 8),
            start_time=row["start_time"], end_time=row["end_time"],
            sort_order=int(row["sort_order"] or 0), active=bool(row["active"]),
            created_at=row["created_at"] or "",
        )


def parse_hhmm(value: str | None) -> int | None:
    """'21:30' → 1290 minutes; '' / None / junk → None (open end)."""
    if not value:
        return None
    try:
        hh, mm = str(value).strip().split(":")[:2]
        h, m = int(hh), int(mm)
    except (ValueError, TypeError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


def in_window(start: str | None, end: str | None, now: datetime | None = None) -> bool:
    """Is `now` inside the start–end window? Empty ends mean «always».

    A window whose end is before its start wraps past midnight
    (22:00–02:00 = night only)."""
    s, e = parse_hhmm(start), parse_hhmm(end)
    if s is None and e is None:
        return True
    now = now or datetime.now()
    cur = now.hour * 60 + now.minute
    if s is None:
        return cur <= e
    if e is None:
        return cur >= s
    if s <= e:
        return s <= cur <= e
    return cur >= s or cur <= e      # overnight window


class MediaRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list_all(self) -> list[MediaItem]:
        rows = self.conn.execute(
            "SELECT * FROM media ORDER BY sort_order, id").fetchall()
        return [MediaItem.from_row(r) for r in rows]

    def list_active(self, now: datetime | None = None) -> list[MediaItem]:
        return [m for m in self.list_all()
                if m.active and in_window(m.start_time, m.end_time, now)]

    def get(self, mid: int) -> MediaItem | None:
        row = self.conn.execute("SELECT * FROM media WHERE id=?", (mid,)).fetchone()
        return MediaItem.from_row(row) if row else None

    def create(self, item: MediaItem) -> int:
        cur = self.conn.execute(
            "INSERT INTO media(kind, path, poster, frames_dir, fps, frame_count,"
            " duration_s, start_time, end_time, sort_order, active)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (item.kind, item.path, item.poster, item.frames_dir, item.fps,
             item.frame_count, item.duration_s, item.start_time or None,
             item.end_time or None, item.sort_order, int(item.active)))
        self.conn.commit()
        return int(cur.lastrowid)

    def update(self, mid: int, **fields) -> None:
        allowed = {"duration_s", "start_time", "end_time", "sort_order", "active"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        cols = ", ".join(f"{k}=?" for k in sets)
        self.conn.execute(f"UPDATE media SET {cols} WHERE id=?",
                          (*sets.values(), mid))
        self.conn.commit()

    def delete(self, mid: int) -> MediaItem | None:
        item = self.get(mid)
        if item is None:
            return None
        self.conn.execute("DELETE FROM media WHERE id=?", (mid,))
        self.conn.commit()
        return item
