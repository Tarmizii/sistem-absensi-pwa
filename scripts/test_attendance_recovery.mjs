import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class Element {
  constructor(id) {
    this.id = id;
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.listeners = new Map();
    this.children = new Map();
  }
  addEventListener(name, callback) {
    const callbacks = this.listeners.get(name) || [];
    callbacks.push(callback);
    this.listeners.set(name, callbacks);
  }
  async click() {
    for (const callback of this.listeners.get("click") || []) await callback();
  }
  querySelector(selector) {
    if (!this.children.has(selector)) this.children.set(selector, new Element(selector));
    return this.children.get(selector);
  }
}

const ids = [
  "attendance-cta", "attendance-today", "attendance-status", "attendance-camera-panel",
  "attendance-video", "attendance-placeholder", "attendance-cancel", "attendance-refresh",
  "attendance-today-date", "attendance-server-time", "attendance-class-name",
  "attendance-status-label", "attendance-checkin-time", "attendance-checkout-time",
  "attendance-status-source", "attendance-prediction", "attendance-schedule-message",
  "attendance-schedule-times",
];
const elements = new Map(ids.map((id) => [id, new Element(id)]));
Object.assign(elements.get("attendance-today").dataset, {
  csrf: "synthetic-csrf", stateUrl: "/student/attendance-state",
  startUrl: "/attendance/checkin/start", frameUrl: "/attendance/checkin/frame",
  checkoutStartUrl: "/attendance/checkout/start", checkoutFrameUrl: "/attendance/checkout/frame",
});
Object.assign(elements.get("attendance-cta").dataset, { ctaAction: "checkin" });
elements.get("attendance-video").readyState = 3;
elements.get("attendance-video").videoWidth = 640;
elements.get("attendance-video").videoHeight = 480;
elements.get("attendance-video").play = async () => {};

const document = {
  hidden: false,
  getElementById: (id) => elements.get(id) || null,
  createElement: () => ({
    getContext: () => ({ drawImage() {} }),
    toBlob: (callback) => callback(new Blob(["synthetic-frame"], { type: "image/jpeg" })),
  }),
  querySelectorAll: () => [],
  addEventListener() {},
};
const window = {
  location: { assign() {}, reloadCount: 0, reload() { this.reloadCount += 1; } },
  addEventListener() {},
  setInterval: () => 1,
  clearInterval() {},
};
let committed = false;
let starts = 0;
let frames = 0;
let stateReads = 0;
const navigator = {
  onLine: true,
  geolocation: {
    getCurrentPosition(resolve) {
      resolve({ coords: { latitude: 5.1, longitude: 97.1, accuracy: 5 } });
    },
  },
  mediaDevices: {
    async getUserMedia() {
      return { getTracks: () => [{ stop() {} }] };
    },
  },
};
class SyntheticFormData { append() {} }

const response = (data) => ({
  redirected: false,
  ok: true,
  json: async () => data,
});
const fetch = async (url) => {
  if (url === "/attendance/checkin/start") {
    starts += 1;
    return response({ challenge_id: "synthetic-challenge", message: "Hadapkan wajah." });
  }
  if (url === "/attendance/checkin/frame") {
    frames += 1;
    committed = true;
    // The simulated server committed check-in but the browser lost the response.
    throw new TypeError("Failed to fetch after server commit");
  }
  if (url === "/student/attendance-state") {
    stateReads += 1;
    return response({
      checkin_time: committed ? "07:01" : null,
      checkout_time: null,
      state: committed ? "waiting" : "checkin",
      cta_enabled: false,
      cta_label: "Pulang mulai 15:00",
      reason: "Presensi pulang dapat dilakukan mulai 15:00.",
    });
  }
  throw new Error(`Unexpected URL ${url}`);
};

const context = vm.createContext({
  AbortController, Blob, FormData: SyntheticFormData, URLSearchParams,
  document, fetch, navigator, setTimeout, clearTimeout, window,
});
for (const file of ["app/static/js/attendance-checkin.js", "app/static/js/attendance-state.js"]) {
  vm.runInContext(await readFile(file, "utf8"), context, { filename: file });
}

await elements.get("attendance-cta").click();
await new Promise((resolve) => setTimeout(resolve, 650));
assert.equal(committed, true, "simulated server must commit before dropping the response");
assert.equal(elements.get("attendance-cta").dataset.locked, "true");
assert.equal(elements.get("attendance-refresh").hidden, false);
await elements.get("attendance-refresh").click();
assert.equal(stateReads, 1, "the client checks the original action through the server state endpoint");
assert.equal(starts, 1, "the client does not automatically start another attendance action");
assert.equal(frames, 1, "the client stops sending frames after the lost response");
assert.equal(window.location.reloadCount, 1, "a confirmed stored check-in refreshes the server-rendered state");
console.log("attendance_recovery=ok; commit_response_lost=found; next_action_not_sent=ok; frame_stream_stopped=ok");
