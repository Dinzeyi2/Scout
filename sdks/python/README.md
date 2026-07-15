# Scout Python SDK

## 2-line automatic monitoring

Add this once to your backend/worker entrypoint. Scout will automatically send app start, heartbeat, and unhandled error signals.

```python
from scout_execution import Scout
scout = Scout.monitor()
```

## FastAPI monitoring

```python
scout.instrument_fastapi(app)
```

That automatically sends request latency, path, method, status code, and error signals as operational metadata. It does not send source code.

## Custom business evidence

```python
scout.track(kind="revenue", source="stripe", name="monthly_recurring_revenue", value=12000, unit="USD", verification_status="verified")
```

Set these environment variables on your backend, Railway service, CI job, or worker:

```bash
SCOUT_BASE_URL=https://your-scout-api.up.railway.app
SCOUT_API_KEY=scout_live_xxxxx
```

Never expose `SCOUT_API_KEY` in browser or mobile code.
