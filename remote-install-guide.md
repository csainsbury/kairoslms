# KairosLMS Remote Installation Guide

This guide provides step-by-step instructions for installing and configuring KairosLMS on a fresh Ubuntu 22.04 LTS server.

## Prerequisites

- A remote server running Ubuntu 22.04 LTS
- Root or sudo access to the server
- Domain name pointing to the server (optional, but recommended)
- API keys for required services:
  - Anthropic API key
  - Gmail API credentials
  - Google Calendar API credentials
  - Todoist API key

## 1. Initial Server Setup

Connect to your server via SSH:

```bash
ssh username@your_server_ip
```

Update the system packages:

```bash
sudo apt update
sudo apt upgrade -y
```

Set up the server timezone:

```bash
sudo timedatectl set-timezone UTC
```

Install basic requirements:

```bash
sudo apt install -y curl wget git vim
```

## 2. Install Docker and Docker Compose

Install Docker:

```bash
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update
sudo apt install -y docker-ce
```

Add your user to the docker group to run Docker without sudo:

```bash
sudo usermod -aG docker ${USER}
```

Log out and log back in so that your group membership is re-evaluated.

Install Docker Compose:

```bash
sudo curl -L "https://github.com/docker/compose/releases/download/v2.17.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

Verify installations:

```bash
docker --version
docker-compose --version
```

## 3. Configure Firewall

Set up firewall rules with UFW:

```bash
sudo apt install -y ufw
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw allow 8000  # KairosLMS default port
sudo ufw enable
```

Verify firewall status:

```bash
sudo ufw status
```

## 4. Clone the KairosLMS Repository

Create a directory for the application:

```bash
mkdir -p ~/kairoslms
cd ~/kairoslms
```

Clone the repository:

```bash
git clone https://github.com/yourusername/kairoslms.git .
```

## 5. Configure Environment Variables

Create the environment configuration file:

```bash
cp config/.env.example config/.env
```

Edit the configuration file with your preferred text editor:

```bash
vim config/.env
```

Add the following environment variables (customize as needed):

```bash
# Database Settings
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_NAME=kairoslms
DB_HOST=db
DB_PORT=5432

# API Settings
SECRET_KEY=your_generated_secret_key

# Gmail API Settings
GMAIL_CREDENTIALS_FILE=/app/config/gmail_credentials.json
GMAIL_TOKEN_FILE=/app/config/gmail_token.json

# Google Calendar API Settings
CALENDAR_CREDENTIALS_FILE=/app/config/calendar_credentials.json
CALENDAR_TOKEN_FILE=/app/config/calendar_token.json

# Todoist API Settings
TODOIST_API_KEY=your_todoist_api_key

# LLM Settings
ANTHROPIC_API_KEY=your_anthropic_api_key

# Backup Settings
ENABLE_BACKUPS=true
BACKUP_ON_SHUTDOWN=true
DB_BACKUP_INTERVAL_DAYS=1
KEEP_BACKUPS_DAYS=30

# Ingestion Settings
EMAIL_INGESTION_INTERVAL_MINUTES=1440
CALENDAR_INGESTION_INTERVAL_MINUTES=60
TODOIST_INGESTION_INTERVAL_MINUTES=30

# Processing Settings
STATUS_OVERVIEW_INTERVAL_HOURS=12
TASK_PRIORITIZATION_INTERVAL_MINUTES=30
LLM_ENHANCED_PROCESSING_INTERVAL_HOURS=24
```

Generate a secure random secret key:

```bash
openssl rand -hex 32
```

Copy the output and replace `your_generated_secret_key` in the .env file with this value.

## 6. Set Up API Credentials

### Gmail and Calendar API Credentials

You have two authentication options for Gmail and Calendar APIs:

#### Option A: OAuth 2.0 Authentication (Requires Browser Access)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Gmail API and Google Calendar API
4. Create OAuth 2.0 credentials (Desktop client type)
5. Download the credentials JSON file
6. Create the config directory and upload the credentials:

```bash
mkdir -p ~/kairoslms/config/credentials
```

Upload the credentials files to the server:

```bash
# From your local machine
scp path/to/your/gmail_credentials.json username@your_server_ip:~/kairoslms/config/credentials/gmail_credentials.json
scp path/to/your/calendar_credentials.json username@your_server_ip:~/kairoslms/config/credentials/calendar_credentials.json
```

Update the .env file to specify OAuth authentication:

```bash
vim config/.env
```

Set the following variables:

```
# Gmail settings
GMAIL_AUTH_METHOD=oauth
GMAIL_CREDENTIALS_FILE=/app/config/credentials/gmail_credentials.json
GMAIL_TOKEN_FILE=/app/config/credentials/gmail_token.json

# Calendar settings
CALENDAR_AUTH_METHOD=oauth
CALENDAR_CREDENTIALS_FILE=/app/config/credentials/calendar_credentials.json
CALENDAR_TOKEN_FILE=/app/config/credentials/calendar_token.json
```

#### Option B: Service Account Authentication (Recommended for Headless Servers)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Gmail API and Google Calendar API
4. Create a Service Account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Give it a name (e.g., "kairoslms-service-account")
   - Grant necessary roles (e.g., Gmail API User, Calendar API User)
   - Click "Done"
5. Create credentials for the service account:
   - Click on the service account you just created
   - Go to the "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose JSON format and click "Create"
   - Download the service account key file
6. Enable domain-wide delegation for the service account:
   - Click on the service account
   - Click "Edit"
   - Enable "Domain-wide delegation"
   - Save

7. In Google Workspace or Gmail admin settings:
   - Go to Security > API Controls
   - In the "Domain-wide Delegation" section, click "Manage Domain-wide Delegation"
   - Add a new API client:
     - Client ID: (use the service account's client ID)
     - OAuth Scopes: https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/calendar.readonly

8. Upload the service account key file to the server:

```bash
mkdir -p ~/kairoslms/config/credentials
```

```bash
# From your local machine
scp path/to/your/service-account-key.json username@your_server_ip:~/kairoslms/config/credentials/google_service_account.json
```

9. Update the .env file to use service account authentication:

```bash
vim config/.env
```

Set the following variables:

```
# Gmail settings
GMAIL_AUTH_METHOD=service_account
GMAIL_SERVICE_ACCOUNT_FILE=/app/config/credentials/google_service_account.json
GMAIL_DELEGATED_EMAIL=your_email@example.com

# Calendar settings
CALENDAR_AUTH_METHOD=service_account
CALENDAR_SERVICE_ACCOUNT_FILE=/app/config/credentials/google_service_account.json
CALENDAR_DELEGATED_EMAIL=your_email@example.com
```

Replace `your_email@example.com` with the email address whose Gmail and Calendar data you want to access.

## 7. Create Directories for Data Persistence

Create directories for logs, backups, and persistent data:

```bash
mkdir -p ~/kairoslms/logs
mkdir -p ~/kairoslms/backups
mkdir -p ~/kairoslms/data
```

## 8. Modify Docker Compose Configuration

Edit the Docker Compose file to add volume mappings:

```bash
vim config/docker-compose.yml
```

Update the volumes section for the app service:

```yaml
volumes:
  - ./logs:/app/logs
  - ./backups:/app/backups
  - ./config:/app/config
  - ./data:/app/data
```

And for the database service:

```yaml
volumes:
  - ./data/postgres:/var/lib/postgresql/data
```

## 9. Start the Application

Build and start the containers:

```bash
cd ~/kairoslms
docker-compose -f config/docker-compose.yml up -d
```

Check if the containers are running:

```bash
docker-compose -f config/docker-compose.yml ps
```

View logs to ensure everything started correctly:

```bash
docker-compose -f config/docker-compose.yml logs -f
```

## 10. Configure Authentication for Google APIs

Depending on which authentication method you chose earlier (OAuth or Service Account), follow the appropriate instructions:

### For OAuth Authentication (Option A)

If you're using OAuth authentication, you'll need to generate and transfer token files. Since this is a headless server, use one of these approaches:

#### Method 1: Local Token Generation and Transfer

1. On your local development machine, run the authentication flow:

```bash
# Clone the repository locally if you haven't already
git clone https://github.com/yourusername/kairoslms.git
cd kairoslms

# Install required packages
pip install -r requirements.txt

# Copy your credential files to the local directory
mkdir -p config/credentials
cp /path/to/your/gmail_credentials.json config/credentials/
cp /path/to/your/calendar_credentials.json config/credentials/

# Create a simple authentication script
cat > authenticate_google.py << 'EOF'
from src.ingestion.email_ingestion import GmailClient
from src.ingestion.calendar_ingestion import CalendarClient

# Gmail authentication
print("Authenticating Gmail...")
gmail_client = GmailClient(
    credentials_file='config/credentials/gmail_credentials.json',
    token_file='config/credentials/gmail_token.json'
)
gmail_client.authenticate()
print("Gmail authentication successful! Token saved to config/credentials/gmail_token.json")

# Calendar authentication
print("Authenticating Google Calendar...")
calendar_client = CalendarClient(
    credentials_file='config/credentials/calendar_credentials.json',
    token_file='config/credentials/calendar_token.json'
)
calendar_client.authenticate()
print("Calendar authentication successful! Token saved to config/credentials/calendar_token.json")
EOF

# Run the authentication script
python authenticate_google.py
```

2. A browser window will open for each service. Complete the OAuth flow by:
   - Signing in with your Google account
   - Granting the requested permissions
   - Waiting for the "Authentication successful" message

3. After successful authentication, token files will be created. Transfer these token files to your remote server:

```bash
# From your local machine
scp config/credentials/gmail_token.json username@your_server_ip:~/kairoslms/config/credentials/
scp config/credentials/calendar_token.json username@your_server_ip:~/kairoslms/config/credentials/
```

#### Method 2: SSH Tunnel with X11 Forwarding

If you prefer to run the OAuth flow directly on the server:

1. Connect to your server with X11 forwarding:

```bash
ssh -X username@your_server_ip
```

2. Install required packages on the server:

```bash
sudo apt-get install -y xauth firefox
```

3. Create an authentication script:

```bash
cd ~/kairoslms
cat > authenticate_google.py << 'EOF'
from src.ingestion.email_ingestion import GmailClient
from src.ingestion.calendar_ingestion import CalendarClient

# Gmail authentication
print("Authenticating Gmail...")
gmail_client = GmailClient()
gmail_client.authenticate()
print("Gmail authentication successful!")

# Calendar authentication
print("Authenticating Google Calendar...")
calendar_client = CalendarClient()
calendar_client.authenticate()
print("Calendar authentication successful!")
EOF
```

4. Run the script:

```bash
# Make sure environment has correct Python path
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run authentication
python authenticate_google.py
```

5. Browser windows should open through X11 forwarding. Complete the authentication for each service.

### For Service Account Authentication (Option B)

If you've configured service account authentication in the `.env` file as outlined in Step 6, no additional authentication steps are required. The service account credentials will be used automatically when the application starts.

To verify the service account setup:

```bash
# Start a Python shell in the container
docker-compose -f config/docker-compose.yml exec app python

# Test authentication
>>> from src.ingestion.email_ingestion import GmailClient
>>> client = GmailClient()
>>> client.authenticate()
>>> # If no errors occur, authentication is working correctly
>>> exit()
```

If you see any errors, check:
1. The service account key file path is correct
2. Domain-wide delegation is properly configured in Google Workspace
3. The delegated email address is correct in your .env file

## 11. Set Up SSL/TLS (Optional but Recommended)

Install Certbot for Let's Encrypt certificates:

```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
```

Obtain a certificate:

```bash
sudo certbot --standalone -d yourdomain.com -d www.yourdomain.com
```

Create a reverse proxy with Nginx (install if needed):

```bash
sudo apt install -y nginx
```

Create a Nginx configuration file:

```bash
sudo vim /etc/nginx/sites-available/kairoslms
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/kairoslms /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 12. Set Up Automatic Backups and Updates

Create a backup script:

```bash
vim ~/kairoslms/scripts/backup.sh
```

Add the content:

```bash
#!/bin/bash
DATE=$(date +%Y-%m-%d)
cd ~/kairoslms
docker-compose -f config/docker-compose.yml exec -T db pg_dump -U postgres kairoslms > backups/kairoslms_db_$DATE.sql
tar -czf backups/kairoslms_backup_$DATE.tar.gz config data backups/kairoslms_db_$DATE.sql
```

Make it executable:

```bash
chmod +x ~/kairoslms/scripts/backup.sh
```

Set up a cron job for automatic backups:

```bash
crontab -e
```

Add the line:

```
0 0 * * * ~/kairoslms/scripts/backup.sh
```

## 13. Verify Installation

Check that the application is running properly:

```bash
curl http://localhost:8000/health
```

You should see a response like:

```json
{"status": "healthy"}
```

Access the web interface at http://yourdomain.com (or https://yourdomain.com if you set up SSL).

## 14. Monitoring Setup (Optional)

Install and configure Prometheus and Grafana for monitoring:

```bash
# Create monitoring directory
mkdir -p ~/monitoring
cd ~/monitoring

# Create docker-compose.yml for monitoring
cat > docker-compose.yml << EOF
version: '3'

services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana
    depends_on:
      - prometheus
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    restart: unless-stopped

volumes:
  grafana-data:
EOF

# Create prometheus config
cat > prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'kairoslms'
    static_configs:
      - targets: ['your_server_ip:8000']
EOF

# Start monitoring
docker-compose up -d
```

Access Grafana at http://yourdomain.com:3000 (default credentials: admin/admin).

## 15. Troubleshooting

### View logs:

```bash
docker-compose -f ~/kairoslms/config/docker-compose.yml logs -f
```

### Restart the application:

```bash
docker-compose -f ~/kairoslms/config/docker-compose.yml restart
```

### Check database connection:

```bash
docker-compose -f ~/kairoslms/config/docker-compose.yml exec db psql -U postgres -d kairoslms -c "SELECT 1;"
```

### Reset and rebuild containers:

```bash
docker-compose -f ~/kairoslms/config/docker-compose.yml down
docker-compose -f ~/kairoslms/config/docker-compose.yml up -d --build
```

## 16. Maintenance and Updates

### Pulling updates:

```bash
cd ~/kairoslms
git pull origin main
docker-compose -f config/docker-compose.yml down
docker-compose -f config/docker-compose.yml up -d --build
```

### Database backup:

```bash
cd ~/kairoslms
docker-compose -f config/docker-compose.yml exec db pg_dump -U postgres kairoslms > backups/kairoslms_db_$(date +%Y-%m-%d).sql
```

### Database restore:

```bash
cat backups/kairoslms_db_YYYY-MM-DD.sql | docker-compose -f config/docker-compose.yml exec -T db psql -U postgres -d kairoslms
```

## Conclusion

Your KairosLMS instance should now be running on your Ubuntu 22.04 server. The system automatically ingests data from email, calendar, and Todoist, processes it using Anthropic's Claude LLM, and provides actionable insights through the web interface.

For additional help or troubleshooting, refer to the project documentation or open an issue on the GitHub repository.