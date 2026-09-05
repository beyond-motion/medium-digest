const dns = require("node:dns");

const LOCALHOST = "localhost";
const IPV4 = "127.0.0.1";

const originalLookup = dns.lookup.bind(dns);
const originalLookupPromise = dns.promises.lookup.bind(dns.promises);

function normalizeCallbackArgs(options, callback) {
  if (typeof options === "function") return { options: undefined, callback: options };
  return { options, callback };
}

dns.lookup = function patchedLookup(hostname, options, callback) {
  const normalized = normalizeCallbackArgs(options, callback);
  if (hostname !== LOCALHOST) return originalLookup(hostname, normalized.options, normalized.callback);

  const result =
    typeof normalized.options === "object" && normalized.options?.all
      ? [{ address: IPV4, family: 4 }]
      : [null, IPV4, 4];

  process.nextTick(() => {
    normalized.callback?.(...result);
  });
};

dns.promises.lookup = async function patchedLookupPromise(hostname, options) {
  if (hostname !== LOCALHOST) return originalLookupPromise(hostname, options);
  if (typeof options === "object" && options?.all) return [{ address: IPV4, family: 4 }];
  return { address: IPV4, family: 4 };
};
