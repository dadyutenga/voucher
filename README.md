# 🌐 Wi-Fi Voucher + Account-Based Billing System

A comprehensive voucher-based hotspot system with account linkage, built with FastAPI and designed to integrate with Cisco Meraki networks.

## 📋 Overview

This system allows customers to:
- Purchase Wi-Fi vouchers through Stripe payments
- Receive voucher codes via email
- Use vouchers to access Wi-Fi through a splash page
- Get time-based or data-based internet access
- Try the service with free 10-minute demo vouchers

## 🛠 Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL
- **Email**: SMTP (Gmail, Mailgun, SendGrid)
- **Payments**: Stripe
- **Frontend**: HTML/JavaScript (Splash Page)
- **Deployment**: Docker + Docker Compose
- **Reverse Proxy**: Nginx (optional)

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL
- Git
- Docker & Docker Compose (optional but recommended)

### 2. Clone the Repository

```bash
git clone <your-repo-url>
cd voucher
```

### 3. Environment Setup

```bash
# Copy the environment template
cp .env.example .env

# Edit the .env file with your configurations
# At minimum, configure:
# - DATABASE_URL
# - SMTP settings
# - STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET
```

### 4. Database Setup

#### Option A: Using Docker Compose (Recommended)

```bash
# Start PostgreSQL and Redis
docker-compose up -d db redis

# Wait for the database to be ready, then initialize
python init_db.py
```

#### Option B: Manual Setup

```bash
# Create database manually in PostgreSQL
createdb wifi_voucher_db

# Install Python dependencies
pip install -r requirements.txt

# Initialize database tables
python init_db.py
```

### 5. Run the Application

#### Development Mode

```bash
# Using the run script
python run.py --mode dev

# Or directly with uvicorn
cd app && uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Production Mode (Docker)

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f app
```

## 📖 API Documentation

Once the application is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Splash Page**: http://localhost:8000/splash

## 🔑 Environment Variables

### Required Variables

```env
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/wifi_voucher_db

# Email/SMTP
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=your-email@gmail.com

# Stripe
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Optional Variables

```env
# Security
SECRET_KEY=your-super-secret-key
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# Meraki Integration
MERAKI_API_KEY=your_meraki_api_key
MERAKI_BASE_GRANT_URL=https://your-meraki-controller.com/guest/s/default/
MERAKI_NETWORK_ID=your_network_id

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0

# Rate Limiting
DEMO_VOUCHER_RATE_LIMIT=3
DEMO_VOUCHER_RATE_WINDOW=3600
```

## 🔄 API Endpoints

### Authentication & Access
- `POST /auth/login` - Login with email + voucher code
- `POST /auth/validate` - Validate voucher without consuming
- `GET /auth/demo-voucher` - Create 10-minute demo voucher

### Payment Processing
- `POST /payment/create-payment-intent` - Create Stripe payment
- `POST /payment/webhook` - Handle Stripe webhooks
- `GET /payment/plans` - Get available voucher plans
- `POST /payment/create-demo-voucher` - Create free demo voucher

### Admin Management
- `GET /admin/vouchers` - List all vouchers
- `GET /admin/accounts` - List all accounts  
- `GET /admin/transactions` - List all transactions
- `POST /admin/vouchers` - Create voucher manually
- `GET /admin/stats` - Get system statistics

### System
- `GET /` - API info
- `GET /health` - Health check
- `GET /splash` - Splash page for Wi-Fi login

## 💳 Payment Flow

1. **Customer Payment**
   - Customer selects voucher plan
   - Payment processed via Stripe
   - Webhook confirms payment

2. **Voucher Creation**
   - System creates voucher automatically
   - Voucher sent to customer email
   - Transaction logged in database

3. **Wi-Fi Access**
   - Customer connects to Wi-Fi
   - Redirected to splash page (`/splash`)
   - Enters email + voucher code
   - System validates and grants access

## 🎯 Demo Voucher System

For testing and customer acquisition:

```bash
# Create a demo voucher via API
curl -X POST "http://localhost:8000/payment/create-demo-voucher?email=test@example.com"

# Or use the splash page "Get Free Demo Voucher" button
```

Demo vouchers provide:
- 10 minutes of free access
- Unlimited data
- Email delivery
- Same validation process as paid vouchers

## 🔧 Development

### Project Structure

```
voucher/
├── app/
│   ├── core/
│   │   ├── config.py          # Settings and configuration
│   │   └── __init__.py
│   ├── models/
│   │   ├── models.py          # SQLAlchemy models
│   │   └── __init__.py
│   ├── routers/
│   │   ├── admin.py           # Admin endpoints
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── payment.py         # Payment processing
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── schemas.py         # Pydantic schemas
│   │   └── __init__.py
│   ├── templates/
│   │   └── splash.html        # Wi-Fi login page
│   ├── database.py            # Database connection
│   ├── main.py               # FastAPI application
│   └── utils.py              # Utility functions
├── docker-compose.yml         # Docker services
├── Dockerfile                # Container definition
├── init_db.py               # Database initialization
├── run.py                   # Application runner
├── requirements.txt         # Python dependencies
└── .env.example            # Environment template
```

### Adding New Features

1. **New API Endpoints**: Add to appropriate router in `app/routers/`
2. **Database Models**: Update `app/models/models.py`
3. **Schemas**: Update `app/schemas/schemas.py`
4. **Business Logic**: Add to `app/utils.py` or create new modules

### Testing

```bash
# Install development dependencies
pip install pytest httpx

# Run tests (when test suite is created)
pytest

# Manual API testing
curl -X GET "http://localhost:8000/health"
curl -X GET "http://localhost:8000/payment/plans"
```

## 🚀 Production Deployment

### Docker Deployment

1. **Prepare Environment**
   ```bash
   # Copy and configure environment
   cp .env.example .env
   # Edit .env with production values
   ```

2. **SSL Configuration**
   ```bash
   # Create SSL directory
   mkdir -p nginx/ssl
   # Add your SSL certificates
   ```

3. **Deploy**
   ```bash
   # Start all services
   docker-compose up -d
   
   # Initialize database
   docker-compose exec app python init_db.py
   
   # Check status
   docker-compose ps
   ```

### Manual Deployment

1. **Server Setup** (Ubuntu/Debian)
   ```bash
   # Install dependencies
   sudo apt update
   sudo apt install python3.11 python3-pip postgresql nginx

   # Create application user
   sudo useradd -m -s /bin/bash voucher
   sudo su - voucher
   ```

2. **Application Setup**
   ```bash
   # Clone and setup
   git clone <repo> wifi-voucher
   cd wifi-voucher
   pip install -r requirements.txt
   
   # Configure environment
   cp .env.example .env
   # Edit .env
   
   # Initialize database
   python init_db.py
   ```

3. **Service Setup**
   ```bash
   # Create systemd service
   sudo nano /etc/systemd/system/wifi-voucher.service
   
   # Add service configuration
   sudo systemctl enable wifi-voucher
   sudo systemctl start wifi-voucher
   ```

## 🔐 Security Considerations

- **Environment Variables**: Never commit `.env` files
- **API Keys**: Rotate Stripe keys regularly
- **Database**: Use strong passwords and restrict access
- **HTTPS**: Always use SSL in production
- **Rate Limiting**: Implement rate limiting for demo vouchers
- **Input Validation**: All inputs are validated via Pydantic
- **SQL Injection**: Using SQLAlchemy ORM prevents SQL injection

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection**
   ```bash
   # Check PostgreSQL status
   sudo systemctl status postgresql
   
   # Test connection
   psql -h localhost -U voucher_user -d wifi_voucher_db
   ```

2. **Email Delivery**
   ```bash
   # Test SMTP settings
   python -c "from app.utils import send_email; send_email('test@example.com', 'Test', 'Test message')"
   ```

3. **Stripe Webhooks**
   - Use ngrok for local development
   - Verify webhook secret in Stripe dashboard
   - Check webhook logs in Stripe

4. **Docker Issues**
   ```bash
   # Check container logs
   docker-compose logs app
   
   # Restart services
   docker-compose restart
   
   # Reset database
   docker-compose down -v
   docker-compose up -d
   ```

## 📊 Monitoring & Logging

- **Health Check**: `GET /health`
- **Application Logs**: Check Docker logs or application output
- **Database Monitoring**: Use adminer at http://localhost:8080
- **Payment Monitoring**: Stripe dashboard

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

- Create an issue in the repository
- Check the troubleshooting section
- Review API documentation at `/docs`

## 🎯 Roadmap

- [ ] SMS delivery option
- [ ] QR code vouchers
- [ ] Bandwidth throttling
- [ ] Multi-tenant support
- [ ] Advanced reporting
- [ ] Mobile app
- [ ] M-Pesa integration (Kenya)
- [ ] Admin dashboard UI

## 📱 Integration with Meraki

To integrate with Cisco Meraki:

1. Configure Meraki splash page to redirect to your `/splash` endpoint
2. Set up the base grant URL in environment variables
3. Configure network ID and API key
4. Test the complete flow from Wi-Fi connection to internet access

The system is designed to work seamlessly with Meraki's captive portal system.