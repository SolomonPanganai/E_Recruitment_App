"""WSGI entry point for the E-Recruitment application."""

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
