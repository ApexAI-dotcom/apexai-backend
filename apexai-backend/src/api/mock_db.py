import json
import logging
import uuid
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Dynamic path relative to the file location to handle running from different directories
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
MOCK_DB_PATH = PROJECT_ROOT / "temp" / "mock_db.json"

# Ensure temp directory exists
MOCK_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _get_mock_db() -> Dict[str, Any]:
    if not MOCK_DB_PATH.exists():
        default_db = {
            "kart_profiles": [],
            "kart_session_logs": [],
            "kart_component_history": [],
            "kart_setups": [],
            "circuits": [],
            "analyses": []
        }
        with open(MOCK_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(default_db, f, indent=2)
        return default_db
    try:
        with open(MOCK_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "kart_profiles": [],
            "kart_session_logs": [],
            "kart_component_history": [],
            "kart_setups": [],
            "circuits": [],
            "analyses": []
        }

def _save_mock_db(db: Dict[str, Any]):
    try:
        with open(MOCK_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving mock db: {e}")

class MockSupabaseTable:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.filters = []
        self.order_by = None
        self.limit_val = None
        self.range_val = None
        self.insert_payload = None
        self.update_payload = None
        self.is_delete = False

    def select(self, fields="*"):
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, values))
        return self

    def order(self, field, desc=False):
        self.order_by = (field, desc)
        return self

    def limit(self, limit):
        self.limit_val = limit
        return self

    def range(self, start, end):
        self.range_val = (start, end)
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def delete(self):
        self.is_delete = True
        return self

    def execute(self):
        db = _get_mock_db()
        if self.table_name not in db:
            db[self.table_name] = []
            
        # 1. Handle INSERT
        if self.insert_payload is not None:
            rows = self.insert_payload if isinstance(self.insert_payload, list) else [self.insert_payload]
            inserted = []
            for r in rows:
                r = {**r}
                if "id" not in r:
                    r["id"] = str(uuid.uuid4())
                if "created_at" not in r:
                    r["created_at"] = datetime.now().isoformat()
                db[self.table_name].append(r)
                inserted.append(r)
            _save_mock_db(db)
            class MockResult:
                def __init__(self, data):
                    self.data = data
            return MockResult(inserted)

        data = db.get(self.table_name, [])

        # 2. Handle UPDATE / DELETE / SELECT
        # First, find matching items
        matching_indices = []
        for idx, row in enumerate(data):
            match = True
            for f_type, field, val in self.filters:
                if f_type == "eq":
                    row_val = row.get(field)
                    if str(row_val) != str(val):
                        match = False
                        break
                elif f_type == "in":
                    row_val = row.get(field)
                    if row_val not in val:
                        match = False
                        break
            if match:
                matching_indices.append(idx)

        if self.is_delete:
            deleted = [data[idx] for idx in matching_indices]
            db[self.table_name] = [row for idx, row in enumerate(data) if idx not in matching_indices]
            _save_mock_db(db)
            class MockResult:
                def __init__(self, data):
                    self.data = data
            return MockResult(deleted)

        if self.update_payload is not None:
            updated = []
            for idx in matching_indices:
                # Make a shallow copy to be safe
                data[idx] = {**data[idx], **self.update_payload}
                updated.append(data[idx])
            _save_mock_db(db)
            class MockResult:
                def __init__(self, data):
                    self.data = data
            return MockResult(updated)

        # It's a SELECT query
        filtered_data = [data[idx] for idx in matching_indices]
        
        # Resolve simple joins for kart_setups -> circuits
        if self.table_name == "kart_setups":
            circuits = db.get("circuits", [])
            circuits_by_id = {c.get("id"): c for c in circuits}
            for row in filtered_data:
                cid = row.get("circuit_id")
                if cid and cid in circuits_by_id:
                    row["circuits"] = circuits_by_id[cid]
                else:
                    row["circuits"] = None

        # Apply order
        if self.order_by:
            field, desc = self.order_by
            filtered_data.sort(key=lambda x: x.get(field) or "", reverse=desc)
            
        # Apply limit
        if self.limit_val:
            filtered_data = filtered_data[:self.limit_val]
            
        # Apply range
        if self.range_val:
            start, end = self.range_val
            filtered_data = filtered_data[start:end+1]

        class MockResult:
            def __init__(self, data):
                self.data = data
        return MockResult(filtered_data)

class MockSupabaseClient:
    def table(self, name: str):
        return MockSupabaseTable(name)
