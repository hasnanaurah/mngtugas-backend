from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Manajemen Tugas Mahasiswa", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "192.168.56.11"),
    "user":     os.getenv("DB_USER", "mngtugas_user"),
    "password": os.getenv("DB_PASSWORD", "manage123"),
    "database": os.getenv("DB_NAME", "mngtugas"),
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# ─── Schema ────────────────────────────────────────────────────────────────
class MKCreate(BaseModel):
    nama_mk: str
    dosen: Optional[str] = ""

class TugasCreate(BaseModel):
    mk_id: int
    judul: str
    deskripsi: Optional[str] = ""
    deadline: str
    prioritas: Optional[str] = "sedang"
    status: Optional[str] = "belum"

class TugasUpdate(BaseModel):
    mk_id: Optional[int] = None
    judul: Optional[str] = None
    deskripsi: Optional[str] = None
    deadline: Optional[str] = None
    prioritas: Optional[str] = None
    status: Optional[str] = None

def serialize(row: dict) -> dict:
    for f in ("deadline", "created_at"):
        if row.get(f):
            row[f] = str(row[f])
    return row

# ═══════════════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"message": "API Manajemen Tugas Mahasiswa v3.0"}

# ── MATA KULIAH ────────────────────────────────────────────────────────────
@app.get("/mata-kuliah")
def get_mk():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM mata_kuliah ORDER BY nama_mk ASC")
    rows = cur.fetchall()
    for r in rows: r["created_at"] = str(r["created_at"])
    cur.close(); conn.close()
    return {"data": rows}

@app.post("/mata-kuliah", status_code=201)
def create_mk(body: MKCreate):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO mata_kuliah (nama_mk, dosen) VALUES (%s, %s)", (body.nama_mk, body.dosen))
    conn.commit(); new_id = cur.lastrowid
    cur.close(); conn.close()
    return {"message": "Mata kuliah ditambahkan", "id": new_id}

@app.put("/mata-kuliah/{mk_id}")
def update_mk(mk_id: int, body: MKCreate):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE mata_kuliah SET nama_mk=%s, dosen=%s WHERE id=%s", (body.nama_mk, body.dosen, mk_id))
    conn.commit(); cur.close(); conn.close()
    return {"message": "Mata kuliah diupdate"}

@app.delete("/mata-kuliah/{mk_id}")
def delete_mk(mk_id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM mata_kuliah WHERE id=%s", (mk_id,))
    conn.commit(); cur.close(); conn.close()
    return {"message": "Mata kuliah dihapus"}

# ── TUGAS ──────────────────────────────────────────────────────────────────
@app.get("/tugas")
def get_tugas(status: Optional[str] = None, prioritas: Optional[str] = None, mk_id: Optional[int] = None):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    q = "SELECT t.*, m.nama_mk, m.dosen FROM tugas t JOIN mata_kuliah m ON t.mk_id = m.id WHERE 1=1"
    params = []
    if status:    q += " AND t.status=%s";    params.append(status)
    if prioritas: q += " AND t.prioritas=%s"; params.append(prioritas)
    if mk_id:     q += " AND t.mk_id=%s";     params.append(mk_id)
    q += " ORDER BY t.deadline ASC"
    cur.execute(q, params)
    rows = [serialize(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"data": rows, "total": len(rows)}

@app.get("/tugas/{tugas_id}")
def get_satu(tugas_id: int):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT t.*, m.nama_mk, m.dosen FROM tugas t JOIN mata_kuliah m ON t.mk_id=m.id WHERE t.id=%s", (tugas_id,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row: raise HTTPException(404, "Tugas tidak ditemukan")
    return serialize(row)

@app.post("/tugas", status_code=201)
def create_tugas(body: TugasCreate):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO tugas (user_id, mk_id, judul, deskripsi, deadline, prioritas, status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (1, body.mk_id, body.judul, body.deskripsi, body.deadline, body.prioritas, body.status)
    )
    conn.commit(); new_id = cur.lastrowid
    cur.close(); conn.close()
    return {"message": "Tugas ditambahkan", "id": new_id}

@app.put("/tugas/{tugas_id}")
def update_tugas(tugas_id: int, body: TugasUpdate):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id FROM tugas WHERE id=%s", (tugas_id,))
    if not cur.fetchone(): raise HTTPException(404, "Tugas tidak ditemukan")
    fields, vals = [], []
    for f, v in body.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); vals.append(v)
    if not fields: raise HTTPException(400, "Tidak ada data")
    vals.append(tugas_id)
    cur.execute(f"UPDATE tugas SET {', '.join(fields)} WHERE id=%s", vals)
    conn.commit(); cur.close(); conn.close()
    return {"message": "Tugas diupdate"}

@app.delete("/tugas/{tugas_id}")
def delete_tugas(tugas_id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM tugas WHERE id=%s", (tugas_id,))
    conn.commit(); cur.close(); conn.close()
    return {"message": "Tugas dihapus"}

@app.get("/statistik")
def statistik():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT
            COUNT(*)                                           AS total,
            SUM(status='belum')                               AS belum,
            SUM(status='dikerjakan')                          AS dikerjakan,
            SUM(status='selesai')                             AS selesai,
            SUM(prioritas='tinggi' AND status!='selesai')     AS mendesak,
            SUM(deadline < NOW() AND status!='selesai')       AS terlambat
        FROM tugas
    """)
    row = cur.fetchone(); cur.close(); conn.close()
    return row
