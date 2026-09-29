# SpendWise - Expense Tracker

SpendWise is a full-stack personal finance management web application built with **Python Flask, MySQL, HTML, CSS, Bootstrap, and JavaScript**.

It helps users manage their daily expenses, income, budgets, categories, financial analytics, and monthly financial reports from a single dashboard.

## Features

### Authentication
- User registration
- User login and logout
- Secure password hashing
- Session-based authentication
- Protected user-specific data
- Account profile management
- Change password
- Delete account

### Expense Management
- Add expenses
- Edit expenses
- Delete expenses
- View expense history
- Expense categories
- Expense notes
- Expense date tracking
- User-specific expenses
- Advanced expense search and filtering
- Filter by:
  - Search keyword
  - Category
  - Year
  - Month
  - Start date
  - End date
  - Minimum amount
  - Maximum amount
- Sort expenses by date or amount

### Income Management
- Add income
- Edit income
- Delete income
- Income categories
- Income date tracking
- Income notes
- User-specific income records

### Budget Management
- Create monthly budgets
- Edit budgets
- Delete budgets
- Category-based budgets
- Monthly budget tracking
- Budget notes
- Budget usage monitoring
- Budget alerts

### Budget Alerts
SpendWise automatically monitors budget usage.

- Below 80% → No warning
- 80%–99% → Warning
- 100% or more → Over-budget alert

### Custom Categories
- View expense categories
- Create custom categories
- Edit custom categories
- Delete custom categories
- Category colors
- System categories and user-specific categories

### Dashboard
The dashboard provides an overview of financial activity.

- Total expenses
- Total income
- Net balance
- Current budgets
- Budget warnings
- Recent expenses
- Financial overview

### Analytics
SpendWise provides interactive financial analytics.

- 7-day analysis
- 30-day analysis
- 6-month analysis
- 12-month analysis
- Custom date range
- Total income
- Total expenses
- Net balance
- Savings rate
- Spending by category
- Income vs expense trends
- Top spending categories
- Transaction counts
- Interactive charts

### Monthly Financial Reports
Generate financial reports for:

- Last 7 days
- Last 30 days
- Current month
- Previous month
- Last 6 months
- Last 12 months
- Custom date range

Reports include:

- Total income
- Total expenses
- Net balance
- Savings rate
- Category-wise expenses
- Budget performance
- Financial trends
- Daily/monthly transaction trends

### PDF Reports
Monthly financial reports can also be exported as PDF files.

## Tech Stack

### Backend
- Python
- Flask
- MySQL
- mysql-connector-python
- Werkzeug
- python-dotenv
- ReportLab

### Frontend
- HTML5
- CSS3
- JavaScript
- Bootstrap 5.3.3
- Bootstrap Icons
- Google Inter Font
- Chart.js

### Database
- MySQL

## Project Structure

```text
SpendWise/
│
├── app.py
│
├── database/
│   └── schema.sql
│
├── static/
│   ├── charts.js
│   └── style.css
│
├── templates/
│   ├── 404.html
│   ├── 500.html
│   ├── account.html
│   ├── add_budget.html
│   ├── add_category.html
│   ├── add_expense.html
│   ├── add_income.html
│   ├── base.html
│   ├── budgets.html
│   ├── categories.html
│   ├── dashboard.html
│   ├── edit_budget.html
│   ├── edit_category.html
│   ├── edit_expense.html
│   ├── edit_income.html
│   ├── expenses.html
│   ├── income.html
│   ├── login.html
│   ├── monthly_report.html
│   └── register.html
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md