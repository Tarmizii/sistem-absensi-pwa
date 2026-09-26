import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const workerSource = fs.readFileSync(path.join(here, "../app/static/service-worker.js"), "utf8");

function makeHarness() {
  const origin = "https://presensi.test";
  const listeners = new Map();
  const store = new Map();
  const requests = [];
  let networkOffline = false;
  const resolveKey = (request) => new URL(typeof request === "string" ? request : request.url, origin).href;

  class MemoryCache {
    constructor(name) { this.name = name; }
    async addAll(urls) {
      for (const url of urls) {
        const request = new Request(new URL(url, origin));
        const response = await fakeFetch(request);
        if (!response.ok) throw new Error(`Cannot precache ${url}`);
        await this.put(request, response);
      }
    }
    async match(request) {
      const response = store.get(this.name)?.get(resolveKey(request));
      return response?.clone();
    }
    async put(request, response) {
      if (!store.has(this.name)) store.set(this.name, new Map());
      store.get(this.name).set(resolveKey(request), response.clone());
    }
  }

  const caches = {
    async open(name) { if (!store.has(name)) store.set(name, new Map()); return new MemoryCache(name); },
    async keys() { return [...store.keys()]; },
    async delete(name) { return store.delete(name); },
    async match(request) {
      for (const entries of store.values()) {
        const response = entries.get(resolveKey(request));
        if (response) return response.clone();
      }
      return undefined;
    },
  };

  async function fakeFetch(request) {
    requests.push(typeof request === "string" ? request : request.url);
    if (networkOffline) throw new TypeError("offline");
    const url = new URL(typeof request === "string" ? request : request.url, origin);
    const body = url.pathname === "/static/offline.html" ? "Anda sedang offline." : `network:${url.pathname}`;
    return new Response(body, {
      status: 200,
      headers: { "Content-Type": url.pathname.endsWith(".css") ? "text/css" : "text/html" },
    });
  }

  const self = {
    location: { origin },
    clients: { claim: async () => {} },
    skipWaiting: async () => {},
    addEventListener: (name, callback) => listeners.set(name, callback),
  };
  const context = vm.createContext({
    self, caches, fetch: fakeFetch, URL, Request, Response, Promise, Set,
  });
  vm.runInContext(workerSource, context, { filename: "service-worker.js" });

  async function fire(name, event) {
    let pending;
    event.waitUntil = (promise) => { pending = promise; };
    event.respondWith = (promise) => { event.intercepted = true; event.response = promise; };
    listeners.get(name)?.(event);
    if (pending) await pending;
    if (event.response) event.result = await event.response;
    return event;
  }

  return {
    listeners, store, requests, caches, fire,
    setOffline(value) { networkOffline = value; },
    staticCache: () => [...store.keys()].find((key) => key.startsWith("presensi-shell-")),
    keys: () => [...store.values()].flatMap((items) => [...items.keys()]),
  };
}

test("install precaches only a small, explicit same-origin static allowlist", async () => {
  const h = makeHarness();
  await h.fire("install", {});
  const keys = h.keys();
  assert.ok(keys.includes("https://presensi.test/static/css/app.css"));
  assert.ok(keys.includes("https://presensi.test/static/offline.html"));
  assert.ok(keys.includes("https://presensi.test/static/fonts/plus-jakarta-sans-variable.ttf"));
  assert.ok(keys.every((key) => new URL(key).pathname.startsWith("/static/")));
  assert.equal(keys.length, 16);
  for (const illustration of ["welcome", "attendance", "enrollment", "success", "school-day", "teacher-welcome", "admin-welcome"]) {
    assert.ok(keys.includes(`https://presensi.test/static/illustrations/${illustration}-v2.webp`));
    assert.ok(!keys.includes(`https://presensi.test/static/illustrations/${illustration}.svg`));
  }
  for (const illustration of ["location", "empty"]) {
    assert.ok(keys.includes(`https://presensi.test/static/illustrations/${illustration}.svg`));
  }
  assert.ok(h.staticCache().endsWith("v8"));
});

test("navigation stays network-only and falls back to generic offline page", async () => {
  const h = makeHarness();
  await h.fire("install", {});
  const before = h.keys();
  let navigation = await h.fire("fetch", {
    request: { method: "GET", mode: "navigate", url: "https://presensi.test/student/dashboard" },
  });
  assert.equal(await navigation.result.text(), "network:/student/dashboard");
  assert.deepEqual(h.keys(), before);
  h.setOffline(true);
  navigation = await h.fire("fetch", {
    request: { method: "GET", mode: "navigate", url: "https://presensi.test/student/dashboard" },
  });
  assert.match(await navigation.result.text(), /sedang offline/i);
  assert.deepEqual(h.keys(), before);
});

test("API, private images, and logout/attendance mutations are never placed in Cache Storage", async () => {
  const h = makeHarness();
  await h.fire("install", {});
  const before = h.keys();
  for (const url of [
    "https://presensi.test/student/attendance-state",
    "https://presensi.test/attendance/8/evidence/checkin/image",
    "https://presensi.test/storage/faces/private.webp",
  ]) {
    const event = await h.fire("fetch", {
      request: { method: "GET", mode: "same-origin", url },
    });
    assert.equal(event.intercepted, undefined);
  }
  const post = await h.fire("fetch", {
    request: { method: "POST", mode: "cors", url: "https://presensi.test/attendance/checkin/frame" },
  });
  assert.equal(post.intercepted, undefined);
  const logout = await h.fire("fetch", {
    request: { method: "POST", mode: "cors", url: "https://presensi.test/logout" },
  });
  assert.equal(logout.intercepted, undefined);
  assert.deepEqual(h.keys(), before);
});

test("only allowlisted static files are cache-first and old app cache versions are removed", async () => {
  const h = makeHarness();
  h.store.set("presensi-shell-v7", new Map());
  h.store.set("another-app-cache", new Map());
  await h.fire("install", {});
  await h.fire("activate", {});
  assert.ok(!h.store.has("presensi-shell-v7"));
  assert.ok(h.store.has("another-app-cache"));
  const staticRequest = { method: "GET", mode: "same-origin", url: "https://presensi.test/static/css/app.css" };
  const networkCalls = h.requests.length;
  h.setOffline(true);
  const staticResponse = await h.fire("fetch", { request: staticRequest });
  assert.equal(await staticResponse.result.text(), "network:/static/css/app.css");
  assert.equal(h.requests.length, networkCalls, "cached CSS must not require the network");
  const before = h.keys();
  await h.fire("fetch", {
    request: { method: "GET", mode: "same-origin", url: "https://presensi.test/static/storage/faces/private.webp" },
  });
  assert.deepEqual(h.keys(), before);
});

test("query strings, other origins, and unlisted scripts do not enter the static cache", async () => {
  const h = makeHarness();
  await h.fire("install", {});
  const before = h.keys();
  for (const url of [
    "https://presensi.test/static/css/app.css?private=1",
    "https://other.test/static/css/app.css",
    "https://presensi.test/static/js/attendance-checkin.js",
  ]) {
    const event = await h.fire("fetch", { request: { method: "GET", mode: "cors", url } });
    assert.equal(event.intercepted, undefined);
  }
  assert.deepEqual(h.keys(), before);
});
