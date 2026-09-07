CREATE TABLE entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    order_id    INTEGER NOT NULL,
    amount      TEXT    NOT NULL,
    kind        TEXT    NOT NULL
);

CREATE INDEX ix_entries_customer ON entries (customer_id);
