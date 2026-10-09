"""Client billing: the authenticated customer's own subscription only.

PayPal captures activate only after backend verification. Hosted links and bank
transfers activate after administrative receipt review. Selection never pays.
"""
from datetime import datetime, timezone,timedelta
import uuid
from math import ceil
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Plan, Subscription, User, PaymentOrder,BillingMethod,AccountAudit
from .dependencies import require_user,require_admin,access_payload
from ..services import paypal

router = APIRouter(prefix="/api/billing", tags=["billing"])
PAYMENT_MESSAGE = "Payment integration not available yet"

class SelectPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: int = Field(ge=1)

def ensure_subscription(db, user, commit=True, *, lock=False) -> Subscription:
    query = select(Subscription).where(Subscription.user_id == user.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        row = Subscription(user_id=user.id, status="trial", plan_id=user.plan_id, started_at=user.trial_started_at, current_period_end=user.trial_ends_at)
        db.add(row)
        if commit: db.commit(); db.refresh(row)
        else: db.flush()
    return row

def plan_payload(plan):
    if plan is None:
        return None
    return {"id": plan.id, "code": plan.code, "name": plan.name, "price_cents": plan.price_cents, "currency": plan.currency, "duration_days": plan.duration_days}

def subscription_payload(db, user) -> dict:
    row = ensure_subscription(db, user)
    now = datetime.now(timezone.utc)
    end = user.trial_ends_at
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    remaining = max(0, ceil((end - now).total_seconds() / 86400)) if end else 0
    plans = [plan_payload(p) for p in db.scalars(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order, Plan.id))]
    return {
        "plan": plan_payload(user.plan),
        "selected_plan": plan_payload(db.get(Plan, row.plan_id)) if row.plan_id else None,
        "trial": {"started_at": user.trial_started_at, "ends_at": user.trial_ends_at, "remaining_days": remaining, "active": remaining > 0},
        "subscription": {"status": row.status, "started_at": row.started_at, "current_period_end": row.current_period_end, "cancelled_at": row.cancelled_at, "auto_renew": bool(row.auto_renew)},
        "plans": plans,
        "payment": {"available": bool(db.scalar(select(BillingMethod.id).where(BillingMethod.user_id.is_(None),BillingMethod.enabled.is_(True)).limit(1))), "message": "Choose checkout; activation requires verified payment" if db.scalar(select(BillingMethod.id).where(BillingMethod.user_id.is_(None),BillingMethod.enabled.is_(True)).limit(1)) else PAYMENT_MESSAGE},
        "access": access_payload(db,user),
    }

@router.get("/subscription")
def get_subscription(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return subscription_payload(db, user)

@router.post("/subscription/select")
def select_plan(data: SelectPlan, user: User = Depends(require_user), db: Session = Depends(get_db)):
    plan = db.get(Plan, data.plan_id)
    if plan is None or not plan.active:
        raise HTTPException(422, "Unknown or inactive plan")
    # Choosing a renewal must not erase already purchased access. Checkout's
    # PaymentOrder records the purchased plan; activation changes the paid plan.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = ensure_subscription(db, user, commit=False, lock=True)
    end = row.current_period_end
    if end and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    paid_period = row.plan_id and end and row.status in {"active", "expired", "cancelled", "pending_payment"}
    if not paid_period:
        row.plan_id = plan.id
        row.status = "pending_payment"
        row.current_period_end = None
        row.cancelled_at = None
        row.auto_renew = False
    db.commit()
    payload = subscription_payload(db, user)
    payload["message"] = f"Plan selected: {plan.name}. Complete checkout; this selection does not activate access."
    return payload

@router.post("/subscription/cancel")
def cancel_subscription(user: User = Depends(require_user), db: Session = Depends(get_db)):
    row = ensure_subscription(db, user)
    if row.status == "cancelled":
        return subscription_payload(db, user)
    row.status = "cancelled"
    row.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    return subscription_payload(db, user)

@router.post("/subscription/reactivate")
def reactivate_subscription(user: User = Depends(require_user), db: Session = Depends(get_db)):
    row = ensure_subscription(db, user)
    if row.status in {"cancelled", "expired"}:
        row.status = "pending_payment" if row.plan_id else "trial"
        row.cancelled_at = None
        db.commit()
    return subscription_payload(db, user)

@router.post("/subscription/renew")
def renew_subscription(user: User = Depends(require_user), db: Session = Depends(get_db)):
    ensure_subscription(db, user)
    raise HTTPException(503, PAYMENT_MESSAGE)

@router.get("/invoices")
def invoices(user: User = Depends(require_user), db: Session = Depends(get_db)):
    # These are verified payment records, not fabricated tax invoices.
    rows = db.scalars(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id, PaymentOrder.status == "paid")
        .order_by(PaymentOrder.paid_at.desc())
    )
    return {
        "available": True,
        "items": [order_payload(row) for row in rows],
        "message": "Verified payment records. Formal tax invoices are not issued by this service.",
    }

@router.get("/payments")
def payments(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id)
        .order_by(PaymentOrder.created_at.desc())
    )
    return {"available": True, "items": [order_payload(row) for row in rows]}

class Checkout(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    plan_id:int=Field(ge=1)
    method_id:uuid.UUID
    billing_note:str=Field(default='',max_length=500)
    payer_name:str=Field(default='',max_length=150)
    payer_email:str=Field(default='',max_length=254)
    payer_country:str=Field(default='',max_length=80)
class PaymentReference(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reference:str=Field(min_length=3,max_length=200)
    sender_name:str=Field(min_length=2,max_length=150)
    sender_email:str=Field(min_length=5,max_length=254)
    sender_bank:str=Field(min_length=2,max_length=150)
    sender_account:str=Field(min_length=4,max_length=200)
    transfer_date:str=Field(min_length=10,max_length=10,pattern=r'^\d{4}-\d{2}-\d{2}$')
    amount_sent_cents:int=Field(ge=1,le=1000000000)
class RejectRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason:str=Field(min_length=3,max_length=500)
RECEIPT_EXTENSIONS={'.png':{'image/png'},'.jpg':{'image/jpeg'},'.jpeg':{'image/jpeg'},'.webp':{'image/webp'},'.pdf':{'application/pdf'}}
RECEIPT_MAX_BYTES=5*1024*1024
def receipts_root():
    from pathlib import Path
    from ..config import settings
    root=Path(settings.workspace_root).resolve().parent/'receipts'
    root.mkdir(parents=True,exist_ok=True)
    return root
def order_payload(row):
    data={key:(str(getattr(row,key)) if key in {'id','user_id','method_id'} and getattr(row,key) is not None else getattr(row,key)) for key in ['id','user_id','plan_id','method_id','plan_name','method_label','amount_cents','currency','duration_days','status','payment_reference','provider_order_id','provider_capture_id','provider_environment','billing_note','sender_name','sender_email','sender_bank','sender_account','payer_name','payer_email','payer_country','transfer_date','amount_sent_cents','reject_reason','created_at','paid_at']}
    data['has_receipt']=bool(row.receipt_path)
    return data
@router.post('/checkout',status_code=201)
def checkout(data:Checkout,user:User=Depends(require_user),db:Session=Depends(get_db)):
    plan=db.get(Plan,data.plan_id);method=db.get(BillingMethod,data.method_id)
    if not plan or not plan.active: raise HTTPException(422,'Unknown or inactive plan')
    if not method or method.user_id is not None or not method.enabled: raise HTTPException(422,'Payment method is unavailable')
    from .management import method_payload
    details=method_payload(method)
    if details['details'].get('checkout_mode')=='link' and (not details['details'].get('payment_url') or not details['details'].get('plan_id')):
        raise HTTPException(503,'This payment method needs its hosted checkout link and matching plan configured by administration. No payment was made.')
    if details['details'].get('currency')!=plan.currency: raise HTTPException(422,'Payment method currency does not match this plan')
    if details['details'].get('plan_id') not in (None,plan.id):raise HTTPException(422,'Payment link belongs to another plan')
    allowed_countries=[c.upper() for c in (details['details'].get('available_country_codes') or [])]
    user_code=(user.country.code.upper() if getattr(user,'country',None) and user.country.code else None)
    if allowed_countries and (not user_code or user_code not in allowed_countries): raise HTTPException(422,'This payment method is not available for your country')
    if details['details'].get('checkout_mode')=='link':
        host=(__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(details['details'].get('payment_url') or '').hostname or '').lower()
        if not details['details'].get('payment_url') or host=='example.com' or host.endswith(('.invalid','.test','.example','.local','.localhost')):
            raise HTTPException(503,'The payment provider for this method is not connected. Administration must configure a real processor checkout link. No payment was made.')
    if details['details'].get('checkout_mode')=='paypal' and not paypal.configured():
        raise HTTPException(503,'PayPal provider is not connected. Ask administration to configure the merchant account.')
    if plan.price_cents<=0 or plan.duration_days<=0: raise HTTPException(422,'Plan requires valid paid price and duration')
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.user_id==user.id,PaymentOrder.plan_id==plan.id,PaymentOrder.method_id==method.id,PaymentOrder.status.in_(['awaiting_payment','pending_review'])))
    if row is None:
        row=PaymentOrder(user_id=user.id,plan_id=plan.id,method_id=method.id,plan_name=plan.name,method_label=method.label,amount_cents=plan.price_cents,currency=plan.currency,duration_days=plan.duration_days,provider_environment=paypal.settings.paypal_environment if details['details'].get('checkout_mode')=='paypal' else None,billing_note=data.billing_note or None,payer_name=data.payer_name or None,payer_email=data.payer_email or None,payer_country=data.payer_country or None)
        db.add(row);db.commit();db.refresh(row)
    if details['details'].get('checkout_mode')=='paypal':
        row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==row.id).with_for_update())
        if row.provider_order_id:
            payload=paypal.show_order(row)
            if payload.get('status')=='COMPLETED':return {'order':order_payload(row),'method':details,'automatic_processing':True,'approval_url':None,'message':'Payment is awaiting server verification. Confirm it to reconcile.'}
        else:
            payload=paypal.create_order(row)
            provider_id=payload.get('id','')
            import re
            if not re.fullmatch(r'[A-Z0-9]{5,100}',provider_id):raise HTTPException(502,'PayPal returned an invalid order')
            row.provider_order_id=provider_id;row.provider_environment=paypal.settings.paypal_environment
        url=paypal.approval_url(payload);db.commit()
        return {'order':order_payload(row),'method':details,'automatic_processing':True,'approval_url':url,'message':'Approve payment on PayPal, then confirm payment here. Only verified completed captures activate subscriptions.'}
    return {'order':order_payload(row),'method':details,'payment_url':details['details'].get('payment_url') if details['details'].get('checkout_mode')=='link' else None,'automatic_processing':False,'message':'Complete payment, then submit its reference. Administration must verify receipt before activation.'}
@router.get('/orders')
def orders(user:User=Depends(require_user),db:Session=Depends(get_db)):
    return [order_payload(row) for row in db.scalars(select(PaymentOrder).where(PaymentOrder.user_id==user.id).order_by(PaymentOrder.created_at.desc()))]
@router.post('/orders/{order_id}/cancel')
def cancel_order(order_id:uuid.UUID,user:User=Depends(require_user),db:Session=Depends(get_db)):
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id,PaymentOrder.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if row.provider_environment:raise HTTPException(409,'PayPal payments cannot be cancelled from here; use Confirm PayPal payment or contact support')
    if row.status in {'paid','sandbox_paid'}:raise HTTPException(409,'Completed payments cannot be cancelled')
    if row.status in {'rejected','cancelled'}:return order_payload(row)
    row.status='cancelled'
    db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action='billing.payment_cancelled'))
    db.commit();return order_payload(row)

@router.delete('/orders/{order_id}',status_code=204)
def delete_order(order_id:uuid.UUID,user:User=Depends(require_user),db:Session=Depends(get_db)):
    from pathlib import Path
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id,PaymentOrder.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if row.status not in {'failed','cancelled','rejected'}:
        raise HTTPException(409,'Only failed, cancelled or rejected payments can be removed; successful payments are kept as records')
    if row.receipt_path:
        try:Path(row.receipt_path).unlink(missing_ok=True)
        except OSError:pass
        receipt_root=receipts_root()/str(row.id)
        try:
            if receipt_root.exists() and not any(receipt_root.iterdir()): receipt_root.rmdir()
        except OSError:pass
    db.delete(row)
    db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action='billing.payment_removed'))
    db.commit()

@router.put('/orders/{order_id}/reference')
def submit_reference(order_id:uuid.UUID,data:PaymentReference,user:User=Depends(require_user),db:Session=Depends(get_db)):
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id,PaymentOrder.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if row.provider_environment:raise HTTPException(409,'PayPal payments require server capture verification, not a manual reference')
    if row.status!='awaiting_payment':raise HTTPException(409,'This payment order is already under review or completed')
    if not row.receipt_path:raise HTTPException(409,'Upload the transfer receipt before submitting for review')
    row.payment_reference=data.reference;row.sender_name=data.sender_name;row.sender_email=data.sender_email;row.sender_bank=data.sender_bank;row.sender_account=data.sender_account;row.transfer_date=data.transfer_date;row.amount_sent_cents=data.amount_sent_cents
    row.status='pending_review';db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action='billing.reference_submitted'));db.commit();return order_payload(row)
@router.post('/orders/{order_id}/receipt')
def upload_receipt(order_id:uuid.UUID,file:UploadFile=File(...),user:User=Depends(require_user),db:Session=Depends(get_db)):
    from pathlib import Path
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id,PaymentOrder.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if row.provider_environment:raise HTTPException(409,'PayPal payments do not use receipt upload')
    if row.status not in {'awaiting_payment','pending_review'}:raise HTTPException(409,'Receipts cannot be changed after review')
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in RECEIPT_EXTENSIONS:raise HTTPException(422,'Receipt must be a PNG, JPEG, WebP or PDF file')
    if file.content_type not in RECEIPT_EXTENSIONS[suffix]:raise HTTPException(422,'Receipt file type does not match its extension')
    content=file.file.read(RECEIPT_MAX_BYTES+1)
    if len(content)>RECEIPT_MAX_BYTES:raise HTTPException(422,'Receipt must be 5 MB or smaller')
    if not content:raise HTTPException(422,'Receipt file is empty')
    folder=receipts_root()/str(row.id)
    folder.mkdir(parents=True,exist_ok=True)
    for old in folder.iterdir():
        if old.is_file():old.unlink()
    import secrets
    target=folder/(secrets.token_hex(8)+suffix)
    target.write_bytes(content)
    if row.receipt_path and row.receipt_path!=str(target):
        try:Path(row.receipt_path).unlink(missing_ok=True)
        except OSError:pass
    row.receipt_path=str(target)
    db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action='billing.receipt_uploaded'));db.commit();return order_payload(row)
@router.get('/orders/{order_id}/receipt')
def download_receipt(order_id:uuid.UUID,user:User=Depends(require_user),db:Session=Depends(get_db)):
    from pathlib import Path
    from fastapi.responses import FileResponse
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id))
    if not row:raise HTTPException(404,'Payment order not found')
    if row.user_id!=user.id and user.role not in {'admin','owner'}:raise HTTPException(404,'Payment order not found')
    if not row.receipt_path or not Path(row.receipt_path).is_file():raise HTTPException(404,'Receipt not found')
    return FileResponse(row.receipt_path)

# Administrative review is a manual receipt check, never a simulated provider webhook.
@router.get('/admin/orders')
def admin_orders(user:User=Depends(require_admin),db:Session=Depends(get_db)):
    return [{**order_payload(row),'email':db.get(User,row.user_id).email} for row in db.scalars(select(PaymentOrder).order_by(PaymentOrder.created_at.desc()).limit(200))]
class AdminConfirm(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reference:str=Field(min_length=3,max_length=200)
@router.post('/admin/orders/{order_id}/confirm')
def confirm_payment(order_id:uuid.UUID,data:AdminConfirm,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if row.provider_environment:raise HTTPException(409,'PayPal payments cannot be manually confirmed')
    if row.status=='paid':return order_payload(row)
    if row.status!='pending_review':raise HTTPException(409,'A submitted payment reference is required before review')
    activate_order(db,row,user.id,data.reference)
    db.commit();return order_payload(row)
@router.post('/admin/orders/{order_id}/reject')
def reject_payment(order_id:uuid.UUID,data:RejectRequest,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if row.provider_environment:raise HTTPException(409,'PayPal payments cannot be manually rejected')
    if row.status in {'paid','rejected'}:return order_payload(row)
    if row.status!='pending_review':raise HTTPException(409,'Only payments under review can be rejected')
    row.status='rejected';row.reject_reason=data.reason;row.reviewed_by=user.id
    db.add(AccountAudit(actor_id=user.id,subject_id=row.user_id,action='billing.payment_rejected'))
    db.commit();return order_payload(row)

def activate_order(db,row,actor_id,reference):
    # Keep the verified capture fields before refreshing the locked order.
    db.flush()
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==row.id).with_for_update().execution_options(populate_existing=True))
    if row.status in {'paid','sandbox_paid'}:
        return
    # Serialize different purchases for the same account, including creation
    # of its first subscription, and refresh any previously loaded state.
    target=db.scalar(select(User).where(User.id==row.user_id).with_for_update().execution_options(populate_existing=True))
    subscription=ensure_subscription(db,target,commit=False,lock=True)
    current_end=subscription.current_period_end
    if current_end and current_end.tzinfo is None:current_end=current_end.replace(tzinfo=timezone.utc)
    now=datetime.now(timezone.utc)
    paid_period=subscription.status=='active' and subscription.plan_id and current_end
    renewal_base=max(now,current_end) if paid_period else now
    # duration_days is the purchased Plan.duration_days snapshot on this order.
    # Trial time is never a renewal base, and its timers remain untouched.
    if not paid_period or current_end<=now:
        subscription.started_at=now
    subscription.plan_id=row.plan_id;subscription.status='active';subscription.current_period_end=renewal_base+timedelta(days=row.duration_days);subscription.cancelled_at=None;subscription.auto_renew=False;target.plan_id=row.plan_id
    if target.status=='archived':target.status='active'
    row.status='paid';row.paid_at=now;row.reviewed_by=actor_id;row.confirmation_reference=reference;db.add(AccountAudit(actor_id=actor_id,subject_id=target.id,action='billing.payment_confirmed'))

@router.post('/orders/{order_id}/paypal/capture')
def capture_paypal(order_id:uuid.UUID,user:User=Depends(require_user),db:Session=Depends(get_db)):
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id,PaymentOrder.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if not row.provider_order_id:raise HTTPException(409,'This is not a PayPal API payment')
    if row.status in {'paid','sandbox_paid'}:return order_payload(row)
    payload=paypal.capture_order(row)
    capture_id=paypal.verified_capture(row,payload)
    row.provider_capture_id=capture_id
    if row.provider_environment=='sandbox':
        row.status='sandbox_paid';row.payment_reference=capture_id
        db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action='billing.sandbox_payment_verified'))
        db.commit();return order_payload(row)
    activate_order(db,row,None,capture_id)
    db.commit();return order_payload(row)

@router.get('/paypal/status')
def paypal_status(user:User=Depends(require_user)):
    return {'configured':paypal.configured(),'environment':paypal.settings.paypal_environment,'sandbox_decline_test':paypal.settings.paypal_sandbox_decline,'card_checkout':'Provider eligibility determines guest card availability','client_id':paypal.settings.paypal_client_id if paypal.configured() else None}
