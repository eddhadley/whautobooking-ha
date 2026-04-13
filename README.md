# ESP Elite Live Auto-Booker – Home Assistant Integration

A Home Assistant custom integration that automatically books padel courts (or other activities) at West Hants Club via ESP Elite Live.

## Features

- **GUI Setup** — Configure credentials and scheduling through the HA UI (Settings → Integrations → Add → ESP Booker)
- **Auto-booking** — Automatically books courts at a configured time each day, N days in advance
- **Booking Management** — Add, remove, and retry bookings via HA services
- **Status Monitoring** — Each booking is exposed as a sensor entity (pending / booked / failed)
- **Calendar View** — All bookings displayed on a HA calendar entity with status indicators
- **Manual Trigger** — `esp_booker.book_now` service to run bookings on demand

## Installation

### HACS (recommended)

1. Add this repository as a [custom repository in HACS](https://hacs.xyz/docs/faq/custom_repositories)
2. Install "ESP Elite Live Auto-Booker"
3. Restart Home Assistant

### Manual

1. Copy the `custom_components/esp_booker` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **ESP Booker**
3. Enter your ESP Elite Live credentials:
   - **Club ID** — e.g. `3076` for West Hants
   - **Username** — your ESP login
   - **Password** — your ESP password
   - **Auto-book hour (UTC)** — hour to run auto-booking (default: 7)
   - **Auto-book minute** — minute to run auto-booking (default: 2)
   - **Days in advance** — how far ahead to book (default: 7)

Your credentials are stored encrypted in Home Assistant's config entries.

## Usage

### Adding Bookings

Call the `esp_booker.add_booking` service from the UI, automations, or scripts:

```yaml
service: esp_booker.add_booking
data:
  date: "20/04/26"
  time: "09:00"
  court: "PADEL02"
  duration_mins: 60
  num_people: 1
```

### Recurring Bookings

Create a HA automation that adds bookings on a schedule:

```yaml
automation:
  - alias: "Weekly Padel Booking"
    trigger:
      - platform: time
        at: "00:01:00"
    condition:
      - condition: time
        weekday:
          - sat
    action:
      - service: esp_booker.add_booking
        data:
          date: >
            {{ (now() + timedelta(days=7)).strftime('%d/%m/%y') }}
          time: "09:00"
          court: "PADEL02"
```

### Manual Booking Trigger

```yaml
service: esp_booker.book_now
data:
  date: "20/04/26"  # optional, defaults to today + advance_days
```

### Retrying Failed Bookings

```yaml
service: esp_booker.retry_booking
data:
  booking_id: "abc123def456"
```

### Removing Bookings

```yaml
service: esp_booker.remove_booking
data:
  booking_id: "abc123def456"
```

## Dashboard

### Recommended Lovelace cards

```yaml
type: vertical-stack
cards:
  # Summary
  - type: entity
    entity: sensor.esp_booker_bookings_summary

  # Calendar view
  - type: calendar
    entities:
      - calendar.esp_booker_court_bookings

  # All booking entities
  - type: entities
    title: All Bookings
    show_header_toggle: false
    entities:
      - type: custom:auto-entities
        filter:
          include:
            - entity_id: "sensor.esp_booker_*"
              not:
                entity_id: "*summary*"
```

## Entities

| Entity | Type | Description |
|---|---|---|
| `sensor.esp_booker_bookings_summary` | Sensor | Summary counts (pending/booked/failed) |
| `sensor.esp_booker_<court>_<time>_<date>` | Sensor | Individual booking status |
| `calendar.esp_booker_court_bookings` | Calendar | All bookings on a calendar |

## Services

| Service | Description |
|---|---|
| `esp_booker.add_booking` | Add a new planned booking |
| `esp_booker.remove_booking` | Remove a booking by ID |
| `esp_booker.retry_booking` | Reset a failed booking to pending |
| `esp_booker.book_now` | Trigger booking run immediately |

## Project Structure

```
custom_components/esp_booker/
├── __init__.py       # Integration setup, services, timer scheduling
├── manifest.json     # HA integration metadata
├── config_flow.py    # GUI config flow (credentials + schedule)
├── const.py          # Constants and defaults
├── coordinator.py    # DataUpdateCoordinator, booking execution
├── esp_client.py     # ESP Elite Live HTTP booking client (from original project)
├── store.py          # Local JSON storage (replaces Azure Table Storage)
├── sensor.py         # Sensor entities (booking status)
├── calendar.py       # Calendar entity
├── services.yaml     # Service definitions
├── strings.json      # UI strings
└── translations/
    └── en.json       # English translations
```
