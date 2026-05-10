# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Backend REST API for **XXXII CONAEA** (Congreso Nacional de Estudiantes de Agronomía), built with Django 5.2 + Django REST Framework. Deployed on Railway via Gunicorn.

## Commands

```bash
# Activate virtualenv (Windows)
venv\Scripts\activate

# Run development server
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Run all tests
python manage.py test

# Run tests for a single app
python manage.py test participant
python manage.py test register

# Import universities from XLSX
python import_universties.py
```

## Architecture

### Project layout

`congress/` is the Django project config (settings, root URLs, wsgi/asgi). All app routes are mounted under `/api/` in `congress/urls.py`.

### Apps and their responsibilities

| App | Prefix | Purpose |
|---|---|---|
| `security` | `/api/security/`, `/api/token/` | Auth, users, email, validations |
| `register` | `/api/register/`, `/api/available-slots/` | Registration + payment pipeline |
| `participant` | `/api/participants/` | Participant CRUD, universities, enrollment docs |
| `activity` | `/api/activities/` | Congress schedule (days, activities, speakers) |
| `partner` | `/api/partner/` | Sponsors and social networks |

### Authentication

JWT via `djangorestframework-simplejwt`. Access tokens expire in 15 minutes; refresh tokens last 90 days. The custom user model is `security.User` (extends `AbstractUser`, linked 1-to-1 to `security.PersonalData`). The JWT token serializer is overridden at `security.serializers.MyTokenObtainPairSerializer`.

### Registration flow (cross-app)

1. **Verify code** — `POST /api/register/verify-code/` checks either a `PartnerUniversity.code` (type `Referido`) or a `DynamicCode` (type `General`).
2. **Inscription** — `POST /api/register/inscription/` is a single atomic transaction that creates: `Registration` → `Participant` → `Enrollment` (PDF) → `ParticipantSpecialCondition` records. Marks `DynamicCode` as `Usado` on success.
3. **Payment** — `POST /api/register/transaction/` uploads a voucher image (converted to WEBP).
4. **Validation** — Admin toggles approvals via `POST /api/security/validation-admin/`. Approving `registration` triggers a welcome email with an embedded QR code sent in a background thread.

### Validation system (`security.Validation`)

A single `Validation` table is used to approve records from other apps. Each row references a `(model, register_id)` pair where `model` is one of `enrollment`, `transaction`, or `registration`. Calling the toggle endpoint again on an existing validation deletes it (un-validates). Approving a `registration` requires all its `enrollment` and `transaction` records to already be validated.

### Media storage

All uploaded files (photos, vouchers, speaker images, partner logos) go to **Cloudinary** via `cloudinary_storage`. Images are converted to WEBP at quality 85 inside each model's `save()` before being handed to the storage backend — this logic lives in `Participant.save()`, `Transaction.save()`, and `Speaker.save()`.

### Email service

`security/services/email_service.py` sends an HTML welcome email with an embedded QR code using Django's `EmailMultiAlternatives` and Mailtrap as the SMTP provider. Sending is controlled by the `AVAILABLE_EMAILS` env var (must be `true` to actually deliver). `security/services/mailtrap_service.py` checks Mailtrap's suppression list before marking a send as successful.

### Real-time slot availability

Two endpoints expose seat counts:
- `GET /api/available-slots/` — standard JSON snapshot (computed with Django ORM).
- `GET /api/available-slots/sse/` — Server-Sent Events stream; calls the PostgreSQL stored procedure `get_slots_data()` every 10 seconds.

### Quota types

`QuotaType` rows (Local, Nacional, Internacional, General) determine pricing tier and map to `PartnerUniversity` records. `PartnerUniversity.code` is a unique auto-generated 5-char key (2 uppercase letters + 3 digits) used as the registration access code for `Referido` participants.

## Key env vars

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (parsed by `dj-database-url`) |
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True`/`False` |
| `AVAILABLE_EMAILS` | Enable email sending (`true`/`false`) |
| `MAILTRAP_API_TOKEN` | Mailtrap API token |
| `MAILTRAP_ACCOUNT_ID` | Mailtrap account ID |
| `MAILTRAP_ENV` | `sandbox` or production |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Cloudinary credentials |
| `LOGO_URL` | Public URL of the CONAEA logo (embedded in emails) |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of allowed origins |

## Conventions

- All models have a soft-delete `is_active` boolean; querysets filter `is_active=True` by default.
- `db_table` is always set explicitly on every model's `Meta`.
- Timezone is `America/Lima`; `USE_TZ = True`.
- Static files are served by WhiteNoise; `STATIC_ROOT = staticfiles/`.
