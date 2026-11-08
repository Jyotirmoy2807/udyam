import os
import re
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal, engine, Base
from app.db.models import (
    Product,
    GstinRegistry,
    UdyamRegistry,
    Partner,
)


def find_data_file(filename: str) -> Path:
    candidates = [
        Path("data") / filename,
        Path("../data") / filename,
        Path("data/YTL_TrackA_Udyam_Digital_Data") / filename,
        Path("../data/YTL_TrackA_Udyam_Digital_Data") / filename,
        Path(__file__).resolve().parent.parent.parent.parent / "data" / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Could not locate data file: {filename}")


def seed_products(session) -> int:
    path = find_data_file("product_catalogue.csv")
    df = pd.read_csv(path)
    count = 0
    for _, row in df.iterrows():
        # Parse available_city_tiers: e.g. "1;2" -> [1, 2]
        tiers_raw = str(row.get("available_city_tiers", "1;2"))
        tiers = [int(t.strip()) for t in tiers_raw.split(";") if t.strip().isdigit()]

        # Parse requires_one_of: e.g. "P01|P02" -> ["P01", "P02"]
        req_raw = str(row.get("requires_one_of", ""))
        requires_one_of = []
        if req_raw and req_raw != "nan":
            requires_one_of = [p.strip() for p in req_raw.split("|") if p.strip()]

        # Parse target_segments: e.g. "micro;prof" -> ["micro", "prof"]
        seg_raw = str(row.get("target_segments", ""))
        target_segments = []
        if seg_raw and seg_raw != "nan":
            target_segments = [s.strip() for s in seg_raw.split(";") if s.strip()]

        stmt = insert(Product).values(
            product_id=str(row["product_id"]).strip(),
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
        stmt = stmt.on_conflict_do_update(
            index_elements=["product_id"],
            set_={
                "name": stmt.excluded.name,
                "category": stmt.excluded.category,
                "description": stmt.excluded.description,
                "unit": stmt.excluded.unit,
                "price_min": stmt.excluded.price_min,
                "price_max": stmt.excluded.price_max,
                "setup_fee": stmt.excluded.setup_fee,
                "min_contract_months": stmt.excluded.min_contract_months,
                "city_tier_availability": stmt.excluded.city_tier_availability,
                "min_employees": stmt.excluded.min_employees,
                "min_sites": stmt.excluded.min_sites,
                "requires_gstin": stmt.excluded.requires_gstin,
                "requires_one_of": stmt.excluded.requires_one_of,
                "typical_install_days": stmt.excluded.typical_install_days,
                "target_segments": stmt.excluded.target_segments,
            },
        )
        session.execute(stmt)
        count += 1
    session.commit()
    return count


def seed_gstin_registry(session) -> int:
    path = find_data_file("mock_gstin_registry.csv")
    df = pd.read_csv(path)
    records = []
    for _, row in df.iterrows():
        addr = str(row["principal_place_of_business"]).strip()
        pincode_match = re.search(r"(\d{6})", addr)
        pincode = pincode_match.group(1) if pincode_match else None

        parts = [p.strip() for p in addr.split(",")]
        city = parts[-2].strip() if len(parts) >= 3 else None

        records.append({
            "gstin": str(row["gstin"]).strip().upper(),
            "legal_name": str(row["legal_name"]).strip(),
            "trade_name": str(row["trade_name"]).strip(),
            "constitution": str(row["constitution"]).strip(),
            "state": str(row["state"]).strip(),
            "city": city,
            "pincode": pincode,
            "address": addr,
            "status": str(row["status"]).strip(),
            "registration_date": str(row["registration_date"]).strip(),
        })

    # Batch insert in chunks of 500
    chunk_size = 500
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        stmt = insert(GstinRegistry).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["gstin"],
            set_={
                "legal_name": stmt.excluded.legal_name,
                "trade_name": stmt.excluded.trade_name,
                "constitution": stmt.excluded.constitution,
                "state": stmt.excluded.state,
                "city": stmt.excluded.city,
                "pincode": stmt.excluded.pincode,
                "address": stmt.excluded.address,
                "status": stmt.excluded.status,
                "registration_date": stmt.excluded.registration_date,
            },
        )
        session.execute(stmt)
    session.commit()
    return len(records)


def seed_udyam_registry(session) -> int:
    path = find_data_file("mock_udyam_registry.csv")
    df = pd.read_csv(path)
    records = []
    for _, row in df.iterrows():
        records.append({
            "udyam_number": str(row["udyam_number"]).strip().upper(),
            "enterprise_name": str(row["enterprise_name"]).strip(),
            "enterprise_type": str(row["enterprise_type"]).strip(),
            "major_activity": str(row["major_activity"]).strip(),
            "nic_description": str(row["nic_description"]).strip() if pd.notnull(row["nic_description"]) else "",
            "city": str(row["city"]).strip() if pd.notnull(row["city"]) else None,
            "state": str(row["state"]).strip(),
            "date_of_registration": str(row["date_of_registration"]).strip(),
        })

    chunk_size = 500
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        stmt = insert(UdyamRegistry).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["udyam_number"],
            set_={
                "enterprise_name": stmt.excluded.enterprise_name,
                "enterprise_type": stmt.excluded.enterprise_type,
                "major_activity": stmt.excluded.major_activity,
                "nic_description": stmt.excluded.nic_description,
                "city": stmt.excluded.city,
                "state": stmt.excluded.state,
                "date_of_registration": stmt.excluded.date_of_registration,
            },
        )
        session.execute(stmt)
    session.commit()
    return len(records)


def seed_partners(session) -> int:
    partners = [
        {
            "name": "Accel Enterprise Direct Partner North",
            "cities": ["Delhi", "Ludhiana", "Lucknow", "Jaipur", "Chandigarh"],
            "segments": ["micro", "professional_offices", "small_multi_site", "small_manufacturers"],
        },
        {
            "name": "Accel Enterprise Direct Partner South",
            "cities": ["Bengaluru", "Chennai", "Kochi", "Hyderabad", "Visakhapatnam"],
            "segments": ["micro", "professional_offices", "small_multi_site", "small_manufacturers"],
        },
        {
            "name": "Accel Enterprise Direct Partner West",
            "cities": ["Mumbai", "Pune", "Ahmedabad", "Nagpur", "Surat"],
            "segments": ["micro", "professional_offices", "small_multi_site", "small_manufacturers"],
        },
        {
            "name": "Accel Enterprise Direct Partner East",
            "cities": ["Kolkata", "Patna", "Bhubaneswar", "Guwahati", "Ranchi"],
            "segments": ["micro", "professional_offices", "small_multi_site", "small_manufacturers"],
        },
    ]
    for p in partners:
        existing = session.query(Partner).filter(Partner.name == p["name"]).first()
        if not existing:
            session.add(Partner(
                name=p["name"],
                cities=p["cities"],
                segments=p["segments"],
            ))
    session.commit()
    return len(partners)


def run_seed():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        p_count = seed_products(session)
        print(f"Seeded products: {p_count}")
        g_count = seed_gstin_registry(session)
        print(f"Seeded GSTIN records: {g_count}")
        u_count = seed_udyam_registry(session)
        print(f"Seeded Udyam records: {u_count}")
        part_count = seed_partners(session)
        print(f"Seeded Channel Partners: {part_count}")
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()
