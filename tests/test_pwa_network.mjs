import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(here, "../app/static/js/pwa-register.js"), "utf8");

test("offline notice becomes a reload action after reconnect and registers root scope", async () => {
  const listeners = new Map();
  const nodeListeners = new Map();
  const nodes = new Map([
    ["network-status", { hidden: true }],
    ["network-status-message", { textContent: "" }],
    ["network-reload", { hidden: true, addEventListener: (name, callback) => nodeListeners.set(name, callback) }],
  ]);
  let reloadCount = 0;
  let registration;
  const window = {
    location: { reload: () => { reloadCount += 1; } },
    addEventListener: (name, callback) => listeners.set(name, callback),
  };
  const navigator = {
    onLine: false,
    serviceWorker: { register: (url, options) => { registration = { url, options }; return Promise.resolve({}); } },
  };
  vm.runInNewContext(source, {
    document: { getElementById: (id) => nodes.get(id) },
    window, navigator,
  });
  assert.equal(nodes.get("network-status").hidden, false);
  assert.match(nodes.get("network-status-message").textContent, /offline/i);
  assert.equal(nodes.get("network-reload").hidden, true);
  assert.equal(registration.url, "/service-worker.js");
  assert.equal(registration.options.scope, "/");

  listeners.get("online")();
  assert.match(nodes.get("network-status-message").textContent, /Muat ulang/i);
  assert.equal(nodes.get("network-reload").hidden, false);
  nodeListeners.get("click")();
  assert.equal(reloadCount, 1);
});
