"""Seed the database with initial data for testing."""
import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portal.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.contrib.auth.models import User
from payments.models import Site, Activity, SiteSenior, ServiceUser, Wallet, AppSetting, COMPANY_WIDE_NAME

# --- Helpers ---


def make_slug(name):
    from django.utils.text import slugify

    base = slugify(name)
    slug = base
    n = 1
    while Site.objects.filter(slug=slug).exclude(name=name).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


# --- Admin ---
TEST_PASSWORD = "password123"
admin_email = "Accounts@SilvaCare.org.uk"
admin, created = User.objects.get_or_create(
    username=admin_email.lower(),
    defaults={
        "email": admin_email,
        "is_staff": True,
        "is_superuser": True,
    },
)
admin.set_password(TEST_PASSWORD)
admin.email = admin_email
admin.is_staff = True
admin.is_superuser = True
admin.save()
print(f"Admin ready: {admin_email} / {TEST_PASSWORD}")

# --- Sites ---

SITE_NAMES = [
    "72 Station Road",
    "74 Station Road",
    "Cherries",
    "Churchways",
    "Crosswalk",
    "Frenchay Park",
    "Grovehurst",
    "Hazels",
    "Kingswood House",
    "North Park",
    "Oakleigh",
    "Oaks",
    "Penn Drive",
    "South Park",
    "Whitchurch Lane",
]

sites = {}
for name in SITE_NAMES:
    site, created = Site.objects.get_or_create(
        name=name, defaults={"slug": make_slug(name), "is_active": True}
    )
    sites[name] = site
    if created:
        print(f"  Created site: {name}")

print(f"\nTotal sites: {Site.objects.count()}")

# --- Site Seniors (only set up explicitly) ---
# Sonia.Penalver@SilvaCare.org.uk as senior for North Park
sonia_email = "Sonia.Penalver@SilvaCare.org.uk"
sonia_site = sites.get("North Park")
if sonia_site:
    sonia, _ = User.objects.get_or_create(
        username=sonia_email.lower(),
        defaults={"email": sonia_email},
    )
    sonia.set_password(TEST_PASSWORD)
    sonia.email = sonia_email
    sonia.first_name = "Sonia"
    sonia.last_name = "Penalver"
    sonia.save()
    SiteSenior.objects.get_or_create(user=sonia, site=sonia_site)
    print(f"  Senior: {sonia_email} / {TEST_PASSWORD}")

# --- Sample account holder (parent/carer) ---
carer_email = "jane.smith@example.com"
carer, created = User.objects.get_or_create(
    username=carer_email.lower(),
    defaults={"email": carer_email, "first_name": "Jane", "last_name": "Smith"},
)
if created:
    carer.set_password(TEST_PASSWORD)
    carer.save()
    Wallet.objects.get_or_create(user=carer, defaults={"balance_pennies": 5000})
    ServiceUser.objects.get_or_create(
        account=carer, name="Robert Smith",
        defaults={"site": sonia_site if sonia_site else None},
    )
    print(f"  Account holder: {carer_email} / {TEST_PASSWORD}")
else:
    Wallet.objects.get_or_create(user=carer, defaults={"balance_pennies": 5000})

# --- App Settings ---
AppSetting.objects.get_or_create(
    key="su_accounts_enabled",
    defaults={"value": "True"},
)
AppSetting.objects.get_or_create(
    key="wallet_system_enabled",
    defaults={"value": "False"},
)
AppSetting.objects.get_or_create(
    key="max_deposit_amount",
    defaults={"value": "100"},
)

# --- Sample activities (only if none exist) ---
if not Activity.objects.exists():
    maple = sites.get("North Park")
    if maple:
        Activity.objects.create(
            site=maple,
            name="Beach Trip",
            description="Day trip to Brighton beach",
            price_pennies=1500,
            start_date="2026-07-15",
        )
        Activity.objects.create(
            site=maple,
            name="Zoo Visit",
            description="Trip to London Zoo",
            price_pennies=2500,
            start_date="2026-08-01",
        )
        Activity.objects.create(
            site=maple,
            name="Theatre Show",
            description="Evening at the West End",
            price_pennies=3500,
            start_date="2026-09-10",
            max_spaces=10,
        )
        Activity.objects.create(
            site=maple,
            name="Swimming Gala",
            description="Inter-site swimming competition",
            price_pennies=500,
            start_date="2026-08-15",
            max_spaces=20,
            payment_closes_at="2026-08-13",
        )

    oakwood = sites.get("South Park")
    if oakwood:
        Activity.objects.create(
            site=oakwood,
            name="Picnic in the Park",
            description="Afternoon picnic at Hyde Park",
            price_pennies=800,
            start_date="2026-07-20",
        )

    # Company-wide activity
    Activity.objects.create(
        site=None,
        name="Summer Festival",
        description="Annual summer festival open to all sites",
        price_pennies=1000,
        start_date="2026-08-20",
        max_spaces=50,
    )

    print("Sample activities created.")

print("\nDone. Run start.bat to launch the server.")
