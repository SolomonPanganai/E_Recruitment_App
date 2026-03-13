# E-Recruitment Portal

A comprehensive recruitment management system built with Flask for managing job postings, applications, interviews, assessments, and offers.

## Features

### Applicant Portal
- User authentication (registration, login, password reset)
- Profile management and document uploads
- Job browsing and application submission
- Assessment completion and tracking
- Interview scheduling and rescheduling
- Application status tracking and notifications
- Internal messaging system

### HR Dashboard
- Job posting creation and management
- Application review and filtering
- Applicant screening and evaluation
- Interview scheduling and feedback
- Offer creation and management
- Staff onboarding
- Recruitment analytics and reporting
- Assessment management

### Admin Functions
- User management (create, edit, delete users)
- Role-based access control
- System settings and configuration
- Audit logs and activity tracking
- Bulk notification system
- Message templates

### Integrations
- SharePoint integration for document library and management
- Email notifications for key events
- Workflow automation via Celery
- Batch SMS notifications (optional)

## Tech Stack

- **Backend**: Flask (Python web framework)
- **Database**: MySQL with SQLAlchemy ORM
- **Task Queue**: Celery with Redis
- **Database Migrations**: Alembic
- **Testing**: Pytest
- **Frontend**: Jinja2 templates, Bootstrap CSS
- **External**: SharePoint integration

## Installation

### Prerequisites

- Python 3.8+
- MySQL Server
- Redis Server
- Git

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/e-recruit-app.git
   cd E-Recruit_App
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

6. **Initialize database with migrations**
   ```bash
   alembic upgrade head
   ```

7. **Create admin user**
   ```bash
   python scripts/create_admin.py
   ```

8. **Start Redis** (Terminal 1)
   ```bash
   redis-server
   ```

9. **Run Celery worker** (Terminal 2)
   ```bash
   celery -A tasks.celery_app worker --loglevel=info
   ```

10. **Run the application** (Terminal 3)
   ```bash
   python wsgi.py
   # or use Flask directly:
   flask run
   ```

9. **Start Celery worker** (Terminal 2)
   ```bash
   celery -A tasks.celery_app worker --loglevel=info
   ```

The application will be available at `http://localhost:5000`

## Project Structure

```
E-Recruit_App/
├── app/
│   ├── __init__.py              # App factory and Flask config
│   ├── models.py                # SQLAlchemy database models
│   ├── forms.py                 # WTForms form definitions
│   ├── routes.py                # Main application routes
│   ├── auth/                    # Authentication blueprint
│   │   └── routes.py            # Login, registration, password reset
│   ├── applicant/               # Applicant portal blueprint
│   │   └── routes.py            # Applicant-facing routes
│   ├── hr/                      # HR dashboard blueprint
│   │   └── routes.py            # HR management routes
│   ├── api/                     # REST API blueprint
│   │   └── routes.py            # REST API endpoints
│   └── utils/                   # Utility modules and helpers
├── templates/                   # Jinja2 HTML templates
│   ├── base.html                # Base template layout
│   ├── admin/                   # Admin templates
│   ├── applicant_messages/      # Messaging templates
│   ├── emails/                  # Email templates
│   ├── errors/                  # Error page templates
│   ├── messages/                # Internal message templates
│   └── workflows/               # Workflow templates
├── static/                      # Static assets
│   ├── css/                     # Stylesheets
│   ├── js/                      # JavaScript files
│   └── images/                  # Images and logos
├── tasks/                       # Celery task definitions
│   ├── celery_app.py           # Celery app configuration
│   └── jobs.py                 # Async job definitions
├── integration/                 # External system integrations
│   └── sharepoint_integration.py# SharePoint document management
├── migrations/                  # Alembic database migrations
│   ├── alembic.ini             # Alembic configuration
│   ├── env.py                  # Migration environment
│   └── versions/               # Individual migration files
├── scripts/                     # Admin and setup scripts
│   ├── create_admin.py         # Create admin user script
│   └── init_sharepoint.py      # Initialize SharePoint
├── tests/                       # Pytest test suite
│   ├── conftest.py             # Pytest fixtures
│   ├── test_auth.py            # Authentication tests
│   ├── test_jobs.py            # Job management tests
│   └── test_applications.py    # Application tests
├── config.py                    # Application configuration classes
├── wsgi.py                      # WSGI entry point for deployment
├── requirements.txt             # Python dependencies
└── database_schema.sql          # Database schema reference
```

## Configuration

Key environment variables (set in `.env`):

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | `your-secret-key-here` |
| `DATABASE_URL` | MySQL connection string | `mysql+pymysql://user:pass@localhost/e_recruit_db` |
| `MAIL_SERVER` | SMTP server address | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP server port | `587` |
| `CELERY_BROKER_URL` | Redis URL for Celery | `redis://localhost:6379/0` |
| `SQLALCHEMY_DATABASE_URI` | SQLAlchemy database URI | `mysql+pymysql://user:pass@localhost/e_recruit_db` |
| `SHAREPOINT_SITE_URL` | SharePoint site URL | `https://your-org.sharepoint.com/sites/recruitment` |

## API Endpoints

### Jobs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List all published jobs |
| `/api/jobs/<id>` | GET | Get job details |
| `/api/jobs` | POST | Create new job (Admin/HR) |
| `/api/jobs/<id>` | PUT | Update job (Admin/HR) |
| `/api/jobs/<id>` | DELETE | Delete job (Admin/HR) |

### Applications
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/applications` | GET | List user's applications |
| `/api/applications/<id>` | GET | Get application details |
| `/api/jobs/<id>/apply` | POST | Submit application |

### Assessments
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/assessments` | GET | List assessments |
| `/api/assessments/<id>` | GET | Get assessment details |
| `/api/assessments/<id>/take` | POST | Submit assessment answers |

### Reports
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reports/summary` | GET | Recruitment statistics |
| `/api/reports/funnel` | GET | Application funnel data |
| `/api/reports/time-to-hire` | GET | Time to hire metrics |

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

Run tests with coverage:
```bash
pytest tests/ --cov=app --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_auth.py -v
```

## Deployment

### Production Checklist

- [ ] Set `FLASK_ENV=production`
- [ ] Set strong `SECRET_KEY`
- [ ] Configure MySQL with production credentials
- [ ] Configure Redis for Celery
- [ ] Set up SSL/TLS certificates
- [ ] Configure email server for notifications
- [ ] Set up SharePoint integration if needed
- [ ] Configure firewall and security groups
- [ ] Set up database backups
- [ ] Configure logging and monitoring

### Running with Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 120 wsgi:app
```

For production with reverse proxy (nginx):
```bash
gunicorn -w 4 -b 127.0.0.1:8000 --pid /var/run/gunicorn.pid wsgi:app
```

## Development

### Running in Development Mode

```bash
set FLASK_ENV=development
set FLASK_DEBUG=1
flask run
```

### Database Migrations

Create a new migration after model changes:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback last migration:
```bash
alembic downgrade -1
```

### Code Style

Follow PEP 8. Format code with black:
```bash
black app/
```

## Troubleshooting

### Database Connection Issues
- Verify MySQL is running
- Check `DATABASE_URL` in `.env`
- Ensure database exists and user has permissions

### Celery Tasks Not Running
- Verify Redis is running
- Check Celery worker logs
- Ensure `CELERY_BROKER_URL` is correct

### Static Files Not Serving
- Run: `flask collect-static` if using Flask-Assets
- Check `STATIC_FOLDER` configuration
- Verify static files are in `static/` directory

## License

Proprietary - Your Organization

## Support

For support, contact: hr@municipality.gov.za

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-13 | Initial release with core features |
