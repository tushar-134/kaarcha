/* Integrated v1.1 live client. Backend required; no silent localStorage fallback. */
(function () {
  const API_BASE = window.KHARCHA_API_BASE || "/api/v1";


  let mode = "error"; // "live" jab backend mil jaye

  // ---------- live fetch ----------
  async function tryFetch(path, opts) {
    const res = await fetch(API_BASE + path, Object.assign({
      headers: { "Content-Type": "application/json" }
    }, opts));
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) {
      const err = new Error((data && data.error && data.error.message) || ("API " + res.status));
      err.code = data && data.error && data.error.code;
      err.apiError = true;
      throw err;
    }
    return data;
  }
  // Sirf connectivity/mode decide karne ke liye; API errors upar throw hote hain.
  async function liveOrLocal(fn) {
    try {
      const out = await fn();
      mode = "live";
      return out;
    } catch (e) {
      mode = "error";
      if (e.apiError) throw e;
      throw new Error("Backend se connection nahi hai. Data save nahi hua. Backend chalao aur dobara try karo.");
    }
  }

  window.KharchaAPI = {
    getMode: () => mode,
    CATEGORIES: ["chai", "food", "trip", "other"],
    listMembers: () => liveOrLocal(async () => (await tryFetch("/members")).members),
    addMember: name => liveOrLocal(() => tryFetch("/members", {method:"POST", body:JSON.stringify({name})})),
    listExpenses: () => liveOrLocal(async () => (await tryFetch("/expenses")).expenses),
    addExpense: exp => liveOrLocal(() => tryFetch("/expenses", {method:"POST", body:JSON.stringify(exp)})),
    deleteExpense: id => liveOrLocal(() => tryFetch("/expenses/" + encodeURIComponent(id), {method:"DELETE"})),
    balances: () => liveOrLocal(async () => (await tryFetch("/balances")).balances),
    settlements: () => liveOrLocal(async () => (await tryFetch("/settlements")).settlements),
    seed: () => liveOrLocal(() => tryFetch("/seed", {method:"POST", body:"{}"})),
    reset: () => liveOrLocal(() => tryFetch("/reset", {method:"POST", body:"{}"}))
  };
})();
