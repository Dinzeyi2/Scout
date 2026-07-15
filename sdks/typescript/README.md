# Scout TypeScript SDK

## 2-line automatic monitoring

Add this once to your backend/server entrypoint. Scout will automatically send app start, heartbeat, and unhandled error signals.

```ts
import { Scout } from "@scout/execution";
Scout.monitor();
```

## 3-line custom evidence

```ts
import { Scout } from "@scout/execution";
const scout = Scout.fromEnv();
await scout.track({ kind: "revenue", source: "stripe", name: "monthly_recurring_revenue", value: 12000, unit: "USD", verification_status: "verified" });
```

Set these environment variables on your backend, Railway service, CI job, or serverless function:

```bash
SCOUT_BASE_URL=https://your-scout-api.up.railway.app
SCOUT_API_KEY=scout_live_xxxxx
```

Never expose `SCOUT_API_KEY` in browser or mobile code.
