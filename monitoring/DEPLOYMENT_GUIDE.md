# Production Deployment Guide

**Last Updated**: February 8, 2026  
**Version**: 1.0  
**Status**: Production-Ready  

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Deployment Methods](#deployment-methods)
5. [Configuration](#configuration)
6. [Security Checklist](#security-checklist)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [Scaling](#scaling)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

## Overview

This guide provides comprehensive instructions for deploying the Trading Engine in production environments. The system is designed for:

- **High Availability**: Multi-container architecture with health checks
- **Scalability**: Horizontal scaling with load balancing
- **Observability**: Integrated logging, metrics, and tracing
- **Security**: API authentication, rate limiting, secure defaults
- **Resilience**: Automatic recovery, circuit breakers, retries

## Architecture

### Components

```
<<<<<<< HEAD
ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ
Ôöé                      Production Environment                      Ôöé
Ôö£ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöñ
Ôöé                                                                   Ôöé
Ôöé  ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ   Ôöé
Ôöé  Ôöé              Trading Engine (Container)                   Ôöé   Ôöé
Ôöé  Ôöé  ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  Python 3.11 + Required Dependencies              Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  - Data Loading & Preprocessing                   Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  - Strategy (Pair Trading)                        Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  - Risk Management                                Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  - Order Execution (IBKR)                         Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  - Monitoring & Dashboard (Flask)                 Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  - JSON Logging                                   Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  - Dashboard Caching                              Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  Ôöé  - API Security (Rate Limit + Auth)               Ôöé  Ôöé   Ôöé
Ôöé  Ôöé  ÔööÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÿ  Ôöé   Ôöé
Ôöé  Ôöé  Port: 5000                                             Ôöé   Ôöé
Ôöé  ÔööÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÿ   Ôöé
Ôöé                                 Ôöé                                 Ôöé
Ôöé  ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔö╝ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ    Ôöé
Ôöé  Ôöé                              Ôöé                          Ôöé    Ôöé
Ôöé  Ôû╝                              Ôû╝                          Ôû╝    Ôöé
Ôöé
Ôöé  ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ  ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ  ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ Ôöé
Ôöé  Ôöé   Redis Cache  Ôöé  Ôöé   Prometheus     Ôöé  Ôöé  ELK Stack      Ôöé Ôöé
Ôöé  Ôöé   - Sessions   Ôöé  Ôöé   - Metrics      Ôöé  Ôöé  - Logs         Ôöé Ôöé
Ôöé  Ôöé   - Cache      Ôöé  Ôöé   - Dashboards   Ôöé  Ôöé  - Analysis     Ôöé Ôöé
Ôöé  Ôöé   Port: 6379   Ôöé  Ôöé   Port: 9090     Ôöé  Ôöé  Port: 9200/5601
Ôöé  ÔööÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÿ  ÔööÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÿ  ÔööÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÿ Ôöé
Ôöé         Ôöé                     Ôöé                     Ôöé             Ôöé
Ôöé  ÔöîÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔö┤ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔö┤ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔö┤ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÉ    Ôöé
Ôöé  Ôöé           Shared Docker Network (bridge)                 Ôöé    Ôöé
Ôöé  ÔööÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÿ    Ôöé
Ôöé                                                                   Ôöé
ÔööÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÿ
=======
┌─────────────────────────────────────────────────────────────────┐
│                      Production Environment                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Trading Engine (Container)                   │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  Python 3.11 + Required Dependencies              │  │   │
│  │  │  - Data Loading & Preprocessing                   │  │   │
│  │  │  - Strategy (Pair Trading)                        │  │   │
│  │  │  - Risk Management                                │  │   │
│  │  │  - Order Execution (IBKR)                         │  │   │
│  │  │  - Monitoring & Dashboard (Flask)                 │  │   │
│  │  │  - JSON Logging                                   │  │   │
│  │  │  - Dashboard Caching                              │  │   │
│  │  │  - API Security (Rate Limit + Auth)               │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │  Port: 5000                                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                 │                                 │
│  ┌──────────────────────────────┼──────────────────────────┐    │
│  │                              │                          │    │
│  ▼                              ▼                          ▼    │
│
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │   Redis Cache  │  │   Prometheus     │  │  ELK Stack      │ │
│  │   - Sessions   │  │   - Metrics      │  │  - Logs         │ │
│  │   - Cache      │  │   - Dashboards   │  │  - Analysis     │ │
│  │   Port: 6379   │  │   Port: 9090     │  │  Port: 9200/5601
│  └────────────────┘  └──────────────────┘  └─────────────────┘ │
│         │                     │                     │             │
│  ┌──────┴─────────────────────┴─────────────────────┴──────┐    │
│  │           Shared Docker Network (bridge)                 │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
>>>>>>> origin/main
```

### Services

| Service | Purpose | Port | Container |
|---------|---------|------|-----------|
| Trading Engine | Main application | 5000 | trading-engine |
| Redis | Caching | 6379 | trading-redis |
| Prometheus | Metrics | 9090 | trading-prometheus |
| Grafana | Visualization | 3000 | trading-grafana |
| Elasticsearch | Log storage | 9200 | trading-elasticsearch |
| Kibana | Log visualization | 5601 | trading-kibana |

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows (with WSL2)
- **CPU**: 4+ cores (8+ recommended for production)
- **Memory**: 8GB minimum (16GB recommended)
- **Disk**: 50GB+ for logs and data (100GB+ recommended)
- **Network**: 100Mbps+ connection recommended

### Software Requirements

- **Docker**: 20.10+ (`docker --version`)
- **Docker Compose**: 1.29+ (`docker-compose --version`)
- **Git**: 2.20+ (`git --version`)
- **Python**: 3.11+ (for local development)

### API Credentials

You'll need:
- ****Broker API Key** (IBKR TWS/Gateway)
- **Exchange API Secret**
- **Optional**: Webhook URLs for notifications

## Deployment Methods

### Method 1: Docker Compose (Recommended for Single Server)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/trading-engine.git
cd trading-engine

# 2. Create environment file
cp config/.env.example .env
# Edit .env with your credentials
nano .env

# 3. Create/update configuration files
mkdir -p config/grafana/{dashboards,datasources}
mkdir -p config/prometheus

# 4. Build and start services
docker-compose up -d

# 5. Verify services are healthy
docker-compose ps
docker-compose logs -f

# 6. Access dashboards
# - Trading Dashboard: http://localhost:5000
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
# - Kibana: http://localhost:5601
```

### Method 2: Kubernetes (Recommended for Multi-Server)

```bash
# 1. Create namespace
kubectl create namespace trading-engine

# 2. Create ConfigMap from .env
kubectl create configmap trading-config --from-file=config/ \
  -n trading-engine

# 3. Create Secrets (sensitive data)
kubectl create secret generic trading-secrets \
  --from-literal=ibkr-host=$IBKR_HOST \
  --from-literal=ibkr-port=$IBKR_PORT \
  -n trading-engine

# 4. Deploy using Helm (optional)
helm install trading-engine ./helm/trading-engine \
  -n trading-engine

# 5. Verify deployment
kubectl get pods -n trading-engine
kubectl logs -f deployment/trading-engine -n trading-engine
```

### Method 3: Manual Installation

```bash
# 1. Install system dependencies
sudo apt-get update
sudo apt-get install -y python3.11 python3-venv pip git

# 2. Clone and setup
git clone https://github.com/your-org/trading-engine.git
cd trading-engine
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp config/.env.example .env
nano .env

# 4. Create log directories
mkdir -p logs/{api,risk,execution}
mkdir -p cache

# 5. Start application
python main.py --mode paper

# 6. In another terminal, run monitoring
python -m monitoring.api
```

## Configuration

### Environment Variables

See `config/.env.example` for complete list. Key variables:

```bash
# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR=/app/logs
LOG_JSON_FORMAT=true

# Caching
ENABLE_DASHBOARD_CACHE=true
CACHE_DEFAULT_TTL=30

# API Security
API_RATE_LIMIT_RPM=600            # Requests per minute
API_KEY_REQUIRED=true
REQUIRE_HTTPS=true                # Set to false only for local dev

# Risk Limits
MAX_DAILY_LOSS_PERCENT=5.0
MAX_POSITION_SIZE=100000
MAX_LEVERAGE=2.0

# Exchange
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
IBKR_PAPER=true                 # Set to false for live
```

### Configuration Files

**Prometheus (config/prometheus.yml)**:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'trading-engine'
    static_configs:
      - targets: ['trading-engine:5000']
```

**Grafana Datasources (config/grafana/datasources/prometheus.yml)**:
```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
```

## Security Checklist

### Ô£à Pre-Deployment

- [ ] All API credentials in `.env` (never in code)
- [ ] SSL/TLS certificates obtained (Let's Encrypt recommended)
- [ ] API keys rotated for all services
- [ ] Network firewall rules configured
- [ ] HTTPS enabled in production
- [ ] Database backups automated
- [ ] Log retention policies configured

### Ô£à Application Security

- [ ] Rate limiting enabled (default: 600 RPM)
- [ ] API key authentication enforced
- [ ] JWT/Bearer token validation working
- [ ] CORS properly configured for your domain
- [ ] Security headers enabled (HSTS, CSP, X-Frame-Options)
- [ ] Input validation on all API endpoints
- [ ] Output sanitization for JSON responses
- [ ] SQL injection protections (if using DB)

### Ô£à Container Security

- [ ] Non-root user in Dockerfile (appuser:1000)
- [ ] Read-only root filesystem where possible
- [ ] Resource limits set (memory, CPU)
- [ ] Health checks configured
- [ ] Image scanning for vulnerabilities
- [ ] Private Docker registry used
- [ ] Image signing enabled

### Ô£à Infrastructure Security

- [ ] VPC/Network isolation configured
- [ ] Secrets management (HashiCorp Vault recommended)
- [ ] Intrusion detection enabled
- [ ] WAF (Web Application Firewall) enabled
- [ ] DDoS protection configured
- [ ] Regular security audits scheduled
- [ ] Incident response plan documented

### Ô£à Operational Security

- [ ] Monitoring and alerting active
- [ ] Automated backups (daily, encrypted)
- [ ] Log aggregation and retention (30+ days)
- [ ] Access control (role-based)
- [ ] Audit logging enabled
- [ ] Change management process documented
- [ ] Disaster recovery plan tested

## Monitoring & Alerting

### Prometheus Metrics

Key metrics to monitor:

```
# API Metrics
api_requests_total                    # Total API requests
api_request_duration_seconds          # Request latency
api_rate_limit_hits_total             # Rate limit violations

# Cache Metrics
cache_hits_total                      # Cache hits
cache_misses_total                    # Cache misses
cache_hit_rate_percent                # Hit rate percentage

# Risk Metrics
position_value_usd                    # Current position value
daily_pnl_usd                         # Daily P&L
risk_score                            # Risk metric (0-100)
circuit_breaker_active                # Circuit breaker status

# System Metrics
container_memory_usage_bytes           # Memory usage
container_cpu_usage_seconds            # CPU time
log_lines_total                       # Total log lines
errors_total                          # Total errors
```

### Grafana Dashboards

Create dashboards to monitor:

1. **System Dashboard**
   - Container health
   - Resource usage
   - Uptime
   - Restarts

2. **API Dashboard**
   - Request rate
   - Response times
   - Error rates
   - Rate limit status

3. **Trading Dashboard**
   - Active positions
   - Daily P&L
   - Risk metrics
   - Order execution stats

4. **Performance Dashboard**
   - Cache hit rate
   - Log volume
   - Database performance

### Alerting Rules

```yaml
groups:
  - name: trading_alerts
    rules:
      # API Alerts
      - alert: HighErrorRate
        expr: (rate(errors_total[5m])) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected ({{ $value }})"

      # Risk Alerts
      - alert: DailyLossExceeded
        expr: daily_pnl_usd < (-1 * max_daily_loss)
        for: 1m
        annotations:
          summary: "Daily loss limit exceeded"

      # System Alerts
      - alert: ContainerMemoryHigh
        expr: (container_memory_usage_bytes / 1e9) > 7
        for: 5m
        annotations:
          summary: "High memory usage ({{ $value }} GB)"
```

### Kibana Saved Searches

```
# Application errors
level: "ERROR" AND environment: "production"

# Slow API requests
duration_ms > 1000 AND logger: "api"

# Risk calculation times
action: "calculate_risk" AND duration_ms > 100

# Circuit breaker activations
message: "circuit*" AND action: "check_risk"
```

## Scaling

### Horizontal Scaling

```bash
# With Docker Swarm
docker swarm init
docker service create --name trading-engine \
  --publish 5000:5000 \
  --replicas 3 \
  trading-engine:latest

# With Kubernetes
kubectl set image deployment/trading-engine \
  trading-engine=trading-engine:v1.2.0
kubectl scale deployment trading-engine --replicas 3
kubectl autoscale deployment trading-engine --min 2 --max 10 \
  --cpu-percent 80
```

### Vertical Scaling

```bash
# Update docker-compose.yml
services:
  trading-engine:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
```

### Database Optimization

```sql
-- Create indices for frequently queried columns
CREATE INDEX idx_trade_timestamp ON trades(timestamp);
CREATE INDEX idx_order_status ON orders(status);
CREATE INDEX idx_position_symbol ON positions(symbol);

-- Archive old data
DELETE FROM trades WHERE timestamp < DATE_SUB(NOW(), INTERVAL 1 YEAR);
```

## Troubleshooting

### Common Issues

#### 1. Container Won't Start
```bash
# Check logs
docker logs trading-engine

# Common causes:
# - Port 5000 in use: change port in docker-compose.yml
# - Missing .env file: cp config/.env.example .env
# - API credentials invalid: verify IBKR_HOST, IBKR_PORT, and IBKR_CLIENT_ID
```

#### 2. High Memory Usage
```bash
# Reduce cache size
CACHE_MAX_SIZE=50

# Reduce log level
LOG_LEVEL=WARNING

# Restart container
docker restart trading-engine
```

#### 3. API Rate Limiting Too Aggressive
```bash
# Increase rate limit
API_RATE_LIMIT_RPM=1000

# Implement client-side rate limiting
import time
for request in requests:
    time.sleep(1/10)  # 10 requests per second
    make_request()
```

#### 4. Dashboard Slow
```bash
# Clear cache
curl -X POST http://localhost:5000/api/cache/clear

# Increase cache TTL
CACHE_DEFAULT_TTL=60

# Enable compression in Nginx
gzip on;
gzip_types application/json;
```

### Debug Mode

```bash
# Enable verbose logging
LOG_LEVEL=DEBUG
VERBOSE_LOGGING=true

# View detailed logs
docker logs -f --tail 100 trading-engine

# Check metrics
curl http://localhost:5000/metrics

# Check health
curl http://localhost:5000/health
```

## Maintenance

### Regular Tasks

#### Daily
- [ ] Monitor error logs
- [ ] Check circuit breaker status
- [ ] Verify backup completion
- [ ] Review risk metrics

#### Weekly
- [ ] Analyze performance trends
- [ ] Review API usage patterns
- [ ] Check disk space
- [ ] Test failover

#### Monthly
- [ ] Update dependencies
- [ ] Review security logs
- [ ] Performance optimization
- [ ] Disaster recovery drill
- [ ] Audit log retention

#### Quarterly
- [ ] Security assessment
- [ ] Capacity planning
- [ ] Architecture review
- [ ] Training/documentation updates

### Updates & Patches

```bash
# Check for updates
docker images
pip list --outdated

# Update base image
docker pull python:3.11-slim

# Rebuild image
docker-compose build --no-cache

# Restart services
docker-compose up -d

# Verify health
docker-compose ps
docker-compose logs
```

### Backup & Recovery

```bash
# Backup logs
tar -czf logs_$(date +%Y%m%d).tar.gz logs/

# Backup Redis data
docker exec trading-redis redis-cli BGSAVE

# Export Elasticsearch indices
curl -X GET "localhost:9200/_cat/indices"

# Restore from backup
tar -xzf logs_20260208.tar.gz -C /backup/
```

## Production Checklist

### Pre-Launch
- [ ] All tests passing (100%)
- [ ] Security audit completed
- [ ] Performance benchmarks met
- [ ] Load testing completed
- [ ] Disaster recovery tested
- [ ] Monitoring configured
- [ ] Alerting configured
- [ ] Documentation reviewed
- [ ] Team trained
- [ ] Go/no-go decision made

### Launch Week
- [ ] Gradual traffic increase (10% ÔåÆ 100%)
- [ ] Monitor all metrics closely
- [ ] Team on-call market hours
- [ ] Daily stand-ups
- [ ] Weekly review meeting

### Ongoing
- [ ] Daily monitoring review
- [ ] Weekly performance analysis
- [ ] Monthly security audit
- [ ] Quarterly capacity planning
- [ ] Annual architecture review

## Support & Resources

- **Documentation**: http://docs.internal.com/trading-engine
- **Status Page**: http://status.internal.com
- **Support Email**: trading-team@example.com
- **On-Call**: Slack #trading-engine-oncall

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-08 | Initial production deployment guide |

---

**Last Updated**: February 8, 2026  
**Maintained By**: Trading Infrastructure Team  
**Status**: Production-Ready
