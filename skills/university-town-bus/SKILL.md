---
name: university-town-bus
description: 查询深圳大学城无界学城穿梭巴士实时信息。Use when users ask about university town shuttle/bus routes, 全部线路, 发车时间, 到站预测, 车在哪里, vehicle GPS, 站点, or 无界学城穿梭巴士.
---

# University Town Bus

## Overview

Use this skill to query the Shenzhen University Town / 无界学城穿梭巴士 mobile service and answer route, station, schedule, prediction, and live vehicle-location questions.

The skill is self-contained. Its runtime helper is `scripts/bus.py`, which uses only the Python 3 standard library and requests fresh anonymous access from the public mobile endpoint for each run.

## Quick Start

Run commands from this skill directory:

```bash
python scripts/bus.py meta
python scripts/bus.py lines
python scripts/bus.py line "无界学城一号线"
python scripts/bus.py predict "无界学城一号线" --station-name "哈工大信息楼"
python scripts/bus.py vehicles "无界学城一号线"
python scripts/bus.py answer "无界学城一号线现在车在哪里？"
```

For machine-readable output, add `--format json` to any subcommand that supports it.

## Data Source

- Base site: `https://predict.ipubtrans.com/mobile`
- Default `tenantId`: `2009511491423047680`
- Default `qrCodeId`: `2011322258011197440`
- Anonymous token endpoint: `POST /mobile/login/guise`

Do not hardcode user credentials, cookies, or long-lived tokens. Let `bus.py` call `login/guise` each run.

If a different QR code or tenant is needed, pass `--tenant-id` / `--qr-code-id`, or set:

```bash
UNIVERSITY_TOWN_BUS_TENANT_ID=...
UNIVERSITY_TOWN_BUS_QR_CODE_ID=...
```

## Workflow

1. For broad questions like "有哪些路线" or "全部线路", run `python scripts/bus.py lines`.
2. For a named route, run `python scripts/bus.py line "<线路名或ID>"`.
3. For ETA or station-specific questions, run `python scripts/bus.py predict "<线路名或ID>" --station-name "<站点名>"`.
4. For "车在哪里" or GPS questions, run `python scripts/bus.py vehicles "<线路名或ID>"`; if no vehicle is active, say so directly.
5. For natural-language user prompts, `python scripts/bus.py answer "<用户问题>"` is usually enough and returns a concise Markdown answer.

## Response Rules

- Reply in Chinese unless the user asks otherwise.
- State the route name, current operating status, selected station, and next-arrival estimate when available.
- If status is `非营运时间` or `暂未发车`, do not treat it as an error.
- If GPS/vehicle data is empty, explain that the service currently returns no active vehicle locations.
- Include the data source briefly, for example: "来源：无界学城穿梭巴士移动端接口。"
- Mention that bus data is real-time and may change quickly.

## Interface Notes

The helper wraps these verified endpoints:

- `POST /mobile/getQrName`: route system name and default map center.
- `POST /mobile/line/list`: all routes near the default or provided coordinates.
- `POST /mobile/line/info`: route stations, track, notice, and schedule text.
- `GET /mobile/predict/first/station/line?keys=...`: line-level prediction/status.
- `GET /mobile/predict/more/station/line`: station-specific prediction.
- `POST /mobile/predict/line/vehList`: live vehicle GPS list.
