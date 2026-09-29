import os
from datetime import date, datetime,timedelta
from functools import wraps
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from io import BytesIO
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    abort,
    session,
    send_file,
)
from werkzeug.security import (check_password_hash, generate_password_hash, )
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

# LOAD ENVIRONMENT
load_dotenv()

# FLASK APP
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (os.getenv("SESSION_COOKIE_SECURE", "False").lower()=="true")

# DATABASE CONNECTION

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "expense_tracker"),
        autocommit=True,
    )

# DATABASE HELPERS

def fetch_all(sql, params=()):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

def fetch_one(sql, params=()):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()

def execute_query(sql, params=()):
    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute(sql, params)
        connection.commit()
        return cursor.lastrowid
    except Error:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

# AUTHENTICATION

def login_required(view_function):
    @wraps(view_function)

    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_function(*args, **kwargs)
    return wrapped_view

# CURRENT USER

@app.context_processor

def inject_current_user():
    current_user = None
    user_id = session.get("user_id")
    if user_id:
        current_user = fetch_one(
            """
            SELECT
                id,
                full_name,
                email,
                created_at
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )
    return {
        "current_user": current_user
    }

# COMMON HELPERS

def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

def parse_month(value):
    if not value:
        return None
    try:
        if len(value) == 7:
            return datetime.strptime(value, "%Y-%m").date().replace(day=1)
        if len(value) == 10:
            return datetime.strptime(value, "%Y-%m-%d").date().replace(day=1)
    except (ValueError, TypeError):
        pass
    return None

def valid_hex_color(value, default="#149B9B"):
    if not value:
        return default
    value = value.strip()
    if (len(value)==7 and value.startswith("#")):
        try:
            int(value[1:], 16)
            return value.upper()
        except ValueError:
            pass
    return default

# INR FORMATTER

@app.template_filter("inr")

def inr(value):
    return f"₹{float(value or 0):,.2f}"

# CATEGORY HELPERS

def get_categories():
    return fetch_all(
        """
        SELECT
            id,
            user_id,
            name,
            color,
            created_at
        FROM categories
        WHERE user_id IS NULL
           OR user_id = %s
        ORDER BY
            CASE
                WHEN user_id IS NULL THEN 0
                ELSE 1
            END,
            name
        """,
        (session["user_id"], )
    )

def get_category(category_id):
    return fetch_one(
        """
        SELECT
            id,
            user_id,
            name,
            color,
            created_at
        FROM categories
        WHERE id = %s
          AND (
                user_id IS NULL
                OR user_id = %s
              )
        """,
        (category_id, session["user_id"])
    )

def category_exists(category_id):
    return fetch_one(
        """
        SELECT
            id
        FROM categories
        WHERE id = %s
          AND (
                user_id IS NULL
                OR user_id = %s
              )
        """,
        (category_id, session["user_id"])
    )

def custom_category_name_exists(name, exclude_id=None):
    sql = """
        SELECT
            id
        FROM categories
        WHERE user_id = %s
          AND LOWER(name) = LOWER(%s)
    """
    params = [
        session["user_id"],
        name
    ]
    if exclude_id is not None:
        sql += """
            AND id != %s
        """
        params.append(exclude_id)
    return fetch_one(sql, tuple(params))

# EXPENSE HELPERS

def get_expense(expense_id):
    return fetch_one(
        """
        SELECT
            e.*,
            c.name AS category_name,
            c.color
        FROM expenses e
        JOIN categories c
            ON c.id = e.category_id
           AND (
                c.user_id IS NULL
                OR c.user_id = e.user_id
               )
        WHERE e.id = %s
          AND e.user_id = %s
        """,
        (expense_id, session["user_id"])
    )

# INCOME HELPERS

def get_income_categories():
    return fetch_all(
        """
        SELECT
            id,
            name,
            color
        FROM income_categories
        ORDER BY name
        """
    )

def get_income(income_id):
    return fetch_one(
        """
        SELECT
            i.*,
            c.name AS category_name,
            c.color
        FROM income i
        JOIN income_categories c
            ON c.id = i.category_id
        WHERE i.id = %s
          AND i.user_id = %s
        """,
        (income_id, session["user_id"])
    )

# BUDGET HELPERS

def get_budget_categories():
    return get_categories()

def get_budget(budget_id):
    return fetch_one(
        """
        SELECT
            b.id,
            b.user_id,
            b.category_id,
            b.amount,
            b.budget_month,
            b.notes,
            b.created_at,
            b.updated_at,
            c.name AS category_name,
            c.color
        FROM budgets b
        LEFT JOIN categories c
            ON c.id = b.category_id
           AND (
                c.user_id IS NULL
                OR c.user_id = b.user_id
               )
        WHERE b.id = %s
          AND b.user_id = %s
        """,
        (budget_id, session["user_id"])
    )

def get_month_budget_total(budget_month):
    return fetch_one(
        """
        SELECT
            id,
            amount,
            budget_month,
            notes
        FROM budgets
        WHERE user_id = %s
          AND category_id IS NULL
          AND budget_month = %s
        LIMIT 1
        """,
        (session["user_id"], budget_month)
    )

def get_category_budgets(budget_month):
    return fetch_all(
        """
        SELECT
            b.id,
            b.category_id,
            b.amount,
            b.budget_month,
            b.notes,
            c.name AS category_name,
            c.color
        FROM budgets b
        JOIN categories c
            ON c.id = b.category_id
           AND (
                c.user_id IS NULL
                OR c.user_id = b.user_id
               )
        WHERE b.user_id = %s
          AND b.budget_month = %s
        ORDER BY c.name
        """,
        (session["user_id"], budget_month)
    )

def get_month_expense_total(budget_month):
    row = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total
        FROM expenses
        WHERE user_id = %s
          AND expense_date >= %s
          AND expense_date < DATE_ADD(
                %s,
                INTERVAL 1 MONTH
              )
        """,
        (session["user_id"], budget_month, budget_month)
    )
    return (float(row["total"]or 0)if row else 0.0)

def get_category_expense_total(category_id, budget_month):
    row = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total
        FROM expenses
        WHERE user_id = %s
          AND category_id = %s
          AND expense_date >= %s
          AND expense_date < DATE_ADD(
                %s,
                INTERVAL 1 MONTH
              )
        """,
        (session["user_id"], category_id, budget_month, budget_month)
    )
    return (float(row["total"]or 0)if row else 0.0)

# CATEGORY MANAGEMENT

@app.route("/categories", methods=["GET"])

@login_required

def categories():
    user_id = session["user_id"]
    category_rows = fetch_all(
        """
        SELECT
            id,
            user_id,
            name,
            color,
            created_at
        FROM categories
        WHERE user_id IS NULL
           OR user_id = %s
        ORDER BY
            CASE
                WHEN user_id IS NULL THEN 0
                ELSE 1
            END,
            name
        """,
        (user_id,)
    )
    system_categories = [
        category
        for category in category_rows
        if category["user_id"] is None
    ]
    custom_categories = [
        category
        for category in category_rows
        if category["user_id"] == user_id
    ]
    return render_template(
        "categories.html",
        system_categories=system_categories,
        custom_categories=custom_categories
    )

@app.route("/categories/add", methods=["GET", "POST"])

@login_required

def add_category():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        color = valid_hex_color(request.form.get("color", "#149B9B"))
        if not name:
            flash("Category name is required.", "danger")
            return render_template("add_category.html")
        if len(name) > 50:
            flash("Category name cannot exceed 50 characters.", "danger")
            return render_template("add_category.html")
        if custom_category_name_exists(name):
            flash("You already have a category with this name.", "warning")
            return render_template("add_category.html")
        try:
            execute_query(
                """
                INSERT INTO categories
                (
                    user_id,
                    name,
                    color
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (session["user_id"], name, color)
            )
            flash(f'"{name}" category created successfully.', "success")
            return redirect(url_for("categories"))
        except Error:
            flash("Unable to create the category. Please try again.", "danger")
    return render_template("add_category.html")

@app.route("/categories/edit/<int:category_id>", methods=["GET", "POST"])

@login_required

def edit_category(category_id):
    category = fetch_one(
        """
        SELECT
            id,
            user_id,
            name,
            color,
            created_at
        FROM categories
        WHERE id = %s
          AND user_id = %s
        """,
        (category_id, session["user_id"])
    )
    if not category:
        flash("Category not found or cannot be edited.", "danger")
        return redirect(url_for("categories"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        color = valid_hex_color(request.form.get("color", "#149B9B"))
        if not name:
            flash("Category name is required.", "danger")
            return render_template("edit_category.html", category=category)
        if len(name) > 50:
            flash("Category name cannot exceed 50 characters.", "danger")
            return render_template("edit_category.html", category=category)
        if custom_category_name_exists(name, category_id):
            flash("You already have another category with this name.", "warning")
            return render_template("edit_category.html", category=category)
        try:
            execute_query(
                """
                UPDATE categories
                SET
                    name = %s,
                    color = %s
                WHERE id = %s
                  AND user_id = %s
                """,
                (name, color, category_id, session["user_id"])
            )
            flash(f'"{name}" category updated successfully.', "success")
            return redirect(url_for("categories"))
        except Error:
            flash("Unable to update the category. Please try again.", "danger")
    return render_template("edit_category.html", category=category)

@app.route("/categories/delete/<int:category_id>", methods=["POST"])

@login_required

def delete_category(category_id):
    category = fetch_one(
        """
        SELECT
            id,
            name
        FROM categories
        WHERE id = %s
          AND user_id = %s
        """,
        (category_id, session["user_id"])
    )
    if not category:
        flash("Category not found or cannot be deleted.", "danger")
        return redirect(url_for("categories"))
    expense_usage = fetch_one(
        """
        SELECT
            COUNT(*) AS total
        FROM expenses
        WHERE category_id = %s
          AND user_id = %s
        """,
        (category_id, session["user_id"])
    )
    if (expense_usage and int(expense_usage["total"])>0):
        flash("This category is being used by your expenses and cannot be deleted.", "warning")
        return redirect(url_for("categories"))
    budget_usage = fetch_one(
        """
        SELECT
            COUNT(*) AS total
        FROM budgets
        WHERE category_id = %s
          AND user_id = %s
        """,
        (category_id, session["user_id"])
    )
    if (budget_usage and int(budget_usage["total"])>0):
        flash("This category is being used by your budgets and cannot be deleted.", "warning")
        return redirect(url_for("categories"))
    try:
        execute_query(
            """
            DELETE FROM categories
            WHERE id = %s
              AND user_id = %s
            """,
            (category_id, session["user_id"])
        )
        flash(f'"{category["name"]}" category deleted successfully.', "success")
    except Error:
        flash("Unable to delete the category. Please try again.", "danger")
    return redirect(url_for("categories"))

# DASHBOARD

@app.route("/", methods=["GET"])

@login_required

def dashboard():
    user_id = session["user_id"]
    current_month = date.today().strftime("%Y-%m")

    # First day of the current month. Used as a real DATE parameter for budget lookups. This avoids DATE_FORMAT() percent-specifier issues in parameterized MySQL queries.
    current_month_start = date.today().replace(day=1)

    # IMPORTANT: mysql-connector-python requires %% when a literal percentage is used inside a parameterized SQL query.
    stats = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS month_total,
            COUNT(*) AS month_count
        FROM expenses
        WHERE user_id = %s
          AND DATE_FORMAT(
                expense_date,
                '%Y-%m'
              ) = %s
        """,
        (user_id, current_month)
    )
    total = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total,
            COUNT(*) AS count
        FROM expenses
        WHERE user_id = %s
        """,
        (user_id,)
    )
    category_data = fetch_all(
        """
        SELECT
            c.name,
            c.color,
            COALESCE(
                SUM(e.amount),
                0
            ) AS total
        FROM categories c
        LEFT JOIN expenses e
            ON c.id = e.category_id
           AND e.user_id = %s
           AND DATE_FORMAT(
                e.expense_date,
                '%Y-%m'
              ) = %s
        WHERE c.user_id IS NULL
           OR c.user_id = %s
        GROUP BY
            c.id,
            c.name,
            c.color
        HAVING SUM(e.amount) > 0
        ORDER BY total DESC
        """,
        (user_id, current_month, user_id)
    )
    recent = fetch_all(
        """
        SELECT
            e.*,
            c.name AS category_name,
            c.color
        FROM expenses e
        JOIN categories c
            ON c.id = e.category_id
           AND (
                c.user_id IS NULL
                OR c.user_id = e.user_id
               )
        WHERE e.user_id = %s
        ORDER BY
            e.expense_date DESC,
            e.id DESC
        LIMIT 6
        """,
        (user_id,)
    )
    monthly_trend = fetch_all(
        """
        SELECT
            DATE_FORMAT(
                expense_date,
                '%Y-%m'
            ) AS month,
            COALESCE(
                SUM(amount),
                0
            ) AS total
        FROM expenses
        WHERE user_id = %s
          AND expense_date >=
              DATE_FORMAT(
                  CURDATE() - INTERVAL 5 MONTH,
                  '%Y-%m-01'
              )
        GROUP BY
            DATE_FORMAT(
                expense_date,
                '%Y-%m'
            )
        ORDER BY month
        """,
        (user_id,)
    )
    top_category = (category_data[0]if category_data else None)
    month_income_row = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total
        FROM income
        WHERE user_id = %s
          AND YEAR(income_date) =
              YEAR(CURDATE())
          AND MONTH(income_date) =
              MONTH(CURDATE())
        """,
        (user_id,)
    )
    month_income = float(month_income_row["total"]or 0)
    month_expenses_row = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total
        FROM expenses
        WHERE user_id = %s
          AND YEAR(expense_date) =
              YEAR(CURDATE())
          AND MONTH(expense_date) =
              MONTH(CURDATE())
        """,
        (user_id,)
    )
    month_expenses = float(month_expenses_row["total"]or 0)
    month_balance = (month_income-month_expenses)
    recent_income = fetch_all(
        """
        SELECT
            i.*,
            c.name AS category_name,
            c.color
        FROM income i
        JOIN income_categories c
            ON c.id = i.category_id
        WHERE i.user_id = %s
        ORDER BY
            i.income_date DESC,
            i.id DESC
        LIMIT 5
        """,
        (user_id,)
    )

    # CURRENT MONTH BUDGET ALERTS
    budget_alerts = fetch_all(
        """
        SELECT
            b.id,
            b.category_id,
            b.amount AS budget_amount,
            COALESCE(
                SUM(e.amount),
                0
            ) AS spent,
            CASE
                WHEN b.category_id IS NULL THEN 'Overall Budget'
                ELSE COALESCE(c.name, 'Unknown Category')
            END AS category_name,
            CASE
                WHEN b.category_id IS NULL THEN '#E96A4A'
                ELSE COALESCE(c.color, '#667984')
            END AS color
        FROM budgets b
        LEFT JOIN categories c
            ON c.id = b.category_id
        LEFT JOIN expenses e
            ON e.user_id = b.user_id
            AND e.expense_date >= b.budget_month
            AND e.expense_date < DATE_ADD(
                b.budget_month,
                INTERVAL 1 MONTH
            )
            AND (
                b.category_id IS NULL
                OR e.category_id = b.category_id
            )
        WHERE b.user_id = %s
          AND b.budget_month = %s
        GROUP BY
            b.id,
            b.category_id,
            b.amount,
            c.name,
            c.color
        ORDER BY
            CASE
                WHEN b.category_id IS NULL THEN 0
                ELSE 1
            END,
            category_name
        """,
        (user_id, current_month_start)
    )

    # Calculate alert status
    budget_warnings = []
    for budget in budget_alerts:
        budget_amount = float(budget["budget_amount"]or 0)
        spent = float(budget["spent"]or 0)
        if budget_amount <= 0:
            continue
        percentage = (spent/budget_amount) * 100
        remaining = (budget_amount-spent)
        if percentage >= 100:
            status = "danger"
            icon = "bi-exclamation-octagon-fill"
            title = "Budget exceeded"
            message = (f'{budget["category_name"]} is 'f'{percentage:.1f}% used.')
        elif percentage >= 80:
            status = "warning"
            icon = "bi-exclamation-triangle-fill"
            title = "Budget warning"
            message = (f'{budget["category_name"]} is 'f'{percentage:.1f}% used.')
        else:
            continue
        budget_warnings.append({
            "id": budget["id"],
            "category_name": budget["category_name"],
            "color": budget["color"],
            "budget_amount": budget_amount,
            "spent": spent,
            "remaining": remaining,
            "percentage": percentage,
            "status": status,
            "icon": icon,
            "title": title,
            "message": message
        })
    return render_template(
        "dashboard.html",
        stats=stats,
        total=total,
        category_data=category_data,
        recent=recent,
        current_month=current_month,
        monthly_trend=monthly_trend,
        top_category=top_category,
        month_income=month_income,
        month_expenses=month_expenses,
        month_balance=month_balance,
        recent_income=recent_income,
        budget_warnings=budget_warnings
    )

# REGISTER

@app.route("/register", methods=["GET", "POST"])

def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("register.html")
        if not email:
            flash("Email is required.", "danger")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        existing_user = fetch_one(
            """
            SELECT
                id
            FROM users
            WHERE email = %s
            """,
            (email,)
        )
        if existing_user:
            flash("An account with this email already exists.", "danger")
            return render_template("register.html")
        password_hash = generate_password_hash(password)
        try:
            user_id = execute_query(
                """
                INSERT INTO users
                (
                    full_name,
                    email,
                    password_hash
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (full_name, email, password_hash)
            )
            session.clear()
            session["user_id"] = user_id
            session["user_email"] = email
            session["user_name"] = full_name
            flash("Account created successfully.", "success")
            return redirect(url_for("dashboard"))
        except Error:
            flash("Unable to create your account. Please try again.", "danger")
    return render_template("register.html")

# LOGIN

@app.route("/login", methods=["GET", "POST"])

def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Please enter your email and password.", "danger")
            return render_template("login.html")
        user = fetch_one(
            """
            SELECT
                id,
                full_name,
                email,
                password_hash
            FROM users
            WHERE email = %s
            """,
            (email,)
        )
        if not user:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        if not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["user_name"] = user["full_name"]
        next_page = request.args.get("next")
        if (next_page and next_page.startswith("/")and not next_page.startswith("//")):
            return redirect(next_page)
        flash(f"Welcome back, {user['full_name']}!", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")

# LOGOUT

@app.route("/logout")

def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

# ACCOUNT

@app.route("/account", methods=["GET", "POST"])

@login_required

def account():
    user_id = session["user_id"]
    user = fetch_one(
        """
        SELECT
            id,
            full_name,
            email,
            created_at
        FROM users
        WHERE id = %s
        """,
        (user_id,)
    )
    if not user:
        session.clear()
        return redirect(url_for("login"))
    if request.method == "POST":
        action = request.form.get("action", "")

        # UPDATE PROFILE
        if action == "update_profile":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            if not full_name or not email:
                flash("Name and email are required.", "danger")
                return redirect(url_for("account"))
            email_exists = fetch_one(
                """
                SELECT
                    id
                FROM users
                WHERE email = %s
                  AND id != %s
                """,
                (email, user_id)
            )
            if email_exists:
                flash("That email address is already in use.", "danger")
                return redirect(url_for("account"))
            try:
                execute_query(
                    """
                    UPDATE users
                    SET
                        full_name = %s,
                        email = %s
                    WHERE id = %s
                    """,
                    (full_name, email, user_id)
                )
                session["user_email"] = email
                session["user_name"] = full_name
                flash("Profile updated successfully.", "success")
            except Error:
                flash("Unable to update your profile. Please try again.", "danger")
            return redirect(url_for("account"))

        # CHANGE PASSWORD
        if action == "change_password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            current_user = fetch_one(
                """
                SELECT
                    password_hash
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )
            if not current_user:
                flash("User account not found.", "danger")
                return redirect(url_for("account"))
            if not check_password_hash(current_user["password_hash"], current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("account"))
            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "danger")
                return redirect(url_for("account"))
            if new_password != confirm_password:
                flash("New passwords do not match.", "danger")
                return redirect(url_for("account"))
            new_hash = generate_password_hash(new_password)
            try:
                execute_query(
                    """
                    UPDATE users
                    SET
                        password_hash = %s
                    WHERE id = %s
                    """,
                    (new_hash, user_id)
                )
                flash("Password changed successfully.", "success")
            except Error:
                flash("Unable to change the password. Please try again.", "danger")
            return redirect(url_for("account"))
    return render_template("account.html", user=user)

# DELETE ACCOUNT

@app.route("/delete-account", methods=["POST"])

@login_required

def delete_account():
    user_id = session["user_id"]
    password = request.form.get("password", "")
    user = fetch_one(
        """
        SELECT
            password_hash
        FROM users
        WHERE id = %s
        """,
        (user_id,)
    )
    if not user:
        session.clear()
        return redirect(url_for("login"))
    if not check_password_hash(user["password_hash"], password):
        flash("Incorrect password. Account was not deleted.", "danger")
        return redirect(url_for("account"))
    try:
        execute_query(
            """
            DELETE FROM users
            WHERE id = %s
            """,
            (user_id,)
        )
        session.clear()
        flash("Your account has been deleted.", "success")
        return redirect(url_for("login"))
    except Error:
        flash("Unable to delete the account. Please try again.", "danger")
        return redirect(url_for("account"))

# ADD EXPENSE

@app.route("/add-expense", methods=["GET", "POST"])

@login_required

def add_expense():
    categories = get_categories()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category_id_raw = request.form.get("category_id", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        expense_date = request.form.get("expense_date", "").strip()
        notes = request.form.get("notes", "").strip()
        parsed_date = parse_date(expense_date)
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            amount = None
        try:
            category_id = int(category_id_raw)
        except (ValueError, TypeError):
            category_id = None
        if (not title or category_id is None or amount is None or amount<=0 or not parsed_date):
            flash("Please complete all required fields with valid values.", "danger")
            return render_template(
                "add_expense.html",
                categories=categories,
                today=date.today().isoformat()
            )
        if not category_exists(category_id):
            flash("Please choose a valid category.", "danger")
            return render_template(
                "add_expense.html",
                categories=categories,
                today=date.today().isoformat()
            )
        try:
            execute_query(
                """
                INSERT INTO expenses
                (
                    user_id,
                    title,
                    category_id,
                    amount,
                    expense_date,
                    notes
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (session["user_id"], title, category_id, amount, parsed_date, notes or None)
            )
            flash("Expense added successfully.", "success")
            return redirect(url_for("expenses"))
        except Error:
            flash("Unable to save the expense. Please try again.", "danger")
    return render_template(
        "add_expense.html",
        categories=categories,
        today=date.today().isoformat()
    )

# EDIT EXPENSE

@app.route("/edit-expense/<int:expense_id>", methods=["GET", "POST"])

@login_required

def edit_expense(expense_id):
    expense = get_expense(expense_id)
    if not expense:
        abort(404)
    categories = get_categories()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category_id_raw = request.form.get("category_id", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        expense_date = request.form.get("expense_date", "").strip()
        notes = request.form.get("notes", "").strip()
        parsed_date = parse_date(expense_date)
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            amount = None
        try:
            category_id = int(category_id_raw)
        except (ValueError, TypeError):
            category_id = None
        if (not title or category_id is None or amount is None or amount<=0 or not parsed_date):
            flash("Please complete all required fields with valid values.", "danger")
            return render_template("edit_expense.html", expense=expense, categories=categories)
        if not category_exists(category_id):
            flash("Please choose a valid category.", "danger")
            return render_template("edit_expense.html", expense=expense, categories=categories)
        try:
            execute_query(
                """
                UPDATE expenses
                SET
                    title = %s,
                    category_id = %s,
                    amount = %s,
                    expense_date = %s,
                    notes = %s
                WHERE id = %s
                  AND user_id = %s
                """,
                (
                    title,
                    category_id,
                    amount,
                    parsed_date,
                    notes or None,
                    expense_id,
                    session["user_id"]
                )
            )
            flash("Expense updated successfully.", "success")
            return redirect(url_for("expenses"))
        except Error:
            flash("Unable to update the expense. Please try again.", "danger")
    return render_template("edit_expense.html", expense=expense, categories=categories)

# DELETE EXPENSE

@app.route("/delete-expense/<int:expense_id>", methods=["POST"])

@login_required

def delete_expense(expense_id):
    expense = get_expense(expense_id)
    if not expense:
        abort(404)
    try:
        execute_query(
            """
            DELETE FROM expenses
            WHERE id = %s
              AND user_id = %s
            """,
            (expense_id, session["user_id"])
        )
        flash(f'"{expense["title"]}" was deleted successfully.', "success")
    except Error:
        flash("Unable to delete the expense. Please try again.", "danger")
    return redirect(request.referrer or url_for("expenses"))

# EXPENSE LIST / SEARCH / FILTERS

@app.route("/expenses")

@login_required

def expenses():
    user_id = session["user_id"]

    # EXISTING FILTERS
    search = request.args.get("search", "").strip()
    selected_category = request.args.get("category", "").strip()
    selected_year = request.args.get("year", "").strip()
    selected_month = request.args.get("month", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    # ADVANCED FILTERS
    min_amount = request.args.get("min_amount", "").strip()
    max_amount = request.args.get("max_amount", "").strip()
    sort = request.args.get("sort", "newest").strip()

    # VALIDATE MINIMUM AMOUNT
    parsed_min_amount = None
    if min_amount:
        try:
            parsed_min_amount = float(min_amount)
            if parsed_min_amount < 0:
                parsed_min_amount = None
                min_amount = ""
        except (ValueError, TypeError):
            parsed_min_amount = None
            min_amount = ""

    # VALIDATE MAXIMUM AMOUNT
    parsed_max_amount = None
    if max_amount:
        try:
            parsed_max_amount = float(max_amount)
            if parsed_max_amount < 0:
                parsed_max_amount = None
                max_amount = ""
        except (ValueError, TypeError):
            parsed_max_amount = None
            max_amount = ""

    # MINIMUM CANNOT BE GREATER THAN MAXIMUM
    if (
        parsed_min_amount is not None
        and parsed_max_amount is not None
        and parsed_min_amount > parsed_max_amount
    ):
        flash("Minimum amount cannot be greater than maximum amount.", "danger")
        parsed_min_amount = None
        parsed_max_amount = None
        min_amount = ""
        max_amount = ""

    # CATEGORIES
    categories = get_categories()

    # AVAILABLE YEARS
    year_rows = fetch_all(
        """
        SELECT DISTINCT
            YEAR(expense_date) AS expense_year
        FROM expenses
        WHERE user_id = %s
        ORDER BY expense_year DESC
        """,
        (user_id, )
    )
    available_years = [
        row["expense_year"]
        for row in year_rows
        if row["expense_year"] is not None
    ]
    current_year = datetime.now().year
    if current_year not in available_years:
        available_years.append(current_year)
    available_years = sorted(set(available_years), reverse=True)

    # BASE QUERY
    sql = """
        SELECT
            e.id,
            e.title,
            e.amount,
            e.expense_date,
            e.notes,
            c.name AS category_name,
            c.color AS category_color
        FROM expenses e
        JOIN categories c
            ON e.category_id = c.id
           AND (
                c.user_id IS NULL
                OR c.user_id = e.user_id
               )
        WHERE e.user_id = %s
    """
    params = [
        user_id
    ]

    # SEARCH
    if search:
        sql += """
            AND (
                e.title LIKE %s
                OR e.notes LIKE %s
                OR c.name LIKE %s
            )
        """
        search_value = f"%{search}%"
        params.extend([search_value, search_value, search_value])

    # CATEGORY FILTER
    if selected_category:
        try:
            category_value = int(selected_category)
            if category_exists(category_value):
                sql += """
                    AND e.category_id = %s
                """
                params.append(category_value)
            else:
                selected_category = ""
        except (ValueError, TypeError):
            selected_category = ""

    # START DATE
    if start_date:
        if parse_date(start_date):
            sql += """
                AND e.expense_date >= %s
            """
            params.append(start_date)
        else:
            start_date = ""

    # END DATE
    if end_date:
        if parse_date(end_date):
            sql += """
                AND e.expense_date <= %s
            """
            params.append(end_date)
        else:
            end_date = ""

    # YEAR + MONTH FILTER
    if (selected_year and selected_month):
        try:
            year_value = int(selected_year)
            month_value = int(selected_month)
            if 1 <= month_value <= 12:
                sql += """
                    AND YEAR(e.expense_date) = %s
                    AND MONTH(e.expense_date) = %s
                """
                params.extend([year_value, month_value])
            else:
                selected_month = ""
        except (ValueError, TypeError):
            selected_year = ""
            selected_month = ""

    # YEAR ONLY
    elif selected_year:
        try:
            year_value = int(selected_year)
            sql += """
                AND YEAR(e.expense_date) = %s
            """
            params.append(year_value)
        except (ValueError, TypeError):
            selected_year = ""

    # MINIMUM AMOUNT
    if parsed_min_amount is not None:
        sql += """
            AND e.amount >= %s
        """
        params.append(parsed_min_amount)

    # MAXIMUM AMOUNT
    if parsed_max_amount is not None:
        sql += """
            AND e.amount <= %s
        """
        params.append(parsed_max_amount)

    # SORTING
    sort_options = {
        "newest": """
            e.expense_date DESC,
            e.id DESC
        """,
        "oldest": """
            e.expense_date ASC,
            e.id ASC
        """,
        "highest": """
            e.amount DESC,
            e.expense_date DESC,
            e.id DESC
        """,
        "lowest": """
            e.amount ASC,
            e.expense_date DESC,
            e.id DESC
        """
    }
    if sort not in sort_options:
        sort = "newest"
    order_sql = sort_options[
        sort
    ]
    sql += f"""
        ORDER BY
            {order_sql}
    """

    # EXECUTE QUERY
    expense_rows = fetch_all(sql, tuple(params))

    # FILTERED TOTAL
    filtered_total = sum(float(expense["amount"])for expense in expense_rows)

    # RENDER PAGE
    return render_template(
        "expenses.html",
        expenses=expense_rows,
        categories=categories,
        available_years=available_years,
        search=search,
        selected_category=selected_category,
        selected_year=selected_year,
        selected_month=selected_month,
        start_date=start_date,
        end_date=end_date,
        min_amount=min_amount,
        max_amount=max_amount,
        sort=sort,
        filtered_total=filtered_total
    )

# FINANCIAL REPORT

@app.route("/report/monthly", methods=["GET"])

@login_required

def monthly_report():
    user_id = session["user_id"]

    # REPORT RANGE
    selected_range = (request.args.get("range")or"this_month")
    today = date.today()
    report_start = today.replace(day=1)
    report_end = today

    # 7 DAYS
    if selected_range == "7d":
        report_start = today - timedelta(days=6)
        report_end = today

    # 30 DAYS
    elif selected_range == "30d":
        report_start = today - timedelta(days=29)
        report_end = today

    # THIS MONTH
    elif selected_range == "this_month":
        report_start = today.replace(day=1)
        report_end = today

    # LAST MONTH
    elif selected_range == "last_month":
        first_day_this_month = today.replace(day=1)
        last_day_previous_month = (first_day_this_month-timedelta(days=1))
        report_start = last_day_previous_month.replace(day=1)
        report_end = last_day_previous_month

    # 6 MONTHS
    elif selected_range == "6m":
        report_end = today
        report_start = (today-timedelta(days=181))

    # 12 MONTHS
    elif selected_range == "12m":
        report_end = today
        report_start = (today-timedelta(days=364))

    # CUSTOM RANGE
    elif selected_range == "custom":
        start_date_string = (request.args.get("start_date")or"")
        end_date_string = (request.args.get("end_date")or"")
        try:
            report_start = datetime.strptime(start_date_string, "%Y-%m-%d").date()
            report_end = datetime.strptime(end_date_string, "%Y-%m-%d").date()
        except ValueError:
            flash("Please select valid start and end dates.", "danger")
            selected_range = "this_month"
            report_start = today.replace(day=1)
            report_end = today
        if report_start > report_end:
            flash("Start date cannot be after end date.", "danger")
            selected_range = "this_month"
            report_start = today.replace(day=1)
            report_end = today

    # OLD MONTH PARAMETER COMPATIBILITY
    selected_month = (request.args.get("month")or report_start.strftime("%Y-%m"))
    try:
        datetime.strptime(selected_month, "%Y-%m").date()
    except ValueError:
        selected_month = report_start.strftime("%Y-%m")

    # CATEGORY-WISE EXPENSE REPORT
    rows = fetch_all(
        """
        SELECT
            c.id,
            c.name,
            c.color,
            COALESCE(
                SUM(e.amount),
                0
            ) AS total,
            COUNT(e.id) AS expense_count
        FROM categories c
        LEFT JOIN expenses e
            ON e.category_id = c.id
            AND e.user_id = %s
            AND e.expense_date >= %s
            AND e.expense_date < DATE_ADD(
                %s,
                INTERVAL 1 DAY
            )
        WHERE
            c.user_id IS NULL
            OR c.user_id = %s
        GROUP BY
            c.id,
            c.name,
            c.color
        ORDER BY
            total DESC
        """,
        (user_id, report_start, report_end, user_id)
    )

    # TOTAL EXPENSES
    grand_total = sum(float(row["total"]or 0)for row in rows)
    expense_count = sum(int(row["expense_count"]or 0)for row in rows)

    # TOTAL INCOME
    income_summary = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total_income,
            COUNT(id) AS income_count
        FROM income
        WHERE
            user_id = %s
            AND income_date >= %s
            AND income_date < DATE_ADD(
                %s,
                INTERVAL 1 DAY
            )
        """,
        (user_id, report_start, report_end)
    )
    total_income = float(income_summary["total_income"]or 0)
    income_count = int(income_summary["income_count"]or 0)

    # NET BALANCE
    net_balance = (total_income-grand_total)

    # SAVINGS RATE
    if total_income > 0:
        savings_rate = (net_balance/total_income) * 100
    else:
        savings_rate = 0

    # INCOME VS EXPENSE TREND
    trend_data = []
    range_days = (report_end-report_start).days + 1

    # DAILY TREND
    if range_days <= 60:
        trend_rows = fetch_all(
            """
            SELECT
                d.report_date,
                COALESCE(
                    (
                        SELECT
                            SUM(e.amount)
                        FROM expenses e
                        WHERE
                            e.user_id = %s
                            AND e.expense_date =
                                d.report_date
                    ),
                    0
                ) AS expense,
                COALESCE(
                    (
                        SELECT
                            SUM(i.amount)
                        FROM income i
                        WHERE
                            i.user_id = %s
                            AND i.income_date =
                                d.report_date
                    ),
                    0
                ) AS income
            FROM
            (
                SELECT
                    DATE_ADD(
                        %s,
                        INTERVAL seq.n DAY
                    ) AS report_date
                FROM
                (
                    SELECT 0 AS n
                    UNION ALL SELECT 1
                    UNION ALL SELECT 2
                    UNION ALL SELECT 3
                    UNION ALL SELECT 4
                    UNION ALL SELECT 5
                    UNION ALL SELECT 6
                    UNION ALL SELECT 7
                    UNION ALL SELECT 8
                    UNION ALL SELECT 9
                    UNION ALL SELECT 10
                    UNION ALL SELECT 11
                    UNION ALL SELECT 12
                    UNION ALL SELECT 13
                    UNION ALL SELECT 14
                    UNION ALL SELECT 15
                    UNION ALL SELECT 16
                    UNION ALL SELECT 17
                    UNION ALL SELECT 18
                    UNION ALL SELECT 19
                    UNION ALL SELECT 20
                    UNION ALL SELECT 21
                    UNION ALL SELECT 22
                    UNION ALL SELECT 23
                    UNION ALL SELECT 24
                    UNION ALL SELECT 25
                    UNION ALL SELECT 26
                    UNION ALL SELECT 27
                    UNION ALL SELECT 28
                    UNION ALL SELECT 29
                    UNION ALL SELECT 30
                    UNION ALL SELECT 31
                    UNION ALL SELECT 32
                    UNION ALL SELECT 33
                    UNION ALL SELECT 34
                    UNION ALL SELECT 35
                    UNION ALL SELECT 36
                    UNION ALL SELECT 37
                    UNION ALL SELECT 38
                    UNION ALL SELECT 39
                    UNION ALL SELECT 40
                    UNION ALL SELECT 41
                    UNION ALL SELECT 42
                    UNION ALL SELECT 43
                    UNION ALL SELECT 44
                    UNION ALL SELECT 45
                    UNION ALL SELECT 46
                    UNION ALL SELECT 47
                    UNION ALL SELECT 48
                    UNION ALL SELECT 49
                    UNION ALL SELECT 50
                    UNION ALL SELECT 51
                    UNION ALL SELECT 52
                    UNION ALL SELECT 53
                    UNION ALL SELECT 54
                    UNION ALL SELECT 55
                    UNION ALL SELECT 56
                    UNION ALL SELECT 57
                    UNION ALL SELECT 58
                    UNION ALL SELECT 59
                ) seq
                WHERE DATE_ADD(
                    %s,
                    INTERVAL seq.n DAY
                ) <= %s
            ) d
            ORDER BY
                d.report_date
            """,
            (user_id, user_id, report_start, report_start, report_end)
        )
        for row in trend_rows:
            report_date = row["report_date"]
            if isinstance(report_date, str):
                try:
                    report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        report_date = datetime.strptime(report_date, "%Y-%m-%d %H:%M:%S").date()
                    except ValueError:
                        continue
            elif isinstance(report_date, datetime):
                report_date = report_date.date()
            trend_data.append(
                {
                    "label": report_date.strftime("%d %b"),
                    "income": float(row["income"]or 0),
                    "expense": float(row["expense"]or 0)
                }
            )

    # MONTHLY TREND
    else:

        # EXPENSES GROUPED BY MONTH
        expense_month_rows = fetch_all(
            """
            SELECT
                DATE_FORMAT(
                    expense_date,
                    '%%Y-%%m'
                ) AS month_key,
                COALESCE(
                    SUM(amount),
                    0
                ) AS total
            FROM expenses
            WHERE
                user_id = %s
                AND expense_date >= %s
                AND expense_date <= %s
            GROUP BY
                DATE_FORMAT(
                    expense_date,
                    '%%Y-%%m'
                )
            ORDER BY
                month_key
            """,
            (user_id, report_start, report_end)
        )

        # INCOME GROUPED BY MONTH
        income_month_rows = fetch_all(
            """
            SELECT
                DATE_FORMAT(
                    income_date,
                    '%%Y-%%m'
                ) AS month_key,
                COALESCE(
                    SUM(amount),
                    0
                ) AS total
            FROM income
            WHERE
                user_id = %s
                AND income_date >= %s
                AND income_date <= %s
            GROUP BY
                DATE_FORMAT(
                    income_date,
                    '%%Y-%%m'
                )
            ORDER BY
                month_key
            """,
            (user_id, report_start, report_end)
        )

        # EXPENSE DICTIONARY
        expense_by_month = {}
        for row in expense_month_rows:
            month_key = row["month_key"]
            if isinstance(month_key, bytes):
                month_key = month_key.decode()
            month_key = str(month_key)
            expense_by_month[month_key] = float(row["total"]or 0)

        # INCOME DICTIONARY
        income_by_month = {}
        for row in income_month_rows:
            month_key = row["month_key"]
            if isinstance(month_key, bytes):
                month_key = month_key.decode()
            month_key = str(month_key)
            income_by_month[month_key] = float(row["total"]or 0)

        # BUILD EVERY MONTH
        current_month = report_start.replace(day=1)
        final_month = report_end.replace(day=1)
        while current_month <= final_month:
            month_key = current_month.strftime("%Y-%m")
            trend_data.append(
                {
                    "label": current_month.strftime("%b %Y"),
                    "income": income_by_month.get(month_key, 0),
                    "expense": expense_by_month.get(month_key, 0)
                }
            )
            current_month = (current_month.replace(day=28)+timedelta(days=4)).replace(day=1)

    # BUDGET PERFORMANCE
    budget_performance = []

    # The budget table stores the month as the first day of that month.
    budget_start_month = report_start.replace(day=1)
    budget_end_month = report_end.replace(day=1)
    budget_rows = fetch_all(
        """
        SELECT
            b.id,
            b.budget_month,
            b.category_id,
            b.amount,
            b.notes,
            COALESCE(
                c.name,
                'Overall Budget'
            ) AS category_name,
            COALESCE(
                c.color,
                '#149B9B'
            ) AS category_color,
            COALESCE(
                (
                    SELECT
                        SUM(e.amount)
                    FROM expenses e
                    WHERE
                        e.user_id = b.user_id
                        AND e.expense_date >=
                            b.budget_month
                        AND e.expense_date <
                            DATE_ADD(
                                b.budget_month,
                                INTERVAL 1 MONTH
                            )
                        AND (
                            b.category_id IS NULL
                            OR e.category_id =
                                b.category_id
                        )
                ),
                0
            ) AS spent
        FROM budgets b
        LEFT JOIN categories c
            ON c.id = b.category_id
        WHERE
            b.user_id = %s
            AND b.budget_month >= %s
            AND b.budget_month <= %s
        ORDER BY
            b.budget_month DESC,
            category_name ASC
        """,
        (user_id, budget_start_month, budget_end_month)
    )
    for row in budget_rows:
        budget_amount = float(row["amount"]or 0)
        spent_amount = float(row["spent"]or 0)
        remaining_amount = (budget_amount-spent_amount)
        if budget_amount > 0:
            usage_percentage = (spent_amount/budget_amount) * 100
        else:
            usage_percentage = 0

        # BUDGET STATUS
        if usage_percentage >= 100:
            budget_status = "Over Budget"
            budget_status_class = "danger"
        elif usage_percentage >= 80:
            budget_status = "Near Limit"
            budget_status_class = "warning"
        else:
            budget_status = "On Track"
            budget_status_class = "success"

        # PROGRESS BAR
        progress_percentage = min(usage_percentage, 100)

        # BUDGET MONTH
        budget_month = row["budget_month"]
        if isinstance(budget_month, str):
            try:
                budget_month = datetime.strptime(budget_month, "%Y-%m-%d").date()
            except ValueError:
                try:
                    budget_month = datetime.strptime(budget_month, "%Y-%m-%d %H:%M:%S").date()
                except ValueError:
                    budget_month = budget_start_month
        elif isinstance(budget_month, datetime):
            budget_month = budget_month.date()
        budget_performance.append(
            {
                "id": row["id"],
                "category_id": row[
                    "category_id"
                ],
                "category_name": row[
                    "category_name"
                ],
                "category_color": row[
                    "category_color"
                ],
                "budget_month": budget_month.strftime("%b %Y"),
                "budget_amount": budget_amount,
                "spent_amount": spent_amount,
                "remaining_amount": remaining_amount,
                "usage_percentage": usage_percentage,
                "progress_percentage": progress_percentage,
                "status": budget_status,
                "status_class": budget_status_class
            }
        )

    # REPORT LABEL
    if selected_range == "7d":
        report_label = "Last 7 Days"
    elif selected_range == "30d":
        report_label = "Last 30 Days"
    elif selected_range == "this_month":
        report_label = today.strftime("%B %Y")
    elif selected_range == "last_month":
        report_label = report_start.strftime("%B %Y")
    elif selected_range == "6m":
        report_label = "Last 6 Months"
    elif selected_range == "12m":
        report_label = "Last 12 Months"
    elif selected_range == "custom":
        report_label = (
            f"{report_start.strftime('%d %b %Y')}"
            f" - "
            f"{report_end.strftime('%d %b %Y')}"
        )
    else:
        report_label = (
            f"{report_start.strftime('%d %b %Y')}"
            f" - "
            f"{report_end.strftime('%d %b %Y')}"
        )

    # RENDER TEMPLATE
    return render_template(
        "monthly_report.html",
        rows=rows,
        grand_total=grand_total,
        expense_count=expense_count,
        selected_month=selected_month,
        selected_range=selected_range,
        start_date=report_start.strftime("%Y-%m-%d"),
        end_date=report_end.strftime("%Y-%m-%d"),
        report_label=report_label,
        total_income=total_income,
        income_count=income_count,
        net_balance=net_balance,
        savings_rate=savings_rate,
        trend_data=trend_data,
        budget_performance=budget_performance
    )

# INCOME LIST / SEARCH / FILTERS

@app.route("/income")

@login_required

def income():
    user_id = session["user_id"]
    search = request.args.get("search", "").strip()
    selected_category = request.args.get("category", "").strip()
    selected_year = request.args.get("year", "").strip()
    selected_month = request.args.get("month", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    query = """
        SELECT
            i.*,
            c.name AS category_name,
            c.color
        FROM income i
        JOIN income_categories c
            ON c.id = i.category_id
        WHERE i.user_id = %s
    """
    params = [
        user_id
    ]
    if search:
        query += """
            AND (
                i.title LIKE %s
                OR i.notes LIKE %s
                OR c.name LIKE %s
            )
        """
        search_value = f"%{search}%"
        params.extend([search_value, search_value, search_value])
    if selected_category:
        try:
            category_value = int(selected_category)
            query += """
                AND i.category_id = %s
            """
            params.append(category_value)
        except ValueError:
            selected_category = ""
    if selected_year:
        try:
            year_value = int(selected_year)
            query += """
                AND YEAR(i.income_date) = %s
            """
            params.append(year_value)
        except ValueError:
            selected_year = ""
    if selected_month:
        try:
            month_value = int(selected_month)
            if 1 <= month_value <= 12:
                query += """
                    AND MONTH(i.income_date) = %s
                """
                params.append(month_value)
            else:
                selected_month = ""
        except ValueError:
            selected_month = ""
    if start_date:
        if parse_date(start_date):
            query += """
                AND i.income_date >= %s
            """
            params.append(start_date)
        else:
            start_date = ""
    if end_date:
        if parse_date(end_date):
            query += """
                AND i.income_date <= %s
            """
            params.append(end_date)
        else:
            end_date = ""
    query += """
        ORDER BY
            i.income_date DESC,
            i.id DESC
    """
    rows = fetch_all(query, tuple(params))
    total = sum(float(row["amount"])for row in rows)
    categories = get_income_categories()
    available_years = fetch_all(
        """
        SELECT DISTINCT
            YEAR(income_date) AS year
        FROM income
        WHERE user_id = %s
        ORDER BY year DESC
        """,
        (user_id,)
    )
    return render_template(
        "income.html",
        income_rows=rows,
        categories=categories,
        total=total,
        search=search,
        selected_category=selected_category,
        selected_year=selected_year,
        selected_month=selected_month,
        start_date=start_date,
        end_date=end_date,
        available_years=available_years
    )

# ADD INCOME

@app.route("/add-income", methods=["GET", "POST"])

@login_required

def add_income():
    categories = get_income_categories()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        category_id_raw = request.form.get("category_id", "").strip()
        income_date = request.form.get("income_date", "").strip()
        notes = request.form.get("notes", "").strip()
        if not title:
            flash("Income source is required.", "danger")
            return render_template(
                "add_income.html",
                categories=categories,
                today=date.today().isoformat()
            )
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Please enter a valid income amount.", "danger")
            return render_template(
                "add_income.html",
                categories=categories,
                today=date.today().isoformat()
            )
        try:
            category_id = int(category_id_raw)
        except (ValueError, TypeError):
            flash("Please select an income category.", "danger")
            return render_template(
                "add_income.html",
                categories=categories,
                today=date.today().isoformat()
            )
        parsed_date = parse_date(income_date)
        if not parsed_date:
            flash("Please select a valid date.", "danger")
            return render_template(
                "add_income.html",
                categories=categories,
                today=date.today().isoformat()
            )
        category = fetch_one(
            """
            SELECT
                id
            FROM income_categories
            WHERE id = %s
            """,
            (category_id,)
        )
        if not category:
            flash("Invalid income category.", "danger")
            return render_template(
                "add_income.html",
                categories=categories,
                today=date.today().isoformat()
            )
        try:
            execute_query(
                """
                INSERT INTO income
                (
                    user_id,
                    title,
                    amount,
                    category_id,
                    income_date,
                    notes
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (session["user_id"], title, amount, category_id, parsed_date, notes or None)
            )
            flash("Income added successfully.", "success")
            return redirect(url_for("income"))
        except Error:
            flash("Unable to save income. Please try again.", "danger")
    return render_template("add_income.html", categories=categories, today=date.today().isoformat())

# EDIT INCOME

@app.route("/edit-income/<int:income_id>", methods=["GET", "POST"])

@login_required

def edit_income(income_id):
    income_record = get_income(income_id)
    if not income_record:
        abort(404)
    categories = get_income_categories()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        category_id_raw = request.form.get("category_id", "").strip()
        income_date = request.form.get("income_date", "").strip()
        notes = request.form.get("notes", "").strip()
        if not title:
            flash("Income source is required.", "danger")
            return render_template("edit_income.html", income=income_record, categories=categories)
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Please enter a valid income amount.", "danger")
            return render_template("edit_income.html", income=income_record, categories=categories)
        try:
            category_id = int(category_id_raw)
        except (ValueError, TypeError):
            flash("Please select an income category.", "danger")
            return render_template("edit_income.html", income=income_record, categories=categories)
        parsed_date = parse_date(income_date)
        if not parsed_date:
            flash("Please select a valid date.", "danger")
            return render_template("edit_income.html", income=income_record, categories=categories)
        category = fetch_one(
            """
            SELECT
                id
            FROM income_categories
            WHERE id = %s
            """,
            (category_id,)
        )
        if not category:
            flash("Invalid income category.", "danger")
            return render_template("edit_income.html", income=income_record, categories=categories)
        try:
            execute_query(
                """
                UPDATE income
                SET
                    title = %s,
                    amount = %s,
                    category_id = %s,
                    income_date = %s,
                    notes = %s
                WHERE id = %s
                  AND user_id = %s
                """,
                (
                    title,
                    amount,
                    category_id,
                    parsed_date,
                    notes or None,
                    income_id,
                    session["user_id"]
                )
            )
            flash("Income updated successfully.", "success")
            return redirect(url_for("income"))
        except Error:
            flash("Unable to update income. Please try again.", "danger")
    return render_template("edit_income.html", income=income_record, categories=categories)

# DELETE INCOME

@app.route("/delete-income/<int:income_id>", methods=["POST"])

@login_required

def delete_income(income_id):
    income_record = get_income(income_id)
    if not income_record:
        abort(404)
    try:
        execute_query(
            """
            DELETE FROM income
            WHERE id = %s
              AND user_id = %s
            """,
            (income_id, session["user_id"])
        )
        flash(f'"{income_record["title"]}" was deleted successfully.', "success")
    except Error:
        flash("Unable to delete income. Please try again.", "danger")
    return redirect(request.referrer or url_for("income"))

# BUDGET MANAGEMENT

@app.route("/budgets")

@login_required

def budgets():
    selected_month = request.args.get("month", datetime.now().strftime("%Y-%m")).strip()
    budget_month_date = parse_month(selected_month)
    if not budget_month_date:
        budget_month_date = (datetime.now().date().replace(day=1))
    selected_month = (budget_month_date.strftime("%Y-%m"))
    budget_month = budget_month_date
    monthly_budget = get_month_budget_total(budget_month)
    total_budget = (float(monthly_budget["amount"])if monthly_budget else 0.0)
    total_spent = get_month_expense_total(budget_month)
    remaining = (total_budget-total_spent)
    if total_budget > 0:
        percentage_used = (total_spent/total_budget) * 100
    else:
        percentage_used = 0
    progress_percentage = min(max(percentage_used, 0), 100)
    category_budgets = get_category_budgets(budget_month)
    category_budget_data = []
    for budget in category_budgets:
        category_spent = (get_category_expense_total(budget["category_id"], budget_month))
        category_amount = float(budget["amount"])
        category_remaining = (category_amount-category_spent)
        if category_amount > 0:
            category_percentage = (category_spent/category_amount) * 100
        else:
            category_percentage = 0
        category_progress = min(max(category_percentage, 0), 100)
        category_budget_data.append(
            {
                "id": budget["id"],
                "category_id": budget["category_id"],
                "category_name": budget["category_name"],
                "color": budget["color"],
                "amount": category_amount,
                "spent": category_spent,
                "remaining": category_remaining,
                "percentage": category_percentage,
                "progress": category_progress,
                "notes": budget["notes"],
            }
        )
    return render_template(
        "budgets.html",
        budget_month=selected_month,
        monthly_budget=monthly_budget,
        total_budget=total_budget,
        total_spent=total_spent,
        remaining=remaining,
        percentage_used=percentage_used,
        progress_percentage=progress_percentage,
        category_budget_data=category_budget_data
    )

# ADD BUDGET

@app.route("/budgets/add", methods=["GET", "POST"])

@login_required

def add_budget():
    categories = get_budget_categories()
    if request.method == "POST":
        category_id_raw = request.form.get("category_id", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        budget_month = request.form.get("budget_month", "").strip()
        notes = request.form.get("notes", "").strip()
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Budget amount must be greater than zero.", "danger")
            return render_template("add_budget.html", categories=categories)
        budget_month_date = parse_month(budget_month)
        if not budget_month_date:
            flash("Invalid budget month.", "danger")
            return render_template("add_budget.html", categories=categories)

        # CATEGORY
        if category_id_raw:
            try:
                category_id = int(category_id_raw)
            except (ValueError, TypeError):
                flash("Invalid category.", "danger")
                return render_template("add_budget.html", categories=categories)
            if not category_exists(category_id):
                flash("Please choose a valid category.", "danger")
                return render_template("add_budget.html", categories=categories)
        else:
            category_id = None

        # DUPLICATE CHECK
        existing = fetch_one(
            """
            SELECT
                id
            FROM budgets
            WHERE user_id = %s
              AND budget_month = %s
              AND (
                    category_id = %s
                    OR (
                        category_id IS NULL
                        AND %s IS NULL
                    )
                  )
            LIMIT 1
            """,
            (session["user_id"], budget_month_date, category_id, category_id)
        )
        if existing:
            flash("A budget already exists for this month and category.", "warning")
            return render_template("add_budget.html", categories=categories)

        # INSERT
        try:
            execute_query(
                """
                INSERT INTO budgets
                (
                    user_id,
                    category_id,
                    amount,
                    budget_month,
                    notes
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (session["user_id"], category_id, amount, budget_month_date, notes or None)
            )
            flash("Budget added successfully.", "success")
        except Error:
            flash("Unable to save the budget. Please try again.", "danger")
            return render_template("add_budget.html", categories=categories)
        return redirect(url_for("budgets", month=budget_month_date.strftime("%Y-%m")))
    return render_template("add_budget.html", categories=categories)

# EDIT BUDGET

@app.route("/budgets/edit/<int:budget_id>", methods=["GET", "POST"])

@login_required

def edit_budget(budget_id):
    budget = get_budget(budget_id)
    if not budget:
        flash("Budget not found.", "danger")
        return redirect(url_for("budgets"))
    categories = get_budget_categories()
    if request.method == "POST":
        category_id_raw = request.form.get("category_id", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        budget_month = request.form.get("budget_month", "").strip()
        notes = request.form.get("notes", "").strip()
        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Budget amount must be greater than zero.", "danger")
            return render_template("edit_budget.html", budget=budget, categories=categories)
        budget_month_date = parse_month(budget_month)
        if not budget_month_date:
            flash("Invalid budget month.", "danger")
            return render_template("edit_budget.html", budget=budget, categories=categories)

        # CATEGORY
        if category_id_raw:
            try:
                category_id = int(category_id_raw)
            except (ValueError, TypeError):
                flash("Invalid category.", "danger")
                return render_template("edit_budget.html", budget=budget, categories=categories)
            if not category_exists(category_id):
                flash("Please choose a valid category.", "danger")
                return render_template("edit_budget.html", budget=budget, categories=categories)
        else:
            category_id = None

        # DUPLICATE CHECK
        existing = fetch_one(
            """
            SELECT
                id
            FROM budgets
            WHERE user_id = %s
              AND id <> %s
              AND budget_month = %s
              AND (
                    category_id = %s
                    OR (
                        category_id IS NULL
                        AND %s IS NULL
                    )
                  )
            LIMIT 1
            """,
            (session["user_id"], budget_id, budget_month_date, category_id, category_id)
        )
        if existing:
            flash("Another budget already exists for this month and category.", "warning")
            return render_template("edit_budget.html", budget=budget, categories=categories)

        # UPDATE
        try:
            execute_query(
                """
                UPDATE budgets
                SET
                    category_id = %s,
                    amount = %s,
                    budget_month = %s,
                    notes = %s
                WHERE id = %s
                  AND user_id = %s
                """,
                (
                    category_id,
                    amount,
                    budget_month_date,
                    notes or None,
                    budget_id,
                    session["user_id"]
                )
            )
            flash("Budget updated successfully.", "success")
        except Error:
            flash("Unable to update the budget. Please try again.", "danger")
            return render_template("edit_budget.html", budget=budget, categories=categories)
        return redirect(url_for("budgets", month=budget_month_date.strftime("%Y-%m")))
    return render_template("edit_budget.html", budget=budget, categories=categories)

# DELETE BUDGET

@app.route("/budgets/delete/<int:budget_id>", methods=["POST"])

@login_required

def delete_budget(budget_id):
    budget = get_budget(budget_id)
    if not budget:
        flash("Budget not found.", "danger")
        return redirect(url_for("budgets"))
    budget_month = budget[
        "budget_month"
    ]
    try:
        execute_query(
            """
            DELETE FROM budgets
            WHERE id = %s
              AND user_id = %s
            """,
            (budget_id, session["user_id"])
        )
        flash("Budget deleted successfully.", "success")
    except Error:
        flash("Unable to delete the budget. Please try again.", "danger")
    return redirect(url_for("budgets", month=budget_month.strftime("%Y-%m")))

# ADVANCED ANALYTICS

@app.route("/analytics", methods=["GET"])

@login_required

def analytics():
    user_id = session["user_id"]
    today = date.today()
    selected_range = request.args.get("range", "30d").strip()
    start_date_raw = request.args.get("start_date", "").strip()
    end_date_raw = request.args.get("end_date", "").strip()

    # DATE RANGE
    if selected_range == "7d":
        from datetime import timedelta
        start_date = today-timedelta(days=6)
        end_date = today
    elif selected_range == "30d":
        from datetime import timedelta
        start_date = today - timedelta(days=29)
        end_date = today
    elif selected_range == "6m":
        start_date = (today.replace(day=1))
        month = start_date.month - 5
        year = start_date.year
        while month <= 0:
            month += 12
            year -= 1
        start_date = start_date.replace(year=year, month=month)
        end_date = today
    elif selected_range == "12m":
        start_date = (today.replace(day=1))
        month = start_date.month - 11
        year = start_date.year
        while month <= 0:
            month += 12
            year -= 1
        start_date = start_date.replace(year=year, month=month)
        end_date = today
    elif selected_range == "custom":
        custom_start = parse_date(start_date_raw)
        custom_end = parse_date(end_date_raw)
        if (custom_start and custom_end and custom_start<=custom_end):
            start_date = custom_start
            end_date = custom_end
        else:
            flash("Please select a valid custom date range.", "warning")
            selected_range = "30d"
            from datetime import timedelta
            start_date = (today-timedelta(days=29))
            end_date = today
    else:
        selected_range = "30d"
        from datetime import timedelta
        start_date = (today-timedelta(days=29))
        end_date = today

    # TOTAL INCOME
    income_row = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total,
            COUNT(*) AS count
        FROM income
        WHERE user_id = %s
          AND income_date >= %s
          AND income_date <= %s
        """,
        (user_id, start_date, end_date)
    )
    total_income = float(income_row["total"]or 0)
    income_count = int(income_row["count"]or 0)

    # TOTAL EXPENSES
    expense_row = fetch_one(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total,
            COUNT(*) AS count
        FROM expenses
        WHERE user_id = %s
          AND expense_date >= %s
          AND expense_date <= %s
        """,
        (user_id, start_date, end_date)
    )
    total_expenses = float(expense_row["total"]or 0)
    expense_count = int(expense_row["count"]or 0)

    # BALANCE
    net_balance = (total_income-total_expenses)

    # SAVINGS RATE
    if total_income > 0:
        savings_rate = (net_balance/total_income) * 100
    else:
        savings_rate = 0

    # EXPENSE BY CATEGORY
    category_rows = fetch_all(
        """
        SELECT
            c.name,
            c.color,
            COALESCE(
                SUM(e.amount),
                0
            ) AS total,
            COUNT(e.id) AS transaction_count
        FROM categories c
        LEFT JOIN expenses e
            ON e.category_id = c.id
           AND e.user_id = %s
           AND e.expense_date >= %s
           AND e.expense_date <= %s
        WHERE c.user_id IS NULL
           OR c.user_id = %s
        GROUP BY
            c.id,
            c.name,
            c.color
        HAVING SUM(e.amount) > 0
        ORDER BY total DESC
        """,
        (user_id, start_date, end_date, user_id)
    )

    # MONTHLY INCOME TREND
    income_trend = fetch_all(
        """
        SELECT
            DATE_FORMAT(
                income_date,
                '%Y-%m'
            ) AS month,
            COALESCE(
                SUM(amount),
                0
            ) AS total
        FROM income
        WHERE user_id = %s
          AND income_date >= %s
          AND income_date <= %s
        GROUP BY
            DATE_FORMAT(
                income_date,
                '%Y-%m'
            )
        ORDER BY month
        """,
        (user_id, start_date, end_date)
    )

    # MONTHLY EXPENSE TREND
    expense_trend = fetch_all(
        """
        SELECT
            DATE_FORMAT(
                expense_date,
                '%Y-%m'
            ) AS month,
            COALESCE(
                SUM(amount),
                0
            ) AS total
        FROM expenses
        WHERE user_id = %s
          AND expense_date >= %s
          AND expense_date <= %s
        GROUP BY
            DATE_FORMAT(
                expense_date,
                '%Y-%m'
            )
        ORDER BY month
        """,
        (user_id, start_date, end_date)
    )

    # MERGE MONTHLY TREND
    trend_map = {}
    for row in income_trend:
        month = row["month"]
        trend_map.setdefault(month, {"income":0, "expense":0})
        trend_map[month]["income"] = float(row["total"]or 0)
    for row in expense_trend:
        month = row["month"]
        trend_map.setdefault(month, {"income":0, "expense":0})
        trend_map[month]["expense"] = float(row["total"]or 0)
    trend_data = []
    for month in sorted(trend_map.keys()):
        trend_data.append(
            {
                "month": month,
                "income": trend_map[month]["income"],
                "expense": trend_map[month]["expense"],
                "balance": (trend_map[month]["income"]-trend_map[month]["expense"])
            }
        )

    # TOP CATEGORY
    top_category = (category_rows[0]if category_rows else None)

    # AVERAGE DAILY EXPENSE
    number_of_days = (end_date-start_date).days + 1
    average_daily_expense = (total_expenses/number_of_days if number_of_days>0 else 0)

    # RENDER
    return render_template(
        "analytics.html",
        selected_range=selected_range,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_income=total_income,
        total_expenses=total_expenses,
        net_balance=net_balance,
        savings_rate=savings_rate,
        income_count=income_count,
        expense_count=expense_count,
        category_rows=category_rows,
        trend_data=trend_data,
        top_category=top_category,
        average_daily_expense=average_daily_expense
    )

# ERROR HANDLERS

@app.errorhandler(404)

def not_found(error):
    return render_template("404.html"), 404

@app.errorhandler(500)

def internal_error(error):
    return render_template("500.html"), 500

# DOWNLOAD MONTHLY / FINANCIAL REPORT PDF

@app.route("/report/monthly/pdf", methods=["GET"])

@login_required

def monthly_report_pdf():
    user_id = session["user_id"]

    # REPORT RANGE
    selected_range = (request.args.get("range")or"this_month").strip()
    today = date.today()
    report_start = today
    report_end = today

    # MONTH SHIFT HELPER

    def shift_month(source_date, months):
        total_months = (source_date.year*12+source_date.month-1+months)
        year = total_months // 12
        month = total_months % 12 + 1
        return date(year, month, 1)

    # RANGE SELECTION
    if selected_range == "7d":
        report_start = (today-timedelta(days=6))
        report_end = today
        report_label = "Last 7 Days"
    elif selected_range == "30d":
        report_start = (today-timedelta(days=29))
        report_end = today
        report_label = "Last 30 Days"
    elif selected_range == "this_month":
        report_start = today.replace(day=1)
        report_end = today
        report_label = today.strftime("%B %Y")
    elif selected_range == "last_month":
        current_month_start = today.replace(day=1)
        report_start = shift_month(current_month_start, -1)
        report_end = (current_month_start-timedelta(days=1))
        report_label = report_start.strftime("%B %Y")
    elif selected_range == "6m":
        current_month_start = today.replace(day=1)
        report_start = shift_month(current_month_start, -5)
        report_end = today
        report_label = "Last 6 Months"
    elif selected_range == "12m":
        current_month_start = today.replace(day=1)
        report_start = shift_month(current_month_start, -11)
        report_end = today
        report_label = "Last 12 Months"
    elif selected_range == "custom":
        start_raw = (request.args.get("start_date", "").strip())
        end_raw = (request.args.get("end_date", "").strip())
        try:
            report_start = datetime.strptime(start_raw, "%Y-%m-%d").date()
            report_end = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            report_start = today.replace(day=1)
            report_end = today
            selected_range = "this_month"
        if report_start > report_end:
            report_start, report_end = (report_end, report_start)
        report_label = (
            f"{report_start.strftime('%d %b %Y')} "
            f"to "
            f"{report_end.strftime('%d %b %Y')}"
        )
    else:
        selected_range = "this_month"
        report_start = today.replace(day=1)
        report_end = today
        report_label = today.strftime("%B %Y")

    # NEXT DAY FOR SQL RANGE
    report_end_exclusive = (report_end+timedelta(days=1))

    # CATEGORY BREAKDOWN
    rows = fetch_all(
        """
        SELECT
            c.name,
            c.color,
            COALESCE(SUM(e.amount), 0) AS total,
            COUNT(e.id) AS expense_count
        FROM categories c
        LEFT JOIN expenses e
            ON e.category_id = c.id
           AND e.user_id = %s
           AND e.expense_date >= %s
           AND e.expense_date < %s
        WHERE c.user_id IS NULL
           OR c.user_id = %s
        GROUP BY
            c.id,
            c.name,
            c.color
        ORDER BY total DESC
        """,
        (user_id, report_start, report_end_exclusive, user_id)
    )

    # TOTAL EXPENSES
    grand_total = sum(float(row["total"]or 0)for row in rows)
    expense_count = sum(int(row["expense_count"]or 0)for row in rows)

    # TOTAL INCOME
    income_summary = fetch_one(
        """
        SELECT
            COALESCE(SUM(amount), 0) AS total_income,
            COUNT(id) AS income_count
        FROM income
        WHERE user_id = %s
          AND income_date >= %s
          AND income_date < %s
        """,
        (user_id, report_start, report_end_exclusive)
    )
    total_income = float(income_summary["total_income"]or 0)
    income_count = int(income_summary["income_count"]or 0)

    # NET BALANCE / SAVINGS RATE
    net_balance = (total_income-grand_total)
    if total_income > 0:
        savings_rate = (net_balance/total_income) * 100
    else:
        savings_rate = 0

    # TREND DATA
    trend_data = []

    # DAILY TREND
    report_days = (report_end-report_start).days + 1
    if report_days <= 60:
        expense_trend_rows = fetch_all(
            """
            SELECT
                expense_date AS report_date,
                COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id = %s
              AND expense_date >= %s
              AND expense_date < %s
            GROUP BY expense_date
            ORDER BY expense_date
            """,
            (user_id, report_start, report_end_exclusive)
        )
        income_trend_rows = fetch_all(
            """
            SELECT
                income_date AS report_date,
                COALESCE(SUM(amount), 0) AS total
            FROM income
            WHERE user_id = %s
              AND income_date >= %s
              AND income_date < %s
            GROUP BY income_date
            ORDER BY income_date
            """,
            (user_id, report_start, report_end_exclusive)
        )
        expense_by_date = {
            (
                row["report_date"]
                if not isinstance(row["report_date"], datetime)
                else row["report_date"].date()
            ): float(row["total"]or 0)
            for row in expense_trend_rows
        }
        income_by_date = {
            (
                row["report_date"]
                if not isinstance(row["report_date"], datetime)
                else row["report_date"].date()
            ): float(row["total"]or 0)
            for row in income_trend_rows
        }
        current_date = report_start
        while current_date <= report_end:
            income_value = (income_by_date.get(current_date, 0))
            expense_value = (expense_by_date.get(current_date, 0))
            trend_data.append({
                "label":
                    current_date.strftime("%d %b"),
                "income":
                    income_value,
                "expense":
                    expense_value,
                "net":
                    income_value - expense_value
            })
            current_date += timedelta(days=1)

    # MONTHLY TREND
    else:
        expense_month_rows = fetch_all(
            """
            SELECT
                DATE_FORMAT(
                    expense_date,
                    '%%Y-%%m'
                ) AS report_month,
                COALESCE(
                    SUM(amount),
                    0
                ) AS total
            FROM expenses
            WHERE user_id = %s
              AND expense_date >= %s
              AND expense_date < %s
            GROUP BY
                DATE_FORMAT(
                    expense_date,
                    '%%Y-%%m'
                )
            ORDER BY report_month
            """,
            (user_id, report_start, report_end_exclusive)
        )
        income_month_rows = fetch_all(
            """
            SELECT
                DATE_FORMAT(
                    income_date,
                    '%%Y-%%m'
                ) AS report_month,
                COALESCE(
                    SUM(amount),
                    0
                ) AS total
            FROM income
            WHERE user_id = %s
              AND income_date >= %s
              AND income_date < %s
            GROUP BY
                DATE_FORMAT(
                    income_date,
                    '%%Y-%%m'
                )
            ORDER BY report_month
            """,
            (user_id, report_start, report_end_exclusive)
        )
        expense_by_month = {
            str(row["report_month"]):
                float(row["total"]or 0)
            for row in expense_month_rows
        }
        income_by_month = {
            str(row["report_month"]):
                float(row["total"]or 0)
            for row in income_month_rows
        }
        current_month = (report_start.replace(day=1))
        final_month = (report_end.replace(day=1))
        while current_month <= final_month:
            month_key = (current_month.strftime("%Y-%m"))
            income_value = (income_by_month.get(month_key, 0))
            expense_value = (expense_by_month.get(month_key, 0))
            trend_data.append({
                "label":
                    current_month.strftime("%b %Y"),
                "income":
                    income_value,
                "expense":
                    expense_value,
                "net":
                    income_value - expense_value
            })
            current_month = shift_month(current_month, 1)

    # BUDGET PERFORMANCE
    budget_performance = []
    budget_start_month = (report_start.replace(day=1))
    budget_end_month = (report_end.replace(day=1))
    budget_rows = fetch_all(
        """
        SELECT
            b.id,
            b.budget_month,
            b.category_id,
            b.amount,
            b.notes,
            COALESCE(
                c.name,
                'Overall Budget'
            ) AS category_name,
            COALESCE(
                c.color,
                '#149B9B'
            ) AS category_color,
            COALESCE(
                (
                    SELECT SUM(e.amount)
                    FROM expenses e
                    WHERE e.user_id = b.user_id
                      AND e.expense_date >= b.budget_month
                      AND e.expense_date < DATE_ADD(
                          b.budget_month,
                          INTERVAL 1 MONTH
                      )
                      AND (
                          b.category_id IS NULL
                          OR e.category_id = b.category_id
                      )
                ),
                0
            ) AS spent
        FROM budgets b
        LEFT JOIN categories c
            ON c.id = b.category_id
        WHERE b.user_id = %s
          AND b.budget_month >= %s
          AND b.budget_month <= %s
        ORDER BY
            b.budget_month DESC,
            category_name ASC
        """,
        (user_id, budget_start_month, budget_end_month)
    )
    for budget in budget_rows:
        budget_amount = float(budget["amount"]or 0)
        spent_amount = float(budget["spent"]or 0)
        remaining_amount = (budget_amount-spent_amount)
        if budget_amount > 0:
            usage_percentage = (spent_amount/budget_amount) * 100
        else:
            usage_percentage = 0
        if usage_percentage >= 100:
            status = "Over Budget"
            status_class = "danger"
        elif usage_percentage >= 80:
            status = "Near Limit"
            status_class = "warning"
        else:
            status = "On Track"
            status_class = "success"
        budget_progress = min(usage_percentage, 100)
        budget_month_value = (budget["budget_month"])
        if isinstance(budget_month_value, datetime):
            budget_month_value = (budget_month_value.date())
        budget_performance.append({
            "id":
                budget["id"],
            "category_id":
                budget["category_id"],
            "category_name":
                budget["category_name"],
            "category_color":
                budget["category_color"],
            "budget_month":
                budget_month_value.strftime("%b %Y"),
            "budget_amount":
                budget_amount,
            "spent_amount":
                spent_amount,
            "remaining_amount":
                remaining_amount,
            "usage_percentage":
                usage_percentage,
            "progress_percentage":
                budget_progress,
            "status":
                status,
            "status_class":
                status_class
        })

    # BUILD PDF
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="SpendWise Financial Report",
        author="SpendWise"
    )

    # COLORS
    BRAND = colors.HexColor("#E96A4A")
    NAVY = colors.HexColor("#17313B")
    TEAL = colors.HexColor("#149B9B")
    GREEN = colors.HexColor("#43A66F")
    GOLD = colors.HexColor("#EDB33E")
    RED = colors.HexColor("#DC5D7A")
    LIGHT = colors.HexColor("#F8F5EF")
    BORDER = colors.HexColor("#E9E3D8")
    MUTED = colors.HexColor("#667984")

    # STYLES
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SpendWiseTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "SpendWiseSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=MUTED,
        spaceAfter=12
    )
    section_style = ParagraphStyle(
        "SpendWiseSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=8
    )
    normal_style = ParagraphStyle(
        "SpendWiseNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=NAVY
    )
    small_style = ParagraphStyle(
        "SpendWiseSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=MUTED
    )

    # MONEY FORMATTER

    def money(value):
        return ("Rs. "+format(float(value or 0), ",.2f"))

    def percent(value):
        return (f"{float(value or 0):,.1f}%")

    # STORY
    story = []

    # HEADER
    story.append(Paragraph("SpendWise", title_style))
    story.append(
        Paragraph(
            "Financial Report",
            ParagraphStyle(
                "ReportTitle",
                parent=section_style,
                fontSize=16,
                textColor=BRAND,
                spaceBefore=0,
                spaceAfter=4
            )
        )
    )
    story.append(
        Paragraph(
            (
                f"<b>Report period:</b> "
                f"{report_label}<br/>"
                f"<b>From:</b> "
                f"{report_start.strftime('%d %b %Y')} "
                f"&nbsp;&nbsp;"
                f"<b>To:</b> "
                f"{report_end.strftime('%d %b %Y')}"
            ),
            subtitle_style
        )
    )

    # SUMMARY
    story.append(Paragraph("Financial Summary", section_style))
    summary_data = [
        [
            Paragraph("<b>Total Income</b>", normal_style),
            Paragraph("<b>Total Expenses</b>", normal_style),
            Paragraph("<b>Net Balance</b>", normal_style),
            Paragraph("<b>Savings Rate</b>", normal_style)
        ],
        [
            Paragraph(
                money(total_income),
                ParagraphStyle("IncomeValue", parent=normal_style, fontSize=11, textColor=GREEN)
            ),
            Paragraph(
                money(grand_total),
                ParagraphStyle("ExpenseValue", parent=normal_style, fontSize=11, textColor=BRAND)
            ),
            Paragraph(
                money(net_balance),
                ParagraphStyle("BalanceValue", parent=normal_style, fontSize=11, textColor=TEAL)
            ),
            Paragraph(
                percent(savings_rate),
                ParagraphStyle("SavingsValue", parent=normal_style, fontSize=11, textColor=NAVY)
            )
        ]
    ]
    summary_table = Table(summary_data, colWidths=[43*mm, 43*mm, 43*mm, 43*mm])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8)
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 8))

    # TRANSACTION COUNTS
    transaction_data = [
        [
            "Expense Transactions",
            "Income Transactions"
        ],
        [
            str(expense_count),
            str(income_count)
        ]
    ]
    transaction_table = Table(transaction_data, colWidths=[86*mm, 86*mm])
    transaction_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EFEB")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
        ])
    )
    story.append(transaction_table)

    # CATEGORY BREAKDOWN
    story.append(Paragraph("Spending by Category", section_style))
    category_data = [
        [
            "Category",
            "Entries",
            "Total",
            "Share"
        ]
    ]
    for row in rows:
        total = float(row["total"]or 0)
        if total <= 0:
            continue
        if grand_total > 0:
            share = (total/grand_total) * 100
        else:
            share = 0
        category_data.append([
            str(row["name"]),
            str(row["expense_count"]or 0),
            money(total),
            percent(share)
        ])
    if len(category_data) == 1:
        category_data.append(["No expenses", "-", money(0), "0.0%"])
    category_table = Table(category_data, colWidths=[72*mm, 28*mm, 45*mm, 27*mm], repeatRows=1)
    category_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
        ])
    )
    story.append(category_table)

    # BUDGET PERFORMANCE
    story.append(Paragraph("Budget Performance", section_style))
    budget_data = [
        [
            "Month",
            "Category",
            "Budget",
            "Spent",
            "Remaining",
            "Usage",
            "Status"
        ]
    ]
    for budget in budget_performance:
        budget_data.append([
            str(budget["budget_month"]),
            str(budget["category_name"]),
            money(budget["budget_amount"]),
            money(budget["spent_amount"]),
            money(budget["remaining_amount"]),
            percent(budget["usage_percentage"]),
            str(budget["status"])
        ])
    if len(budget_data) == 1:
        budget_data.append(["No budgets", "-", money(0), money(0), money(0), "0.0%", "No Budget"])
    budget_table = Table(
        budget_data,
        colWidths=[
            25 * mm,
            39 * mm,
            27 * mm,
            27 * mm,
            29 * mm,
            22 * mm,
            25 * mm
        ],
        repeatRows=1
    )
    budget_style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ALIGN", (2, 1), (5, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5)
    ]

    # STATUS COLORS
    for index, budget in enumerate(budget_performance, start=1):
        if budget["status_class"] == "danger":
            budget_style_commands.append(("TEXTCOLOR", (6, index), (6, index), RED))
        elif budget["status_class"] == "warning":
            budget_style_commands.append(("TEXTCOLOR", (6, index), (6, index), GOLD))
        else:
            budget_style_commands.append(("TEXTCOLOR", (6, index), (6, index), GREEN))
    budget_table.setStyle(TableStyle(budget_style_commands))
    story.append(budget_table)

    # TREND DATA
    story.append(PageBreak())
    story.append(Paragraph("Income vs Expense Trend", section_style))
    story.append(
        Paragraph(
            ("The table below contains the same trend data ""used by the Financial Report chart."),
            subtitle_style
        )
    )
    trend_table_data = [
        [
            "Period",
            "Income",
            "Expenses",
            "Net"
        ]
    ]
    for trend in trend_data:
        trend_table_data.append([
            str(trend["label"]),
            money(trend["income"]),
            money(trend["expense"]),
            money(trend["net"])
        ])
    if len(trend_table_data) == 1:
        trend_table_data.append(["No data", money(0), money(0), money(0)])
    trend_table = Table(trend_table_data, colWidths=[55*mm, 40*mm, 40*mm, 40*mm], repeatRows=1)
    trend_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
        ])
    )
    story.append(trend_table)

    # FOOTER
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            ("Generated by SpendWise · "f"{datetime.now().strftime('%d %b %Y %H:%M')}"),
            ParagraphStyle("FooterText", parent=small_style, alignment=TA_CENTER)
        )
    )

    # BUILD PDF
    doc.build(story)
    pdf_buffer.seek(0)

    # SAFE FILE NAME
    safe_range = (selected_range.replace(" ", "_"))
    filename = (f"SpendWise_Financial_Report_"f"{safe_range}.pdf")
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

# RUN APPLICATION
if __name__ == "__main__":
    app.run(debug=True)
