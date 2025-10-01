import base64
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)

class GmailService:
    SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, credentials_json=None):
        self.credentials_json = credentials_json
        self.service = None
    
    def authenticate_with_token(self, token_data):
        """Authenticate using provided OAuth token"""
        try:
            creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
            
            # Refresh token if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            self.service = build('gmail', 'v1', credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False
    
    def send_email(self, to_address, subject, content, tracking_pixel_id):
        """Send email with tracking pixel"""
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['to'] = to_address
            message['subject'] = subject
            
            # Add tracking pixel to content
            html_content = f"""
            {content}
            <img src="http://localhost:5000/track/open/{tracking_pixel_id}" width="1" height="1" style="display:none;">
            """
            
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send email
            send_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully: {send_message['id']}")
            return send_message['id']
            
        except HttpError as error:
            logger.error(f"Gmail API error: {error}")
            return None
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return None
    
    def check_replies(self, account_email):
        """Check for replies in the inbox"""
        try:
            # Search for replies
            query = f"to:{account_email} is:unread"
            results = self.service.users().messages().list(
                userId='me',
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            return len(messages)
            
        except Exception as e:
            logger.error(f"Error checking replies: {e}")
            return 0
