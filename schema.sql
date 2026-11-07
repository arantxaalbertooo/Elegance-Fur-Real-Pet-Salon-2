-- Elegance Fur Real Pet Salon CRM Hub (SQLite).
-- Table and column names follow elegance_fur_real.sql. Lines marked "-- EXTRA" are additions
-- the CRM features need (appointments, reminders, feedback, and the staff / pet / service details in the seed data).
PRAGMA foreign_keys = ON;

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('Admin', 'Receptionist', 'Groomer')),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    staff_code VARCHAR(10) UNIQUE,      -- EXTRA (GRM-001, REC-001, ADM-001)
    email VARCHAR(100) NOT NULL UNIQUE, -- EXTRA (staff sign in with email or username)
    phone VARCHAR(20), specialty VARCHAR(100), experience VARCHAR(30), availability VARCHAR(60), rating REAL  -- EXTRA
);

CREATE TABLE segments (
    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_name VARCHAR(50) NOT NULL UNIQUE,
    min_clv DECIMAL(12,2) NOT NULL CHECK (min_clv >= 0),
    description VARCHAR(255)
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(20),
    address VARCHAR(255),
    segment_id INTEGER REFERENCES segments(segment_id) ON DELETE SET NULL,
    consent_given BOOLEAN NOT NULL DEFAULT 0 CHECK (consent_given IN (0,1)),
    consent_date DATE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pets (
    pet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    breed VARCHAR(100) DEFAULT 'Mixed',
    age VARCHAR(50),
    size VARCHAR(20) DEFAULT 'Small',
    coat VARCHAR(50) DEFAULT 'Short',
    allergies TEXT,
    notes TEXT,                          -- behavior notes
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    species VARCHAR(20), medical_conditions TEXT, grooming_preferences TEXT   -- EXTRA
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    unit_price DECIMAL(12,2) NOT NULL CHECK (unit_price >= 0),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    duration_minutes INTEGER NOT NULL DEFAULT 60 CHECK (duration_minutes > 0)  -- EXTRA (used to prevent double-booking)
);

-- EXTRA: a booking. Seed "orders" are loaded here; completing one writes the order lines below (which drive CLV).
CREATE TABLE appointments (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    pet_id INTEGER REFERENCES pets(pet_id) ON DELETE SET NULL,
    groomer_id INTEGER REFERENCES users(user_id),
    appointment_datetime TIMESTAMP NOT NULL,
    status VARCHAR(15) NOT NULL DEFAULT 'Scheduled' CHECK (status IN ('Scheduled','In progress','Completed','Canceled')),
    groomer_notes TEXT,
    source_opportunity_id INTEGER REFERENCES opportunities(opportunity_id)
);
CREATE TABLE appointment_services (
    appointment_id INTEGER NOT NULL REFERENCES appointments(appointment_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    price_charged DECIMAL(12,2) NOT NULL CHECK (price_charged >= 0),
    PRIMARY KEY (appointment_id, product_id)
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    total_amount DECIMAL(12,2) NOT NULL,
    order_date DATE NOT NULL,
    appointment_id INTEGER REFERENCES appointments(appointment_id) ON DELETE CASCADE   -- EXTRA
);

CREATE TABLE opportunities (
    opportunity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE RESTRICT,
    owner_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    stage VARCHAR(15) NOT NULL CHECK (stage IN ('Lead','Qualified','Proposal','Won','Lost')),
    expected_amount DECIMAL(12,2) NOT NULL CHECK (expected_amount >= 0),
    expected_close_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE interactions (
    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    channel VARCHAR(15) NOT NULL CHECK (channel IN ('Call','Email','Chat','Walk-in')),
    notes TEXT,
    interaction_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    related_ref VARCHAR(20)              -- EXTRA (e.g. TKT-006, OPP-004)
);

CREATE TABLE tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    assigned_to INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    subject VARCHAR(150) NOT NULL,
    priority VARCHAR(10) NOT NULL CHECK (priority IN ('Low','Medium','High')),
    status VARCHAR(15) NOT NULL CHECK (status IN ('Open','In progress','Closed')),
    csat_score INTEGER CHECK (csat_score BETWEEN 1 AND 5),
    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP NULL
);

-- EXTRA tables
CREATE TABLE reminders (
    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL REFERENCES appointments(appointment_id) ON DELETE CASCADE,
    reminder_type VARCHAR(15) NOT NULL CHECK (reminder_type IN ('Upcoming','Follow-up')),
    scheduled_at TIMESTAMP NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending','Sent'))
);
CREATE TABLE feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL REFERENCES appointments(appointment_id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    grooming_rating INTEGER NOT NULL CHECK (grooming_rating BETWEEN 1 AND 5),
    service_rating INTEGER NOT NULL CHECK (service_rating BETWEEN 1 AND 5),
    comments TEXT,
    created_at TIMESTAMP NOT NULL
);
