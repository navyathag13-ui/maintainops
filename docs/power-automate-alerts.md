# Setting up the Teams low-stock alert flow

The notifier (`backend/app/notify.py`) POSTs JSON to a webhook. Any of these flows can receive it.

## Option A: Teams Workflows (no Power Automate licence needed)

1. In Microsoft Teams, open the channel that should get alerts, click **...** next to it, then **Workflows**.
2. Pick the template **Send webhook alerts to a channel** (older tenants call it **Post to a channel when a webhook request is received**). If the channel menu's search doesn't respond, open the **Workflows** app, go to **Templates** and search "webhook" there.
3. Name it "MaintainOps low-stock alerts", confirm the team and channel, and click **Add workflow**.
4. Copy the URL it shows. Treat it like a password: anyone with it can post to the channel.
5. Check that **Who can trigger the flow** is **Anyone** (Power Automate, trigger card). The notifier sends no Microsoft sign-in token.
6. Run the notifier with it:

   ```bash
   cd backend
   MAINTAINOPS_WEBHOOK_URL="<copied URL>" python -m app.notify --once
   ```

The template posts the Adaptive Card in the payload's `attachments`, so nothing else needs mapping.

## Option B: Power Automate with your own steps

Use this to add logic, for example an email for critical parts only.

1. At make.powerautomate.com, create an **Instant cloud flow** with the trigger **When an HTTP request is received** (a premium trigger), or **When a Teams webhook request is received**.
2. In the trigger, choose **Use sample payload to generate schema** and paste:

   ```json
   {"event_id": 1, "part_id": 4, "part_name": "Wood Screws", "sku": "WS-1",
    "quantity_on_hand": 2, "reorder_threshold": 5, "is_critical": false,
    "occurred_at": "2026-11-10T12:00:00+00:00",
    "message": "Low stock: Wood Screws (SKU WS-1) has 2 left; reorder threshold is 5."}
   ```

3. Add **Condition**: `is_critical` is equal to `true`.
   - If yes: **Post message in a chat or channel** with `message`, plus **Send an email (V2)** to the buyer.
   - If no: **Post message in a chat or channel** with `message`.
4. Save, copy the trigger's HTTP URL and run the notifier as above.

## Checking it

To check the flow alone, without the database:

```bash
cd backend
python -m app.notify --test
```

It asks for the URL (input hidden) and sends one sample card.

To check the full path:

Use a part until it drops below its reorder threshold (the seeded Wood Screws already are), then run `python -m app.notify --once`. The log shows `Run done: {'sent': 1, ...}` and the message appears in the channel. Running it again sends nothing, because the event is already marked `sent`.
