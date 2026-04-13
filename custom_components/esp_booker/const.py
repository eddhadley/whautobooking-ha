"""Constants for the ESP Booker integration."""

DOMAIN = "esp_booker"

CONF_CLUB_ID = "club_id"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_BOOK_HOUR = "book_hour"
CONF_BOOK_MINUTE = "book_minute"
CONF_ADVANCE_DAYS = "advance_days"

DEFAULT_CLUB_ID = "3076"
DEFAULT_BOOK_HOUR = 7
DEFAULT_BOOK_MINUTE = 2
DEFAULT_ADVANCE_DAYS = 7

# Booking statuses
STATUS_PENDING = "pending"
STATUS_BOOKED = "booked"
STATUS_FAILED = "failed"

# Known activities/courts for West Hants
COURTS = ["PADEL01", "PADEL02", "PADEL03"]
DURATIONS = [30, 60, 90, 120]

# Default booking field values
DEFAULT_CATEGORY = "Padel"
DEFAULT_GROUP = "V_Padel"
DEFAULT_GROUP_DESC = "Book Padel Courts"
DEFAULT_ACTIVITY = "PADEL60"
DEFAULT_ACTIVITY_DESC = "Padel 60 Mins"
DEFAULT_ACTIVITY_TYPE = "A"
DEFAULT_LOCATION_TYPE = "Padel"
DEFAULT_EXPORT_ID = "000093"
DEFAULT_DURATION_MINS = 60
DEFAULT_NUM_PEOPLE = 1
