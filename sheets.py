import json
from typing import Dict, Any

import gspread
from google.oauth2.service_account import Credentials


class GoogleSheetsLogger:
    def __init__(self, spreadsheet_id: str, service_account_json: str) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.service_account_json = service_account_json
        self.sheet = self._connect()

    def _connect(self):
        info: Dict[str, Any] = json.loads(self.service_account_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(self.spreadsheet_id)
        return spreadsheet.sheet1

    def append_row(self, row: Dict[str, str]) -> None:
        headers = [
            "timestamp",
            "user_id",
            "input_type",
            "original_input",
            "source_link",
            "topic",
            "summary",
            "rewrite",
        ]
        self.sheet.append_row([row.get(h, "") for h in headers], value_input_option="RAW")
