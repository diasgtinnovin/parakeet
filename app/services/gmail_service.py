import base64
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)

class GmailService:
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify'  # Added for marking as read
    ]
    
    def __init__(self, credentials_json=None):
        self.credentials_json = credentials_json
        self.service = None
    
    def authenticate_with_token(self, token_data):
        """Authenticate using provided OAuth token"""
        try:
            # Ensure dict and defensively fill required fields if available via env
            if not isinstance(token_data, dict):
                raise ValueError("oauth token_data must be a dict")

            td = dict(token_data)  # shallow copy

            # Backfill token endpoint and client credentials from env if missing
            td.setdefault('token_uri', os.getenv('GOOGLE_TOKEN_URI', 'https://oauth2.googleapis.com/token'))
            if 'client_id' not in td and os.getenv('GOOGLE_CLIENT_ID'):
                td['client_id'] = os.getenv('GOOGLE_CLIENT_ID')
            if 'client_secret' not in td and os.getenv('GOOGLE_CLIENT_SECRET'):
                td['client_secret'] = os.getenv('GOOGLE_CLIENT_SECRET')

            # Check if token has required scopes - if not, it needs re-authentication
            provided_scopes = set(td.get('scopes', []) or [])
            missing_scopes = [s for s in self.SCOPES if s not in provided_scopes]
            if missing_scopes:
                logger.warning(f"Gmail token missing required scopes: {missing_scopes}. Account needs re-authentication.")
                return False

            creds = Credentials.from_authorized_user_info(td, self.SCOPES)

            # Refresh token if needed
            if creds.expired:
                if creds.refresh_token and creds.client_id and creds.client_secret and creds.token_uri:
                    try:
                        creds.refresh(Request())
                        logger.info("Successfully refreshed expired credentials")
                    except Exception as refresh_error:
                        logger.error(f"Failed to refresh credentials: {refresh_error}")
                        return False
                else:
                    logger.error("Credentials expired and cannot refresh: missing refresh_token/client_id/client_secret/token_uri")
                    return False

            self.service = build('gmail', 'v1', credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False
    
    def send_email(self, to_address, subject, content, tracking_pixel_id=None):
        """
        Send email with optional tracking pixel
        If tracking_pixel_id is None, sends without tracking pixel (for replies)
        """
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['to'] = to_address
            message['subject'] = subject
            
            # Add tracking pixel only if provided
            if tracking_pixel_id:
                html_content = f"""
                {content}
                <img src="http://localhost:5000/track/open/{tracking_pixel_id}" width="1" height="1" style="display:none;">
                """
            else:
                html_content = content
            
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
    
    def send_reply(self, to_address, subject, content, in_reply_to_id=None):
        """
        Send a reply email without tracking pixel
        """
        try:
            # Create message
            message = MIMEText(content)
            message['to'] = to_address
            message['subject'] = f"Re: {subject}" if not subject.startswith('Re:') else subject
            
            # Add In-Reply-To header if message ID is provided
            if in_reply_to_id:
                message['In-Reply-To'] = in_reply_to_id
                message['References'] = in_reply_to_id
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send email
            send_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Reply sent successfully: {send_message['id']}")
            return send_message['id']
            
        except HttpError as error:
            logger.error(f"Gmail API error: {error}")
            return None
        except Exception as e:
            logger.error(f"Error sending reply: {e}")
            return None
    
    def get_unread_emails(self, sender_email=None, max_results=10):
        """
        Get unread emails from inbox
        If sender_email is provided, filter by sender
        Returns list of message objects with id, from, subject, snippet, date
        """
        try:
            query = "is:unread in:inbox"
            if sender_email:
                query += f" from:{sender_email}"
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return []
            
            # Get detailed information for each message
            detailed_messages = []
            for msg in messages:
                try:
                    msg_detail = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    headers = msg_detail.get('payload', {}).get('headers', [])
                    
                    # Extract relevant headers
                    from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
                    message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
                    date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
                    
                    detailed_messages.append({
                        'id': msg['id'],
                        'from': from_email,
                        'subject': subject,
                        'message_id': message_id,
                        'snippet': msg_detail.get('snippet', ''),
                        'date': date,
                        'internal_date': msg_detail.get('internalDate', '')
                    })
                except Exception as e:
                    logger.error(f"Error getting message details for {msg['id']}: {e}")
                    continue
            
            return detailed_messages
            
        except Exception as e:
            logger.error(f"Error getting unread emails: {e}")
            return []
    
    def mark_as_read(self, message_id):
        """
        Mark an email as read (remove UNREAD label)
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            logger.info(f"Marked message {message_id} as read")
            return True
            
        except HttpError as error:
            logger.error(f"Gmail API error marking as read: {error}")
            return False
        except Exception as e:
            logger.error(f"Error marking message as read: {e}")
            return False
    
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
