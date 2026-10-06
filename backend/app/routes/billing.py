"""Client billing: the authenticated customer's own subscription only.

PayPal captures activate only after backend verification. Hosted links and bank
transfers activate after administrative receipt review. Selection never pays.
"""
from datetime import datetime, timezone,timedelta
import uuid
from math import ceil
from fastapi import APIRouter, Depends, HTTPException
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

def ensure_subscription(db, user, commit=True) -> Subscription:
    row = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
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
    row = ensure_subscription(db, user)
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
def invoices(user: User = Depends(require_user)):
    return {"available": False, "message": PAYMENT_MESSAGE, "items": []}

@router.get("/payments")
def payments(user: User = Depends(require_user)):
    return {"available": False, "message": PAYMENT_MESSAGE, "items": []}

class Checkout(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan_id:int=Field(ge=1)
    method_id:uuid.UUID
class PaymentReference(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reference:str=Field(min_length=3,max_length=200)
def order_payload(row):
    return {key:(str(getattr(row,key)) if key in {'id','user_id','method_id'} and getattr(row,key) is not None else getattr(row,key)) for key in ['id','user_id','plan_id','method_id','plan_name','method_label','amount_cents','currency','duration_days','status','payment_reference','provider_environment','created_at','paid_at']}
@router.post('/checkout',status_code=201)
def checkout(data:Checkout,user:User=Depends(require_user),db:Session=Depends(get_db)):
    plan=db.get(Plan,data.plan_id);method=db.get(BillingMethod,data.method_id)
    if not plan or not plan.active: raise HTTPException(422,'Unknown or inactive plan')
    if not method or method.user_id is not None or not method.enabled: raise HTTPException(422,'Payment method is unavailable')
    from .management import method_payload
    details=method_payload(method)
    if details['details'].get('currency')!=plan.currency: raise HTTPException(422,'Payment method currency does not match this plan')
    if details['details'].get('plan_id') not in (None,plan.id):raise HTTPException(422,'Payment link belongs to another plan')
    if plan.price_cents<=0 or plan.duration_days<=0: raise HTTPException(422,'Plan requires valid paid price and duration')
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.user_id==user.id,PaymentOrder.plan_id==plan.id,PaymentOrder.method_id==method.id,PaymentOrder.status.in_(['awaiting_payment','pending_review'])))
    if row is None:
        row=PaymentOrder(user_id=user.id,plan_id=plan.id,method_id=method.id,plan_name=plan.name,method_label=method.label,amount_cents=plan.price_cents,currency=plan.currency,duration_days=plan.duration_days,provider_environment=paypal.settings.paypal_environment if details['details'].get('checkout_mode')=='paypal' else None)
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
@router.put('/orders/{order_id}/reference')
def submit_reference(order_id:uuid.UUID,data:PaymentReference,user:User=Depends(require_user),db:Session=Depends(get_db)):
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id,PaymentOrder.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if row.provider_environment:raise HTTPException(409,'PayPal payments require server capture verification, not a manual reference')
    if row.status!='awaiting_payment':raise HTTPException(409,'This payment order is already under review or completed')
    row.payment_reference=data.reference;row.status='pending_review';db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action='billing.reference_submitted'));db.commit();return order_payload(row)

# Administrative review is a manual receipt check, never a simulated provider webhook.
@router.get('/admin/orders')
def admin_orders(user:User=Depends(require_admin),db:Session=Depends(get_db)):
    return [{**order_payload(row),'email':db.get(User,row.user_id).email} for row in db.scalars(select(PaymentOrder).order_by(PaymentOrder.created_at.desc()).limit(200))]
@router.post('/admin/orders/{order_id}/confirm')
def confirm_payment(order_id:uuid.UUID,data:PaymentReference,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    row=db.scalar(select(PaymentOrder).where(PaymentOrder.id==order_id).with_for_update())
    if not row:raise HTTPException(404,'Payment order not found')
    if row.provider_environment:raise HTTPException(409,'PayPal payments cannot be manually confirmed')
    if row.status=='paid':return order_payload(row)
    if row.status!='pending_review':raise HTTPException(409,'A submitted payment reference is required before review')
    activate_order(db,row,user.id,data.reference)
    db.commit();return order_payload(row)

def activate_order(db,row,actor_id,reference):
    target=db.scalar(select(User).where(User.id==row.user_id).with_for_update());subscription=ensure_subscription(db,target,commit=False)
    current_end=subscription.current_period_end
    if current_end and current_end.tzinfo is None:current_end=current_end.replace(tzinfo=timezone.utc)
    now=datetime.now(timezone.utc);start=max(now,current_end) if subscription.status=='active' and current_end else now
    subscription.plan_id=row.plan_id;subscription.status='active';subscription.started_at=now;subscription.current_period_end=start+timedelta(days=row.duration_days);subscription.cancelled_at=None;subscription.auto_renew=False;target.plan_id=row.plan_id
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
    if row.provider_environment=='sandbox' and not paypal.settings.testing:
        row.status='sandbox_paid';row.payment_reference=capture_id
        db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action='billing.sandbox_payment_verified'))
        db.commit();return order_payload(row)
    activate_order(db,row,None,capture_id)
    db.commit();return order_payload(row)

@router.get('/paypal/status')
def paypal_status(user:User=Depends(require_user)):
    return {'configured':paypal.configured(),'environment':paypal.settings.paypal_environment,'sandbox_decline_test':paypal.settings.paypal_sandbox_decline,'card_checkout':'Provider eligibility determines guest card availability'}
