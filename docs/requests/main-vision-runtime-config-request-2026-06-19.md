# Main/Vision runtime config request — smartfactory-vision hostname alignment

- Date: 2026-06-19 KST
- Vision PC current LAN IP: `192.168.10.59`
- Vision PC primary interface: `enp3s0`
- Vision PC MAC address: `a0:ad:9f:bd:63:1b`
- Main dashboard currently reachable: `http://smartfactory-main.local:8088/dashboard/overview`
- Evidence directory: `.omx/reports/main-vision-align-20260619T020230Z/`

## Summary

Vision side is currently running and reachable on the LAN, but Main proxy is still configured with the placeholder upstream `http://<vision-host-or-name>:8090` / `:8100`. Therefore Main dashboard loads, but Main's Vision proxy endpoints return `504 Gateway Timeout` with name-resolution errors.

This needs a Main runtime configuration update plus a network-level stable name/IP plan.

## What Vision side has already aligned

The Vision no-robot bundle is running in tmux window `3:Development`.

Live processes/listeners:

```text
0.0.0.0:8100   AI Server
0.0.0.0:8090   public Vision Stream Gateway
127.0.0.1:18090 internal tb3_1 overlay bridge
127.0.0.1:18091 internal tb3_2 overlay bridge
```

Direct Vision endpoints are healthy from the Vision PC:

```bash
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
curl http://smartfactory-vision.local:8100/api/v1/health
```

A temporary Avahi/mDNS A-record publisher is running in tmux for this test:

```text
smartfactory-vision.local -> 192.168.10.59
```

This is a test-time workaround only. It is not a substitute for router/DNS/DHCP configuration.

## Current Main-side evidence

Main dashboard itself is reachable:

```text
GET http://smartfactory-main.local:8088/dashboard/overview -> 200
```

Main external config reports placeholder Vision upstreams:

```json
{
  "vision": {
    "api_base_url": "http://<vision-host-or-name>:8100",
    "stream_base_url": "http://<vision-host-or-name>:8090"
  },
  "system": {
    "camera_health": {
      "base_url": "http://<vision-host-or-name>:8090",
      "error": "[Errno -2] Name or service not known"
    }
  }
}
```

Main proxy endpoints currently fail:

```text
GET http://smartfactory-main.local:8088/api/v1/vision/bridge/status
-> 504 {"detail":"vision upstream unreachable: [Errno -2] Name or service not known"}

GET http://smartfactory-main.local:8088/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=2
-> 504 {"detail":"vision stream upstream unreachable: [Errno -2] Name or service not known"}
```

## Required Main runtime configuration

Please update Main server runtime env/config to use hostname-first Vision endpoints:

```bash
VISION_API_BASE_URL=http://smartfactory-vision.local:8100
VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

Fallbacks should be explicit and used only when hostname resolution or health checks fail:

```bash
VISION_API_FALLBACK_BASE_URL=http://192.168.10.59:8100
VISION_STREAM_FALLBACK_BASE_URL=http://192.168.10.59:8090
LMS_VISION_STREAM_FALLBACK_BASE_URL=http://192.168.10.59:8090
```

If Main currently does not support fallback envs, please at least replace the placeholder values:

```text
http://<vision-host-or-name>:8100 -> http://smartfactory-vision.local:8100
http://<vision-host-or-name>:8090 -> http://smartfactory-vision.local:8090
```

Then restart/reload the Main service.

## Required router/DNS/DHCP reservation

Because this classroom/network IP is not guaranteed to remain stable, reserve the Vision PC address at the router/DHCP layer:

```text
Device: SmartFactory Vision PC
MAC:    a0:ad:9f:bd:63:1b
IP:     192.168.10.59
Name:   smartfactory-vision.local or smartfactory-vision
```

Recommended policy:

1. Router DHCP reservation pins `a0:ad:9f:bd:63:1b` to `192.168.10.59` or another operator-approved stable IP.
2. DNS/mDNS/host alias resolves `smartfactory-vision.local` to that reserved IP.
3. Main uses hostname-first config, with explicit IP fallback only for diagnosis/recovery.

## Acceptance checks after Main update

Run from the Vision PC or another machine on the same LAN:

```bash
getent hosts smartfactory-vision.local
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
curl http://smartfactory-vision.local:8100/api/v1/health
curl http://smartfactory-main.local:8088/api/v1/system/external-config
curl http://smartfactory-main.local:8088/api/v1/vision/bridge/status
curl 'http://smartfactory-main.local:8088/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=2'
```

Expected result:

- `smartfactory-vision.local` resolves to the reserved Vision PC IP.
- direct Vision health/status returns `200`.
- Main external config no longer contains `<vision-host-or-name>`.
- Main proxy bridge status returns `200`.
- Main proxy stream returns MJPEG headers or a controlled no-frame stream while robots/cameras are absent.

## Notes

- The Vision bundle is read-only and reports `motion_command_allowed=false`.
- Robot/camera absence is expected during this check; source state may be `no_frame` until robot camera feeds are connected.
- The temporary tmux mDNS publisher must not be considered production configuration.
