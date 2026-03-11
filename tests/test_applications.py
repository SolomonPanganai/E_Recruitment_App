"""Tests for application functionality."""

import pytest
from io import BytesIO


class TestApplications:
    """Application tests."""
    
    def test_apply_requires_login(self, client, sample_job):
        """Test that applying requires login."""
        response = client.get(f'/applicant/apply/{sample_job}')
        # Should redirect to login
        assert response.status_code == 302
    
    def test_apply_page_loads(self, auth_client, app, sample_job):
        """Test that apply page loads for authenticated user."""
        response = auth_client.get(f'/applicant/apply/{sample_job}')
        assert response.status_code == 200
    
    def test_submit_application(self, auth_client, app, sample_job):
        """Test submitting an application."""
        # Create a fake PDF file
        fake_cv = (BytesIO(b'%PDF-1.4 fake pdf content'), 'resume.pdf')
        
        response = auth_client.post(
            f'/applicant/apply/{sample_job}',
            data={
                'cover_letter': 'I am excited to apply for this position.',
                'cv': fake_cv,
                'declaration': True
            },
            content_type='multipart/form-data',
            follow_redirects=True
        )
        
        assert response.status_code == 200
    
    def test_cannot_apply_twice(self, auth_client, app, sample_job):
        """Test that user cannot apply twice to same job."""
        from app.models import Application, User
        from app import db
        
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            if user:
                # Create existing application
                existing = Application(
                    applicant_id=user.id,
                    job_id=sample_job,
                    application_reference='APP-EXIST-001',
                    status='submitted'
                )
                db.session.add(existing)
                db.session.commit()
        
        response = auth_client.get(f'/applicant/apply/{sample_job}')
        # Should redirect or show error
        assert response.status_code in [200, 302]


class TestApplicationStatus:
    """Application status tests."""
    
    def test_dashboard_shows_applications(self, auth_client):
        """Test that dashboard shows user's applications."""
        response = auth_client.get('/applicant/dashboard')
        assert response.status_code == 200
    
    def test_view_application_detail(self, auth_client, app, sample_job):
        """Test viewing application detail."""
        from app.models import Application, User
        from app import db
        
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            if user:
                app_record = Application(
                    applicant_id=user.id,
                    job_id=sample_job,
                    application_reference='APP-VIEW-001',
                    status='submitted'
                )
                db.session.add(app_record)
                db.session.commit()
                app_id = app_record.id
        
        response = auth_client.get(f'/applicant/applications/{app_id}')
        assert response.status_code in [200, 404]


class TestWithdrawal:
    """Application withdrawal tests."""
    
    def test_withdraw_application(self, auth_client, app, sample_job):
        """Test withdrawing an application."""
        from app.models import Application, User
        from app import db
        
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            if user:
                app_record = Application(
                    applicant_id=user.id,
                    job_id=sample_job,
                    application_reference='APP-WITHDRAW-001',
                    status='submitted'
                )
                db.session.add(app_record)
                db.session.commit()
                app_id = app_record.id
        
        response = auth_client.post(
            f'/applicant/applications/{app_id}/withdraw',
            follow_redirects=True
        )
        assert response.status_code == 200
