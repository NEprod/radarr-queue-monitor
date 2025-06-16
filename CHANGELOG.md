## v1.0.0 - 2025-06-16

### Added
- Python-based Radarr cleaner script for queue monitoring
- Auto-removes downloads without English audio language
- Adds failed downloads to Radarr history and blocklist
- Tracks retry attempts using a local SQLite database
- Configurable retry limits and time windows via environment variables
- Clean logging with rotating file handler
- Dockerfile for easy container deployment

### Notes
- Requires `RADARR_URL` and `RADARR_API_KEY` set via environment
- Designed to run as a Docker container on Unraid or Linux

