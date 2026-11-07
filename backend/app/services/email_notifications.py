"""Gateway notifications from committed audit/billing events. No AI or new daemon.

A receipt is claimed before provider submission. An interrupted/failed submission
is never automatically resent, because SMTP acceptance can be ambiguous.
"""
from datetime import datetime,timedelta,timezone
from email.message import EmailMessage
from hashlib import sha256
from sqlalchemy import inspect,select,text,table,column,exists,cast,String,literal,func
from sqlalchemy.exc import IntegrityError
from ..models import User,AccountAudit,Subscription
from . import email_service_policies as policies,email_verification,email_delivery

AUDIT_SERVICES={
 'account.email_verified':'welcome_email','account.registered_active':'welcome_email',
 'session.login':'login_security','password.changed':'password_changed','password.reset':'password_changed',
 'account.email_changed':'email_changed','account.suspended':'account_suspension',
 'account.admin_suspended':'account_suspension','account.admin_archived':'account_suspension',
 'billing.payment_confirmed':'payment_receipt','billing.payment_rejected':'payment_failed',
 'security.failed_login':'unusual_activity',
}
MANUAL=frozenset({'system_updates','service_incident','backup_status'})
SCHEDULED=frozenset({'subscription_expiry','renewal_reminder','trial_expiring'})
SUPPORTED=frozenset(AUDIT_SERVICES.values())|MANUAL|SCHEDULED|{'support_received'}
TITLES={
 'support_received':('New support email','رسالة دعم جديدة'),
 'welcome_email':('Welcome to OpenCode Gateway','مرحبًا بك في OpenCode Gateway'),
 'login_security':('A new sign-in to your account','تسجيل دخول جديد لحسابك'),
 'password_changed':('Your password was changed','تغيّرت كلمة المرور'),
 'email_changed':('Your account email was updated','حُدّث بريد حسابك'),
 'account_suspension':('Your account access was suspended','تم إيقاف وصول حسابك'),
 'payment_receipt':('Your payment was confirmed','تم تأكيد دفعتك'),
 'payment_failed':('Your payment was rejected','لم تُقبل دفعتك'),
 'unusual_activity':('An unsuccessful sign-in attempt','محاولة دخول غير ناجحة'),
 'subscription_expiry':('Your subscription has expired','انتهى اشتراكك'),
 'renewal_reminder':('Your subscription expires soon','اقترب انتهاء اشتراكك'),
 'trial_expiring':('Your trial expires soon','اقترب انتهاء تجربتك'),
 'system_updates':('Platform update','تحديث المنصة'),
 'service_incident':('Service incident report','بلاغ حالة الخدمة'),
 'backup_status':('Administrator backup status report','تقرير المدير عن النسخ الاحتياطي'),
}

def ready(db):return inspect(db.connection()).has_table('email_notification_receipts')

def enabled_since(db,service):
    row=db.execute(text('SELECT enabled,updated_at FROM email_service_policies WHERE service_id=:s'),{'s':service}).first()
    if not row or not row[0]:return None
    value=row[1]
    if isinstance(value,str):value=datetime.fromisoformat(value)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def deliver(db,user,service,key,detail=''):
    if service not in SUPPORTED or not policies.enabled(db,service,False):return 'disabled'
    if not ready(db):return 'migration_required'
    config=email_verification.smtp_settings(db)
    if not email_delivery.ready(config):return 'sender_unavailable'
    event_key=sha256((service+':'+str(user.id)+':'+str(key)).encode()).hexdigest()
    try:
        db.execute(text('INSERT INTO email_notification_receipts(event_key,source_key,service_id,user_id,state) VALUES (:k,:source,:s,:u,:state)'),{'k':event_key,'source':str(key),'s':service,'u':user.id.hex,'state':'submitting'})
        db.commit()
    except IntegrityError:
        db.rollback();return 'already_recorded'
    subject=TITLES[service][1 if user.preferred_language=='ar' else 0]
    message=EmailMessage();message['To']=user.email;message['From']=config['smtp_from'];message['Subject']=subject
    message.set_content(subject+'\n\n'+detail[:2000]+'\n\nOpenCode Gateway\nThis is an account notification; no password, token or project content is included.')
    try:
        email_delivery.send(config,message);state='accepted'
    except Exception:
        # Sanitized receipt only; no vendor response, secret or recipient in logs.
        state='uncertain'
    db.execute(text('UPDATE email_notification_receipts SET state=:s WHERE event_key=:k'),{'k':event_key,'s':state});db.commit()
    return state

def sweep():
    from ..database import SessionLocal
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        if not ready(db):return
        # Only events occurring after this particular notification was enabled.
        for service in set(AUDIT_SERVICES.values()):
            since=enabled_since(db,service)
            if since is None:continue
            actions=[action for action,value in AUDIT_SERVICES.items() if value==service]
            receipts=table('email_notification_receipts',column('source_key'),column('service_id'))
            done=exists(select(1).select_from(receipts).where(receipts.c.source_key==literal('audit:')+cast(AccountAudit.id,String),receipts.c.service_id==service))
            events=db.scalars(select(AccountAudit).where(~done,AccountAudit.action.in_(actions),AccountAudit.created_at>=max(since,now-timedelta(days=1))).order_by(AccountAudit.id).limit(100))
            for event in list(events):
                user=db.get(User,event.subject_id) if event.subject_id else None
                if user:
                    if service=='unusual_activity':
                        since_attempt=_aware(event.created_at)-timedelta(hours=1)
                        count=db.scalar(select(func.count()).select_from(AccountAudit).where(AccountAudit.subject_id==user.id,AccountAudit.action=='security.failed_login',AccountAudit.created_at>=since_attempt,AccountAudit.created_at<=event.created_at))
                        if count<5:continue
                        key='failed-login-hour:'+_aware(event.created_at).strftime('%Y%m%d%H')
                    else:key='audit:'+str(event.id)
                    deliver(db,user,service,key)

        poll_support(db)
        for service in SCHEDULED:
            if not policies.enabled(db,service,False):continue
            if service=='trial_expiring':
                users=db.scalars(select(User).where(User.role=='customer',User.status=='active',User.trial_ends_at>now,User.trial_ends_at<=now+timedelta(days=3)).limit(100))
                for user in list(users):
                    sub=db.scalar(select(Subscription).where(Subscription.user_id==user.id))
                    if sub and sub.plan_id and sub.status in {'active','cancelled'} and sub.current_period_end and _aware(sub.current_period_end)>now:continue
                    deliver(db,user,service,str(user.trial_ends_at),'Trial end: '+str(user.trial_ends_at))
            else:
                query=select(Subscription).where(Subscription.plan_id.is_not(None),Subscription.status.in_(['active','expired','cancelled']))
                if service=='renewal_reminder':query=query.where(Subscription.current_period_end>now,Subscription.current_period_end<=now+timedelta(days=7))
                else:query=query.where(Subscription.current_period_end<=now,Subscription.current_period_end>=now-timedelta(days=1))
                for sub in list(db.scalars(query.limit(100))):
                    user=db.get(User,sub.user_id)
                    if user:deliver(db,user,service,str(sub.current_period_end),'Subscription end: '+str(sub.current_period_end))

def _aware(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def poll_support(db):
    """Read inbox metadata only; no email bodies, no inferred reply status."""
    import uuid
    from . import admin_email_config
    since=enabled_since(db,'support_received')
    if since is None:return
    key=(admin_email_config.read(db) or {}).get('inbox_api_key')
    if not key:return
    try:payload=email_delivery.read_resend('/emails/receiving?limit=50',key)
    except Exception:return  # A key's presence never proves Full access permission.
    recipients=list(db.scalars(select(User).where(User.role.in_(['admin','owner']),User.status=='active')))
    for item in payload.get('data',[]):
        addresses=item.get('to') or []
        if not isinstance(addresses,list) or not any(str(address).lower()=='support@opencode-gateway.codes' for address in addresses):continue
        try:
            identifier=str(uuid.UUID(str(item.get('id'))))
            created=_aware(datetime.fromisoformat(str(item.get('created_at')).replace('Z','+00:00')))
        except (ValueError,TypeError):continue
        if created<since:continue
        for user in recipients:deliver(db,user,'support_received','support:'+identifier)
