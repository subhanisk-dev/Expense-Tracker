CREATE DATABASE IF NOT EXISTS expense_tracker;
USE expense_tracker;

CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    color VARCHAR(20) NOT NULL DEFAULT '#6c63ff'
);

CREATE TABLE expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(120) NOT NULL,
    category_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    expense_date DATE NOT NULL,
    notes VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_expense_category FOREIGN KEY (category_id) REFERENCES categories(id),
    CONSTRAINT valid_amount CHECK (amount > 0)
);

INSERT IGNORE INTO categories (name, color) VALUES
('Food & Dining', '#E96A4A'),
('Transport', '#149B9B'),
('Shopping', '#7C62CB'),
('Bills & Utilities', '#DC5D7A'),
('Entertainment', '#EDB33E'),
('Health', '#43A66F'),
('Other', '#5271C2');
