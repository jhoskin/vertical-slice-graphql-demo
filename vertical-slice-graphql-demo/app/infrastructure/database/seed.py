"""
Seed script for populating the database with initial data.

Run with: uv run python -m app.infrastructure.database.seed
"""
import json
from datetime import datetime

from app.infrastructure.database.models import (
    AuditLog,
    ProtocolVersion,
    Site,
    Trial,
    TrialSite,
)
from app.infrastructure.database.session import init_db, session_scope


def seed_data() -> None:
    """Seed the database with initial data."""
    print("Initializing database...")
    init_db()

    with session_scope() as session:
        print("Clearing existing data...")
        # Clear existing data (in reverse order of dependencies)
        session.query(AuditLog).delete()
        session.query(TrialSite).delete()
        session.query(ProtocolVersion).delete()
        session.query(Site).delete()
        session.query(Trial).delete()
        session.commit()

        print("Creating trials...")
        # Create 3 trials across phases
        trial1 = Trial(
            name="ACME Trial Alpha",
            phase="Phase I",
            status="active",
            created_at=datetime.utcnow(),
        )
        trial2 = Trial(
            name="Beta Oncology Study",
            phase="Phase II",
            status="active",
            created_at=datetime.utcnow(),
        )
        trial3 = Trial(
            name="Gamma Cardiovascular Trial",
            phase="Phase III",
            status="draft",
            created_at=datetime.utcnow(),
        )
        session.add_all([trial1, trial2, trial3])
        session.flush()  # Get IDs

        print("Creating sites...")
        # Create 2 sites
        site1 = Site(name="Memorial Hospital", country="USA")
        site2 = Site(name="University Medical Center", country="UK")
        session.add_all([site1, site2])
        session.flush()  # Get IDs

        print("Linking sites to trials...")
        # Link sites to trial1
        trial_site1 = TrialSite(trial_id=trial1.id, site_id=site1.id, status="active")
        trial_site2 = TrialSite(trial_id=trial1.id, site_id=site2.id, status="pending")
        session.add_all([trial_site1, trial_site2])

        print("Creating protocol versions...")
        # Create 1 protocol version per trial
        protocol1 = ProtocolVersion(
            trial_id=trial1.id,
            version="v1.0",
            notes="Initial protocol for Alpha trial",
            created_at=datetime.utcnow(),
        )
        protocol2 = ProtocolVersion(
            trial_id=trial2.id,
            version="v1.2",
            notes="Updated protocol with revised endpoints",
            created_at=datetime.utcnow(),
        )
        protocol3 = ProtocolVersion(
            trial_id=trial3.id,
            version="v1.0",
            notes="Draft protocol for Gamma trial",
            created_at=datetime.utcnow(),
        )
        session.add_all([protocol1, protocol2, protocol3])

        print("Creating audit logs...")
        # Create several audit entries
        audit1 = AuditLog(
            user="system",
            action="create_trial",
            entity="trial",
            entity_id=str(trial1.id),
            payload_json=json.dumps(
                {"name": trial1.name, "phase": trial1.phase, "status": trial1.status}
            ),
            created_at=datetime.utcnow(),
        )
        audit2 = AuditLog(
            user="system",
            action="create_trial",
            entity="trial",
            entity_id=str(trial2.id),
            payload_json=json.dumps(
                {"name": trial2.name, "phase": trial2.phase, "status": trial2.status}
            ),
            created_at=datetime.utcnow(),
        )
        audit3 = AuditLog(
            user="system",
            action="register_site",
            entity="trial_site",
            entity_id=f"{trial1.id}_{site1.id}",
            payload_json=json.dumps(
                {
                    "trial_id": trial1.id,
                    "site_id": site1.id,
                    "site_name": site1.name,
                    "status": "active",
                }
            ),
            created_at=datetime.utcnow(),
        )
        audit4 = AuditLog(
            user="admin",
            action="update_trial_metadata",
            entity="trial",
            entity_id=str(trial1.id),
            payload_json=json.dumps({"status": {"old": "draft", "new": "active"}}),
            created_at=datetime.utcnow(),
        )
        session.add_all([audit1, audit2, audit3, audit4])

        session.commit()
        print(f"✓ Seeded database successfully!")
        print(f"  - {3} trials created")
        print(f"  - {2} sites created")
        print(f"  - {2} trial-site links created")
        print(f"  - {3} protocol versions created")
        print(f"  - {4} audit log entries created")


if __name__ == "__main__":
    seed_data()
