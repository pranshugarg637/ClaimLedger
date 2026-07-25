"""
Local SQLite database layer.
No external DB server required — everything runs from a single file
(backend/database/claims.db), which makes the whole system trivially
portable and fully offline.
"""
import sqlite3
import json
import uuid
import re
import hashlib
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DATABASE_PATH


def _connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't already exist. Safe to call on every boot."""
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            policy_number TEXT PRIMARY KEY,
            holder_name TEXT NOT NULL,
            plan_type TEXT NOT NULL,
            coverage_limit REAL NOT NULL,
            remaining_coverage REAL NOT NULL,
            covered_procedures TEXT NOT NULL,  -- JSON list
            status TEXT NOT NULL DEFAULT 'active',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            hospital_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            network_status TEXT NOT NULL,   -- in-network / out-of-network
            accreditation TEXT NOT NULL,
            city TEXT,
            fraud_flags INTEGER DEFAULT 0
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS fraud_patterns (
            pattern_id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            indicator_type TEXT NOT NULL,     -- e.g. 'billing', 'duplicate', 'provider'
            severity TEXT NOT NULL            -- low / medium / high
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS medical_procedures (
            procedure_code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            typical_cost_min REAL NOT NULL,
            typical_cost_max REAL NOT NULL,
            requires_preauth INTEGER DEFAULT 0
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS patient_history (
            patient_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            previous_claims INTEGER DEFAULT 0,
            previous_rejections INTEGER DEFAULT 0,
            known_conditions TEXT   -- JSON list
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            patient_name TEXT NOT NULL,
            policy_number TEXT NOT NULL,
            hospital_id TEXT,
            procedure_code TEXT,
            claimed_amount REAL NOT NULL,
            document_path TEXT,
            status TEXT NOT NULL DEFAULT 'submitted',
            current_stage TEXT DEFAULT 'uploaded',
            decision TEXT,
            confidence_score REAL,
            fraud_score REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            state_json TEXT   -- full LangGraph final state, for explainability
        )""")
        existing_claim_columns = {row[1] for row in c.execute("PRAGMA table_info(claims)").fetchall()}
        if "submitted_by" not in existing_claim_columns:
            c.execute("ALTER TABLE claims ADD COLUMN submitted_by TEXT")

        c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            input_summary TEXT,
            output_summary TEXT,
            confidence REAL,
            reasoning TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS policy_members (
            policy_number TEXT NOT NULL, patient_id TEXT NOT NULL, member_name TEXT NOT NULL,
            PRIMARY KEY (policy_number, patient_id),
            FOREIGN KEY (policy_number) REFERENCES policies(policy_number)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS policy_documents (
            document_id TEXT PRIMARY KEY, policy_number TEXT NOT NULL, source_name TEXT NOT NULL,
            extracted_text TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY (policy_number) REFERENCES policies(policy_number)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS claim_reviews (
            claim_id TEXT PRIMARY KEY, reviewer TEXT NOT NULL, decision TEXT NOT NULL,
            reasoning TEXT NOT NULL, reviewed_at TEXT NOT NULL,
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
            salt TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        # Keep existing demo databases compatible after the policy-member
        # table is introduced. Real imports replace/add these records.
        c.executemany("INSERT OR IGNORE INTO policy_members VALUES (?,?,?)", [
            ("POL-1001", "PAT-001", "Ravi Kumar"), ("POL-1002", "PAT-002", "Anita Sharma"),
            ("POL-1003", "PAT-003", "Mohammed Farid"), ("POL-1004", "PAT-004", "Priya Nair"),
        ])

        conn.commit()


def seed_if_empty():
    """Populate reference data (policies, hospitals, fraud patterns, procedures)."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM policies")
        if c.fetchone()[0] > 0:
            return  # already seeded

        policies = [
            ("POL-1001", "Ravi Kumar", "Gold", 500000, 500000,
             json.dumps(["CARD-ANGIO", "ORTHO-KNEE", "GEN-SURGERY"]), "active", "2025-01-01", "2027-01-01"),
            ("POL-1002", "Anita Sharma", "Silver", 200000, 150000,
             json.dumps(["GEN-SURGERY", "MATERNITY"]), "active", "2024-06-01", "2026-06-01"),
            ("POL-1003", "Mohammed Farid", "Platinum", 1000000, 1000000,
             json.dumps(["CARD-ANGIO", "ORTHO-KNEE", "GEN-SURGERY", "ONCOLOGY"]), "active", "2023-01-01", "2028-01-01"),
            ("POL-1004", "Priya Nair", "Silver", 200000, 20000,
             json.dumps(["GEN-SURGERY"]), "expired", "2020-01-01", "2022-01-01"),
        ]
        c.executemany("INSERT INTO policies VALUES (?,?,?,?,?,?,?,?,?)", policies)

        hospitals = [
            ("HOSP-01", "Fortis City Hospital", "in-network", "NABH", "Delhi", 0),
            ("HOSP-02", "Apollo Central", "in-network", "NABH", "Mumbai", 0),
            ("HOSP-03", "QuickCure Clinic", "out-of-network", "unaccredited", "Delhi", 3),
            ("HOSP-04", "Max Super Speciality", "in-network", "JCI", "Delhi", 0),
        ]
        c.executemany("INSERT INTO hospitals VALUES (?,?,?,?,?,?)", hospitals)

        fraud_patterns = [
            ("FP-01", "Claim amount significantly exceeds typical procedure cost", "billing", "high"),
            ("FP-02", "Duplicate claim submitted within 30 days for same procedure", "duplicate", "high"),
            ("FP-03", "Hospital has repeated fraud flags on record", "provider", "medium"),
            ("FP-04", "Claim filed immediately after policy activation (<15 days)", "timing", "medium"),
            ("FP-05", "Mismatched patient identity across documents", "identity", "high"),
        ]
        c.executemany("INSERT INTO fraud_patterns VALUES (?,?,?,?)", fraud_patterns)

        procedures = [
            ("CARD-ANGIO", "Coronary Angiography", 80000, 150000, 1),
            ("ORTHO-KNEE", "Knee Replacement Surgery", 150000, 300000, 1),
            ("GEN-SURGERY", "General Surgery (appendectomy etc.)", 30000, 90000, 0),
            ("MATERNITY", "Maternity Delivery", 40000, 120000, 0),
            ("ONCOLOGY", "Cancer Chemotherapy Cycle", 60000, 200000, 1),
        ]
        c.executemany("INSERT INTO medical_procedures VALUES (?,?,?,?,?)", procedures)

        patients = [
            ("PAT-001", "Ravi Kumar", 2, 0, json.dumps(["hypertension"])),
            ("PAT-002", "Anita Sharma", 0, 0, json.dumps([])),
            ("PAT-003", "Mohammed Farid", 5, 1, json.dumps(["diabetes", "cardiac history"])),
            ("PAT-004", "Priya Nair", 1, 1, json.dumps([])),
        ]
        c.executemany("INSERT INTO patient_history VALUES (?,?,?,?,?)", patients)
        c.executemany("INSERT INTO policy_members VALUES (?,?,?)", [
            ("POL-1001", "PAT-001", "Ravi Kumar"), ("POL-1002", "PAT-002", "Anita Sharma"),
            ("POL-1003", "PAT-003", "Mohammed Farid"), ("POL-1004", "PAT-004", "Priya Nair"),
        ])

        conn.commit()


def new_claim(patient_id, patient_name, policy_number, hospital_id, procedure_code,
              claimed_amount, document_path, submitted_by=None):
    claim_id = f"CLM-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO claims (claim_id, patient_id, patient_name, policy_number, hospital_id,
                                 procedure_code, claimed_amount, document_path, status,
                                 current_stage, created_at, updated_at, submitted_by)
                        VALUES (?,?,?,?,?,?,?,?, 'submitted', 'uploaded', ?, ?, ?)
        """, (claim_id, patient_id, patient_name, policy_number, hospital_id,
                            procedure_code, claimed_amount, document_path, now, now, submitted_by))
    return claim_id


def update_claim_stage(claim_id, stage, status=None):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        if status:
            conn.execute("UPDATE claims SET current_stage=?, status=?, updated_at=? WHERE claim_id=?",
                         (stage, status, now, claim_id))
        else:
            conn.execute("UPDATE claims SET current_stage=?, updated_at=? WHERE claim_id=?",
                         (stage, now, claim_id))


def finalize_claim(claim_id, decision, confidence_score, fraud_score, state_json):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute("""
            UPDATE claims
            SET decision=?, confidence_score=?, fraud_score=?, status=?,
                current_stage='completed', updated_at=?, state_json=?
            WHERE claim_id=?
        """, (decision, confidence_score, fraud_score, decision, now, state_json, claim_id))


def get_claim(claim_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        return dict(row) if row else None


def list_claims(limit=100, patient_id=None):
    with get_conn() as conn:
        query = """
            SELECT c.*, cr.reviewer, cr.reviewed_at, cr.reasoning AS review_reasoning,
                   CASE
                       WHEN c.decision IS NULL OR c.decision = 'needs_review' THEN 'pending'
                       WHEN cr.claim_id IS NOT NULL THEN 'human_review'
                       ELSE 'direct'
                     END AS decision_source
            FROM claims c
            LEFT JOIN claim_reviews cr ON cr.claim_id = c.claim_id
        """
        params = []
        if patient_id:
            query += " WHERE (c.patient_id=? OR c.submitted_by=?)"
            params.extend([patient_id, patient_id])
        query += " ORDER BY c.created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def insert_audit_log(claim_id, agent, action, input_summary, output_summary, confidence, reasoning):
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO audit_logs (id, claim_id, agent, action, input_summary, output_summary,
                                     confidence, reasoning, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (log_id, claim_id, agent, action, input_summary, output_summary, confidence, reasoning, now))
    return log_id


def get_audit_logs(claim_id=None, limit=200):
    with get_conn() as conn:
        if claim_id:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE claim_id=? ORDER BY timestamp ASC", (claim_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_policy(policy_number):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM policies WHERE policy_number=?", (policy_number,)).fetchone()
        return dict(row) if row else None


def policy_has_member(policy_number, patient_id):
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM policy_members WHERE policy_number=? AND patient_id=?",
                            (policy_number, patient_id)).fetchone() is not None


def import_policy(policy, patient_id, member_name, policy_text):
    """Upsert authorised policy data and store its wording for local RAG."""
    with get_conn() as conn:
        conn.execute("""INSERT INTO policies VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(policy_number) DO UPDATE SET
            holder_name=excluded.holder_name, plan_type=excluded.plan_type, coverage_limit=excluded.coverage_limit,
            remaining_coverage=excluded.remaining_coverage, covered_procedures=excluded.covered_procedures,
            status=excluded.status, start_date=excluded.start_date, end_date=excluded.end_date""",
            (policy["policy_number"], policy["holder_name"], policy["plan_type"], policy["coverage_limit"],
             policy["remaining_coverage"], json.dumps(policy["covered_procedures"]), policy["status"],
             policy["start_date"], policy["end_date"]))
        conn.execute("INSERT OR REPLACE INTO policy_members VALUES (?,?,?)", (policy["policy_number"], patient_id, member_name))
        if policy_text.strip():
            conn.execute("INSERT INTO policy_documents VALUES (?,?,?,?,?)", (str(uuid.uuid4()), policy["policy_number"],
                         "admin_import", policy_text, datetime.now(timezone.utc).isoformat()))


def retrieve_policy_context(policy_number, query, limit=3):
    """Local lexical RAG over administrator-imported policy wording."""
    terms = set(re.findall(r"[a-z0-9]{3,}", (query or "").lower()))
    with get_conn() as conn:
        rows = conn.execute("SELECT extracted_text FROM policy_documents WHERE policy_number=?", (policy_number,)).fetchall()
    candidates = []
    for row in rows:
        for chunk in re.split(r"\n\s*\n|(?<=\.)\s+", row["extracted_text"]):
            score = len(terms & set(re.findall(r"[a-z0-9]{3,}", chunk.lower())))
            if score:
                candidates.append((score, chunk.strip()))
    return [text for _, text in sorted(candidates, reverse=True)[:limit]]


def list_claims_for_review(limit=100):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM claims WHERE decision='needs_review' ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def complete_manual_review(claim_id, reviewer, decision, reasoning):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute("UPDATE claims SET decision=?, status=?, current_stage='manually_reviewed', updated_at=? WHERE claim_id=?",
                     (decision, decision, now, claim_id))
        conn.execute("""INSERT INTO claim_reviews VALUES (?,?,?,?,?)
            ON CONFLICT(claim_id) DO UPDATE SET reviewer=excluded.reviewer, decision=excluded.decision,
            reasoning=excluded.reasoning, reviewed_at=excluded.reviewed_at""",
                     (claim_id, reviewer, decision, reasoning, now))


def create_user(username, password, role):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    with get_conn() as conn:
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?)", (username.lower().strip(), digest, salt, role, datetime.now(timezone.utc).isoformat()))


def authenticate_user(username, password):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username.lower().strip(),)).fetchone()
    if not row:
        return None
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), row["salt"].encode(), 200_000).hex()
    return dict(row) if secrets.compare_digest(digest, row["password_hash"]) else None


def get_hospital(hospital_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM hospitals WHERE hospital_id=?", (hospital_id,)).fetchone()
        return dict(row) if row else None


def get_procedure(procedure_code):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM medical_procedures WHERE procedure_code=?", (procedure_code,)).fetchone()
        return dict(row) if row else None


def get_patient_history(patient_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM patient_history WHERE patient_id=?", (patient_id,)).fetchone()
        return dict(row) if row else None


def all_fraud_patterns():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM fraud_patterns").fetchall()
        return [dict(r) for r in rows]


def dashboard_stats(patient_id=None):
    with get_conn() as conn:
        where = " WHERE (patient_id=? OR submitted_by=?)" if patient_id else ""
        params = (patient_id, patient_id) if patient_id else ()
        total = conn.execute(f"SELECT COUNT(*) c FROM claims{where}", params).fetchone()["c"]
        approved = conn.execute(f"SELECT COUNT(*) c FROM claims{where}{' AND' if where else ' WHERE'} decision='approved'", params).fetchone()["c"]
        rejected = conn.execute(f"SELECT COUNT(*) c FROM claims{where}{' AND' if where else ' WHERE'} decision='rejected'", params).fetchone()["c"]
        review = conn.execute(f"SELECT COUNT(*) c FROM claims{where}{' AND' if where else ' WHERE'} decision='needs_review'", params).fetchone()["c"]
        pending = conn.execute(f"SELECT COUNT(*) c FROM claims{where}{' AND' if where else ' WHERE'} status IN ('submitted', 'processing')", params).fetchone()["c"]
        avg_conf = conn.execute(f"SELECT AVG(confidence_score) a FROM claims{where}{' AND' if where else ' WHERE'} confidence_score IS NOT NULL", params).fetchone()["a"]
        total_amount = conn.execute(f"SELECT SUM(claimed_amount) s FROM claims{where}", params).fetchone()["s"]
        human_approved = conn.execute(f"""SELECT COUNT(*) c FROM claims c
            INNER JOIN claim_reviews r ON r.claim_id=c.claim_id
            WHERE c.decision='approved'{(' AND (c.patient_id=? OR c.submitted_by=?)' if patient_id else '')}""", params).fetchone()["c"]
        human_rejected = conn.execute(f"""SELECT COUNT(*) c FROM claims c
            INNER JOIN claim_reviews r ON r.claim_id=c.claim_id
            WHERE c.decision='rejected'{(' AND (c.patient_id=? OR c.submitted_by=?)' if patient_id else '')}""", params).fetchone()["c"]
        return {
            "total_claims": total,
            "approved": approved,
            "rejected": rejected,
            "needs_review": review,
            "pending": pending,
            "direct_approved": approved - human_approved,
            "direct_rejected": rejected - human_rejected,
            "human_approved": human_approved,
            "human_rejected": human_rejected,
            "avg_confidence": round(avg_conf, 3) if avg_conf else None,
            "total_claimed_amount": total_amount or 0,
        }
