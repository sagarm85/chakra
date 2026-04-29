import logging
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
COLUMNS = ["Story ID", "Story Title", "Task", "Status", "Updated At"]
TASK_COLUMNS = ["Story ID", "Story Title", "Task #", "Task Name", "Description", "Status", "Updated At"]


class SheetsTool:
    def __init__(self, credentials_path: str, spreadsheet_id: str, sheet_name: str):
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        client = gspread.authorize(creds)
        self._spreadsheet = client.open_by_key(spreadsheet_id)
        self._sheet = self._get_or_create_sheet(sheet_name)

    def _get_or_create_sheet(self, name: str) -> gspread.Worksheet:
        try:
            ws = self._spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self._spreadsheet.add_worksheet(name, rows=1000, cols=len(COLUMNS))
            ws.append_row(COLUMNS)
            logger.info("Created new sheet: %s", name)
        return ws

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _find_row(self, story_id: str, task: str) -> int | None:
        records = self._sheet.get_all_records()
        for i, row in enumerate(records, start=2):
            if row.get("Story ID") == story_id and row.get("Task") == task:
                return i
        return None

    def upsert_row(self, story_id: str, story_title: str, task: str, status: str) -> None:
        row_num = self._find_row(story_id, task)
        now = self._now()
        if row_num:
            self._sheet.update(f"A{row_num}:E{row_num}", [[story_id, story_title, task, status, now]])
            logger.info("Sheets update: %s / %s → %s", story_id, task, status)
        else:
            self._sheet.append_row([story_id, story_title, task, status, now])
            logger.info("Sheets insert: %s / %s → %s", story_id, task, status)

    def update_status(self, story_id: str, task: str, status: str) -> None:
        row_num = self._find_row(story_id, task)
        if not row_num:
            logger.warning("Row not found for %s / %s", story_id, task)
            return
        now = self._now()
        self._sheet.update_cell(row_num, 4, status)
        self._sheet.update_cell(row_num, 5, now)
        logger.info("Sheets status: %s / %s → %s", story_id, task, status)

    def get_all_story_ids(self) -> list[str]:
        records = self._sheet.get_all_records()
        return [r["Story ID"] for r in records if r.get("Story ID")]

    @property
    def _tasks_sheet(self) -> gspread.Worksheet:
        if not hasattr(self, "_tasks_ws"):
            tasks_name = self._sheet.title + " Tasks"
            try:
                self._tasks_ws = self._spreadsheet.worksheet(tasks_name)
            except gspread.WorksheetNotFound:
                self._tasks_ws = self._spreadsheet.add_worksheet(
                    tasks_name, rows=1000, cols=len(TASK_COLUMNS)
                )
                self._tasks_ws.append_row(TASK_COLUMNS)
                logger.info("Created tasks sheet: %s", tasks_name)
        return self._tasks_ws

    def write_tasks(self, story_id: str, story_title: str, tasks: list[dict]) -> None:
        now = self._now()
        for i, task in enumerate(tasks, start=1):
            self._tasks_sheet.append_row([
                story_id,
                story_title,
                i,
                task["task"],
                task["description"],
                "Pending",
                now,
            ])
        logger.info("Wrote %d task rows for %s", len(tasks), story_id)

    def _find_task_row(self, story_id: str, task_name: str) -> int | None:
        records = self._tasks_sheet.get_all_records()
        for i, row in enumerate(records, start=2):
            if row.get("Story ID") == story_id and row.get("Task Name") == task_name:
                return i
        return None

    def get_task_status(self, story_id: str, task_name: str) -> str:
        records = self._tasks_sheet.get_all_records()
        for row in records:
            if row.get("Story ID") == story_id and row.get("Task Name") == task_name:
                return str(row.get("Status", "Pending"))
        return "Pending"

    def update_task_status(self, story_id: str, task_name: str, status: str) -> None:
        row_num = self._find_task_row(story_id, task_name)
        if not row_num:
            logger.warning("Task row not found: %s / %s", story_id, task_name)
            return
        self._tasks_sheet.update_cell(row_num, 6, status)
        self._tasks_sheet.update_cell(row_num, 7, self._now())
        logger.info("Task status: %s / %s → %s", story_id, task_name, status)

    def clear_tasks(self, story_id: str) -> None:
        records = self._tasks_sheet.get_all_records()
        row_nums = [
            i + 2
            for i, row in enumerate(records)
            if row.get("Story ID") == story_id
        ]
        for row_num in reversed(row_nums):
            self._tasks_sheet.delete_rows(row_num)
        logger.info("Cleared %d task rows for %s", len(row_nums), story_id)
