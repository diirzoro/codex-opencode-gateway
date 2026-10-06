"""Server-only PayPal Orders bridge. No card details or tokens reach Gateway UI."""
from decimal import Decimal,InvalidOperation
from urllib.parse import urlsplit
import re,json
import httpx
from fastapi import HTTPException
from ..config import settings

def configured():
    return bool(settings.paypal_client_id and settings.paypal_client_secret and settings.paypal_merchant_id)

def request(method,path,body=None,request_id=None,negative=False):
    if not configured():raise HTTPException(503,'PayPal provider is not connected. Ask administration to configure the merchant account.')
    base='https://api-m.sandbox.paypal.com' if settings.paypal_environment=='sandbox' else 'https://api-m.paypal.com'
    try:
        with httpx.Client(timeout=25,follow_redirects=False,trust_env=False) as client:
            token=client.post(base+'/v1/oauth2/token',auth=(settings.paypal_client_id,settings.paypal_client_secret),data={'grant_type':'client_credentials'})
            if token.status_code!=200:raise HTTPException(503,'PayPal merchant authentication failed')
            headers={'Authorization':'Bearer '+token.json()['access_token'],'Prefer':'return=representation'}
            if request_id:headers['PayPal-Request-Id']=request_id
            if negative and settings.paypal_environment=='sandbox' and settings.paypal_sandbox_decline:
                headers['PayPal-Mock-Response']=json.dumps({'mock_application_codes':'INSTRUMENT_DECLINED'})
            response=client.request(method,base+path,json=body,headers=headers)
            payload=response.json()
    except (httpx.HTTPError,ValueError,KeyError):raise HTTPException(502,'PayPal is unavailable. No payment has been confirmed; retry or contact support.')
    if response.status_code>=400:
        issues={d.get('issue') for d in payload.get('details',[]) if isinstance(d,dict)}
        if 'INSTRUMENT_DECLINED' in issues:raise HTTPException(402,'PayPal declined the payment method. Choose another funding source; your subscription has not been activated.')
        raise HTTPException(502,'PayPal could not complete the payment. Your subscription has not been activated.')
    return payload

def create_order(row):
    base=settings.public_base_url.rstrip('/')
    parsed=urlsplit(base)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or (parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in {'127.0.0.1','localhost','::1'})):
        raise HTTPException(503,'Configure a valid public Gateway URL for PayPal checkout')
    value=f'{row.amount_cents/100:.2f}'
    body={'intent':'CAPTURE','purchase_units':[{'custom_id':str(row.id),'description':row.plan_name,'payee':{'merchant_id':settings.paypal_merchant_id},'amount':{'currency_code':row.currency,'value':value}}],
          'payment_source':{'paypal':{'experience_context':{'shipping_preference':'NO_SHIPPING','landing_page':'BILLING','user_action':'PAY_NOW','return_url':base+'/?payment_return='+str(row.id),'cancel_url':base+'/?payment_cancel='+str(row.id)}}}}
    return request('POST','/v2/checkout/orders',body,'create-'+str(row.id))

def approval_url(payload):
    url=next((link.get('href','') for link in payload.get('links',[]) if link.get('rel') in {'payer-action','approve'}),'')
    parsed=urlsplit(url)
    allowed='www.sandbox.paypal.com' if settings.paypal_environment=='sandbox' else 'www.paypal.com'
    if parsed.scheme!='https' or parsed.hostname!=allowed or parsed.username or parsed.password or parsed.port not in (None,443):
        raise HTTPException(502,'PayPal returned an invalid approval URL')
    return url

def show_order(row):
    if not row.provider_order_id or not re.fullmatch(r'[A-Z0-9]{5,100}',row.provider_order_id):raise HTTPException(409,'No valid PayPal order exists')
    if row.provider_environment!=settings.paypal_environment:raise HTTPException(409,'PayPal environment changed; this payment must be reconciled in its original environment')
    return request('GET','/v2/checkout/orders/'+row.provider_order_id)

def capture_order(row):
    payload=show_order(row)
    if payload.get('status')=='COMPLETED':return payload
    if payload.get('status')!='APPROVED':raise HTTPException(409,'Approve payment on PayPal before confirming it here')
    return request('POST','/v2/checkout/orders/'+row.provider_order_id+'/capture',{},'capture-'+str(row.id),negative=True)

def verified_capture(row,payload):
    try:
        units=payload['purchase_units']
        if payload['id']!=row.provider_order_id or payload['status']!='COMPLETED' or len(units)!=1:raise ValueError()
        unit=units[0];captures=unit['payments']['captures']
        if unit['custom_id']!=str(row.id) or unit['payee']['merchant_id']!=settings.paypal_merchant_id or len(captures)!=1:raise ValueError()
        capture=captures[0];amount=capture['amount']
        if capture['status']!='COMPLETED' or amount['currency_code']!=row.currency or Decimal(amount['value'])!=Decimal(row.amount_cents)/100 or not capture['id']:raise ValueError()
        return capture['id']
    except (KeyError,ValueError,TypeError,InvalidOperation):raise HTTPException(502,'Payment verification failed. No subscription was activated; contact support.')
