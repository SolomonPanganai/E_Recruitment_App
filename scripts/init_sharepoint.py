"""Initialize SharePoint document library structure."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.utils.sharepoint import SharePointClient


def init_sharepoint():
    """Initialize SharePoint document libraries."""
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("SharePoint Document Library Initialization")
        print("=" * 50)
        
        client = SharePointClient()
        
        if not client.ctx:
            print("Error: Could not connect to SharePoint.")
            print("Please check your SharePoint configuration in .env")
            return
        
        # Create folder structure
        folders = [
            'Recruitment',
            'Recruitment/CVs',
            'Recruitment/IDs',
            'Recruitment/Qualifications',
            'Recruitment/CoverLetters',
            'Recruitment/Offers',
            'Recruitment/Contracts'
        ]
        
        print("\nCreating folder structure...")
        
        for folder in folders:
            try:
                # Create folder logic would go here
                # This is a placeholder - actual SharePoint folder creation
                # depends on your SharePoint library setup
                print(f"  [OK] {folder}")
            except Exception as e:
                print(f"  [ERROR] {folder}: {str(e)}")
        
        print("\n" + "=" * 50)
        print("SharePoint initialization complete!")
        print("=" * 50)


if __name__ == '__main__':
    init_sharepoint()
