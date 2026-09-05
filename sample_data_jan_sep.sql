USE expense_tracker;

-- PRESENTATION DATA: January to September 2026
-- Run this file ONCE after schema.sql. It adds 45 realistic demo expenses
-- and does not delete any existing data.

INSERT INTO expenses (title, category_id, amount, expense_date, notes)
SELECT demo.title, categories.id, demo.amount, demo.expense_date, demo.notes
FROM (
    SELECT 'January groceries' AS title, 'Food & Dining' AS category_name, 2350.00 AS amount, '2026-01-05' AS expense_date, 'Monthly supermarket visit' AS notes
    UNION ALL SELECT 'Metro recharge', 'Transport', 650.00, '2026-01-08', 'January commute'
    UNION ALL SELECT 'Electricity payment', 'Bills & Utilities', 1450.00, '2026-01-12', 'Home electricity bill'
    UNION ALL SELECT 'Weekend movie', 'Entertainment', 600.00, '2026-01-18', 'Two movie tickets'
    UNION ALL SELECT 'Pharmacy purchase', 'Health', 540.00, '2026-01-24', 'Vitamins and medicines'

    UNION ALL SELECT 'February groceries', 'Food & Dining', 2180.00, '2026-02-04', 'Monthly supermarket visit'
    UNION ALL SELECT 'Cab rides', 'Transport', 920.00, '2026-02-09', 'Office travel'
    UNION ALL SELECT 'Mobile recharge', 'Bills & Utilities', 499.00, '2026-02-12', 'Prepaid plan'
    UNION ALL SELECT 'New headphones', 'Shopping', 1899.00, '2026-02-16', 'Personal electronics'
    UNION ALL SELECT 'Cafe visit', 'Entertainment', 480.00, '2026-02-22', 'Coffee with friends'

    UNION ALL SELECT 'March groceries', 'Food & Dining', 2520.00, '2026-03-03', 'Monthly supermarket visit'
    UNION ALL SELECT 'Fuel refill', 'Transport', 2100.00, '2026-03-07', 'Petrol'
    UNION ALL SELECT 'Internet bill', 'Bills & Utilities', 799.00, '2026-03-11', 'Broadband plan'
    UNION ALL SELECT 'Spring clothing', 'Shopping', 2800.00, '2026-03-19', 'Clothes purchase'
    UNION ALL SELECT 'Dental check-up', 'Health', 900.00, '2026-03-26', 'Routine appointment'

    UNION ALL SELECT 'April groceries', 'Food & Dining', 2450.00, '2026-04-04', 'Monthly supermarket visit'
    UNION ALL SELECT 'Bus pass', 'Transport', 700.00, '2026-04-06', 'Monthly travel pass'
    UNION ALL SELECT 'Water bill', 'Bills & Utilities', 620.00, '2026-04-12', 'Apartment water bill'
    UNION ALL SELECT 'Streaming subscription', 'Entertainment', 649.00, '2026-04-15', 'Monthly subscription'
    UNION ALL SELECT 'Birthday gift', 'Shopping', 1500.00, '2026-04-25', 'Gift for friend'

    UNION ALL SELECT 'May groceries', 'Food & Dining', 2600.00, '2026-05-02', 'Monthly supermarket visit'
    UNION ALL SELECT 'Train tickets', 'Transport', 1350.00, '2026-05-09', 'Outstation journey'
    UNION ALL SELECT 'Electricity payment', 'Bills & Utilities', 1680.00, '2026-05-12', 'Summer electricity bill'
    UNION ALL SELECT 'Restaurant dinner', 'Food & Dining', 1250.00, '2026-05-18', 'Family dinner'
    UNION ALL SELECT 'Gym fee', 'Health', 1200.00, '2026-05-25', 'Monthly fitness fee'

    UNION ALL SELECT 'June groceries', 'Food & Dining', 2380.00, '2026-06-03', 'Monthly supermarket visit'
    UNION ALL SELECT 'Fuel refill', 'Transport', 2350.00, '2026-06-08', 'Petrol'
    UNION ALL SELECT 'Phone bill', 'Bills & Utilities', 699.00, '2026-06-11', 'Postpaid bill'
    UNION ALL SELECT 'Monsoon shoes', 'Shopping', 2200.00, '2026-06-16', 'Footwear purchase'
    UNION ALL SELECT 'Concert tickets', 'Entertainment', 1100.00, '2026-06-27', 'Live music event'

    UNION ALL SELECT 'July groceries', 'Food & Dining', 2750.00, '2026-07-04', 'Monthly supermarket visit'
    UNION ALL SELECT 'Cab rides', 'Transport', 1150.00, '2026-07-10', 'Office travel'
    UNION ALL SELECT 'Internet bill', 'Bills & Utilities', 799.00, '2026-07-12', 'Broadband plan'
    UNION ALL SELECT 'Doctor consultation', 'Health', 800.00, '2026-07-17', 'Routine consultation'
    UNION ALL SELECT 'Book purchase', 'Other', 650.00, '2026-07-24', 'Study material'

    UNION ALL SELECT 'August groceries', 'Food & Dining', 2680.00, '2026-08-03', 'Monthly supermarket visit'
    UNION ALL SELECT 'Metro recharge', 'Transport', 650.00, '2026-08-07', 'Monthly commute'
    UNION ALL SELECT 'Electricity payment', 'Bills & Utilities', 1580.00, '2026-08-11', 'Home electricity bill'
    UNION ALL SELECT 'Festival shopping', 'Shopping', 3600.00, '2026-08-19', 'Clothes and gifts'
    UNION ALL SELECT 'Movie and snacks', 'Entertainment', 850.00, '2026-08-29', 'Weekend outing'

    UNION ALL SELECT 'September groceries', 'Food & Dining', 2850.00, '2026-09-02', 'Monthly supermarket visit'
    UNION ALL SELECT 'Fuel refill', 'Transport', 2400.00, '2026-09-05', 'Petrol'
    UNION ALL SELECT 'Internet and mobile bills', 'Bills & Utilities', 1298.00, '2026-09-10', 'Monthly utility payment'
    UNION ALL SELECT 'Festival shopping', 'Shopping', 4200.00, '2026-09-16', 'Clothes and home items'
    UNION ALL SELECT 'Health check-up', 'Health', 1100.00, '2026-09-23', 'Annual check-up'
) AS demo
JOIN categories ON categories.name = demo.category_name;
