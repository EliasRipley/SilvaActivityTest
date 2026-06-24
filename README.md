# Silva Care Activity Payment Portal

A Django app for Silva Care sites to publish activities (trips, events, etc.) and let parents/carers pay by card via Stripe.

## Local Development

```
pip install -r requirements.txt
cp .env.example .env          # then fill in your Stripe test keys
python manage.py migrate
python seed_data.py
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Deployment

### Option 1 — PythonAnywhere (free, no credit card)

**One-time setup:**

1. Sign up at [pythonanywhere.com](https://www.pythonanywhere.com) (free account)
2. Open a **Bash** console from the dashboard
3. Clone the repo:

```
git clone https://github.com/EliasRipley/SilvaActivityTest.git
cd SilvaActivityTest
pip install --user -r requirements.txt
python manage.py migrate
python seed_data.py
```

4. Go to the **Web** tab → **Add a new web app** → **Manual configuration** → **Python 3.13**
5. Under **Code**, set the working directory to `/home/<your-username>/SilvaActivityTest/`
6. Click the **WSGI configuration file** link, wipe everything, paste:

```python
import os, sys
path = "/home/<your-username>/SilvaActivityTest"
if path not in sys.path:
    sys.path.insert(0, path)
os.environ["DJANGO_SETTINGS_MODULE"] = "portal.settings"
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

7. **Save** → green **Reload** button
8. Site is live at `https://<your-username>.pythonanywhere.com/`

**Redeploy after code changes:**

```
cd ~/SilvaActivityTest
git pull
python manage.py migrate
```

Then hit **Reload** on the Web tab.

### Option 2 — Google Cloud Run + Neon Postgres (scalable, modern)

**Prerequisites:**

- A Google Cloud project with billing enabled
- A free [Neon](https://neon.tech) Postgres database (or any Postgres host)
- GitHub repo is public (or use Cloud Source Repositories)

**One-time setup:**

1. Get your Neon connection string — looks like:
   `postgresql://user:pass@ep-xxxx.eu-west-2.aws.neon.tech/dbname?sslmode=require`

2. Open [Cloud Shell](https://console.cloud.google.com) and run:

```
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

git clone https://github.com/EliasRipley/SilvaActivityTest.git
cd SilvaActivityTest

gcloud run deploy silva-activity-portal \
  --source . \
  --region europe-west2 \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=<your-neon-url>,DJANGO_SECRET_KEY=<random-key>,DJANGO_ALLOWED_HOSTS=*,STRIPE_PUBLIC_KEY=pk_test_...,STRIPE_SECRET_KEY=sk_test_...,DJANGO_DEBUG=True,DJANGO_SETTINGS_MODULE=portal.settings"
```

3. Cloud Run will print a `.run.app` URL — that's your live site.

**Redeploy after code changes:**

```
cd ~/SilvaActivityTest
git pull
gcloud run deploy silva-activity-portal --source . --region europe-west2 --allow-unauthenticated
```

**Take offline (stop accepting requests):**

```
gcloud run services update silva-activity-portal --no-allow-unauthenticated --region europe-west2
```

**Take offline (stop ALL charges — disable billing on the project):**

Console → [Billing](https://console.cloud.google.com/billing) → find your billing account → **My projects** tab → three dots next to `silvaactivity` → **Disable billing**.

Or from Cloud Shell:

```
gcloud beta billing projects unlink silvaactivity
```

**Bring back online:**

```
gcloud run services update silva-activity-portal --allow-unauthenticated --region europe-west2
```

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | On Cloud Run | Postgres connection string. If unset, uses SQLite locally. |
| `DJANGO_SECRET_KEY` | Yes | Any random string |
| `DJANGO_DEBUG` | No | `True` or `False` |
| `DJANGO_ALLOWED_HOSTS` | No | Comma-separated, defaults to `*` |
| `STRIPE_PUBLIC_KEY` | Yes | From Stripe dashboard |
| `STRIPE_SECRET_KEY` | Yes | From Stripe dashboard |
| `STRIPE_WEBHOOK_SECRET` | No | Set in Stripe dashboard for webhook verification |
| `BOOKING_HOLD_MINUTES` | No | How long a space is reserved during payment (default 10) |
| `DJANGO_SETTINGS_MODULE` | Cloud Run | `portal.settings` |

## Default Logins (after running seed_data.py)

| Role | Username | Password |
|------|----------|----------|
| Admin (head office) | `Accounts@SilvaCare.org.uk` | `password123` |
| Site Senior | `Sonia.Penalver@SilvaCare.org.uk` | `password123` |
