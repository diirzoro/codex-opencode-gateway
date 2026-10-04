"""Create account, session, and location tables.
Revision ID: 0001_accounts
Revises: None
"""
from alembic import op
import sqlalchemy as sa
revision = "0001_accounts"; down_revision = None; branch_labels = None; depends_on = None

def upgrade():
    op.create_table("countries", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False, unique=True), sa.Column("code", sa.String(2), nullable=False, unique=True), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("regions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_regions_country_id", "regions", ["country_id"])
    op.create_table("cities", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_cities_region_id", "cities", ["region_id"])
    op.create_table("users", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("username", sa.String(50), nullable=False, unique=True), sa.Column("email", sa.String(254), nullable=False, unique=True), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("phone", sa.String(30), nullable=False), sa.Column("postal_code", sa.String(24), nullable=False), sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=False), sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id")), sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id")), sa.Column("role", sa.String(20), nullable=False, server_default="customer"), sa.Column("status", sa.String(20), nullable=False, server_default="active"), sa.Column("preferred_language", sa.String(5), nullable=False, server_default="ar"), sa.Column("preferred_theme", sa.String(10), nullable=False, server_default="light"), sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_login_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_users_username", "users", ["username"], unique=True); op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("auth_sessions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"]); op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True); op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    countries = sa.table("countries", sa.column("id", sa.Integer), sa.column("name", sa.String), sa.column("code", sa.String), sa.column("enabled", sa.Boolean))
    op.bulk_insert(countries, [{"id":1,"name":"Yemen","code":"YE","enabled":True},{"id":2,"name":"Saudi Arabia","code":"SA","enabled":True},{"id":3,"name":"United Arab Emirates","code":"AE","enabled":True}])
    regions = sa.table("regions", sa.column("id", sa.Integer), sa.column("country_id", sa.Integer), sa.column("name", sa.String), sa.column("enabled", sa.Boolean))
    op.bulk_insert(regions, [{"id":1,"country_id":1,"name":"Sana'a","enabled":True},{"id":2,"country_id":1,"name":"Aden","enabled":True},{"id":3,"country_id":2,"name":"Riyadh","enabled":True},{"id":4,"country_id":3,"name":"Dubai","enabled":True}])
    cities = sa.table("cities", sa.column("id", sa.Integer), sa.column("region_id", sa.Integer), sa.column("name", sa.String), sa.column("enabled", sa.Boolean))
    op.bulk_insert(cities, [{"id":1,"region_id":1,"name":"Sana'a","enabled":True},{"id":2,"region_id":2,"name":"Aden","enabled":True},{"id":3,"region_id":3,"name":"Riyadh","enabled":True},{"id":4,"region_id":4,"name":"Dubai","enabled":True}])

def downgrade():
    op.drop_table("auth_sessions"); op.drop_table("users"); op.drop_table("cities"); op.drop_table("regions"); op.drop_table("countries")
