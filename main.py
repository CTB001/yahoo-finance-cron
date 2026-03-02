"""
Metal/Commodity Delayed Price Fetcher
======================================
Fetches 10-minute interval prices for:
  XAUUSD, XAGUSD, XCUUSD, XPTUSD, XPLUSD, XAUTRY

Two time windows per run:
  1) Yesterday 18:10 (if Monday → Friday 18:10) — single snapshot
  2) Today 08:00 → current time, every 10 minutes

Output:
  - prices.txt  : appended each run
  - prices.xlsx : overwritten each run
  - Mail sent with XLSX attachment
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
import os
import smtplib
from email.message import EmailMessage

# ── Configuration ────────────────────────────────────────────────────────────

# Local timezone (Turkey)
LOCAL_TZ = pytz.timezone("Europe/Istanbul")

# Mail settings (GitHub Secrets'tan gelecek)
MAIL_FROM = os.environ["MAIL_FROM"]
MAIL_TO   = os.environ["MAIL_TO"]
MAIL_PASS = os.environ["MAIL_PASS"]

# yfinance tickers mapped to our product names
TICKER_MAP = {
    "XAUUSD": "GC=F",   # Gold futures (USD)
    "XAGUSD": "SI=F",   # Silver futures (USD)
    "XCUUSD": "HG=F",   # Copper futures (USD)
    "XPTUSD": "PL=F",   # Platinum futures (USD)
    "XPLUSD": "PA=F",   # Palladium futures (USD)
    "USDTRY": "TRY=X",  # USD/TRY (used to compute XAUTRY)
}

PRODUCTS = ["XAUUSD", "XAGUSD", "XCUUSD", "XPTUSD", "XPLUSD", "XAUTRY"]

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TXT_FILE   = os.path.join(OUTPUT_DIR, "prices.txt")
XLSX_FILE  = os.path.join(OUTPUT_DIR, "prices.xlsx")

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_previous_business_day(dt: datetime) -> datetime:
    prev = dt - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev


def build_time_slots(now_local: datetime):
    slots = []

    prev_day = get_previous_business_day(now_local)
    prev_snap = prev_day.replace(hour=18, minute=10, second=0, microsecond=0)
    slots.append(prev_snap)

    today_start = now_local.replace(hour=8, minute=0, second=0, microsecond=0)
    completed_minutes = (now_local.minute // 10) * 10
    today_end = now_local.replace(minute=completed_minutes, second=0, microsecond=0)

    t = today_start
    while t <= today_end:
        if t not in slots:
            slots.append(t)
        t += timedelta(minutes=10)

    slots.sort()
    return slots


def fetch_ohlc(ticker: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    try:
        df = yf.download(
            ticker,
            start=start_utc,
            end=end_utc,
            interval="1m",
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df = df[["Close"]].rename(columns={"Close": "close"})
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.resample("10min").last().dropna()
        return df
    except Exception as e:
        print(f"[WARN] {ticker} fetch failed: {e}")
        return pd.DataFrame()


def get_price_at(df: pd.DataFrame, target_utc: datetime):
    if df.empty:
        return None
    diffs = abs(df.index - target_utc)
    min_idx = diffs.argmin()
    if diffs[min_idx] <= pd.Timedelta(minutes=10):
        return round(float(df["close"].iloc[min_idx]), 6)
    return None

# ── Main ─────────────────────────────────────────────────────────────────────

def main():

    if not slots:
      print("No time slots generated")
      return
    now_local = datetime.now(LOCAL_TZ)

    slots = build_time_slots(now_local)
    start_utc = slots[0].astimezone(pytz.utc) - timedelta(minutes=15)
    end_utc   = now_local.astimezone(pytz.utc) + timedelta(minutes=15)

    raw = {}
    for product, ticker in TICKER_MAP.items():
        raw[product] = fetch_ohlc(ticker, start_utc, end_utc)

    rows = []
    for slot in slots:
        slot_utc = slot.astimezone(pytz.utc)
        row = {"time": slot.strftime("%Y-%m-%d %H:%M")}

        xauusd_price = get_price_at(raw["XAUUSD"], slot_utc)
        usdtry_price = get_price_at(raw["USDTRY"], slot_utc)

        for product in PRODUCTS:
            if product == "XAUTRY":
                row["XAUTRY"] = (
                    round(xauusd_price * usdtry_price, 4)
                    if xauusd_price and usdtry_price else None
                )
            else:
                row[product] = get_price_at(raw[product], slot_utc)

        rows.append(row)

    df = pd.DataFrame(rows, columns=["time"] + PRODUCTS)

    # Write TXT
    with open(TXT_FILE, "a", encoding="utf-8") as f:
        f.write(f"\nRun: {now_local}\n")
        f.write(df.to_string(index=False))
        f.write("\n")

    # Write XLSX
    with pd.ExcelWriter(XLSX_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Prices")

    # Send Mail
    msg = EmailMessage()
    msg["Subject"] = f"Metal Prices {now_local.strftime('%Y-%m-%d %H:%M')} (TR)"
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    msg.set_content("Güncel metal/emtia fiyatları ekteki Excel dosyasındadır.")

    with open(XLSX_FILE, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="prices.xlsx",
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(MAIL_FROM, MAIL_PASS)
        server.send_message(msg)

    print("OK - Mail sent")


if __name__ == "__main__":
    main()
