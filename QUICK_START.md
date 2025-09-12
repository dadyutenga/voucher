# 🚀 Quick Start Guide - Wi-Fi Voucher System

Get your Wi-Fi voucher system up and running in minutes!

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL database
- Email account (Gmail recommended)
- M-Pesa account (for Kenya payments, optional)

## ⚡ 5-Minute Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Environment

```bash
# Copy the environment template
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Database - Update with your PostgreSQL details
DATABASE_URL=postgresql://username:password@localhost:5432/wifi_voucher_db

# Email - Use Gmail App Password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=your-email@gmail.com

# M-Pesa - Get from Safaricom Developer Portal (optional)
MPESA_CONSUMER_KEY=your_mpesa_consumer_key
MPESA_CONSUMER_SECRET=your_mpesa_consumer_secret
MPESA_SHORTCODE=your_business_shortcode
MPESA_PASSKEY=your_mpesa_passkey
MPESA_CALLBACK_URL=https://yourdomain.com/payment/mpesa/callback
```

### 3. Initialize Database

```bash
python init_db.py
```

### 4. Start the Server

```bash
python run.py
```

## 🎯 Test Your Setup

### Access the System
- **API Documentation**: http://localhost:8000/docs
- **Splash Page**: http://localhost:8000/splash
- **Health Check**: http://localhost:8000/health

### Create a Demo Voucher

1. Visit: http://localhost:8000/splash
2. Enter your email address
3. Click "Get Free Demo Voucher"
4. Check your email for the voucher code
5. Use the code to test login

### Test with API

```bash
# Create demo voucher
curl -X POST "http://localhost:8000/payment/create-demo-voucher?email=test@example.com"

# Validate voucher
curl -X POST "http://localhost:8000/auth/validate" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "voucher_code": "YOUR_CODE"}'

# Test dummy payment
curl -X POST "http://localhost:8000/payment/dummy/process" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "amount": 50, "duration": 60, "payment_reference": "TEST123"}'
```

## 🐳 Docker Quick Start

### Using Docker Compose

```bash
# Start all services (PostgreSQL + App)
docker-compose up -d

# Initialize database
docker-compose exec app python init_db.py

# View logs
docker-compose logs -f app
```

Access at: http://localhost:8000

## 📧 Email Setup (Gmail)

1. Go to Google Account Settings
2. Enable 2-Factor Authentication
3. Generate an App Password:
   - Go to Security → 2-Step Verification → App passwords
   - Select "Mail" and your device
   - Use the generated password in `SMTP_PASSWORD`

## 💳 M-Pesa Setup (Optional)

1. Create Safaricom Developer account at https://developer.safaricom.co.ke
2. Create a new app and get your credentials:
   - Consumer Key → `MPESA_CONSUMER_KEY`
   - Consumer Secret → `MPESA_CONSUMER_SECRET`
3. Get your business shortcode and passkey:
   - Business shortcode → `MPESA_SHORTCODE`
   - Passkey → `MPESA_PASSKEY`
4. Set callback URL: `https://yourdomain.com/payment/mpesa/callback`

## 🧪 Testing Payments

The system includes a dummy payment option for testing:
- No setup required
- Instantly creates vouchers
- Perfect for development and testing
- Access via splash page "Test Payment" option

## 🔧 Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Create database manually if needed
createdb wifi_voucher_db
```

### Email Not Sending
```bash
# Test email configuration
python -c "from app.utils import send_email; send_email('test@example.com', 'Test', 'Test message')"
```

### Port Already in Use
```bash
# Run on different port
python run.py --port 8001
```

### Import Errors
```bash
# Make sure you're in the project root directory
cd voucher
python run.py
```

## 📱 Usage Flow

1. **Customer Journey**:
   - Connects to Wi-Fi → Redirected to splash page
   - Enters email → Gets demo voucher or purchases plan
   - Chooses payment method (M-Pesa or Test Payment)
   - Uses voucher code → Gets internet access

2. **Payment Options**:
   - **Demo**: Free 10-minute voucher
   - **Test Payment**: Simulate payment for development
   - **M-Pesa**: Real mobile money payments (Kenya)

3. **Admin Tasks**:
   - View stats: http://localhost:8000/admin/stats
   - List vouchers: http://localhost:8000/admin/vouchers
   - Check transactions: http://localhost:8000/admin/transactions

## 🎯 Next Steps

1. **Customize Voucher Plans**: Edit `/payment/plans` endpoint
2. **Style Splash Page**: Modify `app/templates/splash.html`
3. **Configure M-Pesa**: Set up real M-Pesa credentials
4. **Add Other Payment Gateways**: Extend payment router
5. **Add Meraki Integration**: Configure Meraki settings in `.env`
6. **Deploy to Production**: Use Docker or manual deployment guide

## 🆘 Need Help?

- Check the main [README.md](README.md) for detailed documentation
- Run system tests: `python test_system.py`
- View API docs: http://localhost:8000/docs

## 🔐 Security Notes

- Change default secrets in production
- Use HTTPS for production deployment
- Regularly rotate API keys
- Secure M-Pesa callback endpoints
- Monitor payment transactions
- Rate limit demo voucher creation

## 💰 Payment Features

- **Multi-currency support**: Prices in KES (Kenyan Shillings)
- **Multiple plans**: From 1-hour to daily passes
- **Data-based plans**: 500MB and 1GB options
- **Instant delivery**: Vouchers sent via email immediately
- **Payment tracking**: Full transaction history

Happy coding! 🚀