---
title: Customers Dataset Overview
asset_id: customers
doc_type: readme
source_url: https://wiki.brightcart.example/data/customers
---
# Customers

The `customers` table is the source of truth for customer identity at
Brightcart. It is written to by the signup service and read by nearly
every downstream sales and finance process.

## What's in it

One row per registered customer: name, contact details, signup date,
country, the marketing campaign that acquired them (if any), and a
predicted `lifetime_value`.

## Who owns it

Sales Engineering. Ping `#data-sales-eng` for schema changes.

## Known issues

A small number of rows (~0.2%) are missing a phone number — these are
customers who signed up before phone verification was required and have
not since added one. This is expected and does not block use of the
table.
