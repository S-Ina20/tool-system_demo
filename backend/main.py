# Three Lab 工具再研磨依頼システム - バックエンド (FastAPI + SQLite)
# 起動方法: uvicorn main:app --reload --port 8000

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import qrcode
import io
import base64
import uuid
from datetime import datetime

app = FastAPI(title="Three Lab 工具再研磨依頼システム")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "tools.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # 既存のテーブルを削除して再作成（デモ用）
    conn.executescript("""
        DROP TABLE IF EXISTS usage_logs;
        DROP TABLE IF EXISTS sharpening_requests;
        DROP TABLE IF EXISTS tools;

        CREATE TABLE tools (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tool_type TEXT NOT NULL,
            material TEXT,
            diameter_mm REAL,
            length_mm REAL,
            flute_count INTEGER,
            coating TEXT,
            manufacturer TEXT,
            serial_number TEXT,
            purchase_date TEXT,
            status TEXT DEFAULT 'active',
            usage_count INTEGER DEFAULT 0,
            resharpening_count INTEGER DEFAULT 0,
            max_resharpening INTEGER DEFAULT 5,
            location TEXT,
            notes TEXT,
            customer_name TEXT DEFAULT 'デモ顧客株式会社',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE sharpening_requests (
            id TEXT PRIMARY KEY,
            tool_id TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            reason TEXT,
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'pending',
            estimated_price INTEGER,
            estimated_delivery TEXT,
            quote_notes TEXT,
            quoted_at TEXT,
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (tool_id) REFERENCES tools(id)
        );

        CREATE TABLE usage_logs (
            id TEXT PRIMARY KEY,
            tool_id TEXT NOT NULL,
            used_by TEXT NOT NULL,
            used_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (tool_id) REFERENCES tools(id)
        );
    """)

    # デモデータ（実在のメーカーと、そのメーカーが実際に得意・製造している工具種類の組み合わせ）
    demo_tools = [
        # OSG: タップ、エンドミル、ドリルの世界トップメーカー
        ("tool-001", "超硬防振型エンドミル AE-VMS φ10", "スクエアエンドミル", "超硬", 10.0, 75.0, 4, "DUARISE", "OSG", "OSG-AEVMS-010", "2025-11-15", "active", 150, 1, 3, "棚A-1"),
        ("tool-002", "スパイラルタップ A-SFT M8", "タップ", "ハイス", 8.0, 70.0, 3, "Vコーティング", "OSG", "OSG-ASFT-M8", "2025-12-05", "active", 45, 0, 1, "棚A-2"),
        
        # 住友電工: 超硬・cBN・焼結ダイヤ工具に強い
        ("tool-003", "イゲタロイ インサート WNMG080408N-GU", "旋削用インサート", "超硬", None, None, None, "AC8025P", "住友電工", "SUM-WNMG-001", "2026-01-20", "sharpening_needed", 280, 2, 3, "棚B-1"),
        ("tool-004", "スミボロン インサート CNGA120408", "旋削用インサート", "cBN", None, None, None, "なし", "住友電工", "SUM-CNGA-002", "2025-10-10", "active", 85, 0, 2, "棚B-2"),
        ("tool-005", "マルチドリル MDW0850NHGS3", "超硬ドリル", "超硬", 8.5, 90.0, 2, "Dex", "住友電工", "SUM-MDW-085", "2026-02-01", "active", 20, 0, 5, "棚B-3"),

        # 京セラ: セラミック、超硬、サーメット、ミーリングに強い
        ("tool-006", "ミーリングインサート BDMT11T308ER-JT", "フライス用インサート", "超硬", None, None, None, "PR1535", "京セラ", "KYO-BDMT-001", "2026-01-15", "active", 110, 1, 3, "棚C-1"),
        ("tool-007", "サーメットインサート TNMG160404", "旋削用インサート", "サーメット", None, None, None, "PV720", "京セラ", "KYO-TNMG-001", "2025-12-20", "active", 60, 0, 2, "棚C-2"),

        # 三菱マテリアル: インサート、超硬エンドミル、ドリル全般
        ("tool-008", "インパクトミラクルエンドミル VQMHVRBD1000R100", "ラジアスエンドミル", "超硬", 10.0, 80.0, 4, "MIRACLE", "三菱マテリアル", "MMC-VQMHV-01", "2026-01-10", "active", 45, 1, 5, "棚D-1"),
        ("tool-009", "WSTARドリル MVS0500X05S050", "超硬ドリル", "超硬", 5.0, 100.0, 2, "DP1020", "三菱マテリアル", "MMC-MVS-050", "2025-09-05", "sharpening_needed", 300, 3, 5, "棚D-2"),

        # タンガロイ: インサートチップ、TACミル（刃先交換式）
        ("tool-010", "旋削用インサート CNMG120408-TM", "旋削用インサート", "超硬", None, None, None, "T9215", "タンガロイ", "TNG-CNMG-001", "2026-02-15", "active", 15, 0, 3, "棚E-1"),
        ("tool-011", "TACカッター用インサート LNMU0303ZER-ML", "フライス用インサート", "超硬", None, None, None, "AH3135", "タンガロイ", "TNG-LNMU-001", "2025-11-20", "active", 140, 1, 3, "棚E-2"),

        # NTK（日本特殊陶業）: セラミック工具、小物部品加工用
        ("tool-012", "セラミックインサート SNGN120408", "旋削用インサート", "セラミック", None, None, None, "HC2", "NTK（日本特殊陶業）", "NTK-SNGN-001", "2026-02-10", "sharpening_needed", 320, 2, 3, "棚F-1"),
        ("tool-013", "SSバイト用インサート DCGT11T302M-CF", "旋削用インサート", "超硬", None, None, None, "QM3", "NTK（日本特殊陶業）", "NTK-DCGT-001", "2026-01-05", "active", 55, 0, 2, "棚F-2"),

        # 日進工具 (NS TOOL): 小径エンドミルに特化
        ("tool-014", "無限コーティング マイクロエンドミル MSE230 φ0.5", "スクエアエンドミル", "超硬", 0.5, 40.0, 2, "無限コーティング", "日進工具", "NS-MSE-005", "2026-02-20", "active", 10, 0, 1, "棚G-1"),
        ("tool-015", "ロングネックボールエンドミル MRB230 R1x10", "ボールエンドミル", "超硬", 2.0, 50.0, 2, "無限コーティング", "日進工具", "NS-MRB-R1", "2025-12-10", "active", 85, 1, 3, "棚G-2"),
    ]
    for t in demo_tools:
        conn.execute("""
            INSERT INTO tools (id, name, tool_type, material, diameter_mm, length_mm, flute_count, coating, manufacturer, serial_number, purchase_date, status, usage_count, resharpening_count, max_resharpening, location)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, t)

    # デモ依頼データ
    demo_reqs = [
        ("req-001", "tool-003", "田中 太郎", "刃先の摩耗が激しい。切削面の品質低下", "high", "quoted", 8500, "2026-03-05", "標準納期での対応可能です"),
        ("req-002", "tool-012", "鈴木 花子", "切削抵抗の増加を感じる", "normal", "pending", None, None, None),
    ]
    for r in demo_reqs:
        conn.execute("""
            INSERT INTO sharpening_requests (id, tool_id, requested_by, reason, priority, status, estimated_price, estimated_delivery, quote_notes)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, r)

    # デモ使用履歴データ
    demo_usage = [
        ("usage-001", "tool-001", "山田 一郎", "2026-02-25 09:15:00", "マシニングセンタ 1号機"),
        ("usage-002", "tool-001", "佐藤 次郎", "2026-02-26 14:30:00", "マシニングセンタ 2号機"),
        ("usage-003", "tool-001", "山田 一郎", "2026-02-27 10:00:00", None),
        ("usage-004", "tool-004", "鈴木 花子", "2026-02-24 08:45:00", "NC旋盤 A号機"),
        ("usage-005", "tool-004", "田中 太郎", "2026-02-26 16:20:00", "NC旋盤 A号機"),
        ("usage-006", "tool-008", "佐藤 次郎", "2026-02-27 11:30:00", "5軸加工機"),
        ("usage-007", "tool-014", "伊藤 三郎", "2026-02-28 09:00:00", "微細加工機"),
    ]
    for u in demo_usage:
        conn.execute("""
            INSERT INTO usage_logs (id, tool_id, used_by, used_at, notes)
            VALUES (?,?,?,?,?)
        """, u)

    conn.commit()
    conn.close()

init_db()

# === Models ===
class SharpeningRequest(BaseModel):
    tool_id: str
    requested_by: str
    reason: str
    priority: str = "normal"

class ToolCreate(BaseModel):
    name: str
    tool_type: str
    material: Optional[str] = None
    diameter_mm: Optional[float] = None
    length_mm: Optional[float] = None
    flute_count: Optional[int] = None
    coating: Optional[str] = None
    manufacturer: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[str] = None
    location: Optional[str] = None
    max_resharpening: Optional[int] = 5
    notes: Optional[str] = None

class QuoteResponse(BaseModel):
    estimated_price: int
    estimated_delivery: str
    quote_notes: Optional[str] = None

class UsageLog(BaseModel):
    used_by: str
    notes: Optional[str] = None
    used_at: Optional[datetime] = None

# === Tools API ===
@app.get("/api/tools")
def list_tools(status: Optional[str] = None):
    conn = get_db()
    query = "SELECT * FROM tools"
    if status:
        query += " WHERE status=?"
        rows = conn.execute(query + " ORDER BY name", (status,)).fetchall()
    else:
        rows = conn.execute(query + " ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/tools/{tool_id}")
def get_tool(tool_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM tools WHERE id=?", (tool_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="工具が見つかりません")
    tool = dict(row)

    # 再研磨履歴
    reqs = conn.execute("""
        SELECT * FROM sharpening_requests
        WHERE tool_id=? ORDER BY requested_at DESC LIMIT 5
    """, (tool_id,)).fetchall()
    tool["sharpening_history"] = [dict(r) for r in reqs]

    # 使用履歴
    usage = conn.execute("""
        SELECT * FROM usage_logs
        WHERE tool_id=? ORDER BY used_at DESC LIMIT 10
    """, (tool_id,)).fetchall()
    tool["usage_history"] = [dict(u) for u in usage]

    conn.close()
    return tool

@app.post("/api/tools")
def create_tool(tool: ToolCreate):
    tool_id = "tool-" + str(uuid.uuid4())[:6]
    conn = get_db()
    conn.execute("""
        INSERT INTO tools (id, name, tool_type, material, diameter_mm, length_mm, flute_count, coating, manufacturer, serial_number, purchase_date, location, max_resharpening, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (tool_id, tool.name, tool.tool_type, tool.material, tool.diameter_mm, tool.length_mm, tool.flute_count, tool.coating, tool.manufacturer, tool.serial_number, tool.purchase_date, tool.location, tool.max_resharpening, tool.notes))
    conn.commit()
    conn.close()
    return {"id": tool_id, "message": "工具を登録しました"}

@app.get("/api/tools/{tool_id}/qr")
def generate_qr(tool_id: str):
    conn = get_db()
    row = conn.execute("SELECT id FROM tools WHERE id=?", (tool_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="工具が見つかりません")
    conn.close()
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(f"TOOL:{tool_id}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    return {"qr_code": f"data:image/png;base64,{b64}", "tool_id": tool_id}

# === Usage Log API ===
@app.get("/api/usage-logs")
def list_all_usage_logs(limit: int = 100):
    conn = get_db()
    rows = conn.execute("""
        SELECT u.*, t.name as tool_name, t.tool_type 
        FROM usage_logs u
        JOIN tools t ON u.tool_id = t.id
        ORDER BY u.used_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/tools/{tool_id}/usage")
def record_usage(tool_id: str, log: UsageLog):
    conn = get_db()
    tool = conn.execute("SELECT * FROM tools WHERE id=?", (tool_id,)).fetchone()
    if not tool:
        raise HTTPException(status_code=404, detail="工具が見つかりません")

    log_id = "usage-" + str(uuid.uuid4())[:6]
    
    # Use provided used_at or default to current timestamp
    used_at_str = log.used_at.isoformat() if log.used_at else datetime.now().isoformat(sep=' ', timespec='seconds')
    
    conn.execute("""
        INSERT INTO usage_logs (id, tool_id, used_by, used_at, notes)
        VALUES (?,?,?,?,?)
    """, (log_id, tool_id, log.used_by, used_at_str, log.notes))

    # 使用回数をインクリメント
    conn.execute("UPDATE tools SET usage_count = usage_count + 1 WHERE id=?", (tool_id,))
    conn.commit()

    new_count = conn.execute("SELECT usage_count FROM tools WHERE id=?", (tool_id,)).fetchone()[0]
    conn.close()

    return {"id": log_id, "message": "使用を記録しました", "new_usage_count": new_count}

@app.get("/api/tools/{tool_id}/usage-history")
def get_usage_history(tool_id: str, limit: int = 20):
    conn = get_db()
    tool = conn.execute("SELECT id FROM tools WHERE id=?", (tool_id,)).fetchone()
    if not tool:
        raise HTTPException(status_code=404, detail="工具が見つかりません")

    rows = conn.execute("""
        SELECT * FROM usage_logs
        WHERE tool_id=? ORDER BY used_at DESC LIMIT ?
    """, (tool_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# === Sharpening Requests API ===
@app.post("/api/sharpening-requests")
def create_sharpening_request(req: SharpeningRequest):
    conn = get_db()
    tool = conn.execute("SELECT * FROM tools WHERE id=?", (req.tool_id,)).fetchone()
    if not tool:
        raise HTTPException(status_code=404, detail="工具が見つかりません")

    # 再研磨可能回数チェック
    if tool["resharpening_count"] >= tool["max_resharpening"]:
        raise HTTPException(status_code=400, detail="再研磨可能回数の上限に達しています")

    req_id = "req-" + str(uuid.uuid4())[:6]
    conn.execute("""
        INSERT INTO sharpening_requests (id, tool_id, requested_by, reason, priority)
        VALUES (?,?,?,?,?)
    """, (req_id, req.tool_id, req.requested_by, req.reason, req.priority))
    conn.execute("UPDATE tools SET status='sharpening_needed' WHERE id=?", (req.tool_id,))
    conn.commit()
    conn.close()
    return {"id": req_id, "message": "再研磨依頼を受け付けました"}

@app.get("/api/sharpening-requests")
def list_sharpening_requests(status: Optional[str] = None):
    conn = get_db()
    query = """
        SELECT sr.*, t.name as tool_name, t.tool_type, t.material, t.manufacturer,
               t.resharpening_count, t.max_resharpening
        FROM sharpening_requests sr
        JOIN tools t ON sr.tool_id=t.id
    """
    if status:
        query += " WHERE sr.status=?"
        rows = conn.execute(query + " ORDER BY sr.requested_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute(query + " ORDER BY sr.requested_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/sharpening-requests/{req_id}")
def get_sharpening_request(req_id: str):
    conn = get_db()
    row = conn.execute("""
        SELECT sr.*, t.name as tool_name, t.tool_type, t.material, t.manufacturer,
               t.resharpening_count, t.max_resharpening, t.serial_number
        FROM sharpening_requests sr
        JOIN tools t ON sr.tool_id=t.id
        WHERE sr.id=?
    """, (req_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="依頼が見つかりません")
    conn.close()
    return dict(row)

@app.patch("/api/sharpening-requests/{req_id}/quote")
def quote_sharpening(req_id: str, quote: QuoteResponse):
    conn = get_db()
    req = conn.execute("SELECT * FROM sharpening_requests WHERE id=?", (req_id,)).fetchone()
    if not req:
        raise HTTPException(status_code=404, detail="依頼が見つかりません")

    conn.execute("""
        UPDATE sharpening_requests
        SET status='quoted', estimated_price=?, estimated_delivery=?, quote_notes=?, quoted_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (quote.estimated_price, quote.estimated_delivery, quote.quote_notes, req_id))
    conn.commit()
    conn.close()
    return {"message": "見積を送信しました"}

@app.patch("/api/sharpening-requests/{req_id}/complete")
def complete_sharpening(req_id: str):
    conn = get_db()
    req = conn.execute("SELECT * FROM sharpening_requests WHERE id=?", (req_id,)).fetchone()
    if not req:
        raise HTTPException(status_code=404, detail="依頼が見つかりません")

    conn.execute("""
        UPDATE sharpening_requests
        SET status='completed', completed_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (req_id,))
    conn.execute("""
        UPDATE tools
        SET status='active', usage_count=0, resharpening_count=resharpening_count+1
        WHERE id=?
    """, (req["tool_id"],))
    conn.commit()
    conn.close()
    return {"message": "再研磨完了"}

# === Stats API ===
@app.get("/api/stats")
def get_stats():
    conn = get_db()
    result = {
        "total_tools": conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0],
        "active_tools": conn.execute("SELECT COUNT(*) FROM tools WHERE status='active'").fetchone()[0],
        "needs_sharpening": conn.execute("SELECT COUNT(*) FROM tools WHERE status='sharpening_needed'").fetchone()[0],
        "pending_requests": conn.execute("SELECT COUNT(*) FROM sharpening_requests WHERE status='pending'").fetchone()[0],
        "quoted_requests": conn.execute("SELECT COUNT(*) FROM sharpening_requests WHERE status='quoted'").fetchone()[0],
    }
    conn.close()
    return result

@app.get("/api/admin/stats")
def get_admin_stats():
    conn = get_db()
    result = {
        "pending_requests": conn.execute("SELECT COUNT(*) FROM sharpening_requests WHERE status='pending'").fetchone()[0],
        "quoted_requests": conn.execute("SELECT COUNT(*) FROM sharpening_requests WHERE status='quoted'").fetchone()[0],
        "completed_this_month": conn.execute("""
            SELECT COUNT(*) FROM sharpening_requests
            WHERE status='completed' AND completed_at >= date('now', 'start of month')
        """).fetchone()[0],
        "total_tools_managed": conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0],
    }
    conn.close()
    return result
