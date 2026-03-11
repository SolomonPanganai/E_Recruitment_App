# E-Recruitment Portal

A comprehensive recruitment management system built with Flask for managing job postings, applications, interviews, and offers.

## Features

### Applicant Portal
- User registration and profile management
- Browse and search job postings
- Online job application with document uploads
- Application status tracking
- Interview schedule viewing
- Offer acceptance/rejection

### HR Dashboard
- Create and manage job postings
- Automatic application screening
- Shortlisting and rejection workflows
- Interview scheduling
- Offer creation and management
- Recruitment reports and analytics

### Admin Functions
- User management (CRUD operations)
- Role-based access control (Admin, HR, Manager, Applicant)
- Comprehensive audit logging
- System configuration

### Integrations
- SharePoint document storage
- Email notifications (SMTP)
- SMS notifications (optional, via Twilio)
- Background task processing (Celery + Redis)

## Tech Stack

- **Backend**: Flask (Python 3.10+)
- **Database**: MySQL with SQLAlchemy ORM
- **Task Queue**: Celery with Redis
- **Frontend**: Bootstrap 5, Jinja2 templates
- **Authentication**: Flask-Login
- **Forms**: Flask-WTF with WTForms

## Installation

### Prerequisites
- Python 3.10 or higher
- MySQL 8.0 or higher
- Redis (for Celery)
- Git

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/e-recruit-app.git
   cd e-recruit-app
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   copy .env.example .env
   # Edit .env with your configuration
   ```

5. **Create MySQL database**
   ```sql
   CREATE DATABASE e_recruit_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

6. **Initialize database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

7. **Create admin user**
   ```bash
   python scripts/create_admin.py
   ```

8. **Run the application**
   ```bash
   flask run
   ```

9. **Start Celery worker** (separate terminal)
   ```bash
   celery -A tasks.celery_app worker --loglevel=info
   ```

## Project Structure

```
E-Recruit_App/
├── app/
│   ├── __init__.py          # App factory
│   ├── models.py            # Database models
│   ├── forms.py             # WTForms
│   ├── routes.py            # Main routes
│   ├── auth/                # Authentication blueprint
│   ├── applicant/           # Applicant portal blueprint
│   ├── hr/                  # HR dashboard blueprint
│   ├── api/                 # REST API blueprint
│   └── utils/               # Utility modules
├── templates/               # Jinja2 templates
├── static/                  # CSS, JS, images
├── tasks/                   # Celery tasks
├── integration/             # External integrations
├── scripts/                 # Admin scripts
├── tests/                   # Unit tests
├── config.py                # Configuration classes
├── wsgi.py                  # WSGI entry point
└── requirements.txt         # Dependencies
```

## Configuration

Key environment variables:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Flask secret key for sessions |
| `DATABASE_URL` | MySQL connection string |
| `MAIL_SERVER` | SMTP server address |
| `CELERY_BROKER_URL` | Redis URL for Celery |
| `SHAREPOINT_SITE_URL` | SharePoint site for documents |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List published jobs |
| `/api/jobs/<id>` | GET | Job details |
| `/api/applications` | GET | User's applications |
| `/api/reports/summary` | GET | Recruitment stats |

## Testing

```bash
pytest tests/
```

## Deployment

### Production Checklist
- [ ] Set `FLASK_ENV=production`
- [ ] Use strong `SECRET_KEY`
- [ ] Configure HTTPS
- [ ] Set up database backups
- [ ] Configure logging
- [ ] Use Gunicorn/uWSGI

### Running with Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

## License

Proprietary - [Your Organization]

## Support

For support, contact: hr@municipality.gov.za
