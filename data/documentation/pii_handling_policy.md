---
title: PII Handling Policy
asset_id:
doc_type: policy
source_url: https://wiki.brightcart.example/policies/pii-handling
---
# PII Handling Policy

This is a company-wide policy, not specific to one dataset.

## Classification

A dataset is marked `contains_pii` if any column holds information that
can identify an individual: name, email, phone, physical address, or
financial identifiers such as a card number fragment.

## Column-level tracking

Beyond the dataset-level flag, individual columns are tagged with a
`pii_category` (`name`, `email`, `phone`, `address`, `financial`) so
that "which column contains PII" can be answered precisely, not just
"which table."

## Datasets currently containing PII

`customers` (name, email, phone), `orders` (shipping address), and
`payments` (card last 4 digits).

## Access

Access to PII columns is restricted to the owning team and Data
Platform. Ad-hoc queries against PII columns should go through the
approved BI tooling, not direct database access.
