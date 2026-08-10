# Brand King POS - Backend

Brand King POS is a robust, Django-based Point of Sale (POS) and Retail Management System designed to handle multi-branch retail operations. It provides comprehensive modules for billing, inventory management, user access control, and revenue reporting.

## 🚀 Key Features

### 1. Authentication & Role-Based Access Control (RBAC)
Secure JWT-based authentication system with granular permissions:
- **Global Admin (`ADMIN`)**: Full access across all branches, ability to reassign staff, and manage POS counters.
- **Sub-Admin (`SUB_ADMIN`)**: High-level managerial access for specific branch oversight.
- **Cashier (`CASHIER`)**: Dedicated access to the Billing module, cart management, and invoice generation.
- **Store Staff (`STORE_STAFF`)**: Dedicated access to Inventory, stock inwarding, and barcode printing.

### 2. Multi-Branch & Counter Management
- Manage multiple physical branches.
- **Two-Counter POS Operation**: Each branch can have multiple registered POS counters. Transactions are securely tied to both the assigned `counter_id` and the operating `cashier_id` to ensure accurate end-of-day reconciliation.

### 3. Inventory & Product Management
- Hierarchical product classification (Categories, Brands, Product Types).
- GST & HSN Code configurations.
- Real-time stock tracking and auditing.
- Automated barcode generation and printing support.
- Bulk product import utilities.

### 4. Billing & Checkout Workflow
- **Cart Management**: Scan barcodes to add items, place carts "on-hold", and resume them later across different counters.
- **Invoicing**: Automated invoice generation calculating CGST, SGST, IGST, and total taxable amounts.
- **Payment Modes**: Track payments via Cash, Card, and UPI.

### 5. Customer & Loyalty Program
- Track customer purchase history.
- Automated loyalty points calculation (e.g., 1 point per ₹100 spent).

### 6. Reporting Engine
- Dynamic revenue dashboards.
- Aggregates overall store revenue, counter-wise revenue, and cashier-wise revenue.
- Transaction counts and payment method breakdowns.

---

## 🛠 Tech Stack

- **Backend Framework**: Django & Django REST Framework (DRF)
- **Database**: PostgreSQL / SQLite (Configurable)
- **Authentication**: Simple JWT
- **Barcode Generation**: `python-barcode`

---

## 📦 Installation & Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd brand-king-pos
   ```

2. **Create a virtual environment & install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Environment Variables**
   Create a `.env` file in the root directory and configure your database and secret keys.

4. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create Superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start the Development Server**
   ```bash
   python manage.py runserver
   ```

---

## 🔗 API Documentation / Postman

All API endpoints are prefixed with `/api/`. Key endpoints include:
- **Auth**: `/api/auth/login/`
- **User Management**:
  - Sub-Admins: `POST /api/sub-admins/` (Global Admin only)
  - Employees (Cashiers/Store Staff): `POST /api/employees/` (Global/Sub-Admin only)
- **Branches & Counters**: `/api/branches/`, `/api/branches/counters/`
- **Products & Inventory**: 
  - Product Creation: `POST /api/products/`
  - Barcode Generation/Printing: `GET /api/barcodes/print/`
- **Billing**: `/api/billing/cart/scan/`, `/api/billing/cart/checkout/`
- **Reports**: `/api/reports/revenue/`

*Note: Import the provided Postman collection for a full list of request payloads and required data formats.*
