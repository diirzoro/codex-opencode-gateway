"""Landing homepage carousel content ("Homepage Content" / "Offers & Messages").

Creates the homepage_items table and seeds the currently approved Landing messages.
English and Arabic copy live in the same row so no second translation system is added.
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_homepage_content"
down_revision = "0013_login_identity"
branch_labels = None
depends_on = None

items = sa.table(
    "homepage_items",
    sa.column("item_type", sa.String),
    sa.column("badge", sa.String),
    sa.column("title_en", sa.String),
    sa.column("title_ar", sa.String),
    sa.column("body_en", sa.Text),
    sa.column("body_ar", sa.Text),
    sa.column("cta_label_en", sa.String),
    sa.column("cta_label_ar", sa.String),
    sa.column("cta_url", sa.String),
    sa.column("icon", sa.String),
    sa.column("media_kind", sa.String),
    sa.column("sort_order", sa.Integer),
    sa.column("enabled", sa.Boolean),
    sa.column("pinned", sa.Boolean),
)

SEED = [
    {"item_type": "platform", "badge": None, "icon": "icon-file", "sort_order": 1, "pinned": False,
     "title_en": "Your files, together", "title_ar": "ملفاتك في مكان واحد",
     "body_en": "Start blank or choose a template. Your project has a space of its own.",
     "body_ar": "ابدأ بمشروع فارغ أو اختر قالبًا. لكل مشروع مساحة تخصّه."},
    {"item_type": "platform", "badge": None, "icon": "icon-clock", "sort_order": 2, "pinned": False,
     "title_en": "Pick up where you left off", "title_ar": "أكمل من حيث توقفت",
     "body_en": "Start a new conversation while keeping the same project files.",
     "body_ar": "ابدأ محادثة جديدة مع الاحتفاظ بملفات مشروعك نفسها."},
    {"item_type": "platform", "badge": None, "icon": "icon-diff", "sort_order": 3, "pinned": False,
     "title_en": "See every change", "title_ar": "كل تغيير أمامك",
     "body_en": "Browse files, inspect the diff, and commit when you are ready.",
     "body_ar": "تصفح الملفات وراجع الفروق، ثم احفظ التغييرات عندما تكون جاهزًا."},
    {"item_type": "update", "badge": "update", "icon": "icon-opencode", "sort_order": 4, "pinned": True,
     "cta_url": "#", "cta_label_en": "Open your workspace", "cta_label_ar": "افتح مساحة عملك",
     "title_en": "Use OpenCode online", "title_ar": "استخدم OpenCode عبر الإنترنت",
     "body_en": "Work with OpenCode directly from your browser without installing it on every device. Open your workspace and continue working from anywhere.",
     "body_ar": "اعمل باستخدام OpenCode مباشرة من متصفحك دون تثبيته على كل جهاز. افتح مساحة عملك وتابع العمل من أي مكان."},
    {"item_type": "partner", "badge": None, "icon": "icon-github", "sort_order": 5, "pinned": False,
     "cta_url": "#", "cta_label_en": "Connect a repository", "cta_label_ar": "اربط مستودعًا",
     "title_en": "Connect your GitHub project", "title_ar": "اربط مشروعك من GitHub",
     "body_en": "Connect your repository, choose your project and branch, and continue working online without downloading the project manually on every device.",
     "body_ar": "اربط المستودع، واختر المشروع والفرع، وواصل العمل عبر الإنترنت دون تنزيل المشروع يدويًا على كل جهاز."},
    {"item_type": "offer", "badge": "offer", "icon": "icon-folder", "sort_order": 6, "pinned": False,
     "cta_url": "#", "cta_label_en": "Start a small project", "cta_label_ar": "ابدأ مشروعًا صغيرًا",
     "title_en": "50 MB project space", "title_ar": "مساحة مشروع حتى 50 MB",
     "body_en": "Create and test small local projects up to 50 MB inside your workspace and continue developing them using your preferred workflow.",
     "body_ar": "أنشئ وجرّب مشاريع محلية صغيرة بحجم يصل إلى 50 MB داخل مساحة عملك، وواصل تطويرها بالطريقة التي تفضلها."},
    {"item_type": "announcement", "badge": "new", "icon": "icon-grid", "sort_order": 7, "pinned": False,
     "cta_url": "#", "cta_label_en": "Get started", "cta_label_ar": "ابدأ الآن",
     "title_en": "Your workspace, online", "title_ar": "مساحة عملك، عبر الإنترنت",
     "body_en": "OpenCode, GitHub and your project files together in the browser — ready whenever you are.",
     "body_ar": "OpenCode وGitHub وملفات مشروعك معًا في المتصفح — جاهزة وقتما تشاء."},
]

rows = [{**item, "media_kind": "icon", "enabled": True} for item in SEED]


def upgrade():
    op.create_table(
        "homepage_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_type", sa.String(30), nullable=False, server_default="platform"),
        sa.Column("badge", sa.String(20), nullable=True),
        sa.Column("title_en", sa.String(200), nullable=False),
        sa.Column("title_ar", sa.String(200), nullable=False),
        sa.Column("body_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_ar", sa.Text(), nullable=False, server_default=""),
        sa.Column("cta_label_en", sa.String(80), nullable=True),
        sa.Column("cta_label_ar", sa.String(80), nullable=True),
        sa.Column("cta_url", sa.String(500), nullable=True),
        sa.Column("icon", sa.String(60), nullable=True),
        sa.Column("media_kind", sa.String(10), nullable=False, server_default="icon"),
        sa.Column("media_path", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.bulk_insert(items, rows)


def downgrade():
    op.drop_table("homepage_items")
