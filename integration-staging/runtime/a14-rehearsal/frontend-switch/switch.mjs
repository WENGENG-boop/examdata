import { pathToFileURL } from 'node:url';
const client = await import(pathToFileURL(process.argv[2]).href);
const store = new Map();
const storage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => { store.set(k, String(v)); },
  removeItem: (k) => { store.delete(k); },
};
const initial = client.clientEnabled({ storage });
client.setClientEnabled(false, { storage });
const afterOff = client.clientEnabled({ storage });
const markerOff = store.get(client.FLAG_NAME);
client.setClientEnabled(true, { storage });
const afterOn = client.clientEnabled({ storage });
const markerGone = !store.has(client.FLAG_NAME);
console.log(JSON.stringify({
  flag: client.FLAG_NAME,
  initial,
  after_off: afterOff,
  marker_after_off: markerOff,
  after_on: afterOn,
  marker_removed_after_on: markerGone,
}));
