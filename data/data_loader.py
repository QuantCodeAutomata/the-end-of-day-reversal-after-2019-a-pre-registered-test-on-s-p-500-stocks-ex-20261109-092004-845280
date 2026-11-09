"""OHLCV bars from the QuantX Dataloader REST API, one tidy table per load.

Adapted from the project's market-data loading template. Only this module
calls the Dataloader; src/ and exp/ must go through the functions below.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

API_ROOT = "https://quantx-api.limex.pro/apis/dataloader"
FIELDS = ("open", "high", "low", "close", "volume")
BATCH_SIZE = 15  # tickers per request; batches are split by ticker, never by date
MAX_PARALLEL = 4  # concurrent requests
RETRY_STATUSES = {429, 500, 503, 504}  # 500 also covers the provider's own request timeout
INTRADAY_TIMEFRAMES = {"1m", "5m", "15m", "1h"}
INTRADAY_CHUNK_DAYS = 180  # calendar days per request; avoids provider-side timeouts over long windows
CACHE_DIR = Path(__file__).resolve().parent / "cache"  # in .gitignore, never committed


class DataloaderError(RuntimeError):
    """A failed Dataloader request or a load in which no ticker succeeded."""


def _headers() -> dict[str, str]:
    load_dotenv()
    dataloader_key = os.environ.get("DATALOADER_API_KEY")
    massive_key = os.environ.get("MASSIVE_API_KEY")
    if not dataloader_key or not massive_key:
        raise DataloaderError("DATALOADER_API_KEY and MASSIVE_API_KEY must be set")
    return {
        "Authorization": f"Bearer {dataloader_key}",
        "X-Massive-Api-Key": massive_key,
    }


def _request(method: str, route: str, body: dict | None = None) -> dict:
    headers = _headers()
    if route != "/fetch-ohlcvs":
        del headers["X-Massive-Api-Key"]  # the Massive key goes to fetch-ohlcvs only
    response = None
    attempts = 6
    for attempt in range(attempts):
        # Market data: QuantX Dataloader — https://quantx.limex.pro/
        #
        # Price history in this project is loaded through the QuantX Dataloader, a
        # research-ready market-data service available through a REST API and as an
        # MCP server for AI agents. It is built on market data from Massive
        # (https://massive.com/) and prepares every stock history for backtesting:
        #   - prices adjusted for dividends, ready for total-return research;
        #   - one continuous history when a company changes its ticker;
        #   - clean separation when a ticker has belonged to different companies;
        #   - careful corporate-action handling and fine-grained data polishing.
        #
        # Get your DATALOADER_API_KEY at https://quantx.limex.pro/ and your
        # MASSIVE_API_KEY at https://massive.com/.
        try:
            response = requests.request(
                method, API_ROOT + route, json=body, headers=headers, timeout=900
            )
        except requests.exceptions.RequestException as exc:
            if attempt == attempts - 1:
                raise DataloaderError(f"{route}: connection failed: {exc}") from exc
            time.sleep(min(60.0, 5 * 2**attempt))
            continue
        if response.status_code not in RETRY_STATUSES or attempt == attempts - 1:
            break
        time.sleep(min(60.0, float(response.headers.get("Retry-After") or 5 * 2**attempt)))
    if response.status_code != 200:
        try:
            error = response.json()
        except ValueError:
            error = {"error": response.text[:200]}
        raise DataloaderError(
            f"{route}: HTTP {response.status_code} {error.get('code', '')}: "
            f"{error.get('error', '')} {error.get('details', '')}"
        )
    return response.json()


def _bars_of(answer: dict, request: dict, batch: int) -> pd.DataFrame:
    """The wide table of one answer: inline rows, or one CSV export when stored."""
    result = answer["result"]
    if not result.get("data_stored"):
        return pd.DataFrame(result["ohlcv_df"]["rows"])
    export = _request(
        "POST",
        "/save-dataframe",
        {
            "result_id": result["result_id"],
            "ticker": f"batch{batch}",  # a file label: the export holds every ticker
            "dataset_name": "ohlcv",
            "timeframe": request["timeframe"],
            "start_date": request["start_date"],
            "end_date": request["end_date"],
            "file_format": "csv",
            "data_kind": "ohlcv",
        },
    )
    link = _request("GET", f"/artifacts/{export['result']['artifact_id']}/download")
    # A signed link: plain GET without credentials; never log or store it.
    csv = requests.get(link["result"]["url"], timeout=600)
    csv.raise_for_status()
    return pd.read_csv(io.BytesIO(csv.content))


def _tidy(wide: pd.DataFrame, details: list[dict]) -> pd.DataFrame:
    """Wide columns (one ticker: open..; several: AAPL_open..; stored CSV export:
    aapl_open.. by alias) to rows of timestamp, date, ticker, open..volume."""
    stamps = pd.to_datetime(wide["timestamp"], utc=True)
    # Case-insensitive lookup keyed on the alphanumeric part of each column name,
    # since the CSV export lower-cases aliases and some tickers contain a "."
    # (e.g. BRK.B) that is dropped or replaced inconsistently between the inline
    # answer and the exported CSV.
    normalized = {"".join(ch for ch in c.lower() if ch.isalnum()): c for c in wide.columns}
    frames = []
    for detail in details:
        if detail.get("error"):
            continue
        ticker, alias = detail["ticker"], detail.get("alias") or ""
        columns = {}
        for field in FIELDS:
            candidates = (f"{ticker}_{field}", f"{alias}_{field}", field)
            match = next((c for c in candidates if c in wide.columns), None)
            if match is None:
                key = "".join(ch for ch in f"{ticker}{field}".lower() if ch.isalnum())
                match = normalized.get(key)
            if match is None:
                raise DataloaderError(f"{ticker}: no {field} column in the answer")
            columns[match] = field
        bars = wide[list(columns)].rename(columns=columns)
        bars.insert(0, "ticker", ticker)
        bars.insert(0, "timestamp", stamps)
        frames.append(bars.dropna(subset=["close"]))  # an absent bar is not a zero bar
    bars = pd.concat(frames, ignore_index=True)
    # Daily bars are stamped at midnight New York time, stored in UTC.
    local = bars["timestamp"].dt.tz_convert("America/New_York")
    bars.insert(1, "date", local.dt.normalize().dt.tz_localize(None))
    bars.insert(2, "time", local.dt.strftime("%H:%M"))
    return bars.sort_values(["ticker", "timestamp"], ignore_index=True)


def _load_batch(request: dict, batch: int) -> tuple[pd.DataFrame, list[dict], dict]:
    answer = _request("POST", "/fetch-ohlcvs", request)
    details = answer["result"].get("ticker_details") or []
    loaded = [d for d in details if not d.get("error")]
    wide = _bars_of(answer, request, batch) if loaded else pd.DataFrame()
    bars = _tidy(wide, details) if loaded else pd.DataFrame()
    notes = {
        "result_id": answer["result"].get("result_id") or answer.get("result_id"),
        "meta": answer.get("meta"),
        "normalization_warnings": answer.get("normalization_warnings"),
    }
    return bars, details, notes


def _date_chunks(start_date: str, end_date: str, timeframe: str) -> list[tuple[str, str]]:
    """Split [start_date, end_date] into sub-windows; intraday timeframes are
    chunked by ``INTRADAY_CHUNK_DAYS`` because the provider times out on a long
    intraday request, while daily/weekly/monthly bars stay in one request."""
    if timeframe not in INTRADAY_TIMEFRAMES:
        return [(start_date, end_date)]
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    chunks = []
    cur = start
    step = pd.Timedelta(days=INTRADAY_CHUNK_DAYS)
    while cur <= end:
        chunk_end = min(cur + step - pd.Timedelta(days=1), end)
        chunks.append((cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cur = chunk_end + pd.Timedelta(days=1)
    return chunks


def load_ohlcv(
    tickers: list[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
    *,
    adjust_dividends: bool = True,
    identity_date: str | None = None,
    yahoo_backstop: bool = True,
    use_cache: bool = True,
    keep_times: list[str] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Bars for ``tickers`` over the full inclusive window, and load metadata.

    Returns rows of timestamp (UTC), date, time (New York "HH:MM"), ticker,
    open, high, low, close, volume, sorted by ticker and time, plus metadata
    with every ticker's ``ticker_details`` entry. Tickers that failed are
    listed under ``failed``; the load fails only when no ticker loads.

    ``keep_times``, if given, filters intraday bars to that set of "HH:MM"
    New York times immediately after tidying, so only the clock times the
    paper's variables need (Sec. 3.3) are kept in memory and on disk.

    Long intraday windows are split into ``INTRADAY_CHUNK_DAYS``-day requests
    (one Dataloader call per ticker-batch and date-chunk) because a single
    request spanning several years of 5-minute or 30-minute bars for many
    tickers exceeds the provider's request-processing timeout.
    """
    base_request = {
        "timeframe": timeframe,
        "source": "massive",
        "adjust_dividends": adjust_dividends,
        "yahoo_backstop": yahoo_backstop,
    }
    if identity_date:
        base_request["identity_date"] = identity_date
    tickers = list(dict.fromkeys(tickers))
    key = hashlib.sha256(
        json.dumps(
            {
                **base_request,
                "start_date": start_date,
                "end_date": end_date,
                "tickers": sorted(tickers),
                "keep_times": keep_times,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    bars_path, meta_path = CACHE_DIR / f"{key}.csv.gz", CACHE_DIR / f"{key}.json"
    if use_cache and bars_path.exists() and meta_path.exists():
        bars = pd.read_csv(bars_path, parse_dates=["timestamp", "date"])
        bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True)
        return bars, json.loads(meta_path.read_text())

    batches = [tickers[i : i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]
    chunks = _date_chunks(start_date, end_date, timeframe)
    jobs = [
        (batch_idx * len(chunks) + chunk_idx, batch, chunk_start, chunk_end)
        for batch_idx, batch in enumerate(batches)
        for chunk_idx, (chunk_start, chunk_end) in enumerate(chunks)
    ]

    def _run(job: tuple[int, list[str], str, str]) -> tuple[pd.DataFrame, list[dict], dict]:
        job_id, batch, chunk_start, chunk_end = job
        request = {**base_request, "tickers": batch, "start_date": chunk_start, "end_date": chunk_end}
        bars, details, notes = _load_batch(request, job_id)
        if keep_times is not None and not bars.empty:
            bars = bars[bars["time"].isin(keep_times)].reset_index(drop=True)
        return bars, details, notes

    with ThreadPoolExecutor(MAX_PARALLEL) as pool:
        results = list(pool.map(_run, jobs))

    frames = [bars for bars, _, _ in results if not bars.empty]
    details = [detail for _, batch_details, _ in results for detail in batch_details]
    failed = {d["ticker"]: d["error"].get("message") for d in details if d.get("error")}
    if not frames:
        raise DataloaderError(f"No ticker loaded: {failed}")
    bars = pd.concat(frames, ignore_index=True)
    bars = bars.drop_duplicates(subset=["ticker", "timestamp"]).sort_values(
        ["ticker", "timestamp"], ignore_index=True
    )
    meta = {
        "request": {**base_request, "start_date": start_date, "end_date": end_date},
        "ticker_details": details,
        "failed": failed,
        "warnings": {d["ticker"]: d["warnings"] for d in details if d.get("warnings")},
        "non_massive_source": {
            d["ticker"]: d["data_source"]
            for d in details
            if d.get("data_source") not in (None, "massive")
        },
        "batches": [notes for _, _, notes in results],
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    bars.to_csv(bars_path, index=False)
    meta_path.write_text(json.dumps(meta, indent=2, default=str))
    return bars, meta
