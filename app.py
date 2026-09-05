import os
from datetime import date, datetime

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "expense_tracker"),
        autocommit=True,
    )


def fetch_all(sql, params=()):
    """Run a SELECT query and return every matching row as dictionaries."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True,buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def fetch_one(sql, params=()):
    """Run a SELECT query and return one row, or None when nothing matches."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True,buffered=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def execute_query(sql, params=()):
    """Run INSERT, UPDATE, or DELETE, then return the affected row id."""
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


def get_categories():
    """Return categories in one consistent order for forms and filters."""
    return fetch_all("SELECT * FROM categories ORDER BY name")


def category_exists(category_id):
    """Check that the category selected in the form really exists."""
    return fetch_one("SELECT id FROM categories WHERE id = %s", (category_id,))


@app.template_filter("inr")
def inr(value):
    return f"₹{float(value or 0):,.2f}"


@app.route("/",methods=['GET'])
def dashboard():
    current_month = date.today().strftime("%Y-%m")
    stats = fetch_one(
        """SELECT COALESCE(SUM(amount), 0) AS month_total, COUNT(*) AS month_count
           FROM expenses WHERE DATE_FORMAT(expense_date, '%Y-%m') = %s""",
        (current_month,)
    )
    total = fetch_one("SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count FROM expenses")
    category_data = fetch_all(
        """SELECT c.name, c.color, COALESCE(SUM(e.amount), 0) AS total
           FROM categories c LEFT JOIN expenses e
           ON c.id = e.category_id AND DATE_FORMAT(e.expense_date, '%Y-%m') = %s
           GROUP BY c.id, c.name, c.color HAVING total > 0 ORDER BY total DESC""",
        (current_month,)
    )
    recent = fetch_all(
        """SELECT e.*, c.name AS category_name, c.color FROM expenses e
           JOIN categories c ON c.id = e.category_id
           ORDER BY e.expense_date DESC, e.id DESC LIMIT 6"""
    )
    return render_template("dashboard.html", stats=stats, total=total,
                           category_data=category_data, recent=recent, current_month=current_month)


@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():
    categories = get_categories()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category_id = request.form.get("category_id")
        amount = request.form.get("amount", type=float)
        expense_date = request.form.get("expense_date")
        notes = request.form.get("notes", "").strip()
        if not title or not category_id or not amount or amount <= 0 or not expense_date:
            flash("Please complete all required fields with a valid amount.", "danger")
            return render_template("add_expense.html", categories=categories, today=date.today().isoformat())
        try:
            datetime.strptime(expense_date, "%Y-%m-%d")
            if not category_exists(category_id):
                flash("Please choose a valid category.", "danger")
                return render_template("add_expense.html", categories=categories, today=date.today().isoformat())
            execute_query("""INSERT INTO expenses (title, category_id, amount, expense_date, notes)
                             VALUES (%s, %s, %s, %s, %s)""",
                          (title, category_id, amount, expense_date, notes))
            flash("Expense added successfully.", "success")
            return redirect(url_for("expenses"))
        except ValueError:
            flash("Please choose a valid date.", "danger")
    return render_template("add_expense.html", categories=categories, today=date.today().isoformat())


@app.route("/expenses",methods=['GET'])
def expenses():
    categories = get_categories()
    selected_category = request.args.get("category", "")
    selected_month = request.args.get("month", "")
    sql = """SELECT e.*, c.name AS category_name, c.color FROM expenses e
             JOIN categories c ON c.id = e.category_id WHERE 1=1"""
    params = []
    if selected_category:
        sql += " AND e.category_id = %s"
        params.append(selected_category)
    if selected_month:
        sql += " AND DATE_FORMAT(e.expense_date, '%Y-%m') = %s"
        params.append(selected_month)
    sql += " ORDER BY e.expense_date DESC, e.id DESC"
    items = fetch_all(sql, params)
    return render_template("expenses.html", expenses=items, categories=categories,
                           selected_category=selected_category, selected_month=selected_month)


@app.route("/report/monthly",methods=['GET'])
def monthly_report():
    selected_month = request.args.get("month") or date.today().strftime("%Y-%m")
    rows = fetch_all(
        """SELECT c.name, c.color, COALESCE(SUM(e.amount), 0) AS total, COUNT(e.id) AS expense_count
           FROM categories c LEFT JOIN expenses e
           ON e.category_id = c.id AND DATE_FORMAT(e.expense_date, '%Y-%m') = %s
           GROUP BY c.id, c.name, c.color ORDER BY total DESC""", (selected_month,)
    )
    grand_total = sum(float(row["total"]) for row in rows)
    return render_template("monthly_report.html", rows=rows, grand_total=grand_total,
                           selected_month=selected_month)


if __name__ == "__main__":
    app.run(debug=True)
