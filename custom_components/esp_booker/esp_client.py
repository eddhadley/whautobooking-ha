"""ESP Elite Live booking client – drives the server-side PHP booking flow.

Ported from the original Azure Function version. This module uses synchronous
requests and should be called via hass.async_add_executor_job() in HA.
"""

import base64
import json
import logging
import re
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.e-s-p.com/elitelive"


class BookingError(Exception):
    """Raised when a booking step fails."""


class ESPBookingClient:
    """Stateful client that walks through the Elite Live booking flow."""

    def __init__(self, club_id: str, username: str, password: str):
        self.club_id = club_id
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-GB,en;q=0.9",
        })

    # ── Step 1: Login ────────────────────────────────────────────────

    def login(self) -> None:
        """Establish club session, GET the login page for CSRF token, then POST credentials."""
        entry_url = f"{BASE_URL}/index.php?clubid={self.club_id}"
        resp = self.session.get(entry_url, allow_redirects=True)
        resp.raise_for_status()
        logger.info("Entry page landed on %s (status %s)", resp.url, resp.status_code)

        login_url = f"{BASE_URL}/login.php?"
        resp = self.session.get(login_url, allow_redirects=True)
        resp.raise_for_status()
        logger.info("Login page status %s, length %d", resp.status_code, len(resp.text))

        token = self._extract_token(resp.text)
        if not token:
            logger.error("Login page HTML (first 2000 chars): %s", resp.text[:2000])
            raise BookingError("Could not extract CSRF tokenstr from login page")

        payload = {
            "username": self.username,
            "password": self.password,
            "tokenstr": token,
            "gotdata": "1",
            "clubid": self.club_id,
            "Submit": "PLEASE WAIT",
        }
        resp = self.session.post(login_url, data=payload, allow_redirects=True)
        resp.raise_for_status()

        if "home.php" not in resp.url and "book_start.php" not in resp.url:
            raise BookingError(f"Login failed – landed on {resp.url}")
        logger.info("Logged in successfully as %s", self.username)

    # ── Step 2: Start booking ────────────────────────────────────────

    def start_booking(self) -> None:
        """POST to book_start.php to initialise the server session."""
        resp = self.session.post(
            f"{BASE_URL}/book_start.php",
            data={},
            allow_redirects=True,
        )
        resp.raise_for_status()
        logger.info("Booking session started")

    # ── Step 3: Select category ──────────────────────────────────────

    def select_category(self, category: str) -> None:
        """GET book_group.php with the chosen category (e.g. 'Padel')."""
        resp = self.session.get(
            f"{BASE_URL}/book_group.php",
            params={"gotdata": "2", "cat": category},
            allow_redirects=True,
        )
        resp.raise_for_status()
        logger.info("Selected category: %s", category)

    # ── Step 4: Select group / configure ─────────────────────────────

    def select_group(
        self,
        group: str,
        description: str,
        duration_mins: int = 60,
        n_date: int = 2,
        look_ahead_days: int = 3,
    ) -> None:
        """GET book_group.php with group-level config."""
        params = {
            "gotdata": "1",
            "GroupSelected": group,
            "NDate": str(n_date),
            "SD": "",
            "SO": "",
            "SP": str(duration_mins),
            "GD": description,
            "TA": "1",
            "CS": "",
            "IQ": "",
            "AP": "",
            "SA": "",
            "GV": "",
            "LD": str(look_ahead_days),
        }
        resp = self.session.get(
            f"{BASE_URL}/book_group.php",
            params=params,
            allow_redirects=True,
        )
        resp.raise_for_status()
        logger.info("Selected group: %s", group)

    # ── Step 5a: Filter availability ─────────────────────────────────

    def filter_availability(
        self,
        date_str: str,
        interval: str = "60 Mins",
        num_people: int = 1,
    ) -> str:
        """POST filter to book_resource_tabular.php. Returns the HTML body."""
        payload = {
            "DateFilter": date_str,
            "IntervalFilter": interval,
            "NumPeople": str(num_people),
            "FilterLocation03": "",
            "gotdata": "1",
        }
        resp = self.session.post(
            f"{BASE_URL}/book_resource_tabular.php?",
            data=payload,
            allow_redirects=True,
        )
        resp.raise_for_status()
        logger.info("Filtered availability for %s", date_str)
        return resp.text

    # ── Step 5b: Select a specific slot ──────────────────────────────

    def select_slot(
        self,
        activity: str,
        activity_desc: str,
        activity_type: str,
        location: str,
        location_type: str,
        location_desc: str,
        export_id: str,
        date_str: str,
        time_str: str,
        num_people: int = 1,
        max_people: int = 1,
        min_people: int = 1,
    ) -> None:
        """POST the base64-encoded selectionData to choose a slot."""
        selection = {
            "BookActivity": activity,
            "BookActDesc": activity_desc,
            "BookActType": activity_type,
            "BookLocation": location,
            "BookLocType": location_type,
            "BookLocDesc": location_desc,
            "BookExport": export_id,
            "MaxPeople": str(max_people),
            "MinPeople": str(min_people),
            "userDate": date_str,
            "userPeople": str(num_people),
            "userTime": time_str,
        }
        encoded = base64.b64encode(
            json.dumps(selection).encode()
        ).decode()

        payload = {"selectionData": encoded, "gotdata": "2"}
        resp = self.session.post(
            f"{BASE_URL}/book_resource_tabular.php?",
            data=payload,
            allow_redirects=True,
        )
        resp.raise_for_status()
        logger.info("Selected slot: %s @ %s on %s", activity, time_str, date_str)

    # ── Step 6: Confirm (no-pay) ─────────────────────────────────────

    def confirm_booking(self) -> bool:
        """Walk through questionnaire → confirm → complete."""
        resp = self.session.get(
            f"{BASE_URL}/book_questionnaire.php?", allow_redirects=True
        )
        resp.raise_for_status()

        resp = self.session.get(
            f"{BASE_URL}/book_confirm.php?", allow_redirects=True
        )
        resp.raise_for_status()
        logger.info("Confirm page loaded – status %s", resp.status_code)

        resp = self.session.get(
            f"{BASE_URL}/wp_cybersource/el_userdetails.php",
            allow_redirects=True,
        )
        resp.raise_for_status()
        logger.info("User-details page loaded – status %s", resp.status_code)

        resp = self.session.get(
            f"{BASE_URL}/wp_cybersource/el_userdetails.php",
            params={"submit_frm_nopay": "Make Booking"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        logger.info(
            "No-pay submission completed – landed on %s (status %s)",
            resp.url,
            resp.status_code,
        )

        if "book_complete" not in resp.url:
            resp = self.session.get(
                f"{BASE_URL}/book_complete.php", allow_redirects=True
            )
            resp.raise_for_status()

        success = "book_complete" in resp.url and resp.status_code == 200
        if not success:
            logger.error(
                "Failed to reach completion page – ended at %s (status %s)",
                resp.url,
                resp.status_code,
            )
            raise BookingError(
                f"Booking did not reach completion page – landed on {resp.url}"
            )

        if (
            "unsuccessful" in resp.text.lower()
            or "failed" in resp.text.lower()
            or "not booked" in resp.text.lower()
        ):
            logger.error(
                "Booking failure detected on completion page: %s", resp.text[:500]
            )
            raise BookingError("Completion page indicates booking was not successful")

        logger.info("Booking confirmed successfully!")
        return True

    # ── Convenience: full booking in one call ────────────────────────

    def book(
        self,
        category: str,
        group: str,
        group_desc: str,
        activity: str,
        activity_desc: str,
        activity_type: str,
        location: str,
        location_type: str,
        location_desc: str,
        export_id: str,
        date_str: str,
        time_str: str,
        duration_mins: int = 60,
        num_people: int = 1,
    ) -> bool:
        """Run the full booking flow end-to-end."""
        self.login()
        self.start_booking()
        self.select_category(category)
        self.select_group(group, group_desc, duration_mins)
        self.filter_availability(date_str, f"{duration_mins} Mins", num_people)
        self.select_slot(
            activity=activity,
            activity_desc=activity_desc,
            activity_type=activity_type,
            location=location,
            location_type=location_type,
            location_desc=location_desc,
            export_id=export_id,
            date_str=date_str,
            time_str=time_str,
            num_people=num_people,
        )
        return self.confirm_booking()

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_token(html: str) -> str | None:
        """Pull the hidden tokenstr value from the login form HTML."""
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("input", {"name": "tokenstr"})
        if tag and tag.get("value"):
            return tag["value"]
        m = re.search(
            r'name=["\']tokenstr["\']\s+value=["\']([a-f0-9]+)["\']', html
        )
        return m.group(1) if m else None
