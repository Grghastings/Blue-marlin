#!/usr/bin/env python3
"""Refresh open procurement opportunities from SAM.gov and the World Bank."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "procurement.js"
SAM_URL = "https://api.sam.gov/opportunities/v2/search"
WORLD_BANK_URL = "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice"
WORLD_BANK_DATASET = "DS00979"
WORLD_BANK_RESOURCE = "RS00909"
USER_AGENT = "Blue-marlin-procurement-dashboard/1.0"
WORLD_BANK_SCAN_ROWS = 4000
MAX_RECORDS_PER_SOURCE = 400


def request_json(url: str, params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}", headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("API request failed")


def iso_date(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    for pattern in ("%d-%b-%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:11], pattern).date().isoformat()
        except ValueError:
            pass
    return ""


def normalize_sam(item: dict[str, Any], checked_on: date) -> dict[str, Any] | None:
    notice_id = str(item.get("noticeId") or "").strip()
    title = str(item.get("title") or "").strip()
    deadline = iso_date(item.get("responseDeadLine") or item.get("reponseDeadLine"))
    active = str(item.get("active") or item.get("status") or "").casefold()
    notice_type = str(item.get("type") or item.get("baseType") or "Procurement notice")
    excluded = {"award notice", "justification", "sale of surplus property"}
    if not notice_id or not title:
        return None
    if notice_type.casefold() in excluded:
        return None
    if deadline and deadline < checked_on.isoformat():
        return None
    if active in {"no", "false", "inactive", "archived"}:
        return None

    office = (
        item.get("fullParentPathName")
        or item.get("organizationName")
        or item.get("department")
        or "U.S. government"
    )
    solicitation = str(item.get("solicitationNumber") or notice_id)
    set_aside = item.get("typeOfSetAsideDescription") or item.get("typeOfSetAside") or ""
    source = item.get("uiLink") or f"https://sam.gov/opp/{notice_id}/view"
    return {
        "sourceSystem": "SAM.gov",
        "bureau": str(office),
        "status": "Open" if deadline else "Active - verify deadline",
        "title": title,
        "awardId": solicitation,
        "postedDate": iso_date(item.get("postedDate")),
        "closeDate": deadline,
        "ceiling": None,
        "winner": str(set_aside),
        "relevance": "UNRATED",
        "why": f"{notice_type}" + (f" • NAICS {item.get('naicsCode')}" if item.get("naicsCode") else ""),
        "instrument": str(notice_type),
        "source": str(source),
    }


def normalize_world_bank(item: dict[str, Any], checked_on: date) -> dict[str, Any] | None:
    title = str(item.get("bid_description") or "").strip()
    record_id = item.get("id")
    notice_type = str(item.get("notice_type") or "Procurement notice").strip()
    deadline = iso_date(item.get("deadline_date"))
    published = iso_date(item.get("publication_date"))
    excluded = {"contract award", "general procurement notice", "procurement plan"}
    if not title or record_id in (None, "") or notice_type.casefold() in excluded:
        return None
    if deadline and deadline < checked_on.isoformat():
        return None
    if not deadline and published and published < (checked_on - timedelta(days=45)).isoformat():
        return None

    country = item.get("country_name") or item.get("region") or "World Bank"
    method = str(item.get("procurement_method") or "").strip()
    category = str(item.get("procurement_category") or "").strip()
    details = " • ".join(part for part in (notice_type, method, category) if part)
    return {
        "sourceSystem": "World Bank",
        "bureau": str(country),
        "status": "Open" if deadline else "Active - verify deadline",
        "title": title,
        "awardId": str(item.get("project_id") or f"WB-{record_id}"),
        "postedDate": published,
        "closeDate": deadline,
        "ceiling": None,
        "winner": "",
        "relevance": "UNRATED",
        "why": details,
        "instrument": notice_type,
        "source": str(item.get("url") or "https://projects.worldbank.org/en/projects-operations/procurement"),
    }


def fetch_sam(checked_on: date, api_key: str) -> list[dict[str, Any]]:
    params = {
        "api_key": api_key,
        "postedFrom": (checked_on - timedelta(days=90)).strftime("%m/%d/%Y"),
        "postedTo": checked_on.strftime("%m/%d/%Y"),
        "rdlfrom": checked_on.strftime("%m/%d/%Y"),
        "rdlto": (checked_on + timedelta(days=365)).strftime("%m/%d/%Y"),
        "limit": 1000,
    }
    raw: list[dict[str, Any]] = []
    offset = 0
    while offset < 25000:
        response = request_json(SAM_URL, {**params, "offset": offset})
        page = response.get("opportunitiesData", [])
        raw.extend(page)
        total = int(response.get("totalRecords") or len(raw))
        if not page or len(raw) >= total or len(page) < params["limit"]:
            break
        offset += params["limit"]
    records = [normalize_sam(item, checked_on) for item in raw]
    return newest_unique([record for record in records if record], MAX_RECORDS_PER_SOURCE)


def fetch_world_bank(checked_on: date) -> list[dict[str, Any]]:
    base = {
        "datasetId": WORLD_BANK_DATASET,
        "resourceId": WORLD_BANK_RESOURCE,
        "type": "json",
    }
    count = int(request_json(WORLD_BANK_URL, {**base, "skip": 0, "top": 1})["count"])
    start = max(0, count - WORLD_BANK_SCAN_ROWS)
    raw: list[dict[str, Any]] = []
    for skip in range(start, count, 1000):
        response = request_json(
            WORLD_BANK_URL, {**base, "skip": skip, "top": min(1000, count - skip)}
        )
        raw.extend(response.get("data", []))
    records = [normalize_world_bank(item, checked_on) for item in raw]
    return newest_unique([record for record in records if record], MAX_RECORDS_PER_SOURCE)


def newest_unique(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    records.sort(key=lambda record: (record.get("postedDate", ""), record.get("closeDate", "")), reverse=True)
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        key = (record["sourceSystem"], record["awardId"], record["title"].casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
        if len(unique) >= limit:
            break
    return unique


def write_records(
    records: list[dict[str, Any]], checked_on: date, warnings: list[str], path: Path = DATA_FILE
) -> None:
    sources = sorted({record["sourceSystem"] for record in records})
    metadata = {
        "asOf": checked_on.strftime("%B %-d, %Y"),
        "lastChecked": checked_on.isoformat(),
        "sources": sources,
        "warnings": warnings,
    }
    contents = (
        "window.PROCUREMENT_DATA = "
        + json.dumps(records, indent=2, ensure_ascii=False)
        + ";\n\nwindow.PROCUREMENT_META = "
        + json.dumps(metadata, indent=2, ensure_ascii=False)
        + ";\n"
    )
    path.write_text(contents, encoding="utf-8")


def main() -> int:
    checked_on = datetime.now(timezone.utc).date()
    warnings: list[str] = []
    records = fetch_world_bank(checked_on)
    print(f"World Bank: retained {len(records)} open opportunities.")

    sam_key = os.environ.get("SAM_API_KEY", "").strip()
    if sam_key:
        sam_records = fetch_sam(checked_on, sam_key)
        records.extend(sam_records)
        print(f"SAM.gov: retained {len(sam_records)} open opportunities.")
    else:
        warning = "SAM.gov is waiting for the SAM_API_KEY repository secret."
        warnings.append(warning)
        print(f"warning: {warning}", file=sys.stderr)

    records.sort(key=lambda record: record.get("postedDate", ""), reverse=True)
    write_records(records, checked_on, warnings)
    print(f"Wrote {len(records)} procurement opportunities to {DATA_FILE.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
