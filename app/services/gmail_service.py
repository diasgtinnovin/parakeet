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
        'https://www.googleapis.com/auth/gmail.modify',  # Added for marking as read
        'https://www.googleapis.com/auth/gmail.labels'  # Added for labeling emails
    ]
    
    def __init__(self, credentials_json=None):
        self.credentials_json = credentials_json
        self.service = None
    
    def authenticate_with_token(self, token_data):
        """
        Authenticate using provided OAuth token
        
        Returns:
            tuple: (success: bool, updated_token_data: dict or None)
            - If authentication succeeds without refresh: (True, None)
            - If authentication succeeds with refresh: (True, new_token_data)
            - If authentication fails: (False, None)
        """
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
                return (False, None)

            creds = Credentials.from_authorized_user_info(td, self.SCOPES)

            # Track if token was refreshed
            token_refreshed = False
            
            # Refresh token if needed
            if creds.expired:
                if creds.refresh_token and creds.client_id and creds.client_secret and creds.token_uri:
                    try:
                        creds.refresh(Request())
                        logger.info("Successfully refreshed expired credentials")
                        token_refreshed = True
                    except Exception as refresh_error:
                        logger.error(f"Failed to refresh credentials: {refresh_error}")
                        return (False, None)
                else:
                    logger.error("Credentials expired and cannot refresh: missing refresh_token/client_id/client_secret/token_uri")
                    return (False, None)

            self.service = build('gmail', 'v1', credentials=creds)
            
            # If token was refreshed, return the new token data
            if token_refreshed:
                updated_token_data = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes
                }
                return (True, updated_token_data)
            
            return (True, None)
        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return (False, None)
    
    def send_email(self, to_address, subject, content, tracking_pixel_id=None):
        """
        Send email 
        """
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['to'] = to_address
            message['subject'] = subject
            
            html_content = content + '\n' + 'green-bulb'
            
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
            # Add keyword "green-bulb" at the end of reply content in a new line
            content_with_keyword = content + '\n' + 'green-bulb'
            
            # Create message
            message = MIMEText(content_with_keyword)
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

    def get_unread_emails_from_any(self, sender_emails, max_results=50):
        """
        Get unread emails from any of the provided sender emails.
        Returns detailed message dicts like get_unread_emails().
        """
        try:
            if not sender_emails:
                return []
            # Build OR query for senders
            senders_query = " OR ".join([f"from:{addr}" for addr in sender_emails])
            query = f"is:unread in:inbox ({senders_query})"

            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            if not messages:
                return []

            detailed_messages = []
            for msg in messages:
                try:
                    msg_detail = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()

                    headers = msg_detail.get('payload', {}).get('headers', [])
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
            logger.error(f"Error getting unread emails from senders: {e}")
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


    def get_spam_emails(self, sender_emails=None, max_results=100):
        """
        Get emails from spam folder
        If sender_emails is provided, filter by those senders
        Returns list of message objects with details
        """
        try:
            query = "in:spam"
            if sender_emails:
                # Build OR query for senders
                if isinstance(sender_emails, list) and len(sender_emails) > 0:
                    senders_query = " OR ".join([f"from:{addr}" for addr in sender_emails])
                    query = f"in:spam ({senders_query})"
            
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
                    to_email = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
                    message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
                    date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
                    
                    detailed_messages.append({
                        'id': msg['id'],
                        'from': from_email,
                        'to': to_email,
                        'subject': subject,
                        'message_id': message_id,
                        'snippet': msg_detail.get('snippet', ''),
                        'date': date,
                        'internal_date': msg_detail.get('internalDate', '')
                    })
                except Exception as e:
                    logger.error(f"Error getting spam message details for {msg['id']}: {e}")
                    continue
            
            return detailed_messages
            
        except Exception as e:
            logger.error(f"Error getting spam emails: {e}")
            return []
    
    def mark_not_spam(self, message_id):
        """
        Mark an email as not spam (remove SPAM label and move to inbox)
        Also marks as read to avoid notification spam
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={
                    'removeLabelIds': ['SPAM'],
                    'addLabelIds': ['INBOX', 'UNREAD']  # Move to inbox and keep unread for engagement
                }
            ).execute()
            
            logger.info(f"Marked message {message_id} as not spam and moved to inbox")
            return True
            
        except HttpError as error:
            logger.error(f"Gmail API error marking as not spam: {error}")
            return False
        except Exception as e:
            logger.error(f"Error marking message as not spam: {e}")
            return False
    
    def move_to_inbox_and_read(self, message_id):
        """
        Move message to inbox and mark as read (for processed spam recovery)
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={
                    'removeLabelIds': ['SPAM', 'UNREAD'],
                    'addLabelIds': ['INBOX']
                }
            ).execute()
            
            logger.info(f"Moved message {message_id} to inbox and marked as read")
            return True
            
        except HttpError as error:
            logger.error(f"Gmail API error moving to inbox: {error}")
            return False
        except Exception as e:
            logger.error(f"Error moving message to inbox: {e}")
            return False
    
    def mark_as_important(self, message_id):
        """
        Mark an email as important (add IMPORTANT label)
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['IMPORTANT']}
            ).execute()
            
            logger.info(f"Marked message {message_id} as important")
            return True
            
        except HttpError as error:
            logger.error(f"Gmail API error marking as important: {error}")
            return False
        except Exception as e:
            logger.error(f"Error marking message as important: {e}")
            return False
    
    def is_email_opened(self, message_id):
        """
        Check if an email has been opened (is not unread)
        """
        try:
            msg_detail = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='minimal'
            ).execute()
            
            label_ids = msg_detail.get('labelIds', [])
            is_opened = 'UNREAD' not in label_ids
            
            return is_opened
            
        except HttpError as error:
            logger.error(f"Gmail API error checking if email is opened: {error}")
            return False
        except Exception as e:
            logger.error(f"Error checking if email is opened: {e}")
            return False
    