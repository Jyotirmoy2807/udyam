import re
from sqlalchemy.orm import Session
from app.ports import GstinRecord, UdyamRecord, RegistryPort
from app.db.models import GstinRegistry, UdyamRegistry


class DatabaseRegistry:
    """Implementation of RegistryPort querying seeded mock registries in Postgres."""

    def __init__(self, session: Session):
        self.session = session

    def get_gstin(self, gstin: str) -> GstinRecord | None:
        """Lookup strictly by exact 15-character GSTIN. Never by business name."""
        if not gstin:
            return None
        cleaned = gstin.strip().upper()
        row = self.session.query(GstinRegistry).filter(GstinRegistry.gstin == cleaned).first()
        if not row:
            return None
        return GstinRecord(
            gstin=row.gstin,
            legal_name=row.legal_name,
            trade_name=row.trade_name,
            constitution=row.constitution,
            state=row.state,
            city=row.city,
            pincode=row.pincode,
            address=row.address,
            status=row.status,
            registration_date=row.registration_date,
        )

    def get_udyam(self, udyam_no: str) -> UdyamRecord | None:
        """Lookup strictly by exact Udyam Registration Number."""
        if not udyam_no:
            return None
        cleaned = udyam_no.strip().upper()
        row = self.session.query(UdyamRegistry).filter(UdyamRegistry.udyam_number == cleaned).first()
        if not row:
            return None
        return UdyamRecord(
            udyam_number=row.udyam_number,
            enterprise_name=row.enterprise_name,
            enterprise_type=row.enterprise_type,
            major_activity=row.major_activity,
            nic_description=row.nic_description,
            city=row.city,
            state=row.state,
            date_of_registration=row.date_of_registration,
        )
