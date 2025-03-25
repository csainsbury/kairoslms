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

### Gmail API Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Gmail API
4. Create OAuth 2.0 credentials
5. Download the credentials JSON file
6. Create the config directory and upload the credentials:

```bash
mkdir -p ~/kairoslms/config/credentials
```

Upload the credentials file to the server and rename it:

```bash
# From your local machine
scp path/to/your/credentials.json username@your_server_ip:~/kairoslms/config/credentials/gmail_credentials.json
```

### Google Calendar API Credentials

1. In the same Google Cloud project, enable the Google Calendar API
2. Use the same OAuth 2.0 credentials or create new ones
3. Download the credentials JSON file (if using new credentials)
4. Upload to the server:

```bash
# From your local machine
scp path/to/your/credentials.json username@your_server_ip:~/kairoslms/config/credentials/calendar_credentials.json
```

Update the .env file to point to the correct paths:

```bash
vim config/.env
```

Change the credential file paths:

```
GMAIL_CREDENTIALS_FILE=/app/config/credentials/gmail_credentials.json
GMAIL_TOKEN_FILE=/app/config/credentials/gmail_token.json
CALENDAR_CREDENTIALS_FILE=/app/config/credentials/calendar_credentials.json
CALENDAR_TOKEN_FILE=/app/config/credentials/calendar_token.json
```

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

## 10. Initialize OAuth Authentication

For Gmail and Calendar APIs, you need to authenticate with Google:

```bash
# Access the app container
docker-compose -f config/docker-compose.yml exec app /bin/bash

# Run the authentication script
python -c "from src.ingestion.email_ingestion import GmailClient; client = GmailClient(); client.authenticate()"
python -c "from src.ingestion.calendar_ingestion import CalendarClient; client = CalendarClient(); client.authenticate()"
```

Follow the authentication flow by copying the URL to your local browser, logging in with Google, and pasting the authorization code back into the terminal.

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