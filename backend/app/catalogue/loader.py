from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import pandas as pd


@dataclass(frozen=True)
class ProductRecord:
    product_id: str
    name: str
    category: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup_fee: int
    min_contract_months: int
    city_tier_availability: list[int]
    min_employees: int
    min_sites: int
    requires_gstin: str
    requires_one_of: list[str]
    typical_install_days: int
    target_segments: list[str]


_catalogue_cache: dict[str, ProductRecord] | None = None


def find_catalogue_csv() -> Path:
    candidates = [
        Path("data/product_catalogue.csv"),
        Path("../data/product_catalogue.csv"),
        Path("data/YTL_TrackA_Udyam_Digital_Data/product_catalogue.csv"),
        Path(__file__).resolve().parent.parent.parent.parent / "data" / "product_catalogue.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("Could not find product_catalogue.csv")


def load_catalogue(csv_path: Path | None = None, reload: bool = False) -> dict[str, ProductRecord]:
    global _catalogue_cache
    if _catalogue_cache is not None and not reload:
        return _catalogue_cache

    path = csv_path or find_catalogue_csv()
    df = pd.read_csv(path)

    catalogue = {}
    for _, row in df.iterrows():
        pid = str(row["product_id"]).strip()

        tiers_raw = str(row.get("available_city_tiers", "1;2"))
        tiers = [int(t.strip()) for t in tiers_raw.split(";") if t.strip().isdigit()]

        req_raw = str(row.get("requires_one_of", ""))
        requires_one_of = []
        if req_raw and req_raw != "nan":
            requires_one_of = [p.strip() for p in req_raw.split("|") if p.strip()]

        seg_raw = str(row.get("target_segments", ""))
        target_segments = []
        if seg_raw and seg_raw != "nan":
            target_segments = [s.strip() for s in seg_raw.split(";") if s.strip()]

        record = ProductRecord(
            product_id=pid,
            name=str(row["product_name"]).strip(),
            category=str(row["category"]).strip(),
            description=str(row["description"]).strip() if pd.notnull(row["description"]) else "",
            unit=str(row["unit"]).strip(),
            price_min=int(row["price_min_inr_per_month"]),
            price_max=int(row["price_max_inr_per_month"]),
            setup_fee=int(row.get("one_time_setup_inr", 0)),
            min_contract_months=int(row.get("min_contract_months", 12)),
            city_tier_availability=tiers,
            min_employees=int(row.get("min_employees", 1)),
            min_sites=int(row.get("min_sites", 1)),
            requires_gstin=str(row.get("requires_gstin", "N")).strip().upper(),
            requires_one_of=requires_one_of,
            typical_install_days=int(row.get("typical_install_days", 7)),
            target_segments=target_segments,
        )
        catalogue[pid] = record

    _catalogue_cache = catalogue
    return catalogue
