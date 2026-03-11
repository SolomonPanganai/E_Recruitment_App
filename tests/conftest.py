"""Test configuration and fixtures."""

import pytest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, JobPosting


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def auth_client(app, client):
    """Create authenticated test client."""
    with app.app_context():
        # Create test user
        user = User(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User',
            role='applicant',
            is_active=True
        )
        user.set_password('testpassword')
        db.session.add(user)
        db.session.commit()
        
        # Login
        client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword'
        }, follow_redirects=True)
        
    return client


@pytest.fixture
def hr_client(app, client):
    """Create HR authenticated test client."""
    with app.app_context():
        # Create HR user
        user = User(
            username='hrofficer',
            email='hr@example.com',
            first_name='HR',
            last_name='Officer',
            role='hr_officer',
            is_active=True
        )
        user.set_password('hrpassword')
        db.session.add(user)
        db.session.commit()
        
        # Login
        client.post('/auth/login', data={
            'email': 'hr@example.com',
            'password': 'hrpassword'
        }, follow_redirects=True)
        
    return client


@pytest.fixture
def sample_job(app):
    """Create a sample job posting."""
    with app.app_context():
        user = User.query.first()
        if not user:
            user = User(
                username='admin',
                email='admin@example.com',
                first_name='Admin',
                last_name='User',
                role='admin'
            )
            user.set_password('admin')
            db.session.add(user)
            db.session.commit()
        
        job = JobPosting(
            title='Software Developer',
            job_reference='JOB-TEST-001',
            department='IT',
            location='Head Office',
            job_purpose='Test job purpose',
            responsibilities='Test responsibilities',
            minimum_requirements={'education': 'Bachelor\'s degree', 'experience': 3},
            closing_date=datetime.utcnow() + timedelta(days=30),
            status='published',
            created_by=user.id
        )
        db.session.add(job)
        db.session.commit()
        return job.id
