# Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `ANDREWS_DATA_ROOT` | `E:\ANDREWS` | Runtime data root for logs, database, models, VM data, and reports |
| `ANDREWS_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `ANDREWS_ENVIRONMENT` | `development` | Runtime environment label |

Configuration rejects empty paths, unsupported log levels, and environment values outside `development`, `test`, or `production`.

