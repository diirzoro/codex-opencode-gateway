"""Independent Help inbox. Never changes existing email verification or provider configuration."""
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db, engine
from ..models import User
from .dependencies import require_user, require_admin

router = APIRouter(prefix="/api/help", tags=["help"])

def initialize():
    # Additive only: no changes to mail services, users, or payment tables.
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS help_settings (
            key VARCHAR(80) PRIMARY KEY, value TEXT NOT NULL
        )"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS help_tickets (
            id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(64) NOT NULL,
            category VARCHAR(60) NOT NULL, subject VARCHAR(180) NOT NULL,
            status VARCHAR(24) NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS help_messages (
            id VARCHAR(36) PRIMARY KEY, ticket_id VARCHAR(36) NOT NULL,
            author_id VARCHAR(64) NOT NULL, author_role VARCHAR(16) NOT NULL,
            body TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS help_tickets_user_idx ON help_tickets (user_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS help_messages_ticket_idx ON help_messages (ticket_id, created_at)"))

def setting(db, key, default):
    return db.execute(text("SELECT value FROM help_settings WHERE key=:k"), {"k":key}).scalar_one_or_none() or default

def settings_payload(db):
    return {"enabled": setting(db,"enabled","true")=="true",
            "welcome":setting(db,"welcome","مرحبًا! كيف يمكننا مساعدتك؟"),
            "categories":[x.strip() for x in setting(db,"categories","شكوى,اقتراح,مشكلة تقنية,استفسار عام").split(",") if x.strip()][:20]}

def list_tickets(db, where="", args=None):
    return [dict(r) for r in db.execute(text("""SELECT t.id,t.category,t.subject,t.status,t.created_at,t.updated_at
        FROM help_tickets t """+where+" ORDER BY t.updated_at DESC LIMIT 100"), args or {}).mappings()]

def messages(db, tid):
    return [dict(r) for r in db.execute(text("""SELECT author_role,body,created_at FROM help_messages
        WHERE ticket_id=:tid ORDER BY created_at,id LIMIT 200"""),{"tid":tid}).mappings()]

@router.get("/settings")
def get_settings(db:Session=Depends(get_db),user:User=Depends(require_user)):
    return settings_payload(db)

class SettingsUpdate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    enabled:bool
    welcome:str=Field(min_length=1,max_length=500)
    categories:list[str]=Field(min_length=1,max_length=20)

@router.put("/admin/settings")
def update_settings(data:SettingsUpdate,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    categories=[s.strip() for s in data.categories]
    if any(not s or len(s)>60 for s in categories):raise HTTPException(422,"Invalid category")
    for key,value in {"enabled":str(data.enabled).lower(),"welcome":data.welcome.strip(),
                      "categories":",".join(categories)}.items():
        db.execute(text("""INSERT INTO help_settings(key,value) VALUES(:k,:v)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value"""),{"k":key,"v":value})
    db.commit()
    return settings_payload(db)

class TicketIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    category:str=Field(min_length=1,max_length=60)
    subject:str=Field(min_length=3,max_length=180)
    message:str=Field(min_length=3,max_length=5000)

@router.post("/tickets",status_code=201)
def new_ticket(data:TicketIn,db:Session=Depends(get_db),user:User=Depends(require_user)):
    settings=settings_payload(db)
    if not settings["enabled"]:raise HTTPException(403,"Help is currently disabled")
    if data.category not in settings["categories"]:raise HTTPException(422,"Unknown category")
    tid=str(uuid4());mid=str(uuid4())
    db.execute(text("""INSERT INTO help_tickets(id,user_id,category,subject)
        VALUES(:id,:u,:c,:s)"""),{"id":tid,"u":str(user.id),"c":data.category,"s":data.subject.strip()})
    db.execute(text("""INSERT INTO help_messages(id,ticket_id,author_id,author_role,body)
        VALUES(:id,:t,:u,'customer',:b)"""),{"id":mid,"t":tid,"u":str(user.id),"b":data.message.strip()})
    db.commit()
    return {"id":tid,"status":"open"}

@router.get("/tickets")
def my_tickets(db:Session=Depends(get_db),user:User=Depends(require_user)):
    return {"items":list_tickets(db,"WHERE t.user_id=:u",{"u":str(user.id)})}

@router.get("/tickets/{ticket_id}")
def ticket_detail(ticket_id:str,db:Session=Depends(get_db),user:User=Depends(require_user)):
    row=db.execute(text("SELECT * FROM help_tickets WHERE id=:id"),{"id":ticket_id}).mappings().first()
    if not row or (str(row["user_id"])!=str(user.id) and user.role not in ("owner","admin","support")):
        raise HTTPException(404,"Ticket not found")
    return {"ticket":dict(row),"messages":messages(db,ticket_id)}

class ReplyIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    message:str=Field(min_length=1,max_length=5000)

@router.post("/tickets/{ticket_id}/messages")
def reply(ticket_id:str,data:ReplyIn,db:Session=Depends(get_db),user:User=Depends(require_user)):
    row=db.execute(text("SELECT user_id,status FROM help_tickets WHERE id=:id"),{"id":ticket_id}).first()
    if not row or (str(row[0])!=str(user.id) and user.role not in ("owner","admin","support")):
        raise HTTPException(404,"Ticket not found")
    if row[1]=="closed":raise HTTPException(409,"Ticket closed")
    role="agent" if user.role in ("owner","admin","support") else "customer"
    db.execute(text("""INSERT INTO help_messages(id,ticket_id,author_id,author_role,body)
        VALUES(:id,:t,:u,:r,:b)"""),{"id":str(uuid4()),"t":ticket_id,"u":str(user.id),"r":role,"b":data.message.strip()})
    db.execute(text("UPDATE help_tickets SET updated_at=CURRENT_TIMESTAMP WHERE id=:id"),{"id":ticket_id})
    db.commit()
    return {"ok":True}

@router.get("/admin/tickets")
def admin_tickets(db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    return {"items":list_tickets(db)}

class StatusIn(BaseModel):
    status:str=Field(pattern="^(open|pending|resolved|closed)$")

@router.patch("/admin/tickets/{ticket_id}/status")
def change_status(ticket_id:str,data:StatusIn,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    result=db.execute(text("""UPDATE help_tickets SET status=:status,updated_at=CURRENT_TIMESTAMP
        WHERE id=:id"""),{"id":ticket_id,"status":data.status})
    if not result.rowcount:raise HTTPException(404,"Ticket not found")
    db.commit()
    return {"ok":True}
