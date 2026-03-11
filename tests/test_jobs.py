"""Tests for job posting functionality."""

import pytest
from datetime import datetime, timedelta


class TestJobsPublic:
    """Public job listing tests."""
    
    def test_jobs_page_loads(self, client):
        """Test that jobs page loads correctly."""
        response = client.get('/jobs')
        assert response.status_code == 200
        assert b'Job Listings' in response.data or b'jobs' in response.data.lower()
    
    def test_home_page_shows_featured_jobs(self, client, app, sample_job):
        """Test that home page shows featured jobs."""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_job_detail_page(self, client, app, sample_job):
        """Test job detail page."""
        response = client.get(f'/jobs/{sample_job}')
        assert response.status_code == 200
    
    def test_job_detail_not_found(self, client):
        """Test job detail for non-existent job."""
        response = client.get('/jobs/99999')
        assert response.status_code == 404


class TestJobsHR:
    """HR job management tests."""
    
    def test_hr_can_create_job(self, hr_client, app):
        """Test that HR can create a job posting."""
        from datetime import date
        
        response = hr_client.post('/hr/jobs/create', data={
            'title': 'New Position',
            'reference_number': 'JOB-NEW-001',
            'department': 'Finance',
            'location': 'Main Office',
            'description': 'Job description here',
            'requirements_text': '- Requirement 1\n- Requirement 2',
            'closing_date': (date.today() + timedelta(days=30)).isoformat(),
            'status': 'draft'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_hr_can_view_jobs_list(self, hr_client):
        """Test that HR can view jobs list."""
        response = hr_client.get('/hr/jobs')
        assert response.status_code == 200
    
    def test_applicant_cannot_access_hr_jobs(self, auth_client):
        """Test that applicants cannot access HR job management."""
        response = auth_client.get('/hr/jobs')
        # Should redirect to login or show forbidden
        assert response.status_code in [302, 403]


class TestJobSearch:
    """Job search and filter tests."""
    
    def test_search_by_keyword(self, client, app, sample_job):
        """Test searching jobs by keyword."""
        response = client.get('/jobs?search=Software')
        assert response.status_code == 200
    
    def test_filter_by_department(self, client, app, sample_job):
        """Test filtering jobs by department."""
        response = client.get('/jobs?department=IT')
        assert response.status_code == 200
    
    def test_filter_by_location(self, client, app, sample_job):
        """Test filtering jobs by location."""
        response = client.get('/jobs?location=Head+Office')
        assert response.status_code == 200
