# 🌐 Wi-Fi Voucher System

A comprehensive, production-ready Wi-Fi voucher management system built with FastAPI, featuring user authentication with Tanzanian mobile numbers, package-based pricing, and admin management capabilities.

## ✨ Features

### 🔐 User Authentication
- **Tanzanian Mobile Number Authentication**: Uses +255 format for user accounts
- **Secure Password System**: bcrypt hashing with JWT tokens
- **User Dashboard**: Comprehensive panel for viewing vouchers and purchasing packages

### 📦 Package Management
- **Admin Package Creation**: Flexible package system with duration, data limits, and pricing
- **Multi-Currency Support**: TZS (Tanzanian Shilling) with support for other currencies
- **Package Categories**: Basic, Standard, Premium, Daily passes, and Data packs

### 🎫 Voucher System
- **10-Character Codes**: Clear, user-friendly alphanumeric voucher codes
- **Package-Based Vouchers**: Vouchers linked to specific packages with defined benefits
- **Status Tracking**: Active, Used, and Expired voucher states

### 💳 Payment Integration
- **M-Pesa Integration**: Ready for Tanzanian mobile money payments
- **Dummy Payment System**: For testing and demo purposes
- **Transaction Tracking**: Complete payment history and status monitoring

### 👨‍💼 Admin Portal
- **Dashboard Analytics**: System statistics and revenue tracking
- **Package Management**: Create, edit, activate/deactivate packages
- **User Management**: View and manage user accounts
- **Transaction Monitoring**: Track all payments and voucher usage

### 🎨 Modern UI/UX
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Intuitive Interface**: Clean, modern design with easy navigation
- **Real-time Updates**: Dynamic content loading and status updates

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python 3.8+)
- **Database**: PostgreSQL with Alembic migrations
- **Authentication**: JWT tokens with bcrypt password hashing
- **Frontend**: HTML5, CSS3, JavaScript (embedded templates)
- **Payment**: M-Pesa API integration
- **Validation**: Pydantic schemas with Tanzanian mobile number validation

## 📋 Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Git

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd voucher
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
copy env_example.txt .env

# Edit .env file with your database credentials
# Minimum required: DATABASE_URL
```

### 3. Database Setup

```bash
# Run the complete database setup (migrations + sample data)
python setup_database.py
```

### 4. Start the Application

```bash
python run.py
```

The application will be available at:
- **Main Application**: http://localhost:8000
- **Admin Portal**: http://localhost:8000/admin/login
- **API Documentation**: http://localhost:8000/docs

## 🔧 Configuration

### Database Configuration

Update your `.env` file with your PostgreSQL credentials:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/wifi_voucher_db
```

### Admin Access

Default admin credentials:
- **Username**: admin
- **Password**: admin123

⚠️ **Change these credentials in production!**

## 📖 Usage Guide

### For Users

1. **Registration**: Visit the homepage and click "Register"
2. **Login**: Use your Tanzanian mobile number (+255xxxxxxxxx) and password
3. **Browse Packages**: View available Wi-Fi packages with different durations and prices
4. **Purchase**: Select a package and complete payment via M-Pesa or demo payment
5. **Use Voucher**: Enter your voucher code on the Wi-Fi splash page

### For Administrators

1. **Access Admin Panel**: http://localhost:8000/admin/login
2. **Dashboard**: View system statistics, user counts, and revenue
3. **Package Management**: Create and manage Wi-Fi packages
4. **User Management**: View and manage user accounts
5. **Transaction Monitoring**: Track all payments and voucher usage

## 🗂️ Project Structure

```
voucher/
├── app/
│   ├── alembic/                 # Database migrations
│   ├── core/
│   │   └── config.py           # Configuration settings
│   ├── models/
│   │   └── models.py           # Database models
│   ├── routers/
│   │   ├── admin.py            # Admin API endpoints
│   │   ├── auth.py             # Authentication endpoints
│   │   └── payment.py          # Payment processing
│   ├── schemas/
│   │   └── schemas.py          # Pydantic schemas
│   ├── templates/              # HTML templates
│   ├── database.py             # Database configuration
│   ├── main.py                 # FastAPI application
│   └── utils.py                # Utility functions
├── static/                     # Static assets
├── setup_database.py           # Database setup script
├── run.py                     # Application runner
└── requirements.txt           # Python dependencies
```

## 🔄 Database Migrations

The system uses Alembic for database migrations:

```bash
# Create new migration
cd app
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# View migration history
alembic history
```

## 📦 Package System

### Package Types

1. **Demo Access** (Free): 15-minute trial
2. **Basic Access**: 1 hour - TZS 1,000
3. **Standard Access**: 3 hours - TZS 2,500
4. **Premium Access**: 12 hours - TZS 5,000
5. **Daily Pass**: 24 hours - TZS 8,000
6. **Data Packs**: Specific data allowances with longer validity

### Creating Custom Packages

Use the admin panel to create packages with:
- **Duration**: Time limit in minutes
- **Data Limit**: Optional data cap in MB
- **Pricing**: Amount and currency
- **Description**: User-friendly description

## 💳 Payment Integration

### M-Pesa Setup

1. Register with Safaricom M-Pesa API
2. Update `.env` with your credentials:

```env
MPESA_CONSUMER_KEY=your_consumer_key
MPESA_CONSUMER_SECRET=your_consumer_secret
MPESA_SHORTCODE=your_shortcode
MPESA_PASSKEY=your_passkey
MPESA_CALLBACK_URL=https://yourdomain.com/payment/mpesa/callback
```

### Demo Payments

For testing, the system includes a dummy payment processor that simulates successful payments.

## 🔐 Security

- **Password Hashing**: bcrypt with salt
- **JWT Tokens**: Secure session management
- **Input Validation**: Comprehensive validation using Pydantic
- **SQL Injection Protection**: SQLAlchemy ORM
- **CORS Configuration**: Configurable cross-origin requests

## 🚀 Deployment

### Production Checklist

1. **Environment Variables**:
   - Set strong `SECRET_KEY`
   - Configure production `DATABASE_URL`
   - Set `ENVIRONMENT=production`
   - Disable `DEBUG=false`

2. **Database**:
   - Use managed PostgreSQL service
   - Enable SSL connections
   - Regular backups

3. **Security**:
   - Use HTTPS
   - Configure proper CORS origins
   - Set up rate limiting
   - Change default admin credentials

4. **Monitoring**:
   - Set up logging
   - Monitor database performance
   - Track payment transactions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Database Connection Issues

1. Verify PostgreSQL is running
2. Check DATABASE_URL format
3. Ensure database exists
4. Verify user permissions

### Migration Issues

```bash
# Reset database (⚠️ destroys all data)
python init_db.py --reset

# Or manually drop and recreate
cd app
alembic downgrade base
alembic upgrade head
```

### Package/Voucher Issues

1. Check admin panel for package status
2. Verify payment completion
3. Check voucher expiration
4. Review transaction logs

## 📞 Support

For issues and questions:
1. Check this README
2. Review the API documentation at `/docs`
3. Check the application logs
4. Create an issue in the repository

---

Built with ❤️ for reliable Wi-Fi access management