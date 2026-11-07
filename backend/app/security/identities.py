"""Pure account identifier normalization; no provider lookups or credential storage."""
import re
DIGITS=str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')


def normalized_phone(value,calling_code=''):
    phone=re.sub(r'[\s().-]','',str(value or '').translate(DIGITS))
    prefix=str(calling_code or '').translate(DIGITS).strip()
    if phone.startswith('00'):phone='+'+phone[2:]
    elif not phone.startswith('+') and phone.isascii() and phone.isdigit():
        if re.fullmatch(r'\+[1-9][0-9]{0,3}',prefix) and not phone.startswith(prefix[1:]):phone=prefix+phone.lstrip('0')
        else:phone='+'+phone
    return phone if re.fullmatch(r'\+[1-9][0-9]{7,14}',phone) else None


def account_keys(username,email,phone,calling_code=''):
    return (str(username or '').strip().casefold() or None,str(email or '').strip().casefold() or None,normalized_phone(phone,calling_code))
