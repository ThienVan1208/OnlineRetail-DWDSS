CREATE DATABASE IF NOT EXISTS retail_dw
  CHARACTER SET utf8mb4 
  COLLATE utf8mb4_unicode_ci;

USE retail_dw;

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL UNIQUE,
    country VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    unit_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00 -- giá niêm yết
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT PRIMARY KEY, -- format YYYYMMDD
    full_date DATE NOT NULL UNIQUE,
    day INT NOT NULL,
    month INT NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL,
    day_of_week VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_sales (
    sales_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    invoice_no VARCHAR(20) NOT NULL,
    date_key INT NOT NULL,
    customer_key INT NOT NULL,
    product_key INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL, -- giá bán
    total_amount DECIMAL(12, 2) NOT NULL,
    
    CONSTRAINT fk_sales_date FOREIGN KEY (date_key) 
        REFERENCES dim_date(date_key) ON DELETE RESTRICT,
    CONSTRAINT fk_sales_customer FOREIGN KEY (customer_key) 
        REFERENCES dim_customer(customer_key) ON DELETE RESTRICT,
    CONSTRAINT fk_sales_product FOREIGN KEY (product_key) 
        REFERENCES dim_product(product_key) ON DELETE RESTRICT,
        
    INDEX idx_sales_date (date_key),
    INDEX idx_sales_customer (customer_key),
    INDEX idx_sales_product (product_key)
);