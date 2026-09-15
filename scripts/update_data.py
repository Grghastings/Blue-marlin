#!/usr/bin/env python3
"""Refresh the dashboard's tracked records from official public APIs."""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data.js"
GRANTS_SEARCH_URL = "https://api.grants.gov/v1/api/search2"
GRANTS_DETAIL_URL = "https://api.grants.gov/v1/api/fetchOpportunity"
USASPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
USER_AGENT = "Blue-marlin-State-assistance-dashboard/1.0"
AWARD_TYPE_CODES = ["02", "03", "04", "05"]
OPPORTUNITY_NUMBER = re.compile(r"^(?:DFOP|OFOP)[A-Z0-9-]+$", re.IGNORECASE)
GRANTS_SOURCE_ID = re.compile(r"grants\.gov/search-results-detail/(\d+)")


def request_json(url: str, payload: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("API request failed")


def load_records(path: Path = DATA_FILE) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    prefix = "window.STATE_ASSISTANCE_DATA = "
    try:
        start = text.index(prefix) + len(prefix)
    except ValueError as error:
        raise ValueError(f"{path} does not contain {prefix!r}") from error
    records, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(records, list):
        raise ValueError("STATE_ASSISTANCE_DATA must be a JSON array")
    return records


def write_records(records: list[dict[str, Any]], checked_on: date, path: Path = DATA_FILE) -> None:
    metadata = {
        "asOf": checked_on.strftime("%B %-d, %Y"),
        "lastChecked": checked_on.isoformat(),
        "sources": ["Grants.gov", "USAspending.gov"],
    }
    contents = (
        "window.STATE_ASSISTANCE_DATA = "
        + json.dumps(records, indent=2, ensure_ascii=False)
        + ";\n\nwindow.STATE_ASSISTANCE_META = "
        + json.dumps(metadata, indent=2, ensure_ascii=False)
        + ";\n"
    )
    path.write_text(contents, encoding="utf-8")


def iso_date(value: Any) -> str:
    if not value:
        return ""
    value = str(value)
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match:
        return match.group(0)
    for pattern in ("%m/%d/%Y", "%b %d, %Y %I:%M:%S %p %Z"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    return ""


def positive_number(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", ""))
    except ValueError:
        return None
    if number <= 0:
        return None
    return int(number) if number.is_integer() else number


def grants_id_from_source(source: str) -> int | None:
    match = GRANTS_SOURCE_ID.search(source or "")
    return int(match.group(1)) if match else None


def find_grants_id(opportunity_number: str) -> int | None:
    response = request_json(
        GRANTS_SEARCH_URL,
        {
            "rows": 25,
            "oppNum": opportunity_number,
            "oppStatuses": "forecasted|posted|closed|archived",
        },
    )
    hits = response.get("data", {}).get("oppHits", [])
    exact = [
        hit
        for hit in hits
        if str(hit.get("number", "")).casefold() == opportunity_number.casefold()
    ]
    return int(exact[0]["id"]) if len(exact) == 1 else None


def fetch_grants_detail(record: dict[str, Any]) -> tuple[int, dict[str, Any]] | None:
    grants_id = record.get("grantsGovId") or grants_id_from_source(record.get("source", ""))
    award_id = str(record.get("awardId", ""))
    if not grants_id and OPPORTUNITY_NUMBER.fullmatch(award_id):
        grants_id = find_grants_id(award_id)
    if not grants_id:
        return None
    response = request_json(GRANTS_DETAIL_URL, {"opportunityId": int(grants_id)})
    if response.get("errorcode") != 0 or not response.get("data"):
        raise RuntimeError(f"Grants.gov did not return opportunity {grants_id}")
    return int(grants_id), response["data"]


def opportunity_status(api_status: str, expected_awards: Any) -> str:
    status = (api_status or "").casefold()
    if status == "posted":
        return "Open"
    if status == "forecasted":
        return "Forecasted"
    if status == "archived":
        return "Archived - award not verified"
    if status == "closed":
        plural = False
        try:
            plural = float(expected_awards) > 1
        except (TypeError, ValueError):
            plural = False
        return "Closed - pending awards" if plural else "Closed - pending award"
    return api_status.title() if api_status else "Status unavailable"


def apply_grants_detail(record: dict[str, Any], grants_id: int, detail: dict[str, Any]) -> bool:
    before = json.dumps(record, sort_keys=True)
    synopsis = detail.get("synopsis") or {}
    record["grantsGovId"] = grants_id
    opportunity_number = detail.get("opportunityNumber")
    if opportunity_number and record.get("awardId") == "Not captured":
        record["awardId"] = opportunity_number
    posted = iso_date(synopsis.get("postingDateStr") or synopsis.get("postingDate"))
    closed = iso_date(synopsis.get("responseDateStr") or synopsis.get("responseDate"))
    if posted:
        record["postedDate"] = posted
    if closed:
        record["closeDate"] = closed
    program_funding = positive_number(synopsis.get("estimatedFunding"))
    award_ceiling = positive_number(synopsis.get("awardCeiling"))
    funding_value = program_funding if program_funding is not None else award_ceiling
    if funding_value is not None:
        record["ceiling"] = funding_value
    expected = synopsis.get("numberOfAwards")
    if expected not in (None, ""):
        parsed = positive_number(expected)
        if parsed is not None and parsed > 0:
            record["expectedAwards"] = parsed
    instruments = synopsis.get("fundingInstruments") or []
    descriptions = [
        item.get("description")
        for item in instruments
        if item.get("description") and item.get("description") != "Other"
    ]
    if descriptions:
        record["instrument"] = " / ".join(descriptions)
    if not str(record.get("status", "")).casefold().startswith("awarded"):
        record["status"] = opportunity_status(detail.get("ost", ""), record.get("expectedAwards"))
    record["opportunityUpdated"] = synopsis.get("lastUpdatedDate") or ""
    record["source"] = f"https://www.grants.gov/search-results-detail/{grants_id}"
    if not record.get("title") and detail.get("opportunityTitle"):
        record["title"] = html.unescape(detail["opportunityTitle"])
    return before != json.dumps(record, sort_keys=True)


def fetch_usaspending_awards(records: list[dict[str, Any]], checked_on: date) -> dict[str, dict[str, Any]]:
    verifiable = [
        record
        for record in records
        if record.get("usaSpendingAwardId")
        or str(record.get("status", "")).casefold().startswith("awarded")
    ]
    award_ids = sorted(
        {
            str(record.get("usaSpendingAwardId") or record.get("awardId"))
            for record in verifiable
        }
    )
    if not award_ids:
        return {}
    start_year = min(
        int(str(record.get("postedDate", checked_on.isoformat()))[:4])
        for record in verifiable
    )
    response = request_json(
        USASPENDING_URL,
        {
            "subawards": False,
            "limit": 100,
            "page": 1,
            "filters": {
                "award_type_codes": AWARD_TYPE_CODES,
                "time_period": [
                    {"start_date": f"{start_year}-01-01", "end_date": checked_on.isoformat()}
                ],
                "award_ids": award_ids,
                "agencies": [
                    {"type": "awarding", "tier": "toptier", "name": "Department of State"}
                ],
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Start Date",
                "End Date",
                "Award Amount",
                "Description",
                "Base Obligation Date",
                "Last Modified Date",
                "generated_internal_id",
            ],
        },
    )
    return {str(item["Award ID"]).casefold(): item for item in response.get("results", [])}


def apply_usaspending_award(record: dict[str, Any], award: dict[str, Any]) -> bool:
    before = json.dumps(record, sort_keys=True)
    official_award_id = str(award.get("Award ID") or "")
    if official_award_id and not str(record.get("status", "")).casefold().startswith("awarded"):
        record["opportunityNumber"] = record.get("awardId", "")
        record["awardId"] = official_award_id
    record["status"] = "AWARDED"
    amount = positive_number(award.get("Award Amount"))
    if amount is not None:
        record["awardAmount"] = amount
    if not record.get("winner") or record.get("winner") == "TBD":
        record["winner"] = award.get("Recipient Name") or "TBD"
    record["officialRecipient"] = award.get("Recipient Name") or record.get("winner", "")
    start = iso_date(award.get("Start Date"))
    end = iso_date(award.get("End Date"))
    if start:
        record["expectedStart"] = start
    if end:
        record["awardEnd"] = end
    record["usaSpendingLastModified"] = award.get("Last Modified Date") or ""
    generated_id = award.get("generated_internal_id")
    if generated_id:
        record["source"] = f"https://www.usaspending.gov/award/{generated_id}/"
    return before != json.dumps(record, sort_keys=True)


def refresh(records: list[dict[str, Any]], checked_on: date) -> tuple[int, list[str]]:
    changed = 0
    warnings: list[str] = []
    candidates = [
        record
        for record in records
        if record.get("grantsGovId")
        or grants_id_from_source(record.get("source", ""))
        or OPPORTUNITY_NUMBER.fullmatch(str(record.get("awardId", "")))
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_grants_detail, record): record for record in candidates}
        for future in as_completed(futures):
            record = futures[future]
            result = future.result()
            if result is None:
                warnings.append(f"No exact Grants.gov match for {record.get('awardId')}")
                continue
            if apply_grants_detail(record, *result):
                changed += 1

    official_awards = fetch_usaspending_awards(records, checked_on)
    for record in records:
        if not record.get("usaSpendingAwardId") and not str(
            record.get("status", "")
        ).casefold().startswith("awarded"):
            continue
        award_id = str(record.get("usaSpendingAwardId") or record.get("awardId", ""))
        award = official_awards.get(award_id.casefold())
        if award is None:
            warnings.append(f"No exact USAspending match for {award_id}")
            continue
        if apply_usaspending_award(record, award):
            changed += 1
    return changed, warnings


def main() -> int:
    checked_on = datetime.now(timezone.utc).date()
    records = load_records()
    changed, warnings = refresh(records, checked_on)
    write_records(records, checked_on)
    print(f"Checked {len(records)} records; {changed} records changed.")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
