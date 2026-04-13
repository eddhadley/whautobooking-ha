/**
 * ESP Booker – Custom Lovelace Card
 * Add/view/manage padel court bookings directly from the HA dashboard.
 */

class ESPBookerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = config;
    if (this._hass) this._render();
  }

  getCardSize() {
    return 6;
  }

  static getConfigElement() {
    return document.createElement("esp-booker-card-editor");
  }

  static getStubConfig() {
    return {};
  }

  _getBookingSensors() {
    if (!this._hass) return [];
    const sensors = [];
    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (
        entityId.startsWith("sensor.") &&
        state.attributes &&
        state.attributes.booking_id &&
        state.attributes.date &&
        state.attributes.time
      ) {
        sensors.push({ entityId, ...state });
      }
    }
    // Sort by date/time
    sensors.sort((a, b) => {
      const da = a.attributes.date || "";
      const ta = a.attributes.time || "";
      const db = b.attributes.date || "";
      const tb = b.attributes.time || "";
      // Parse dd/MM/yy to comparable string
      const pa = da.split("/").reverse().join("") + ta.replace(":", "");
      const pb = db.split("/").reverse().join("") + tb.replace(":", "");
      return pa.localeCompare(pb);
    });
    return sensors;
  }

  _getSummary() {
    if (!this._hass) return null;
    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (
        entityId.startsWith("sensor.") &&
        state.attributes &&
        typeof state.attributes.pending === "number" &&
        typeof state.attributes.booked === "number" &&
        typeof state.attributes.failed === "number" &&
        typeof state.attributes.total === "number"
      ) {
        return state;
      }
    }
    return null;
  }

  async _addBooking(bookNow) {
    const root = this.shadowRoot;
    const date = root.getElementById("esp-date").value;
    const time = root.getElementById("esp-time").value;
    const court = root.getElementById("esp-court").value;
    const duration = parseInt(root.getElementById("esp-duration").value, 10);
    const people = parseInt(root.getElementById("esp-people").value, 10);

    if (!date || !time) {
      this._showMessage("Please select a date and time.", "error");
      return;
    }

    // Convert date from yyyy-mm-dd (input) to dd/MM/yy (ESP format)
    const [y, m, d] = date.split("-");
    const espDate = `${d}/${m}/${y.slice(2)}`;

    try {
      await this._hass.callService("esp_booker", "add_booking", {
        date: espDate,
        time: time,
        court: court,
        duration_mins: duration,
        num_people: people,
      });

      if (bookNow) {
        // Small delay to let the booking be stored
        await new Promise((resolve) => setTimeout(resolve, 1000));
        await this._hass.callService("esp_booker", "book_now", {
          date: espDate,
        });
        this._showMessage(`Booking submitted and triggered for ${espDate} at ${time}`, "success");
      } else {
        this._showMessage(`Booking scheduled for ${espDate} at ${time}`, "success");
      }
    } catch (err) {
      this._showMessage(`Error: ${err.message}`, "error");
    }
  }

  async _retryBooking(bookingId) {
    try {
      await this._hass.callService("esp_booker", "retry_booking", {
        booking_id: bookingId,
      });
      this._showMessage("Booking reset to pending for retry.", "success");
    } catch (err) {
      this._showMessage(`Retry failed: ${err.message}`, "error");
    }
  }

  async _removeBooking(bookingId) {
    try {
      await this._hass.callService("esp_booker", "remove_booking", {
        booking_id: bookingId,
      });
      this._showMessage("Booking removed.", "success");
    } catch (err) {
      this._showMessage(`Remove failed: ${err.message}`, "error");
    }
  }

  _showMessage(text, type) {
    const root = this.shadowRoot;
    const msg = root.getElementById("esp-message");
    if (msg) {
      msg.textContent = text;
      msg.className = `message ${type}`;
      msg.style.display = "block";
      setTimeout(() => {
        msg.style.display = "none";
      }, 5000);
    }
  }

  _render() {
    if (!this._hass) return;

    const summary = this._getSummary();
    const sensors = this._getBookingSensors();
    const pending = sensors.filter((s) => s.state === "pending");
    const booked = sensors.filter((s) => s.state === "booked");
    const failed = sensors.filter((s) => s.state === "failed");

    // Default date: 7 days from now
    const defaultDate = new Date();
    defaultDate.setDate(defaultDate.getDate() + 7);
    const defDateStr = defaultDate.toISOString().split("T")[0];

    const statusIcon = (status) => {
      if (status === "pending") return "⏳";
      if (status === "booked") return "✅";
      if (status === "failed") return "❌";
      return "❓";
    };

    const renderBookingRow = (sensor) => {
      const a = sensor.attributes;
      const actions =
        sensor.state === "failed"
          ? `<button class="btn btn-small btn-retry" data-id="${a.booking_id}">Retry</button>
             <button class="btn btn-small btn-remove" data-id="${a.booking_id}">Remove</button>`
          : sensor.state === "pending"
          ? `<button class="btn btn-small btn-remove" data-id="${a.booking_id}">Remove</button>`
          : "";

      return `
        <div class="booking-row ${sensor.state}">
          <span class="booking-icon">${statusIcon(sensor.state)}</span>
          <div class="booking-details">
            <strong>${a.location || "?"}</strong> &middot; ${a.date || "?"} at ${a.time || "?"}
            <br><span class="booking-meta">${a.duration_mins || 60} mins &middot; ${a.num_people || 1} ${(a.num_people || 1) === 1 ? "person" : "people"}</span>
            ${sensor.state === "failed" && a.error_message ? `<br><span class="booking-error">${a.error_message}</span>` : ""}
          </div>
          <div class="booking-actions">${actions}</div>
        </div>`;
    };

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,.15));
          padding: 16px;
          font-family: var(--primary-font-family, Roboto, sans-serif);
          color: var(--primary-text-color, #333);
        }
        h2 { margin: 0 0 12px; font-size: 1.2em; display: flex; align-items: center; gap: 8px; }
        .form-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
          margin-bottom: 12px;
        }
        .form-grid.full { grid-template-columns: 1fr; }
        label { font-size: 0.85em; color: var(--secondary-text-color, #666); margin-bottom: 2px; display: block; }
        input, select {
          width: 100%;
          padding: 8px;
          border: 1px solid var(--divider-color, #ddd);
          border-radius: 8px;
          background: var(--input-fill-color, var(--secondary-background-color, #f5f5f5));
          color: var(--primary-text-color, #333);
          font-size: 0.95em;
          box-sizing: border-box;
        }
        .button-row { display: flex; gap: 8px; margin-bottom: 16px; }
        .btn {
          flex: 1;
          padding: 10px 16px;
          border: none;
          border-radius: 8px;
          font-size: 0.95em;
          font-weight: 500;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }
        .btn-schedule { background: var(--primary-color, #03a9f4); color: #fff; }
        .btn-schedule:hover { filter: brightness(1.1); }
        .btn-booknow { background: #ff9800; color: #fff; }
        .btn-booknow:hover { filter: brightness(1.1); }
        .btn-small {
          flex: unset;
          padding: 4px 10px;
          font-size: 0.8em;
          border-radius: 6px;
        }
        .btn-retry { background: #ff9800; color: #fff; }
        .btn-remove { background: var(--error-color, #db4437); color: #fff; }
        .message {
          display: none;
          padding: 8px 12px;
          border-radius: 8px;
          margin-bottom: 12px;
          font-size: 0.9em;
        }
        .message.success { background: #e8f5e9; color: #2e7d32; }
        .message.error { background: #fbe9e7; color: #c62828; }
        .summary {
          display: flex;
          gap: 16px;
          padding: 10px 0;
          margin-bottom: 12px;
          border-bottom: 1px solid var(--divider-color, #ddd);
          font-size: 0.9em;
        }
        .summary-item { display: flex; align-items: center; gap: 4px; }
        .section-title {
          font-size: 0.95em;
          font-weight: 600;
          margin: 12px 0 6px;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .booking-row {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          padding: 8px;
          border-radius: 8px;
          margin-bottom: 4px;
          background: var(--secondary-background-color, #f5f5f5);
        }
        .booking-row.failed { background: #fbe9e7; }
        .booking-icon { font-size: 1.2em; margin-top: 2px; }
        .booking-details { flex: 1; font-size: 0.9em; line-height: 1.4; }
        .booking-meta { color: var(--secondary-text-color, #666); font-size: 0.85em; }
        .booking-error { color: var(--error-color, #db4437); font-size: 0.8em; }
        .booking-actions { display: flex; gap: 4px; align-items: flex-start; }
        .empty { color: var(--secondary-text-color, #999); font-size: 0.85em; font-style: italic; padding: 4px 8px; }
        .divider { border-top: 1px solid var(--divider-color, #ddd); margin: 8px 0; }
      </style>

      <div class="card">
        <h2>🎾 ESP Booker</h2>

        <div id="esp-message" class="message"></div>

        <!-- Add Booking Form -->
        <div class="form-grid">
          <div>
            <label>Date</label>
            <input type="date" id="esp-date" value="${defDateStr}">
          </div>
          <div>
            <label>Time</label>
            <input type="time" id="esp-time" value="09:00">
          </div>
          <div>
            <label>Court</label>
            <select id="esp-court">
              <option value="PADEL01">Padel 01</option>
              <option value="PADEL02" selected>Padel 02</option>
              <option value="PADEL03">Padel 03</option>
            </select>
          </div>
          <div>
            <label>Duration</label>
            <select id="esp-duration">
              <option value="30">30 mins</option>
              <option value="60" selected>60 mins</option>
              <option value="90">90 mins</option>
              <option value="120">120 mins</option>
            </select>
          </div>
        </div>
        <div class="form-grid full">
          <div>
            <label>Number of People</label>
            <select id="esp-people">
              ${[1, 2, 3, 4, 5, 6, 7, 8]
                .map((n) => `<option value="${n}"${n === 1 ? " selected" : ""}>${n}</option>`)
                .join("")}
            </select>
          </div>
        </div>

        <div class="button-row">
          <button class="btn btn-schedule" id="btn-schedule">📅 Schedule Booking</button>
          <button class="btn btn-booknow" id="btn-booknow">⚡ Book Now</button>
        </div>

        <!-- Summary -->
        ${
          summary
            ? `<div class="summary">
                <span class="summary-item">⏳ ${summary.attributes.pending || 0} pending</span>
                <span class="summary-item">✅ ${summary.attributes.booked || 0} booked</span>
                <span class="summary-item">❌ ${summary.attributes.failed || 0} failed</span>
              </div>`
            : ""
        }

        <!-- Pending -->
        ${
          pending.length
            ? `<div class="section-title">⏳ Pending</div>
               ${pending.map(renderBookingRow).join("")}`
            : ""
        }

        <!-- Confirmed -->
        ${
          booked.length
            ? `<div class="section-title">✅ Confirmed</div>
               ${booked.map(renderBookingRow).join("")}`
            : ""
        }

        <!-- Failed -->
        ${
          failed.length
            ? `<div class="section-title">❌ Failed</div>
               ${failed.map(renderBookingRow).join("")}`
            : ""
        }

        ${!pending.length && !booked.length && !failed.length ? `<div class="empty">No bookings yet.</div>` : ""}
      </div>
    `;

    // Wire up buttons
    this.shadowRoot.getElementById("btn-schedule").addEventListener("click", () => this._addBooking(false));
    this.shadowRoot.getElementById("btn-booknow").addEventListener("click", () => this._addBooking(true));

    // Wire up retry/remove buttons
    this.shadowRoot.querySelectorAll(".btn-retry").forEach((btn) => {
      btn.addEventListener("click", () => this._retryBooking(btn.dataset.id));
    });
    this.shadowRoot.querySelectorAll(".btn-remove").forEach((btn) => {
      btn.addEventListener("click", () => this._removeBooking(btn.dataset.id));
    });
  }
}

// Simple config editor (no config needed, but HA requires the element)
class ESPBookerCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  setConfig(config) {
    this._config = config;
    this.shadowRoot.innerHTML = `<p style="padding:8px">No configuration needed. Just add the card!</p>`;
  }
  get _value() {
    return this._config || {};
  }
}

customElements.define("esp-booker-card", ESPBookerCard);
customElements.define("esp-booker-card-editor", ESPBookerCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "esp-booker-card",
  name: "ESP Booker",
  description: "Add and manage padel court bookings via ESP Elite Live",
  preview: true,
});
