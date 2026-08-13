---
title: Revenue Recognition Policy
asset_id: revenue_model
doc_type: policy
source_url: https://wiki.brightcart.example/finance/revenue-recognition
---
# Revenue Recognition Policy

This document defines how Brightcart recognizes revenue for reporting
purposes, as implemented in the `revenue_model` dbt model.

## Rule

Revenue for an order line item is recognized when:

1. The order item exists in `order_items`, **and**
2. The parent order has an associated payment in `payments` with
   `payment_status` of `paid` or `refunded`, **and**
3. Any amount later returned (see `returns`) is subtracted.

This is expressed as:

```
net_revenue = gross_amount - refund_amount
```

where `gross_amount = unit_price * quantity - discount_amount`.

## Why payments matter

Orders with status `processing` do not yet have a completed payment and
are excluded from recognized revenue until payment settles. Orders with
status `cancelled` are excluded entirely — no payment is ever collected.

## Aggregation

`revenue_model` rows (one per order line item) are grouped by calendar
month into `monthly_revenue`, which is what the Revenue Dashboard
displays.
