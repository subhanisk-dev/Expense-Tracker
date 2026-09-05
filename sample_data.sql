USE expense_tracker;

-- Demonstration entries. Dates are relative to today, so the graphs work
-- whenever this script is imported.
UPDATE categories
SET color = CASE name
    WHEN 'Food & Dining' THEN '#E96A4A'
    WHEN 'Transport' THEN '#149B9B'
    WHEN 'Shopping' THEN '#7C62CB'
    WHEN 'Bills & Utilities' THEN '#DC5D7A'
    WHEN 'Entertainment' THEN '#EDB33E'
    WHEN 'Health' THEN '#43A66F'
    WHEN 'Other' THEN '#5271C2'
    ELSE color
END;

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'Weekly groceries', id, 1850.00, CURDATE() - INTERVAL 2 DAY, 'Vegetables, staples and household items'
FROM categories WHERE name = 'Food & Dining';

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'Dinner with friends', id, 780.00, CURDATE() - INTERVAL 1 DAY, 'Restaurant bill'
FROM categories WHERE name = 'Food & Dining';

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'Metro card recharge', id, 500.00, CURDATE() - INTERVAL 3 DAY, 'Monthly travel top-up'
FROM categories WHERE name = 'Transport';

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'Fuel refill', id, 2200.00, CURDATE(), 'Petrol'
FROM categories WHERE name = 'Transport';

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'Internet bill', id, 799.00, CURDATE() - INTERVAL 3 DAY, 'Broadband subscription'
FROM categories WHERE name = 'Bills & Utilities';

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'Electricity bill', id, 1460.00, CURDATE() - INTERVAL 2 DAY, 'Monthly payment'
FROM categories WHERE name = 'Bills & Utilities';

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'T-shirt and shoes', id, 2499.00, CURDATE() - INTERVAL 1 DAY, 'Weekend shopping'
FROM categories WHERE name = 'Shopping';

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'Movie tickets', id, 650.00, CURDATE() - INTERVAL 2 DAY, 'Evening show'
FROM categories WHERE name = 'Entertainment';

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT 'Pharmacy', id, 425.00, CURDATE(), 'Medicines'
FROM categories WHERE name = 'Health';
