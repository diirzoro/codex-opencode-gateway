"""Enforce normalized identity uniqueness; refuse existing duplicates without deleting users."""
import re
import sqlalchemy as sa
from alembic import op
revision='0026_unique_registration_identities'
down_revision='0025_email_verification_codes'
branch_labels=None
depends_on=None


def keys(row):
    # Frozen counterpart of security.identities for deterministic historic migration.
    table=str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')
    phone=re.sub(r'[\s().-]','',str(row.phone or '').translate(table))
    prefix=str(row.postal_code or '').translate(table).strip()
    if phone.startswith('00'):phone='+'+phone[2:]
    elif not phone.startswith('+') and phone.isascii() and phone.isdigit():
        if re.fullmatch(r'\+[1-9][0-9]{0,3}',prefix) and not phone.startswith(prefix[1:]):phone=prefix+phone.lstrip('0')
        else:phone='+'+phone
    if not re.fullmatch(r'\+[1-9][0-9]{7,14}',phone):phone=None
    return (str(row.username or '').strip().casefold() or None,str(row.email or '').strip().casefold() or None,phone)


def upgrade():
    bind=op.get_bind()
    rows=list(bind.execute(sa.text('SELECT id, username, email, phone, postal_code FROM users')))
    seen=[set(),set(),set()];duplicates=[set(),set(),set()];normalized=[]
    for row in rows:
        values=keys(row);normalized.append((row.id,values))
        for index,value in enumerate(values):
            if value is None:continue
            if value in seen[index]:duplicates[index].add(value)
            seen[index].add(value)
    if any(duplicates):
        counts=', '.join(name+'='+str(len(group)) for name,group in zip(('username','email','phone'),duplicates))
        raise RuntimeError('Existing normalized account duplicates require owner reconciliation; no users were changed: '+counts)
    for name,size in [('username_identity',50),('email_identity',254),('phone_identity',32)]:op.add_column('users',sa.Column(name,sa.String(size),nullable=True))
    for uid,(username,email,phone) in normalized:
        bind.execute(sa.text('UPDATE users SET username_identity=:u,email_identity=:e,phone_identity=:p WHERE id=:id'),{'u':username,'e':email,'p':phone,'id':uid})
    for name in ('username_identity','email_identity','phone_identity'):op.create_index('ix_users_'+name,'users',[name],unique=True)


def downgrade():
    raise RuntimeError('Do not discard account uniqueness safeguards')
