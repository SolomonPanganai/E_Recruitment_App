"""SharePoint integration utilities."""
import os
from flask import current_app


class SharePointClient:
    """Client for SharePoint document integration."""
    
    def __init__(self, app=None):
        self.site_url = None
        self.client_id = None
        self.client_secret = None
        self.tenant_id = None
        self.documents_library = None
        self._access_token = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app config."""
        self.site_url = app.config.get('SHAREPOINT_SITE_URL')
        self.client_id = app.config.get('SHAREPOINT_CLIENT_ID')
        self.client_secret = app.config.get('SHAREPOINT_CLIENT_SECRET')
        self.tenant_id = app.config.get('SHAREPOINT_TENANT_ID')
        self.documents_library = app.config.get('SHAREPOINT_DOCUMENTS_LIBRARY', 'Recruitment Documents')
    
    @property
    def is_configured(self):
        """Check if SharePoint is configured."""
        return all([self.site_url, self.client_id, self.client_secret, self.tenant_id])
    
    def get_access_token(self):
        """Get OAuth access token for SharePoint."""
        if not self.is_configured:
            return None
        
        # Placeholder: Implement OAuth2 token acquisition
        # Using Microsoft Authentication Library (MSAL)
        # 
        # from msal import ConfidentialClientApplication
        # 
        # app = ConfidentialClientApplication(
        #     self.client_id,
        #     authority=f"https://login.microsoftonline.com/{self.tenant_id}",
        #     client_credential=self.client_secret
        # )
        # 
        # result = app.acquire_token_for_client(
        #     scopes=["https://graph.microsoft.com/.default"]
        # )
        # 
        # return result.get('access_token')
        
        return self._access_token
    
    def create_folder(self, folder_path):
        """Create a folder in SharePoint document library."""
        if not self.is_configured:
            current_app.logger.warning('SharePoint not configured, skipping folder creation')
            return None
        
        # Placeholder: Implement folder creation via Graph API
        # 
        # import requests
        # 
        # headers = {
        #     'Authorization': f'Bearer {self.get_access_token()}',
        #     'Content-Type': 'application/json'
        # }
        # 
        # url = f"{self.site_url}/_api/web/folders/add('{folder_path}')"
        # response = requests.post(url, headers=headers)
        # 
        # return response.json()
        
        current_app.logger.info(f'Would create SharePoint folder: {folder_path}')
        return {'path': folder_path}
    
    def upload_file(self, local_file_path, sharepoint_folder, filename=None):
        """Upload a file to SharePoint."""
        if not self.is_configured:
            current_app.logger.warning('SharePoint not configured, skipping file upload')
            return None
        
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f'File not found: {local_file_path}')
        
        if not filename:
            filename = os.path.basename(local_file_path)
        
        # Placeholder: Implement file upload via Graph API
        # 
        # import requests
        # 
        # with open(local_file_path, 'rb') as f:
        #     file_content = f.read()
        # 
        # headers = {
        #     'Authorization': f'Bearer {self.get_access_token()}',
        #     'Content-Type': 'application/octet-stream'
        # }
        # 
        # url = (f"{self.site_url}/_api/web/GetFolderByServerRelativeUrl('{sharepoint_folder}')"
        #        f"/Files/add(url='{filename}',overwrite=true)")
        # 
        # response = requests.post(url, headers=headers, data=file_content)
        # 
        # return response.json().get('ServerRelativeUrl')
        
        current_app.logger.info(f'Would upload to SharePoint: {local_file_path} -> {sharepoint_folder}/{filename}')
        return f'{sharepoint_folder}/{filename}'
    
    def download_file(self, sharepoint_url, local_path):
        """Download a file from SharePoint."""
        if not self.is_configured:
            current_app.logger.warning('SharePoint not configured, skipping file download')
            return None
        
        # Placeholder: Implement file download via Graph API
        # 
        # import requests
        # 
        # headers = {
        #     'Authorization': f'Bearer {self.get_access_token()}'
        # }
        # 
        # url = f"{self.site_url}/_api/web/GetFileByServerRelativeUrl('{sharepoint_url}')/$value"
        # response = requests.get(url, headers=headers)
        # 
        # with open(local_path, 'wb') as f:
        #     f.write(response.content)
        # 
        # return local_path
        
        current_app.logger.info(f'Would download from SharePoint: {sharepoint_url}')
        return local_path
    
    def delete_file(self, sharepoint_url):
        """Delete a file from SharePoint."""
        if not self.is_configured:
            return None
        
        # Placeholder: Implement file deletion
        current_app.logger.info(f'Would delete from SharePoint: {sharepoint_url}')
        return True
    
    def list_folder_contents(self, folder_path):
        """List contents of a SharePoint folder."""
        if not self.is_configured:
            return []
        
        # Placeholder: Implement folder listing
        current_app.logger.info(f'Would list SharePoint folder: {folder_path}')
        return []
    
    def get_file_url(self, sharepoint_path):
        """Get the full URL for a SharePoint file."""
        if not self.site_url:
            return None
        return f"{self.site_url}/{sharepoint_path}"


# Helper functions for application document management

def create_job_folder(job):
    """Create SharePoint folder for a job posting."""
    client = SharePointClient()
    client.init_app(current_app._get_current_object())
    
    folder_path = f"{client.documents_library}/Jobs/{job.job_reference}"
    result = client.create_folder(folder_path)
    
    if result:
        job.sharepoint_folder_path = folder_path
    
    return folder_path


def create_application_folder(application):
    """Create SharePoint folder for an application."""
    client = SharePointClient()
    client.init_app(current_app._get_current_object())
    
    job_folder = application.job.sharepoint_folder_path or f"Jobs/{application.job.job_reference}"
    folder_path = f"{client.documents_library}/{job_folder}/Applications/{application.application_reference}"
    
    result = client.create_folder(folder_path)
    
    if result:
        application.sharepoint_folder_path = folder_path
    
    return folder_path


def upload_application_document(document, local_file_path):
    """Upload an application document to SharePoint."""
    client = SharePointClient()
    client.init_app(current_app._get_current_object())
    
    if not client.is_configured:
        return None
    
    application = document.application
    if not application.sharepoint_folder_path:
        create_application_folder(application)
    
    sharepoint_url = client.upload_file(
        local_file_path,
        application.sharepoint_folder_path,
        document.file_name
    )
    
    if sharepoint_url:
        document.sharepoint_url = sharepoint_url
    
    return sharepoint_url


def sync_documents_to_sharepoint(application):
    """Sync all application documents to SharePoint."""
    for document in application.documents.all():
        if document.local_path and not document.sharepoint_url:
            upload_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'],
                f'applications/{application.id}',
                document.local_path
            )
            if os.path.exists(upload_path):
                upload_application_document(document, upload_path)
