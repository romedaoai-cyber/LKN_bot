"""
Local JSON-file storage — simple get/set helpers for each collection.
All data is a list of dicts keyed by 'id'.
"""
import json
from pathlib import Path
from datetime import datetime


def _load(filepath: Path) -> list:
    if filepath.exists():
        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(filepath: Path, data: list):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class LocalStore:
    def __init__(self, filepath: Path):
        self.filepath = filepath

    def all(self) -> list:
        return _load(self.filepath)

    def get(self, id_: str) -> dict | None:
        return next((r for r in self.all() if r.get("id") == id_), None)

    def save(self, record: dict):
        """Insert or update by id."""
        records = self.all()
        idx = next((i for i, r in enumerate(records) if r.get("id") == record.get("id")), None)
        if idx is not None:
            record["updated_at"] = datetime.utcnow().isoformat()
            records[idx] = record
        else:
            records.append(record)
        _save(self.filepath, records)

    def delete(self, id_: str):
        records = [r for r in self.all() if r.get("id") != id_]
        _save(self.filepath, records)

    def filter(self, **kwargs) -> list:
        results = self.all()
        for key, val in kwargs.items():
            results = [r for r in results if r.get(key) == val]
        return results

    def get_single(self) -> dict:
        """For single-document stores (brand_profile)."""
        records = self.all()
        return records[0] if records else {}

    def save_single(self, record: dict):
        """For single-document stores (brand_profile)."""
        _save(self.filepath, [record])
