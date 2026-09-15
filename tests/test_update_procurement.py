import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.update_procurement import (
    iso_date,
    newest_unique,
    normalize_sam,
    normalize_world_bank,
    write_records,
)


class UpdateProcurementTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 9, 15)

    def test_iso_date_supports_both_sources(self):
        self.assertEqual(iso_date("16-Sep-2026"), "2026-09-16")
        self.assertEqual(iso_date("2026-09-20T17:00:00-04:00"), "2026-09-20")

    def test_normalize_sam_open_notice(self):
        record = normalize_sam(
            {
                "noticeId": "abc123",
                "title": "Legal advisory services",
                "solicitationNumber": "SOL-1",
                "postedDate": "2026-09-10",
                "responseDeadLine": "2026-10-01T17:00:00-04:00",
                "organizationName": "Department of State",
                "type": "Solicitation",
                "naicsCode": "541110",
                "active": "Yes",
            },
            self.today,
        )
        self.assertEqual(record["sourceSystem"], "SAM.gov")
        self.assertEqual(record["closeDate"], "2026-10-01")
        self.assertIn("541110", record["why"])

    def test_normalize_sam_rejects_expired_notice(self):
        self.assertIsNone(
            normalize_sam(
                {
                    "noticeId": "old",
                    "title": "Old notice",
                    "responseDeadLine": "2026-09-01T17:00:00-04:00",
                },
                self.today,
            )
        )

    def test_normalize_sam_rejects_award_notice(self):
        self.assertIsNone(
            normalize_sam(
                {
                    "noticeId": "award",
                    "title": "Awarded contract",
                    "type": "Award Notice",
                    "active": "Yes",
                },
                self.today,
            )
        )

    def test_normalize_world_bank_open_notice(self):
        record = normalize_world_bank(
            {
                "id": 468999,
                "bid_description": "Consulting services",
                "country_name": "Kenya",
                "deadline_date": "30-Sep-2026",
                "publication_date": "10-Sep-2026",
                "notice_type": "Request for Expression of Interest",
                "procurement_method": "Quality Based Selection",
                "project_id": "P123456",
                "url": "https://example.test/notice",
            },
            self.today,
        )
        self.assertEqual(record["sourceSystem"], "World Bank")
        self.assertEqual(record["bureau"], "Kenya")
        self.assertEqual(record["status"], "Open")

    def test_world_bank_contract_award_is_not_an_opportunity(self):
        self.assertIsNone(
            normalize_world_bank(
                {"id": 1, "bid_description": "Award", "notice_type": "Contract Award"},
                self.today,
            )
        )

    def test_newest_unique_removes_duplicates(self):
        row = {"sourceSystem": "World Bank", "awardId": "P1", "title": "Same", "postedDate": "2026-09-10"}
        self.assertEqual(len(newest_unique([row.copy(), row.copy()], 10)), 1)

    def test_write_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "procurement.js"
            write_records([], self.today, ["SAM key missing"], path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("window.PROCUREMENT_DATA", text)
            self.assertIn("SAM key missing", text)


if __name__ == "__main__":
    unittest.main()
