CREATE DATABASE IF NOT EXISTS expense_tracker;
USE expense_tracker;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    name VARCHAR(50) NOT NULL,
    color VARCHAR(20) NOT NULL DEFAULT '#6c63ff',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_category_user_name UNIQUE (user_id, name),
    CONSTRAINT fk_categories_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_categories_user_id ON categories(user_id);

CREATE TABLE IF NOT EXISTS expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    title VARCHAR(120) NOT NULL,
    category_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    expense_date DATE NOT NULL,
    notes VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_expense_category FOREIGN KEY (category_id) REFERENCES categories(id),
    CONSTRAINT fk_expenses_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT valid_amount CHECK (amount > 0)
);

CREATE INDEX idx_expenses_user_id ON expenses(user_id);

CREATE TABLE IF NOT EXISTS income_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    color VARCHAR(20) NOT NULL DEFAULT '#43A66F'
);

CREATE TABLE IF NOT EXISTS income (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    category_id INT NOT NULL,
    income_date DATE NOT NULL,
    notes VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_income_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_income_category FOREIGN KEY (category_id) REFERENCES income_categories(id) ON DELETE RESTRICT,
    CONSTRAINT chk_income_amount CHECK (amount > 0)
);

CREATE INDEX idx_income_user_id ON income(user_id);
CREATE INDEX idx_income_date ON income(income_date);
CREATE INDEX idx_income_category_id ON income(category_id);

CREATE TABLE IF NOT EXISTS budgets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    category_id INT NULL,
    amount DECIMAL(12,2) NOT NULL,
    budget_month DATE NOT NULL,
    notes VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_budgets_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_budgets_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    CONSTRAINT chk_budget_amount CHECK (amount > 0),
    UNIQUE KEY uq_user_category_month (user_id, category_id, budget_month)
);

CREATE INDEX idx_budgets_user_id ON budgets(user_id);
CREATE INDEX idx_budgets_category_id ON budgets(category_id);
CREATE INDEX idx_budgets_month ON budgets(budget_month);

INSERT INTO categories (user_id, name, color) VALUES
(NULL, 'Food & Dining', '#E96A4A'),
(NULL, 'Transport', '#149B9B'),
(NULL, 'Shopping', '#7C62CB'),
(NULL, 'Bills & Utilities', '#DC5D7A'),
(NULL, 'Entertainment', '#EDB33E'),
(NULL, 'Health', '#43A66F'),
(NULL, 'Other', '#5271C2')
ON DUPLICATE KEY UPDATE color = VALUES(color);

INSERT INTO income_categories (name, color) VALUES
('Salary', '#43A66F'),
('Freelance', '#149B9B'),
('Business', '#7C62CB'),
('Bonus', '#EDB33E'),
('Investment', '#5271C2'),
('Gift', '#E96A4A'),
('Other', '#667984')
ON DUPLICATE KEY UPDATE color = VALUES(color);
