# Brevo Service Downtime Alerts

This module monitors multiple service health endpoints and delivers Brevo email alerts when any target goes down (and optionally when it recovers).

## 1. Configure Brevo credentials

Provide the Brevo transactional email credentials through environment variables (e.g. in `.env`):

```
BREVO_API_KEY=your-brevo-api-key
BREVO_SENDER_EMAIL=alerts@example.com
BREVO_SENDER_NAME=Platform Alerts
BREVO_ALERT_RECIPIENTS=you@example.com,teammate@example.com
```

- `BREVO_API_KEY` must be a transactional key with permission to send emails.
- `BREVO_ALERT_RECIPIENTS` accepts a comma-separated list; you can also pass recipients directly to the helper if you integrate it elsewhere.

## 2. Describe the services to watch

Create a JSON or YAML file that lists the services and provide its path via `SERVICE_MONITOR_CONFIG`. An example JSON file is provided in `monitoring/examples/services.example.json`.

```jsonc
{
  "services": [
    {
      "name": "embedding_service",
      "description": "Embedding service health endpoint",
      "url": "https://embedding.example.com/health",
      "method": "GET",
      "timeout": 10,
      "expected_statuses": [200],
      "failure_threshold": 2
    }
  ]
}
```

Alternatively, set a quick inline configuration:

```
SERVICE_MONITOR_ENDPOINTS="Service A|https://service-a/health,Service B|https://service-b/health|HEAD"
```

Each entry is interpreted as `name|url|method`, with `GET` as the default method.

Optional tuning variables (defaults in parentheses):

- `SERVICE_MONITOR_INTERVAL` (`60` seconds): time between checks.
- `SERVICE_MONITOR_DEFAULT_TIMEOUT` (`10` seconds): timeout applied when the service definition omits one.
- `SERVICE_MONITOR_DEFAULT_FAILURE_THRESHOLD` (`1`): number of consecutive failures before a service is marked down.
- `SERVICE_MONITOR_DOWN_NOTIFY_COOLDOWN` (`900` seconds): minimum time between repeated down alerts for the same service.
- `SERVICE_MONITOR_SEND_RECOVERY` (`true`): set to `false` to suppress recovery notifications.
- `SERVICE_MONITOR_RECOVERY_NOTIFY_COOLDOWN` (`0` seconds): throttle recovery alerts if desired.

## 3. Run the monitor

Execute the monitor as an ad-hoc check:

```
python -m monitoring.service_monitor --once
```

To keep it running continually (e.g. in a process manager, container, or cron job), omit `--once`:

```
python -m monitoring.service_monitor
```

Log level can be changed via `--log-level DEBUG` or `SERVICE_MONITOR_LOG_LEVEL`.

## 4. Application integration

- The FastAPI application (`main.py`) automatically starts the monitor in a background task when either `SERVICE_MONITOR_ENABLED` is set to a truthy value or a service configuration env var (`SERVICE_MONITOR_CONFIG` or `SERVICE_MONITOR_ENDPOINTS`) is present.
- To opt out explicitly, set `SERVICE_MONITOR_ENABLED=false`.
- Shutdown is coordinated through the app lifespan handler, so the monitor stops cleanly when the API process terminates.

## 5. Additional deployment pointers

- Wrap the script in a systemd service, Docker container, or Kubernetes CronJob for production use.
- The helper `monitoring.brevo.send_brevo_email` is reusable if you need to trigger custom notifications elsewhere.
- When using YAML configuration files, install `PyYAML` (`pip install pyyaml`).

## 6. Troubleshooting

- Missing Brevo credentials or recipients will raise configuration errors before monitoring starts.
- Per-service failures are logged with a counter showing progress toward the failure threshold.
- If alerts do not arrive, check network access to `https://api.brevo.com` and confirm the Brevo account is authorised for the sender/recipient domains.
