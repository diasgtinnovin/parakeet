# Email Warmup POC - API Reference

## Table of Contents
1. [OAuth API](#oauth-api)
2. [Accounts API](#accounts-api)
3. [Analytics API](#analytics-api)
4. [Email Tracking API](#email-tracking-api)
5. [Error Responses](#error-responses)
6. [Authentication](#authentication)

---

## Base URL

```
http://localhost:5000
```

---

## OAuth API

Base path: `/api/oauth`

### Sign In Page

```http
GET /api/oauth/signin
```

**Description**: Displays HTML sign-in page with Google OAuth button.

**Response**: HTML page

**Example**:
```bash
curl http://localhost:5000/api/oauth/signin
```

---

### Initiate OAuth Flow

```http
GET /api/oauth/login
```

**Description**: Redirects to Google OAuth consent screen.

**Response**: 302 Redirect to Google

**Example**:
```bash
curl -L http://localhost:5000/api/oauth/login
```

---

### OAuth Callback

```http
GET /api/oauth/callback?state={state}&code={code}&scope={scope}
```

**Description**: Handles OAuth callback from Google, creates/updates account.

**Parameters**:
- `state` (query, required): OAuth state token
- `code` (query, required): Authorization code from Google
- `scope` (query, required): Granted scopes

**Response**: HTML success page

**Success Response**:
```html
<!DOCTYPE html>
<html>
<head><title>OAuth Success!</title></head>
<body>
    <h1>🎉 Success!</h1>
    <div class="success">
        <h3>✅ Account user@example.com added successfully</h3>
        <p><strong>Account ID:</strong> 1</p>
        <p><strong>Email:</strong> user@example.com</p>
    </div>
    <div class="info">
        <h4>🚀 What's Next:</h4>
        <ul>
            <li>Your account is now active in the warmup service</li>
            <li>Emails will be sent automatically every 2 minutes</li>
            <li>Check analytics at /api/analytics/account/1</li>
        </ul>
    </div>
</body>
</html>
```

**Error Response** (500):
```json
{
  "error": "OAuth failed: Invalid state parameter"
}
```

---

## Accounts API

Base path: `/api/accounts`

### Add Account (Manual)

```http
POST /api/accounts/add
Content-Type: application/json
```

**Description**: Manually add email account with OAuth token.

**Request Body**:
```json
{
  "email": "user@example.com",
  "provider": "gmail",
  "oauth_token": {
    "token": "ya29.a0...",
    "refresh_token": "1//0e...",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "123...apps.googleusercontent.com",
    "client_secret": "GOCSPX-...",
    "scopes": [
      "https://www.googleapis.com/auth/gmail.send",
      "https://www.googleapis.com/auth/gmail.readonly"
    ]
  },
  "daily_limit": 5
}
```

**Success Response** (201):
```json
{
  "message": "Account added successfully",
  "account_id": 1,
  "email": "user@example.com"
}
```

**Error Responses**:

*Missing Field* (400):
```json
{
  "error": "Missing required field: email"
}
```

*Account Exists* (409):
```json
{
  "error": "Account already exists"
}
```

*Invalid Token* (400):
```json
{
  "error": "Invalid OAuth token or connection failed"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:5000/api/accounts/add \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "provider": "gmail",
    "oauth_token": {...},
    "daily_limit": 5
  }'
```

---

### List Accounts

```http
GET /api/accounts/list
```

**Description**: Retrieve all active email accounts.

**Success Response** (200):
```json
{
  "accounts": [
    {
      "id": 1,
      "email": "warmup@example.com",
      "provider": "gmail",
      "daily_limit": 12,
      "warmup_score": 48,
      "created_at": "2025-10-01T10:30:00"
    },
    {
      "id": 2,
      "email": "pool1@example.com",
      "provider": "gmail",
      "daily_limit": 5,
      "warmup_score": 0,
      "created_at": "2025-10-01T11:15:00"
    }
  ]
}
```

**cURL Example**:
```bash
curl http://localhost:5000/api/accounts/list
```

---

### Pause Account

```http
POST /api/accounts/{account_id}/pause
```

**Description**: Pause warmup for specific account (sets `is_active=False`).

**Path Parameters**:
- `account_id` (integer, required): Account ID

**Success Response** (200):
```json
{
  "message": "Account paused successfully"
}
```

**Error Response** (404):
```json
{
  "error": "Account not found"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:5000/api/accounts/1/pause
```

---

### Resume Account

```http
POST /api/accounts/{account_id}/resume
```

**Description**: Resume warmup for paused account (sets `is_active=True`).

**Path Parameters**:
- `account_id` (integer, required): Account ID

**Success Response** (200):
```json
{
  "message": "Account resumed successfully"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:5000/api/accounts/1/resume
```

---

## Analytics API

Base path: `/api/analytics`

### Account Analytics

```http
GET /api/analytics/account/{account_id}
```

**Description**: Get detailed analytics for specific account.

**Path Parameters**:
- `account_id` (integer, required): Account ID

**Success Response** (200):
```json
{
  "account_id": 1,
  "email": "warmup@example.com",
  "total_emails": 67,
  "opened_emails": 42,
  "replied_emails": 15,
  "open_rate": 62.69,
  "reply_rate": 22.39,
  "warmup_score": 48,
  "daily_limit": 12,
  "is_active": true
}
```

**Fields Explanation**:
- `total_emails`: Total warmup emails sent from this account
- `opened_emails`: Number of emails that were opened (tracking pixel triggered)
- `replied_emails`: Number of emails that received replies
- `open_rate`: Percentage of sent emails that were opened
- `reply_rate`: Percentage of sent emails that received replies
- `warmup_score`: Calculated as `min(100, (open_rate * 0.6 + reply_rate * 0.4) * 2)`
- `daily_limit`: Current daily sending limit (based on warmup phase)
- `is_active`: Whether account is actively sending emails

**Error Response** (404):
```json
{
  "error": "Account not found"
}
```

**cURL Example**:
```bash
curl http://localhost:5000/api/analytics/account/1
```

---

### Overview Analytics

```http
GET /api/analytics/overview
```

**Description**: Get system-wide analytics for all accounts.

**Success Response** (200):
```json
{
  "total_accounts": 5,
  "total_emails": 342,
  "total_opened": 215,
  "total_replied": 87,
  "overall_open_rate": 62.87,
  "overall_reply_rate": 25.44
}
```

**Fields Explanation**:
- `total_accounts`: Number of active accounts in the system
- `total_emails`: Total warmup emails sent across all accounts
- `total_opened`: Total emails opened across all accounts
- `total_replied`: Total emails replied across all accounts
- `overall_open_rate`: System-wide open rate percentage
- `overall_reply_rate`: System-wide reply rate percentage

**cURL Example**:
```bash
curl http://localhost:5000/api/analytics/overview
```

---

## Email Tracking API

Base path: `/track`

### Track Email Open

```http
GET /track/open/{tracking_pixel_id}
```

**Description**: Track email opens via invisible 1x1 pixel. This endpoint is embedded in sent emails as an image tag.

**Path Parameters**:
- `tracking_pixel_id` (string, required): Unique tracking UUID for the email

**Success Response** (200):
- **Content-Type**: `image/png`
- **Body**: 1x1 transparent PNG pixel (binary)

**Behavior**:
1. Receives request when email HTML loads the image
2. Finds Email record by `tracking_pixel_id`
3. Updates `is_opened = True` and `opened_at = current_timestamp`
4. Returns transparent 1x1 PNG image

**Email HTML Example**:
```html
<p>Email content here...</p>
<img src="http://localhost:5000/track/open/a1b2c3d4-e5f6-7890-abcd-ef1234567890" 
     width="1" height="1" style="display:none;">
```

**cURL Example**:
```bash
curl http://localhost:5000/track/open/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  --output pixel.png
```

---

## Error Responses

### Standard Error Format

All error responses follow this format:

```json
{
  "error": "Error description message"
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 500 | Internal Server Error | Server-side error |

### Common Error Messages

**400 Bad Request**:
- `"Missing required field: {field_name}"`
- `"Invalid OAuth token or connection failed"`
- `"Invalid OAuth state"`

**404 Not Found**:
- `"Account not found"`
- `"Email not found"`

**409 Conflict**:
- `"Account already exists"`

**500 Internal Server Error**:
- `"Internal server error"`
- `"OAuth failed: {error_details}"`

---

## Authentication

### Current Implementation

The service currently uses **OAuth 2.0 for Gmail API access** only. There is **no authentication required** for API endpoints themselves.

**OAuth Flow**:
1. User clicks "Sign in with Google" on `/api/oauth/signin`
2. Redirected to Google OAuth consent screen
3. User grants permissions
4. Google redirects to `/api/oauth/callback` with authorization code
5. Service exchanges code for access token and refresh token
6. Tokens stored in Account model for API access

### OAuth Scopes

```
https://www.googleapis.com/auth/gmail.send      # Send emails
https://www.googleapis.com/auth/gmail.readonly  # Read emails/replies
```

### Future Recommendations

For production deployment, consider adding:

1. **API Key Authentication**:
```http
GET /api/analytics/overview
Authorization: Bearer {api_key}
```

2. **JWT Tokens**:
```http
POST /api/accounts/add
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

3. **Rate Limiting**:
- Limit requests per IP/API key
- Prevent abuse of tracking endpoints

4. **CORS Configuration**:
- Restrict allowed origins
- Configure for production domain

---

## Usage Examples

### Complete Workflow Example

**1. Add Account via OAuth**:
```bash
# Open in browser
http://localhost:5000/api/oauth/signin

# Click "Sign in with Google"
# Grant permissions
# Account automatically created
```

**2. Configure as Warmup Account**:
```bash
# Use setup script
python scripts/setup_warmup_config.py

# Or manually update database
UPDATE account SET account_type='warmup', warmup_target=50, warmup_day=1 
WHERE email='warmup@example.com';
```

**3. Monitor Analytics**:
```bash
# Check specific account
curl http://localhost:5000/api/analytics/account/1 | jq

# Check overall stats
curl http://localhost:5000/api/analytics/overview | jq
```

**4. Pause/Resume Warmup**:
```bash
# Pause
curl -X POST http://localhost:5000/api/accounts/1/pause

# Resume
curl -X POST http://localhost:5000/api/accounts/1/resume
```

**5. List All Accounts**:
```bash
curl http://localhost:5000/api/accounts/list | jq
```

---

### Python SDK Example

```python
import requests

BASE_URL = "http://localhost:5000"

class WarmupClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
    
    def list_accounts(self):
        response = requests.get(f"{self.base_url}/api/accounts/list")
        return response.json()
    
    def get_analytics(self, account_id):
        response = requests.get(f"{self.base_url}/api/analytics/account/{account_id}")
        return response.json()
    
    def pause_account(self, account_id):
        response = requests.post(f"{self.base_url}/api/accounts/{account_id}/pause")
        return response.json()
    
    def resume_account(self, account_id):
        response = requests.post(f"{self.base_url}/api/accounts/{account_id}/resume")
        return response.json()
    
    def get_overview(self):
        response = requests.get(f"{self.base_url}/api/analytics/overview")
        return response.json()

# Usage
client = WarmupClient()

# List all accounts
accounts = client.list_accounts()
print(f"Total accounts: {len(accounts['accounts'])}")

# Get analytics for account 1
analytics = client.get_analytics(1)
print(f"Open rate: {analytics['open_rate']}%")
print(f"Warmup score: {analytics['warmup_score']}")

# Pause account
client.pause_account(1)

# Get overview
overview = client.get_overview()
print(f"System open rate: {overview['overall_open_rate']}%")
```

---

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:5000';

class WarmupClient {
  constructor(baseUrl = BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async listAccounts() {
    const response = await axios.get(`${this.baseUrl}/api/accounts/list`);
    return response.data;
  }

  async getAnalytics(accountId) {
    const response = await axios.get(`${this.baseUrl}/api/analytics/account/${accountId}`);
    return response.data;
  }

  async pauseAccount(accountId) {
    const response = await axios.post(`${this.baseUrl}/api/accounts/${accountId}/pause`);
    return response.data;
  }

  async resumeAccount(accountId) {
    const response = await axios.post(`${this.baseUrl}/api/accounts/${accountId}/resume`);
    return response.data;
  }

  async getOverview() {
    const response = await axios.get(`${this.baseUrl}/api/analytics/overview`);
    return response.data;
  }
}

// Usage
(async () => {
  const client = new WarmupClient();

  // List all accounts
  const accounts = await client.listAccounts();
  console.log(`Total accounts: ${accounts.accounts.length}`);

  // Get analytics
  const analytics = await client.getAnalytics(1);
  console.log(`Open rate: ${analytics.open_rate}%`);

  // Get overview
  const overview = await client.getOverview();
  console.log(`System open rate: ${overview.overall_open_rate}%`);
})();
```

---

## Postman Collection

Import this JSON into Postman for easy API testing:

```json
{
  "info": {
    "name": "Email Warmup API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Accounts",
      "item": [
        {
          "name": "List Accounts",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/api/accounts/list"
          }
        },
        {
          "name": "Pause Account",
          "request": {
            "method": "POST",
            "url": "{{base_url}}/api/accounts/1/pause"
          }
        },
        {
          "name": "Resume Account",
          "request": {
            "method": "POST",
            "url": "{{base_url}}/api/accounts/1/resume"
          }
        }
      ]
    },
    {
      "name": "Analytics",
      "item": [
        {
          "name": "Account Analytics",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/api/analytics/account/1"
          }
        },
        {
          "name": "Overview Analytics",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/api/analytics/overview"
          }
        }
      ]
    }
  ],
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:5000"
    }
  ]
}
```

---

For implementation details, see [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md).  
For workflow understanding, see [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md).
