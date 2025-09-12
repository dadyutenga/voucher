
# 📑 Wi-Fi Voucher + Account-Based Billing System (FastAPI + Meraki)

## 1. Overview
A voucher-based hotspot system with **account linkage**.
- Customers pay → get voucher → delivered via **email**.
- Voucher grants **time-based or data-based** internet access.
- Access controlled via **Cisco Meraki Splash API**.
- Admin dashboard to manage users, vouchers, and payments.

---

## 2. Tech Stack
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL
- **Email**: SMTP (Gmail, Mailgun, or SendGrid)
- **Payments**: Stripe or M-Pesa (Daraja API)
- **Frontend**: React (optional admin panel + splash page)
- **Deployment**: Docker + Nginx

---

## 3. Core Features
- **Voucher Management**
  - Generate vouchers (duration/data limit).
  - Assign to user accounts.
  - Track usage & expiry.

- **Account System**
  - Identify users by **email address**.
  - Store voucher history.
  - Show balance / time remaining.

- **Payment Integration**
  - Stripe/M-Pesa → Webhook → Generate voucher.
  - Transaction log for audits.

- **Access Control**
  - Meraki Splash Page → redirect to FastAPI login.
  - Voucher + email check.
  - Grant access if valid, block otherwise.

- **Admin Dashboard**
  - Manage accounts, vouchers, transactions.
  - Reports: active users, revenue, voucher stats.

---

## 5. API Endpoints (FastAPI)

### Public
- `POST /auth/login` → Login with email + voucher.
- `POST /payment/webhook` → Handle Zenopay/M-Pesa payment, issue voucher.

### Admin
this  must be   automatically  after  payment   or  we  make  the  use  get  a   voucher   for    10  mins   demo  ` → Generate voucher.
- `GET /admin/vouchers` → List vouchers.
- `GET /admin/accounts` → List accounts.
- `GET /admin/transactions` → List transactions.

---

## 6. Flow

1. **User Payment**
   - Customer pays via Zenopay/M-Pesa.
   - FastAPI webhook confirms → create voucher.

2. **Voucher Delivery (Email)**
   - Send voucher code to user email.
   - Example email:

   ```
   Subject: Your Wi-Fi Voucher
   Body:
   Hello Dadi, thanks for your payment!
   Voucher Code: ABC123
   Valid for: 2 hours
   Use on Wi-Fi Splash Page to log in.
   ```

3. **Wi-Fi Login**
   - Connect to Meraki Wi-Fi → Redirects to Splash Page.
   - Enter email + voucher → FastAPI validates.
   - If valid → redirect to `base_grant_url` → internet access granted.

4. **Session Expiry**
   - When duration/data runs out → voucher expires.
   - User must top-up again.

---

## 7. Development Phases
- **Phase 1**: FastAPI skeleton + DB models.
- **Phase 2**: Voucher generation + email delivery.
- **Phase 3**: Payment integration (Stripe/M-Pesa).
- **Phase 4**: Meraki Splash API integration.
- **Phase 5**: Admin dashboard (React).
- **Phase 6**: Reports + optimizations.

---

- Support SMS (optional upgrade).
- Add QR-code vouchers for cafes/shops.
- Bandwidth throttling per voucher plan.


after  paying  go  the   splash login
please   treate   this  project  as   saas  dont  give  me   light  code    and  make  it  work
