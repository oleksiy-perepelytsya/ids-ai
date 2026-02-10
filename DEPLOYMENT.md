# IDS Phase 1 - Deployment & Testing Guide

## Quick Deployment

### 1. Prerequisites Check

```bash
# Verify Docker is installed
docker --version
docker-compose --version

# Verify Git is installed (for cloning)
git --version
```

### 2. Setup Environment

```bash
# Navigate to IDS directory
cd ids

# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env  # or vim, code, etc.
```

### 3. Required API Keys

Get these before deploying:

**Telegram Bot Token:**
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow prompts to create bot
4. Copy token to `.env`

**Your Telegram User ID:**
1. Message [@userinfobot](https://t.me/userinfobot)
2. Copy your user ID
3. Add to `ALLOWED_TELEGRAM_USERS` in `.env`

**Gemini API Key:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create API key
3. Copy to `.env`

**Anthropic Claude API Key:**
1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create API key
3. Copy to `.env`

### 4. Configure .env

Minimal required configuration:

```bash
# .env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ALLOWED_TELEGRAM_USERS=12345
GEMINI_API_KEY=your_gemini_key
ANTHROPIC_API_KEY=your_claude_key

# Optional - defaults are fine
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=ids
CHROMADB_HOST=chromadb
CHROMADB_PORT=8000
REDIS_URL=redis://redis:6379
ROUND_LOGGING=true
MAX_ROUNDS=3
LOG_LEVEL=INFO
```

### 5. Build and Start

```bash
# Build containers
docker-compose build

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# Should see 4 containers running:
# - ids-app (your bot)
# - ids-mongodb
# - ids-chromadb
# - ids-redis
```

### 6. Verify Startup

```bash
# Watch logs
docker-compose logs -f ids

# You should see:
# - ids_starting
# - agents_created count=7
# - telegram_bot_running

# Exit logs with Ctrl+C
```

### 7. Test Bot

Open Telegram and:

1. Find your bot (search by username you gave @BotFather)
2. Send `/start`
3. You should get welcome message

If you see "⛔ Unauthorized" - check your user ID in .env

---

## Testing Checklist

### Basic Functionality

- [ ] Bot responds to `/start`
- [ ] Bot responds to `/help`
- [ ] Can register project: `/register_project test Test project`
- [ ] Can list projects: `/list_projects`
- [ ] Can switch project: `/project test`
- [ ] Can send question and get response

### Full Deliberation Test

```
You: Should I accept a charter at $45k/day for 6 months?

Expected flow:
1. Bot: "🏛️ Starting Parliament deliberation..."
2. Bot: "⏳ Round 1 in progress..."
3. Bot: "📊 Round 1 Complete" (if ROUND_LOGGING=true)
4. Bot: Either consensus or continues to Round 2
5. Bot: Final decision or dead-end prompt
```

### Dead-End Test

```
You: Give me an impossible question with conflicting requirements

Expected:
1. Multiple rounds
2. "⚠️ DEAD-END REACHED"
3. Shows diverging perspectives
4. Buttons: [Provide Feedback] [Restart Fresh]
```

### Commands Test

```bash
/status     # Should show current session
/history    # Should show past sessions
/cancel     # Should cancel active session
```

---

## Troubleshooting

### Bot Not Responding

**Check logs:**
```bash
docker-compose logs ids
```

**Common issues:**

1. **"unauthorized_access_attempt"**
   - Your user ID not in ALLOWED_TELEGRAM_USERS
   - Fix: Add your ID to .env and restart

2. **"telegram_bot_token invalid"**
   - Wrong bot token
   - Fix: Check token from @BotFather

3. **Container crashed**
   ```bash
   docker-compose restart ids
   ```

### API Errors

**Gemini API errors:**
```bash
# Check logs for "gemini_call_failed"
docker-compose logs ids | grep gemini

# Verify API key is valid
# Check quota at https://makersuite.google.com/
```

**Claude API errors:**
```bash
# Check logs for "claude_call_failed"
docker-compose logs ids | grep claude

# Verify API key
# Check credits at https://console.anthropic.com/
```

### Database Connection Issues

**MongoDB not connecting:**
```bash
# Check MongoDB is running
docker-compose ps mongodb

# Check logs
docker-compose logs mongodb

# Restart if needed
docker-compose restart mongodb ids
```

**ChromaDB not connecting:**
```bash
docker-compose ps chromadb
docker-compose restart chromadb ids
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Increase Docker memory limit
# Docker Desktop: Settings > Resources > Memory
```

---

## Development Mode

There are two docker-compose configurations:

### Production (`docker-compose.yml`)
- Uses pre-built images from registry
- No code volume mounts (code is baked into image)
- Faster, cleaner deployment

```bash
# Production deployment
docker compose pull
docker compose up -d
```

### Development (`docker-compose.dev.yml`)
- Builds image locally
- Mounts code directories for live reload
- Changes to code are reflected immediately

```bash
# Development with live reload
docker compose -f docker-compose.dev.yml up

# Rebuild after dependency changes
docker compose -f docker-compose.dev.yml up --build
```

**Important**: When using pre-built images (production), don't mount code volumes or you'll override the image contents with potentially outdated local files.

### View Live Logs

```bash
# All services
docker-compose logs -f

# Just IDS
docker-compose logs -f ids

# Just errors
docker-compose logs ids | grep ERROR
```

### Database Inspection

**MongoDB:**
```bash
# Connect to MongoDB
docker exec -it ids-mongodb mongosh

# Use IDS database
use ids

# View collections
show collections

# View sessions
db.sessions.find().pretty()

# View projects
db.projects.find().pretty()

# Exit
exit
```

**ChromaDB:**
```bash
# ChromaDB runs on http://localhost:8000
# No direct CLI, but you can check health
curl http://localhost:8000/api/v1/heartbeat
```

---

## Stopping & Cleanup

### Stop Everything

```bash
# Stop containers (keep data)
docker-compose down

# Stop and remove volumes (delete data)
docker-compose down -v
```

### Restart Fresh

```bash
# Complete reset
docker-compose down -v
docker-compose up -d --build
```

### View Disk Usage

```bash
docker system df
```

---

## CI/CD Deployment (VPS with Pre-built Containers)

For small VPS instances that can't build Docker images locally, use this automated deployment approach.

### How It Works

1. **GitHub Actions builds** the Docker image on GitHub's runners
2. **Pushes** the image to GitHub Container Registry (ghcr.io)
3. **SSH into VPS** and pulls the pre-built image
4. **Restarts** containers with the new image

### Initial VPS Setup

```bash
# On your VPS
cd ~
git clone https://github.com/oleksiy-perepelytsya/ids-ai.git
cd ids-ai

# Create .env file
cp dotenv_example .env
nano .env  # Add your API keys

# First deployment - pull pre-built image
docker compose pull
docker compose up -d
```

### GitHub Secrets Configuration

Add these to your repository (Settings → Secrets and variables → Actions):

- `SSH_HOST`: Your VPS IP or hostname
- `SSH_USERNAME`: SSH username (e.g., `oleksiy_perepelytsya`)
- `SSH_PRIVATE_KEY`: Your SSH private key
- `SSH_PORT`: SSH port (usually 22)

### Automatic Deployments

Every push to `master` branch will:
1. Build Docker image in GitHub Actions
2. Push to GitHub Container Registry
3. Deploy to your VPS automatically

### Manual Deployment

```bash
# On VPS, pull latest image and restart
cd /home/oleksiy_perepelytsya/ids-ai
git pull origin master
docker compose pull
docker compose up -d
```

### View Deployment Logs

Check GitHub Actions tab in your repository to see build/deploy progress.

### Troubleshooting CI/CD

**Image pull fails:**
```bash
# Login to registry manually
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_USERNAME --password-stdin
docker compose pull
```

**Deployment hangs:**
```bash
# Check SSH connection
ssh -i ~/.ssh/id_rsa user@your-vps-ip

# Check disk space on VPS
df -h
docker system df
```

**Clean up old images:**
```bash
docker image prune -af
```

---

## Production Deployment

### Security Checklist

- [ ] Change default MongoDB password
- [ ] Use secrets management for API keys (not .env in prod)
- [ ] Setup firewall rules
- [ ] Enable HTTPS if exposing webhooks
- [ ] Regular backups of MongoDB
- [ ] Monitor API usage/costs
- [ ] Setup log aggregation
- [ ] Alert on errors

### Monitoring

Add to docker-compose.yml:

```yaml
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

### Backup Script

```bash
#!/bin/bash
# backup.sh

# Backup MongoDB
docker exec ids-mongodb mongodump --out /tmp/backup
docker cp ids-mongodb:/tmp/backup ./backups/$(date +%Y%m%d)

# Backup ChromaDB data
docker cp ids-chromadb:/chroma/chroma ./backups/chroma_$(date +%Y%m%d)
```

---

## Performance Tuning

### Adjust Thresholds

Edit `ids/config/thresholds.yaml`:

```yaml
consensus:
  confidence_threshold:
    round_1: 80.0  # Lower = easier consensus
    round_2: 70.0
    round_3: 65.0
```

Then restart:
```bash
docker-compose restart ids
```

### Disable Round Logging

For faster responses:
```bash
# .env
ROUND_LOGGING=false
```

### Reduce Max Rounds

```bash
# .env
MAX_ROUNDS=2  # Default is 3
```

---

## Common Tasks

### Add New User

```bash
# Edit .env
ALLOWED_TELEGRAM_USERS=12345,67890

# Restart
docker-compose restart ids
```

### View User Activity

```bash
docker exec -it ids-mongodb mongosh

use ids
db.sessions.aggregate([
  { $group: { _id: "$telegram_user_id", count: { $sum: 1 } } }
])
```

### Clear Old Sessions

```bash
docker exec -it ids-mongodb mongosh

use ids
db.sessions.deleteMany({
  created_at: { $lt: new Date(Date.now() - 30*24*60*60*1000) }
})
```

---

## Getting Help

### Check System Health

```bash
# All containers running?
docker-compose ps

# Any errors in logs?
docker-compose logs ids | grep -i error

# Database connections OK?
docker-compose exec ids python -c "
from ids.storage import MongoSessionStore
import asyncio
asyncio.run(MongoSessionStore().sessions.find_one({}))
print('MongoDB OK')
"
```

### Debug Mode

```bash
# Enable debug logging
# .env
LOG_LEVEL=DEBUG

docker-compose restart ids
docker-compose logs -f ids
```

### Report Issues

When reporting issues, include:

1. `docker-compose logs ids` output
2. Your `.env` (without API keys)
3. Bot command you tried
4. Expected vs actual behavior

---

## Success Indicators

You know it's working when:

✅ All 4 containers running
✅ No errors in logs
✅ Bot responds to /start
✅ Can complete full deliberation
✅ Reaches consensus or dead-end appropriately
✅ Round logging works (if enabled)
✅ Projects can be registered and switched
✅ Sessions persist in MongoDB

**Ready to test! 🚀**
