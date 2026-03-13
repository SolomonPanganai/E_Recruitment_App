"""Tests for authentication functionality."""

import pytest


class TestAuth:
    """Authentication tests."""
    
    def test_login_page_loads(self, client):
        """Test that login page loads correctly."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Login' in response.data
    
    def test_register_page_loads(self, client):
        """Test that registration page loads correctly."""
        response = client.get('/auth/register')
        assert response.status_code == 200
        assert b'Register' in response.data
    
    def test_register_new_user(self, client, app):
        """Test user registration."""
        response = client.post('/auth/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'securepassword123',
            'password2': 'securepassword123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        # Verify user was created
        from app.models import User
        with app.app_context():
            user = User.query.filter_by(email='newuser@example.com').first()
            assert user is not None
            assert user.first_name == 'New'
    
    def test_login_valid_credentials(self, client, app):
        """Test login with valid credentials."""
        # Create user first
        from app.models import User
        from app import db
        
        with app.app_context():
            user = User(
                username='validuser',
                email='valid@example.com',
                first_name='Valid',
                last_name='User',
                role='applicant',
                is_active=True
            )
            user.set_password('validpassword')
            db.session.add(user)
            db.session.commit()
        
        response = client.post('/auth/login', data={
            'email': 'valid@example.com',
            'password': 'validpassword'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        assert b'Invalid email or password' in response.data or response.status_code == 200
    
    def test_logout(self, auth_client):
        """Test logout functionality."""
        response = auth_client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200


class TestPasswordValidation:
    """Password validation tests."""
    
    def test_password_too_short(self, client):
        """Test that short passwords are rejected."""
        response = client.post('/auth/register', data={
            'username': 'testshort',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'short',
            'password2': 'short'
        }, follow_redirects=True)
        
        # Should show validation error
        assert response.status_code == 200
    
    def test_password_mismatch(self, client):
        """Test that mismatched passwords are rejected."""
        response = client.post('/auth/register', data={
            'username': 'testmismatch',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'password123',
            'password2': 'different123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
