# Shopify + ERPNext Integration Setup Guide

This guide walks you through connecting your Shopify store to ERPNext using the Ecom Bridge app. By the end, orders placed on Shopify will automatically create Sales Orders, Sales Invoices, and Delivery Notes in ERPNext. Stock levels from ERPNext will sync back to Shopify, and fulfilling an order in ERPNext will mark it as fulfilled in Shopify.

---

## Prerequisites

- ERPNext site with the **Ecom Bridge** app installed
- A Shopify store (any plan)
- Admin access to both systems

---

## Part 1: Shopify Custom App Setup

### Step 1: Create a Custom App in Shopify

1. Log in to your **Shopify Admin** panel
2. Go to **Settings** (bottom-left) > **Apps and sales channels**
3. Click **Develop apps** (top-right)
4. If prompted, click **Allow custom app development**
5. Click **Create an app**
6. Enter a name (e.g., `ERPNext Bridge`) and select your email
7. Click **Create app**

### Step 2: Configure API Scopes

1. In your new app, click the **Configuration** tab
2. Under **Admin API access scopes**, add the following scopes:

```
read_customers,write_customers,read_fulfillments,write_fulfillments,read_merchant_managed_fulfillment_orders,write_merchant_managed_fulfillment_orders,read_inventory,write_inventory,read_locations,read_orders,write_orders,read_products,write_products,read_shipping
```

Or select them individually:

| Scope | Purpose |
|-------|---------|
| `read_customers`, `write_customers` | Sync customer data |
| `read_orders`, `write_orders` | Sync orders from Shopify |
| `read_products`, `write_products` | Sync product/item data |
| `read_fulfillments`, `write_fulfillments` | Create fulfillments |
| `read_merchant_managed_fulfillment_orders`, `write_merchant_managed_fulfillment_orders` | Mark orders as fulfilled from ERPNext |
| `read_inventory`, `write_inventory` | Push stock levels from ERPNext to Shopify |
| `read_locations` | Map Shopify locations to ERPNext warehouses |
| `read_shipping` | Sync shipping charges |

3. Click **Save**

### Step 3: Install the App and Get Credentials

1. Go to the **API credentials** tab
2. Click **Install app**
3. Copy and save these three values (you will need them in ERPNext):
   - **Admin API access token** (starts with `shpat_` -- shown only once!)
   - **API key** (Client ID)
   - **API secret key** (click the eye icon to reveal)

> **Important**: The access token is shown only once. Copy it immediately and store it securely.

### Step 4: Enable Inventory Tracking on Products

For stock levels to sync from ERPNext to Shopify, each product must have inventory tracking enabled:

1. Go to **Products** in Shopify Admin
2. Click on a product
3. Scroll to the **Inventory** section
4. Check **Track quantity**
5. Set the stock quantity for your location
6. Repeat for all products

> **Tip**: If you have many products, the Ecom Bridge app can enable tracking programmatically via the API.

---

## Part 2: ERPNext Configuration

### Step 5: Configure Shopify Setting

1. In ERPNext, go to the search bar and type **Shopify Setting**
2. Check **Enable Shopify**

#### Authentication Details

| Field | Value |
|-------|-------|
| **Shop URL** | Your Shopify store URL (e.g., `your-store.myshopify.com`) -- without `https://` |
| **Password / Access Token** | The `shpat_...` token from Step 3 |
| **Shared Secret / API Secret** | The API secret key from Step 3 |

3. Click **Save** -- this will register webhooks with Shopify automatically

#### Item Mapping

| Field | Description |
|-------|-------------|
| **Item Sync Mode** | `Auto-create new items` creates ERPNext items for new Shopify products. `Map to existing items only` maps by SKU/name/barcode. `Map existing first, then auto-create` tries matching first. |
| **Match Items By** | Choose `SKU`, `Item Name`, or `Barcode` for matching existing items |

> **Tip**: Use **Bulk Map Items** button to map all existing Shopify products to ERPNext items at once.

#### Customer Settings

| Field | Value |
|-------|-------|
| **Customer Group** | Select a customer group (e.g., `Commercial`) |
| **Default Customer** | (Optional) Fallback customer if Shopify order has no customer |

#### Company Settings

| Field | Value |
|-------|-------|
| **Company** | Your ERPNext company |
| **Cost Center** | Default cost center for Shopify transactions |
| **Cash/Bank Account** | Account for Shopify payments |

#### Order Sync Settings

| Field | Value |
|-------|-------|
| **Sales Order Series** | Naming series for Shopify orders (e.g., `SAL-ORD-.YYYY.-`) |
| **Import Delivery Notes from Shopify on Shipment** | Check to auto-create DNs when orders are fulfilled in Shopify |
| **Delivery Note Series** | Naming series for DNs (e.g., `MAT-DN-.YYYY.-`) |
| **Import Sales Invoice from Shopify if Payment is marked** | Check to auto-create SIs when orders are paid |
| **Sales Invoice Series** | Naming series for SIs (e.g., `ACC-SINV-.YYYY.-`) |

#### Tax Mapping

Map each Shopify tax/shipping charge to an ERPNext account:

| Shopify Tax | ERPNext Account |
|-------------|-----------------|
| Your tax name (e.g., `IGST`) | Tax account (e.g., `IGST - COMPANY`) |
| Your shipping name | Shipping charges account (e.g., `Shipping Charges - COMPANY`) |

Also set the **Default Sales Tax Account** and **Default Shipping Charges Account** as fallbacks.

#### Inventory Sync

| Field | Value |
|-------|-------|
| **Default Warehouse** | The ERPNext warehouse for Shopify transactions |
| **Update ERPNext stock levels to Shopify** | Check to enable automatic stock sync |
| **Inventory Sync Frequency** | How often to push stock (5, 10, 15, 30, or 60 minutes) |

Then:
1. Click **Fetch Shopify Locations** to load your Shopify locations
2. Map each Shopify location to the corresponding ERPNext warehouse

#### ERPNext to Shopify Sync

| Field | Value |
|-------|-------|
| **Upload new ERPNext Items to Shopify** | Check to push new items from ERPNext to Shopify |
| **Update Shopify Item after updating ERPNext item** | Check to sync item changes |
| **Sync New Items as Active** | Check to make new items active in Shopify |

4. Click **Save**

### Step 6: Configure Ecom Bridge Settings

1. Go to **Ecom Bridge Settings** in ERPNext
2. Check **Enabled**

#### General Settings

| Field | Value |
|-------|-------|
| **Company** | Your ERPNext company |
| **Default Currency** | Your currency (e.g., `SAR`) |

#### Shopify Overrides

| Field | Value |
|-------|-------|
| **Enable Shopify Overrides** | Check to enable |
| **Default Warehouse** | Warehouse for Shopify orders |
| **Cost Center** | Cost center for Shopify orders |
| **Sales Tax Template** | (Optional) Default tax template |
| **Shipping Charges Account** | Account for shipping charges |

#### Fulfillment Sync

| Field | Value |
|-------|-------|
| **Sync Fulfillment to Shopify** | Check to auto-mark Shopify orders as fulfilled when a Delivery Note is submitted in ERPNext |

#### Inventory Sync

| Field | Value |
|-------|-------|
| **Sync Inventory to Shopify** | Check to enable periodic stock sync |
| **Sync Interval** | Frequency in minutes |

3. Click **Save**

---

## Part 3: Verify the Integration

### Test 1: Order Sync (Shopify to ERPNext)

1. Place a test order on your Shopify store
2. In ERPNext, check **Sales Order** list -- a new SO should appear within a minute
3. If the order is paid, a **Sales Invoice** will also be created
4. If the order is fulfilled in Shopify, a **Delivery Note** will be created

### Test 2: Fulfillment Sync (ERPNext to Shopify)

1. In ERPNext, open a Sales Order linked to a Shopify order
2. Create a **Delivery Note** from it (Create > Delivery Note)
3. **Submit** the Delivery Note
4. Check Shopify -- the order should now show as **Fulfilled**

### Test 3: Inventory Sync (ERPNext to Shopify)

1. In ERPNext, create a **Stock Entry** (Material Receipt) for one of your Shopify items
2. Wait for the sync interval (or trigger manually -- see below)
3. Check the product in Shopify -- the stock level should match ERPNext

### Manual Sync Triggers

You can trigger syncs manually from the browser console (while logged into ERPNext):

```js
// Force inventory sync
frappe.call({method: "ecom_bridge.api.dashboard.force_inventory_sync", callback: r => console.log(r)})

// Force fulfillment sync for a specific Delivery Note
frappe.call({
    method: "ecom_bridge.api.dashboard.force_fulfillment_sync",
    args: {delivery_note: "MAT-DN-2026-00001"},
    callback: r => console.log(r)
})
```

---

## How It Works

### Order Flow: Shopify to ERPNext

```
Customer places order on Shopify
    |
    v
Webhook fires to ERPNext
    |
    v
Sales Order created in ERPNext
    |
    +-- Order is paid --> Sales Invoice created
    |
    +-- Order is fulfilled in Shopify --> Delivery Note created
```

### Fulfillment Flow: ERPNext to Shopify

```
Delivery Note submitted in ERPNext
    |
    v
Hook checks: Is this a Shopify order? Is sync enabled?
    |
    v
Background job calls Shopify Fulfillment API
    |
    v
Order marked as "Fulfilled" in Shopify
```

### Inventory Flow: ERPNext to Shopify

```
Stock Entry / Purchase Receipt updates Bin qty
    |
    v
Scheduler runs every X minutes
    |
    v
Queries items where bin.modified > last inventory sync
    |
    v
Pushes (actual_qty - reserved_qty) to Shopify per location
    |
    v
Shopify shows updated stock; out-of-stock items blocked from ordering
```

---

## Troubleshooting

### Orders not syncing from Shopify

- Check **Shopify Setting** > **Webhooks Details** -- webhooks should be listed
- Check **Ecommerce Integration Log** for errors
- Verify the Shop URL and Access Token are correct

### Fulfillment not syncing to Shopify

- Ensure **Ecom Bridge Settings** > **Sync Fulfillment to Shopify** is checked
- The Delivery Note must be linked to a Sales Order that has a `shopify_order_id`
- Check that the Shopify app has `read_merchant_managed_fulfillment_orders` and `write_merchant_managed_fulfillment_orders` scopes
- Check **Ecommerce Integration Log** for 403 errors (scope issue)

### Inventory not syncing to Shopify

- Ensure **Shopify Setting** > **Update ERPNext stock levels to Shopify** is checked
- Warehouse mapping must be configured (Fetch Shopify Locations first)
- Products must have **Track quantity** enabled in Shopify
- Items must have an **Ecommerce Item** record linking them to Shopify variants
- Check **Ecommerce Integration Log** for "inventory tracking not enabled" errors

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Inventory item does not have inventory tracking enabled` | Shopify product doesn't have "Track quantity" checked | Enable tracking in Shopify Admin > Products |
| `The api_client does not have the required permission(s)` | Missing API scopes | Add the missing scopes in Shopify app configuration and reinstall |
| `Unverified Webhook Data` | Shared secret mismatch | Verify the Shared Secret in Shopify Setting matches the app's API secret |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `ecom_bridge.api.dashboard.get_sync_dashboard` | GET | Get sync status for both platforms |
| `ecom_bridge.api.dashboard.get_sync_logs` | GET | Get recent sync logs |
| `ecom_bridge.api.dashboard.force_sync` | POST | Trigger order sync |
| `ecom_bridge.api.dashboard.force_inventory_sync` | POST | Trigger inventory sync to Shopify |
| `ecom_bridge.api.dashboard.force_fulfillment_sync` | POST | Trigger fulfillment sync for a Delivery Note |
