# Scout TypeScript SDK

## 2-line automatic monitoring

Add this once to your backend/server entrypoint. Scout will automatically send app start, heartbeat, and unhandled error signals.

```ts
import { Scout } from "@scout/execution";
const scout = Scout.monitor();
```

## Express / Node API monitoring

```ts
app.use(scout.httpMiddleware());
```

That automatically sends request latency, route, method, status code, and error signals as operational metadata. It does not send source code.

## Custom business evidence

```ts
await scout.track({ kind: "revenue", source: "stripe", name: "monthly_recurring_revenue", value: 12000, unit: "USD", verification_status: "verified" });
```

Set these environment variables on your backend, Railway service, CI job, or serverless function:

```bash
SCOUT_BASE_URL=https://your-scout-api.up.railway.app
SCOUT_API_KEY=scout_live_xxxxx
```

Never expose `SCOUT_API_KEY` in browser or mobile code.
