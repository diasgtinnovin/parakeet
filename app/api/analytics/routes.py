from flask import request, jsonify, render_template_string
from app import db
from app.models.account import Account
from app.models.email import Email
from app.models.email_schedule import EmailSchedule
from . import analytics_bp
from sqlalchemy import func, case
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ============================================
# API ENDPOINTS (JSON Data)
# ============================================

@analytics_bp.route('/account/<int:account_id>', methods=['GET'])
def get_account_analytics(account_id):
    """Get analytics for a specific account"""
    try:
        account = Account.query.get_or_404(account_id)
        
        # Get email statistics
        total_emails = Email.query.filter_by(account_id=account_id).count()
        opened_emails = Email.query.filter_by(account_id=account_id, is_opened=True).count()
        replied_emails = Email.query.filter_by(account_id=account_id, is_replied=True).count()
        
        # Calculate rates
        open_rate = (opened_emails / total_emails * 100) if total_emails > 0 else 0
        reply_rate = (replied_emails / total_emails * 100) if total_emails > 0 else 0
        
        # Calculate warmup score
        warmup_score = min(60, int((open_rate * 0.6 + reply_rate * 0.4) * 2))
        
        # Update account warmup score
        account.warmup_score = warmup_score
        db.session.commit()
        
        return jsonify({
            'account_id': account_id,
            'email': account.email,
            'total_emails': total_emails,
            'opened_emails': opened_emails,
            'replied_emails': replied_emails,
            'open_rate': round(open_rate, 2),
            'reply_rate': round(reply_rate, 2),
            'warmup_score': warmup_score,
            'daily_limit': account.daily_limit,
            'is_active': account.is_active
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@analytics_bp.route('/overview', methods=['GET'])
def get_overview_analytics():
    """Get overview analytics for all accounts"""
    try:
        # Get total statistics
        total_accounts = Account.query.filter_by(is_active=True).count()
        total_emails = Email.query.count()
        total_opened = Email.query.filter_by(is_opened=True).count()
        total_replied = Email.query.filter_by(is_replied=True).count()
        
        # Calculate overall rates
        overall_open_rate = (total_opened / total_emails * 100) if total_emails > 0 else 0
        overall_reply_rate = (total_replied / total_emails * 100) if total_emails > 0 else 0
        
        return jsonify({
            'total_accounts': total_accounts,
            'total_emails': total_emails,
            'total_opened': total_opened,
            'total_replied': total_replied,
            'overall_open_rate': round(overall_open_rate, 2),
            'overall_reply_rate': round(overall_reply_rate, 2)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting overview analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ============================================
# NEW: COMPREHENSIVE DASHBOARD DATA
# ============================================

@analytics_bp.route('/dashboard/data', methods=['GET'])
def get_dashboard_data():
    """Get complete dashboard data including warmup and pool accounts"""
    try:
        # ===== WARMUP ACCOUNTS =====
        warmup_accounts = Account.query.filter_by(
            is_active=True,
            account_type='warmup'
        ).all()
        
        warmup_data = []
        for account in warmup_accounts:
            # Sent emails statistics
            total_sent = Email.query.filter_by(account_id=account.id).count()
            opened = Email.query.filter_by(account_id=account.id, is_opened=True).count()
            replied = Email.query.filter_by(account_id=account.id, is_replied=True).count()
            
            # Today's statistics
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_sent = Email.query.filter(
                Email.account_id == account.id,
                Email.sent_at >= today_start
            ).count()
            
            # Pending schedules for today
            today_pending = EmailSchedule.query.filter(
                EmailSchedule.account_id == account.id,
                EmailSchedule.schedule_date == datetime.utcnow().date(),
                EmailSchedule.status == 'pending'
            ).count()
            
            # Calculate rates
            open_rate = (opened / total_sent * 100) if total_sent > 0 else 0
            reply_rate = (replied / total_sent * 100) if total_sent > 0 else 0
            # Compute warmup score dynamically to avoid stale values
            computed_warmup_score = min(100, int((open_rate * 0.6 + reply_rate * 0.4) * 2))
            # Persist updated score (best effort; avoid failing the request)
            # try:
            #     if account.warmup_score != computed_warmup_score:
            #         account.warmup_score = computed_warmup_score
            #         db.session.commit()
            # except Exception:
            #     db.session.rollback()
            
            warmup_data.append({
                'id': account.id,
                'email': account.email,
                'warmup_day': account.warmup_day,
                'warmup_phase': account.get_warmup_phase(),
                'daily_limit': account.daily_limit,
                'warmup_target': account.warmup_target,
                'timezone': account.timezone,
                'today_sent': today_sent,
                'today_pending': today_pending,
                'total_sent': total_sent,
                'total_opened': opened,
                'total_replied': replied,
                'open_rate': round(open_rate, 1),
                'reply_rate': round(reply_rate, 1),
                'warmup_score': account.warmup_score,
                'progress_percentage': round((account.daily_limit / account.warmup_target * 100), 1) if account.warmup_target > 0 else 0
            })
        
        # ===== POOL ACCOUNTS =====
        pool_accounts = Account.query.filter_by(
            is_active=True,
            account_type='pool'
        ).all()
        
        pool_data = []
        for account in pool_accounts:
            # Received emails (emails sent TO this pool account)
            total_received = Email.query.filter_by(to_address=account.email).count()
            received_opened = Email.query.filter_by(to_address=account.email, is_opened=True).count()
            received_replied = Email.query.filter_by(to_address=account.email, is_replied=True).count()
            
            # Today's received
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_received = Email.query.filter(
                Email.to_address == account.email,
                Email.sent_at >= today_start
            ).count()
            
            # Engagement rates
            open_rate = (received_opened / total_received * 100) if total_received > 0 else 0
            reply_rate = (received_replied / total_received * 100) if total_received > 0 else 0
            
            pool_data.append({
                'id': account.id,
                'email': account.email,
                'timezone': account.timezone,
                'today_received': today_received,
                'total_received': total_received,
                'total_opened': received_opened,
                'total_replied': received_replied,
                'open_rate': round(open_rate, 1),
                'reply_rate': round(reply_rate, 1),
            })
        
        # ===== OVERALL STATISTICS =====
        total_emails_sent = Email.query.count()
        total_opened = Email.query.filter_by(is_opened=True).count()
        total_replied = Email.query.filter_by(is_replied=True).count()
        
        overall_open_rate = (total_opened / total_emails_sent * 100) if total_emails_sent > 0 else 0
        overall_reply_rate = (total_replied / total_emails_sent * 100) if total_emails_sent > 0 else 0
        
        # Today's statistics
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_sent = Email.query.filter(Email.sent_at >= today_start).count()
        today_opened = Email.query.filter(
            Email.sent_at >= today_start,
            Email.is_opened == True
        ).count()
        today_replied = Email.query.filter(
            Email.sent_at >= today_start,
            Email.is_replied == True
        ).count()
        
        # Pending schedules
        total_pending = EmailSchedule.query.filter(
            EmailSchedule.schedule_date == datetime.utcnow().date(),
            EmailSchedule.status == 'pending'
        ).count()
        
        return jsonify({
            'overall': {
                'total_warmup_accounts': len(warmup_data),
                'total_pool_accounts': len(pool_data),
                'total_emails_sent': total_emails_sent,
                'total_opened': total_opened,
                'total_replied': total_replied,
                'overall_open_rate': round(overall_open_rate, 1),
                'overall_reply_rate': round(overall_reply_rate, 1),
                'today_sent': today_sent,
                'today_opened': today_opened,
                'today_replied': today_replied,
                'today_pending': total_pending
            },
            'warmup_accounts': warmup_data,
            'pool_accounts': pool_data,
            'last_updated': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# NEW: HTML DASHBOARD VIEW
# ============================================

@analytics_bp.route('/dashboard', methods=['GET'])
@analytics_bp.route('/', methods=['GET'])  # Make this the default route
def analytics_dashboard():
    """Render beautiful HTML dashboard"""
    
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Email Warmup Analytics Dashboard — Light</title>
  <style>
    :root {
      --bg: #f6f7fb;
      --card: #ffffff;
      --text: #1f2937; /* slate-800 */
      --muted: #6b7280; /* slate-500 */
      --subtle: #9aa3b2; /* slate-400 */
      --primary: #4f46e5; /* indigo-600 */
      --primary-50: #eef2ff; /* indigo-50 */
      --primary-100: #e0e7ff; /* indigo-100 */
      --accent: #06b6d4; /* cyan-500 */
      --success: #16a34a; /* green-600 */
      --warning: #d97706; /* amber-600 */
      --danger: #dc2626; /* red-600 */
      --ring: rgba(79,70,229,0.12);
      --shadow: 0 8px 30px rgba(15, 23, 42, 0.08);
      --radius: 14px;
      --radius-sm: 10px;
      --radius-lg: 18px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    html, body { height: 100%; }

    body {
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, "Helvetica Neue", Arial, "Apple Color Emoji", "Segoe UI Emoji";
      color: var(--text);
      background: radial-gradient(1200px 800px at 10% -10%, var(--primary-50), transparent),
                  radial-gradient(1000px 700px at 110% -10%, #ecfeff, transparent),
                  var(--bg);
      padding: 28px;
      letter-spacing: 0.01em;
    }

    .container { max-width: 1200px; margin: 0 auto; }

    /* Header */
    .header {
      background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(255,255,255,0.82));
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1px solid #eef2f7;
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow);
      padding: 28px 28px 22px;
    }

    .header h1 {
      font-size: 28px;
      font-weight: 750;
      letter-spacing: -0.02em;
      display: flex; align-items: center; gap: 10px;
    }

    .header p {
      color: var(--muted);
      margin-top: 6px;
      font-size: 15px;
    }

    .header-actions { margin-top: 18px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

    .button {
      appearance: none; border: 0; cursor: pointer;
      padding: 10px 16px; font-weight: 600; font-size: 14px;
      border-radius: 12px; transition: transform .15s ease, box-shadow .2s ease, background .2s ease;
      display: inline-flex; align-items: center; gap: 8px;
      box-shadow: 0 2px 0 rgba(79,70,229,0.08), 0 8px 24px rgba(79,70,229,0.12);
      background: linear-gradient(180deg, var(--primary), #4338ca);
      color: white;
    }
    .button:hover { transform: translateY(-1px); box-shadow: 0 3px 0 rgba(79,70,229,0.1), 0 14px 36px rgba(79,70,229,0.2); }
    .button:active { transform: translateY(0); }

    .subtle { background: #f1f5f9; color: #0f172a; box-shadow: none; }
    .subtle:hover { background: #e2e8f0; }

    .last-updated { color: var(--subtle); font-size: 13px; }

    /* Stats */
    .stats-grid {
      display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      margin-top: 22px; margin-bottom: 26px;
    }

    .stat-card {
      background: var(--card);
      border: 1px solid #eef2f7;
      border-radius: var(--radius);
      padding: 18px 18px 16px;
      box-shadow: var(--shadow);
      transition: transform .18s ease, box-shadow .2s ease;
    }
    .stat-card:hover { transform: translateY(-3px); box-shadow: 0 12px 34px rgba(2,6,23,0.12); }

    .stat-label { color: var(--muted); font-size: 12px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em; }
    .stat-value { font-size: 32px; font-weight: 800; margin-top: 8px; letter-spacing: -0.02em; }
    .stat-subtext { margin-top: 6px; color: var(--subtle); font-size: 13px; }

    /* Section Title */
    .section-title {
      background: var(--card);
      border: 1px solid #eef2f7;
      border-radius: var(--radius);
      padding: 14px 18px;
      box-shadow: var(--shadow);
      margin: 12px 0 10px;
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
    }
    .section-title h2 { font-size: 18px; display: flex; align-items: center; gap: 10px; }

    .badge {
      font-size: 12px; font-weight: 700; padding: 6px 10px; border-radius: 999px; border: 1px solid transparent;
    }
    .badge-warmup { background: #fff7ed; color: #c2410c; border-color: #ffedd5; }
    .badge-pool { background: #f0f9ff; color: #0369a1; border-color: #e0f2fe; }

    /* Tables */
    .table-container {
      background: var(--card);
      border: 1px solid #eef2f7;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: clip;
    }

    table { width: 100%; border-collapse: collapse; }

    thead th {
      position: sticky; top: 0; z-index: 1;
      background: linear-gradient(180deg, #fafbff, #f4f6fd);
      color: #475569; text-transform: uppercase; font-size: 12px; letter-spacing: 0.06em;
      padding: 14px 16px; border-bottom: 1px solid #e5e7eb;
    }

    tbody td { padding: 16px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
    tbody tr:hover { background: #fafafa; }

    .email-strong { font-weight: 700; letter-spacing: -0.01em; }
    .muted { color: var(--muted); font-size: 12px; }

    /* Progress */
    .progress {
      display: flex; flex-direction: column; gap: 6px; min-width: 220px;
    }
    .progress-bar { width: 100%; height: 10px; background: #eef2f7; border-radius: 999px; overflow: hidden; }
    .progress-fill { height: 100%; background: linear-gradient(90deg, #22c55e, #16a34a); border-radius: 999px; transition: width .3s ease; }

    /* Metrics */
    .metric { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 10px; font-weight: 700; font-size: 12px; border: 1px solid #eef2f7; }
    .metric-good { background: #ecfdf5; color: #065f46; }
    .metric-medium { background: #fffbeb; color: #78350f; }
    .metric-low { background: #fef2f2; color: #7f1d1d; }

    /* Score */
    .score { font-size: 22px; font-weight: 800; letter-spacing: -0.02em; }

    /* States */
    .loading {
      text-align: center; color: var(--muted); padding: 48px 0;
    }
    .spinner { width: 48px; height: 48px; border: 4px solid rgba(15,23,42,0.06); border-top-color: var(--primary); border-radius: 999px; animation: spin 1s linear infinite; margin: 0 auto; }
    @keyframes spin { to { transform: rotate(360deg); } }

    .error {
      background: #fee2e2; color: #7f1d1d; border: 1px solid #fecaca;
      border-radius: 12px; padding: 14px 16px; margin: 12px 0;
    }

    .empty-state { text-align: center; padding: 48px 18px; color: var(--muted); }
    .empty-state-icon { font-size: 56px; margin-bottom: 8px; }

    /* Small utility helpers */
    .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .col { display: flex; flex-direction: column; gap: 6px; }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div class="header">
      <h1>📧 Email Warmup Analytics</h1>
      <p>Clean, real‑time visibility into warmup campaigns and pool accounts.</p>
      <div class="header-actions">
        <button class="button" onclick="loadDashboard()" id="refresh-btn">
          <span id="refresh-icon">🔄</span>
          Refresh Data
        </button>
        <span class="last-updated" id="last-updated"></span>
      </div>
    </div>

    <!-- Loading State -->
    <div id="loading" class="loading">
      <div class="spinner"></div>
      <p style="margin-top:12px">Loading dashboard data…</p>
    </div>

    <!-- Error -->
    <div id="error" class="error" style="display:none"></div>

    <!-- Content -->
    <div id="dashboard-content" style="display:none">
      <!-- Stats -->
      <div class="stats-grid" id="overall-stats"></div>

      <!-- Warmup Accounts -->
      <div class="section-title">
        <h2><span>🔥</span> Warmup Accounts</h2>
        <span class="badge badge-warmup" id="warmup-count">0 accounts</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Email Account</th>
              <th>Warmup Progress</th>
              <th>Today</th>
              <th>Total Sent</th>
              <th>Engagement</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody id="warmup-table"></tbody>
        </table>
      </div>

      <!-- Pool Accounts -->
      <div class="section-title">
        <h2><span>💧</span> Pool Accounts</h2>
        <span class="badge badge-pool" id="pool-count">0 accounts</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Email Account</th>
              <th>Timezone</th>
              <th>Today Received</th>
              <th>Total Received</th>
              <th>Opened</th>
              <th>Replied</th>
              <th>Engagement Rate</th>
            </tr>
          </thead>
          <tbody id="pool-table"></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    async function loadDashboard() {
      const loading = document.getElementById('loading');
      const error = document.getElementById('error');
      const content = document.getElementById('dashboard-content');
      const refreshIcon = document.getElementById('refresh-icon');

      loading.style.display = 'block';
      error.style.display = 'none';
      content.style.display = 'none';
      refreshIcon.textContent = '⏳';

      try {
        const res = await fetch('/api/analytics/dashboard/data');
        if (!res.ok) throw new Error('Failed to fetch data');
        const data = await res.json();

        renderOverallStats(data.overall);
        renderWarmupAccounts(data.warmup_accounts);
        renderPoolAccounts(data.pool_accounts);

        const lastUpdated = new Date(data.last_updated);
        document.getElementById('last-updated').textContent = `Last updated: ${lastUpdated.toLocaleString()}`;

        loading.style.display = 'none';
        content.style.display = 'block';
        refreshIcon.textContent = '🔄';
      } catch (e) {
        error.textContent = `Error: ${e.message}. Please check if the server is running.`;
        error.style.display = 'block';
        loading.style.display = 'none';
        document.getElementById('refresh-icon').textContent = '❌';
      }
    }

    function statCard(label, value, subtext) {
      return `
        <div class="stat-card">
          <div class="stat-label">${label}</div>
          <div class="stat-value">${value}</div>
          <div class="stat-subtext">${subtext}</div>
        </div>
      `;
    }

    function renderOverallStats(stats) {
      const c = document.getElementById('overall-stats');
      c.innerHTML = [
        statCard('Warmup Accounts', stats.total_warmup_accounts, 'Active campaigns'),
        statCard('Pool Accounts', stats.total_pool_accounts, 'Recipient pool'),
        statCard('Total Emails Sent', stats.total_emails_sent, `Today: ${stats.today_sent} · Pending: ${stats.today_pending}`),
        statCard('Open Rate', `${stats.overall_open_rate}%`, `${stats.total_opened} emails opened`),
        statCard('Reply Rate', `${stats.overall_reply_rate}%`, `${stats.total_replied} replies received`),
      ].join('');
    }

    function renderWarmupAccounts(accounts) {
      const tbody = document.getElementById('warmup-table');
      const badge = document.getElementById('warmup-count');
      badge.textContent = `${accounts.length} accounts`;

      if (!accounts.length) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="empty-state">
              <div class="empty-state-icon">📭</div>
              <div>No warmup accounts yet</div>
              <div class="muted">Add accounts via OAuth to start warming up</div>
            </td>
          </tr>`;
        return;
      }

      tbody.innerHTML = accounts.map(acc => `
        <tr>
          <td>
            <div class="col">
              <span class="email-strong">${acc.email}</span>
              <span class="muted">${acc.warmup_phase}</span>
            </div>
          </td>
          <td>
            <div class="progress">
              <div class="row">
                <span class="muted">Day ${acc.warmup_day}</span>
                <span style="font-weight:700">${acc.daily_limit}/${acc.warmup_target} emails</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill" style="width:${acc.progress_percentage}%"></div>
              </div>
              <span class="muted">${acc.progress_percentage}% of target</span>
            </div>
          </td>
          <td>
            <div class="col">
              <span style="font-size:18px; font-weight:800">${acc.today_sent}</span>
              <span class="muted">${acc.today_pending} pending</span>
            </div>
          </td>
          <td><span style="font-size:18px; font-weight:800">${acc.total_sent}</span></td>
          <td>
            <div class="col" style="gap:8px">
              <span class="metric ${getMetricClass(acc.open_rate)}">📖 ${acc.open_rate}%</span>
              <span class="metric ${getMetricClass(acc.reply_rate)}">💬 ${acc.reply_rate}%</span>
            </div>
          </td>
          <td>
            <div class="score" style="color:${getScoreColor(acc.warmup_score)}">${acc.warmup_score}</div>
            <div class="muted">/100</div>
          </td>
        </tr>
      `).join('');
    }

    function renderPoolAccounts(accounts) {
      const tbody = document.getElementById('pool-table');
      const badge = document.getElementById('pool-count');
      badge.textContent = `${accounts.length} accounts`;

      if (!accounts.length) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="empty-state">
              <div class="empty-state-icon">💧</div>
              <div>No pool accounts yet</div>
              <div class="muted">Add pool accounts to receive warmup emails</div>
            </td>
          </tr>`;
        return;
      }

      tbody.innerHTML = accounts.map(acc => `
        <tr>
          <td><span class="email-strong">${acc.email}</span></td>
          <td><span class="muted">${acc.timezone}</span></td>
          <td><span style="font-size:18px; font-weight:800">${acc.today_received}</span></td>
          <td><span style="font-size:18px; font-weight:800">${acc.total_received}</span></td>
          <td><span class="metric ${getMetricClass(acc.open_rate)}">${acc.total_opened} (${acc.open_rate}%)</span></td>
          <td><span class="metric ${getMetricClass(acc.reply_rate)}">${acc.total_replied} (${acc.reply_rate}%)</span></td>
          <td>
            <div style="font-weight:700">Open: ${acc.open_rate}% · Reply: ${acc.reply_rate}%</div>
          </td>
        </tr>
      `).join('');
    }

    function getMetricClass(v) {
      if (v >= 50) return 'metric-good';
      if (v >= 25) return 'metric-medium';
      return 'metric-low';
    }

    function getScoreColor(s) {
      if (s >= 70) return '#16a34a';
      if (s >= 40) return '#d97706';
      return '#dc2626';
    }

    // Auto-refresh
    setInterval(loadDashboard, 30000);
    loadDashboard();
  </script>
</body>
</html>

    """
    
    return render_template_string(html_template)
