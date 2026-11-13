"""Server-only PayPal Orders bridge. No card details or tokens reach Gateway UI."""
from decimal import Decimal,InvalidOperation
from urllib.parse import urlsplit
import re,json,logging
import httpx
from fastapi import HTTPException
from ..config import settings

def admin_config(db=None):
    """Read encrypted Admin PayPal profile without exposing client secrets.

    Existing environment-based PayPal installs keep working as a fallback.
    A partially configured dynamic profile stays disabled rather than
    accidentally mixing its credentials with legacy environment secrets.
    """
    if db is not None:
        from . import payment_provider_profiles as profiles
        if profiles.schema_ready(db):
            row=profiles._one(db,'paypal')
            if row is not None and row['connection_mode']=='api':
                fields={item['key']:item['value'] for item in profiles._decode(row['encrypted_fields'])}
                if all(fields.get(key) for key in ('client_id','client_secret','merchant_id')):
                    return {'environment':'sandbox' if row['environment']=='test' else 'live',
                            'client_id':fields['client_id'],
                            'client_secret':fields['client_secret'],
                            'merchant_id':fields['merchant_id'],
                            'source':'admin_dynamic'}
    return {'environment':settings.paypal_environment,
            'client_id':settings.paypal_client_id or '',
            'client_secret':settings.paypal_client_secret or '',
            'merchant_id':settings.paypal_merchant_id or '',
            'source':'existing_environment'}


def configured(db=None):
    cfg=admin_config(db)
    return bool(cfg['client_id'] and cfg['client_secret'] and cfg['merchant_id'])


def request(method,path,body=None,request_id=None,negative=False,db=None):
    cfg=admin_config(db)
    if not configured(db):raise HTTPException(503,'PayPal provider is not connected. Configure the merchant account in Admin.')
    base='https://api-m.sandbox.paypal.com' if cfg['environment']=='sandbox' else 'https://api-m.paypal.com'
    try:
        with httpx.Client(timeout=25,follow_redirects=False,trust_env=False) as client:
            token=client.post(base+'/v1/oauth2/token',auth=(cfg['client_id'],cfg['client_secret']),data={'grant_type':'client_credentials'})
            if token.status_code!=200:raise HTTPException(503,'PayPal merchant authentication failed')
            headers={'Authorization':'Bearer '+token.json()['access_token'],'Prefer':'return=representation'}
            if request_id:headers['PayPal-Request-Id']=request_id
            if negative and cfg['environment']=='sandbox' and settings.paypal_sandbox_decline:
                headers['PayPal-Mock-Response']=json.dumps({'mock_application_codes':'INSTRUMENT_DECLINED'})
            response=client.request(method,base+path,json=body,headers=headers)
            payload=response.json()
    except (httpx.HTTPError,ValueError,KeyError):raise HTTPException(502,'PayPal is unavailable. No payment has been confirmed; retry or contact support.')
    if response.status_code>=400:
        issues={d.get('issue') for d in payload.get('details',[]) if isinstance(d,dict)}
        if 'INSTRUMENT_DECLINED' in issues:raise HTTPException(402,'PayPal declined the payment method. Choose another funding source; your subscription has not been activated.')
        safe_issues=sorted(issue for issue in issues if isinstance(issue,str) and re.fullmatch(r'[A-Z_]{1,80}',issue))
        debug_id=payload.get('debug_id','')
        if not isinstance(debug_id,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}',debug_id):debug_id=''
        logging.getLogger(__name__).warning('PayPal request rejected: status=%s issues=%s reference=%s',response.status_code,','.join(safe_issues),debug_id)
        if issues & {'PAYEE_ACCOUNT_RESTRICTED','PAYEE_ACCOUNT_NOT_VERIFIED','PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING','PAYEE_ACCOUNT_INVALID'}:
            raise HTTPException(503,'The PayPal merchant account cannot receive this payment. Administration must verify merchant eligibility. No subscription was activated.')
        suffix=(' Reference: '+debug_id) if debug_id else ''
        raise HTTPException(502,'PayPal could not complete the payment. Your subscription has not been activated.'+suffix)
    return payload

def create_order(row,db=None):
    cfg=admin_config(db)
    base=settings.public_base_url.rstrip('/')
    parsed=urlsplit(base)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or (parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in {'127.0.0.1','localhost','::1'})):
        raise HTTPException(503,'Configure a valid public Gateway URL for PayPal checkout')
    value=f'{row.amount_cents/100:.2f}'
    body={'intent':'CAPTURE','purchase_units':[{'custom_id':str(row.id),'description':row.plan_name,'payee':{'merchant_id':cfg['merchant_id']},'amount':{'currency_code':row.currency,'value':value}}],
          'payment_source':{'paypal':{'experience_context':{'shipping_preference':'NO_SHIPPING','landing_page':'BILLING','user_action':'PAY_NOW','return_url':base+'/?payment_return='+str(row.id),'cancel_url':base+'/?payment_cancel='+str(row.id)}}}}
    return request('POST','/v2/checkout/orders',body,'create-'+str(row.id),db=db)

def approval_url(payload,db=None):
    url=next((link.get('href','') for link in payload.get('links',[]) if link.get('rel') in {'payer-action','approve'}),'')
    parsed=urlsplit(url)
    allowed='www.sandbox.paypal.com' if admin_config(db)['environment']=='sandbox' else 'www.paypal.com'
    if parsed.scheme!='https' or parsed.hostname!=allowed or parsed.username or parsed.password or parsed.port not in (None,443):
        raise HTTPException(502,'PayPal returned an invalid approval URL')
    return url

def show_order(row,db=None):
    if not row.provider_order_id or not re.fullmatch(r'[A-Z0-9]{5,100}',row.provider_order_id):raise HTTPException(409,'No valid PayPal order exists')
    if row.provider_environment!=admin_config(db)['environment']:raise HTTPException(409,'PayPal environment changed; this payment must be reconciled in its original environment')
    return request('GET','/v2/checkout/orders/'+row.provider_order_id,db=db)

def capture_order(row,db=None):
    payload=show_order(row,db=db)
    if payload.get('status')=='COMPLETED':return payload
    if payload.get('status')!='APPROVED':raise HTTPException(409,'Approve payment on PayPal before confirming it here')
    return request('POST','/v2/checkout/orders/'+row.provider_order_id+'/capture',{},'capture-'+str(row.id),negative=True,db=db)

def verified_capture(row,payload,db=None):
    try:
        units=payload['purchase_units']
        if payload['id']!=row.provider_order_id or payload['status']!='COMPLETED' or len(units)!=1:raise ValueError()
        unit=units[0];captures=unit['payments']['captures']
        if unit['custom_id']!=str(row.id) or unit['payee']['merchant_id']!=admin_config(db)['merchant_id'] or len(captures)!=1:raise ValueError()
        capture=captures[0];amount=capture['amount']
        if capture['status']!='COMPLETED' or amount['currency_code']!=row.currency or Decimal(amount['value'])!=Decimal(row.amount_cents)/100 or not capture['id']:raise ValueError()
        return capture['id']
    except (KeyError,ValueError,TypeError,InvalidOperation):raise HTTPException(502,'Payment verification failed. No subscription was activated; contact support.')
