"""OneDrive integration utilities."""
import os
import requests
import json
from flask import current_app

try:
    from msal import ConfidentialClientApplication
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False
    ConfidentialClientApplication = None


class OneDriveClient:
    """Client for OneDrive document integration."""
    
    def __init__(self, app=None):
        self.client_id = None
        self.client_secret = None
        self.tenant_id = None
        self.onedrive_folder_id = None  # Root folder ID for documents
        self._access_token = None
        self._token_cache = {}
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app config."""
        self.client_id = app.config.get('ONEDRIVE_CLIENT_ID') or app.config.get('SHAREPOINT_CLIENT_ID')
        self.client_secret = app.config.get('ONEDRIVE_CLIENT_SECRET') or app.config.get('SHAREPOINT_CLIENT_SECRET')
        self.tenant_id = app.config.get('ONEDRIVE_TENANT_ID') or app.config.get('SHAREPOINT_TENANT_ID')
        self.onedrive_folder_id = app.config.get('ONEDRIVE_FOLDER_ID')
    
    @property
    def is_configured(self):
        """Check if OneDrive is configured."""
        return all([self.client_id, self.client_secret, self.tenant_id])
    
    def get_access_token(self):
        """Get OAuth access token for OneDrive using MSAL."""
        if not self.is_configured:
            current_app.logger.error('OneDrive not configured')
            return None
        
        if not MSAL_AVAILABLE:
            current_app.logger.error('MSAL library not installed. Run: pip install msal')
            return None
        
        if self._access_token:
            return self._access_token
        
        try:
            app = ConfidentialClientApplication(
                self.client_id,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
                client_credential=self.client_secret
            )
            
            result = app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
            
            if 'access_token' in result:
                self._access_token = result['access_token']
                return self._access_token
            else:
                current_app.logger.error(f'Failed to get OneDrive token: {result.get("error_description")}')
                return None
        
        except Exception as e:
            current_app.logger.error(f'Error acquiring OneDrive token: {str(e)}')
            return None
    
    def _make_request(self, method, endpoint, **kwargs):
        """Make an authenticated request to Microsoft Graph API."""
        token = self.get_access_token()
        if not token:
            return None
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f"https://graph.microsoft.com/v1.0{endpoint}"
        
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.text else {'success': True}
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'OneDrive API request failed: {str(e)}')
            return None
    
    def create_folder(self, folder_name, parent_folder_id=None):
        """Create a folder in OneDrive."""
        if not self.is_configured:
            current_app.logger.warning('OneDrive not configured')
            return None
        
        parent_id = parent_folder_id or self.onedrive_folder_id or 'root'
        
        data = {
            'name': folder_name,
            'folder': {},
            '@microsoft.graph.conflictBehavior': 'rename'
        }
        
        endpoint = f'/me/drive/items/{parent_id}/children'
        result = self._make_request('POST', endpoint, json=data)
        
        if result:
            current_app.logger.info(f'Created OneDrive folder: {folder_name}')
            return result.get('id')
        
        return None
    
    def upload_file(self, local_file_path, onedrive_folder_id=None, filename=None):
        """Upload a file to OneDrive."""
        if not self.is_configured:
            current_app.logger.warning('OneDrive not configured')
            return None
        
        if not os.path.exists(local_file_path):
            current_app.logger.error(f'File not found: {local_file_path}')
            return None
        
        if not filename:
            filename = os.path.basename(local_file_path)
        
        parent_id = onedrive_folder_id or self.onedrive_folder_id or 'root'
        
        try:
            with open(local_file_path, 'rb') as f:
                file_content = f.read()
            
            endpoint = f'/me/drive/items/{parent_id}:/{filename}:/content'
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}',
                'Content-Type': 'application/octet-stream'
            }
            
            url = f"https://graph.microsoft.com/v1.0{endpoint}"
            response = requests.put(url, headers=headers, data=file_content)
            response.raise_for_status()
            
            result = response.json()
            current_app.logger.info(f'Uploaded file to OneDrive: {filename}')
            return result.get('webUrl')
        
        except Exception as e:
            current_app.logger.error(f'Failed to upload file to OneDrive: {str(e)}')
            return None
    
    def download_file(self, onedrive_file_id, local_path):
        """Download a file from OneDrive."""
        if not self.is_configured:
            return None
        
        try:
            endpoint = f'/me/drive/items/{onedrive_file_id}/content'
            token = self.get_access_token()
            
            headers = {'Authorization': f'Bearer {token}'}
            url = f"https://graph.microsoft.com/v1.0{endpoint}"
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            current_app.logger.info(f'Downloaded file from OneDrive: {local_path}')
            return local_path
        
        except Exception as e:
            current_app.logger.error(f'Failed to download file from OneDrive: {str(e)}')
            return None
    
    def delete_file(self, onedrive_file_id):
        """Delete a file from OneDrive."""
        if not self.is_configured:
            return None
        
        endpoint = f'/me/drive/items/{onedrive_file_id}'
        result = self._make_request('DELETE', endpoint)
        
        if result is not None:
            current_app.logger.info(f'Deleted file from OneDrive')
            return True
        
        return False
    
    def list_folder_contents(self, folder_id=None):
        """List contents of a OneDrive folder."""
        if not self.is_configured:
            return []
        
        parent_id = folder_id or self.onedrive_folder_id or 'root'
        endpoint = f'/me/drive/items/{parent_id}/children'
        
        result = self._make_request('GET', endpoint)
        
        if result and 'value' in result:
            return result['value']
        
        return []
    
    def get_sharing_link(self, onedrive_file_id, link_type='view'):
        """Get a sharing link for a OneDrive file."""
        if not self.is_configured:
            return None
        
        data = {
            'type': link_type,  # 'view', 'edit', 'embed'
            'scope': 'organization'  # or 'anonymous'
        }
        
        endpoint = f'/me/drive/items/{onedrive_file_id}/createLink'
        result = self._make_request('POST', endpoint, json=data)
        
        if result and 'link' in result:
            return result['link']['webUrl']
        
        return None
    
    def sync_documents(self, documents, target_folder_name='Recruitment Documents'):
        """Sync documents from local storage to OneDrive."""
        if not self.is_configured:
            current_app.logger.warning('OneDrive not configured for sync')
            return {'synced': 0, 'failed': 0, 'errors': []}
        
        try:
            # Create or get target folder
            target_folder_id = self.create_folder(target_folder_name)
            if not target_folder_id:
                # Try to find existing folder
                contents = self.list_folder_contents()
                for item in contents:
                    if item.get('name') == target_folder_name and 'folder' in item:
                        target_folder_id = item['id']
                        break
            
            synced = 0
            failed = 0
            errors = []
            
            for doc in documents:
                try:
                    if doc.local_path:
                        local_file = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.local_path)
                        
                        if os.path.exists(local_file):
                            web_url = self.upload_file(local_file, target_folder_id, doc.file_name)
                            
                            if web_url:
                                doc.sharepoint_url = web_url
                                synced += 1
                            else:
                                failed += 1
                                errors.append(f'Failed to upload {doc.file_name}')
                        else:
                            current_app.logger.warning(f'Local file not found: {local_file}')
                            failed += 1
                except Exception as e:
                    failed += 1
                    errors.append(f'Error syncing {doc.file_name}: {str(e)}')
                    current_app.logger.error(f'Error syncing document {doc.id}: {str(e)}')
            
            return {'synced': synced, 'failed': failed, 'errors': errors}
        
        except Exception as e:
            current_app.logger.error(f'Error during OneDrive sync: {str(e)}')
            return {'synced': 0, 'failed': 0, 'errors': [str(e)]}
    
    def get_file_info(self, onedrive_file_id):
        """Get detailed information about a OneDrive file."""
        if not self.is_configured:
            return None
        
        endpoint = f'/me/drive/items/{onedrive_file_id}'
        return self._make_request('GET', endpoint)


# Helper function to initialize OneDrive client
onedrive_client = OneDriveClient()
