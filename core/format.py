"""CHIZ Booth — price/time formatting helpers (Toman, digits, Jalali date)."""
from __future__ import annotations


def format_toman(amount: int, currency: str = "تومان") -> str:
    """1234567 -> '1,234,567 تومان' (Latin digits, RTL-safe grouping)."""
    return f"{int(amount):,} {currency}".strip()


def group_digits(n: int) -> str:
    return f"{int(n):,}"


# --- Jalali (Persian) date conversion: standard civil algorithm ---

def to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    g_day_no += g_d_m[gm2] + gd2
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + (j_day_no % 31)
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + ((j_day_no - 186) % 30)
    return jy, jm, jd


def jalali_date(date_str: str) -> str:
    """'2026-09-30 14:03:00' (or date only) -> '1405/07/08'."""
    try:
        d = date_str.split(" ")[0]
        y, m, day = (int(x) for x in d.split("-"))
        jy, jm, jd = to_jalali(y, m, day)
        return f"{jy}/{jm:02d}/{jd:02d}"
    except (ValueError, AttributeError, IndexError):
        return date_str or ""


def jalali_date_time(date_str: str) -> str:
    """'2026-09-30 14:03:00' -> '1405/07/08 14:03'."""
    try:
        date_part, time_part = date_str.split(" ")
        return f"{jalali_date(date_part)} {time_part[:5]}"
    except (ValueError, AttributeError):
        return date_str or ""
