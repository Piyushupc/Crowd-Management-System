# CrowdSafe Monitor

CrowdSafe Monitor is a computer-vision starter application for monitoring people in a defined area. It processes a camera or video source, compares the detected count with an administrator-defined threshold, records alerts, and can notify a configured authority by email.

> **Project status:** This repository currently uses OpenCV's HOG people detector as its baseline. It is a prototype/starter implementation, not a validated safety-critical crowd-management system.

## Current capabilities

- Configure monitored areas, camera sources, safe-count thresholds, and notification email addresses.
- Process webcam, RTSP, local video, or supported camera-index sources.
- Optionally define a region of interest for monitoring.
- Record timestamped alerts in SQLite.
- Save annotated snapshots when a threshold is exceeded.
- Send notifications through configured SMTP settings.
- Review monitoring status and recent alerts through the application dashboard.

## Technology

- Python, FastAPI, OpenCV, SQLite, SMTP

Check the source and dependency files for exact runtime requirements and supported configuration options.

## Run locally

1. Clone the repository and enter the project directory.
2. Create and activate a virtual environment.
3. Install dependencies from `requirements.txt`.
4. Configure camera and SMTP settings using the mechanism documented in the source.
5. Start the FastAPI application with the entry point and command used by this repository.

Review configuration before exposing the service publicly.

## Important limitations

- HOG detection can be affected by camera angle, lighting, occlusion, and crowd density.
- A people count is not a reliable measure of crowd safety or flow by itself.
- RTSP availability, camera health, notification delivery, and alert latency need operational monitoring.
- SQLite and synchronous notification handling are starter-level choices, not necessarily suitable for high-volume deployment.

## Recommended next steps

- Evaluate a modern detector such as YOLO on representative footage; document the model, dataset, confidence threshold, and measured precision/recall before claiming improved detection.
- Add multi-object tracking and measure count stability across frames.
- Move long-running notification work to a queue and add retry/dead-letter handling.
- Add Docker-based setup, automated tests, structured logs, and health checks.
- Evaluate false positives/negatives under realistic lighting, occlusion, and camera placement.

## Safety and privacy

Do not use this prototype as the sole basis for emergency decisions. Obtain appropriate consent and authorization for camera use, restrict access to snapshots and recordings, define retention periods, and protect credentials outside source control.

## Author

Piyush Rai — [GitHub](https://github.com/Piyushupc)
