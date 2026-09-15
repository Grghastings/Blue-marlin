import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.update_data import (
    apply_grants_detail,
    apply_usaspending_award,
    grants_id_from_source,
    load_records,
    opportunity_status,
    positive_number,
    write_records,
)


class UpdateDataTests(unittest.TestCase):
    def test_grants_id_from_source(self):
        self.assertEqual(
            grants_id_from_source("https://www.grants.gov/search-results-detail/362963"),
            362963,
        )
        self.assertIsNone(grants_id_from_source("https://example.com/no-id"))

    def test_opportunity_status(self):
        self.assertEqual(opportunity_status("posted", 1), "Open")
        self.assertEqual(opportunity_status("closed", 1), "Closed - pending award")
        self.assertEqual(opportunity_status("closed", 3), "Closed - pending awards")

    def test_zero_is_not_a_positive_number(self):
        self.assertIsNone(positive_number("0"))
        self.assertEqual(positive_number("1,250,000"), 1250000)

    def test_apply_grants_detail_preserves_curated_title(self):
        record = {
            "awardId": "Not captured",
            "title": "Curated title",
            "status": "Closed - pending award",
        }
        detail = {
            "opportunityNumber": "DFOP0019999",
            "opportunityTitle": "Official title",
            "ost": "POSTED",
            "synopsis": {
                "postingDateStr": "2026-09-01-00-00-00",
                "responseDateStr": "2026-10-01-00-00-00",
                "awardCeiling": "1,250,000",
                "estimatedFunding": "2,500,000",
                "numberOfAwards": "2",
                "fundingInstruments": [{"description": "Cooperative Agreement"}],
                "lastUpdatedDate": "Sep 02, 2026 01:00:00 PM EDT",
            },
        }
        self.assertTrue(apply_grants_detail(record, 123456, detail))
        self.assertEqual(record["title"], "Curated title")
        self.assertEqual(record["awardId"], "DFOP0019999")
        self.assertEqual(record["status"], "Open")
        self.assertEqual(record["ceiling"], 2500000)
        self.assertEqual(record["expectedAwards"], 2)

    def test_zero_award_count_does_not_replace_curated_value(self):
        record = {
            "awardId": "DFOP0019999",
            "title": "Test",
            "status": "Closed - pending award",
            "expectedAwards": "1+",
        }
        detail = {
            "opportunityNumber": "DFOP0019999",
            "ost": "CLOSED",
            "synopsis": {"numberOfAwards": "0"},
        }
        apply_grants_detail(record, 123456, detail)
        self.assertEqual(record["expectedAwards"], "1+")

    def test_apply_usaspending_award_updates_amount(self):
        record = {"awardId": "ABC", "winner": "Friendly Name", "awardAmount": 1}
        award = {
            "Award Amount": 25.5,
            "Recipient Name": "OFFICIAL NAME INC.",
            "Start Date": "2026-01-02",
            "End Date": "2027-01-01",
            "Last Modified Date": "2026-09-10 12:00:00",
            "generated_internal_id": "ASST_NON_ABC_019",
        }
        self.assertTrue(apply_usaspending_award(record, award))
        self.assertEqual(record["awardAmount"], 25.5)
        self.assertEqual(record["winner"], "Friendly Name")
        self.assertEqual(record["officialRecipient"], "OFFICIAL NAME INC.")

    def test_verified_pending_record_becomes_awarded(self):
        record = {
            "awardId": "DFOP0019999",
            "usaSpendingAwardId": "SAQMMA26CA9999",
            "status": "Closed - pending award",
            "winner": "TBD",
        }
        award = {
            "Award ID": "SAQMMA26CA9999",
            "Award Amount": 1000000,
            "Recipient Name": "EXAMPLE RECIPIENT",
        }
        apply_usaspending_award(record, award)
        self.assertEqual(record["status"], "AWARDED")
        self.assertEqual(record["opportunityNumber"], "DFOP0019999")
        self.assertEqual(record["awardId"], "SAQMMA26CA9999")
        self.assertEqual(record["winner"], "EXAMPLE RECIPIENT")

    def test_data_file_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.js"
            records = [{"id": 1, "title": "Test"}]
            write_records(records, date(2026, 9, 15), path)
            self.assertEqual(load_records(path), records)
            self.assertIn('"lastChecked": "2026-09-15"', path.read_text())


if __name__ == "__main__":
    unittest.main()
