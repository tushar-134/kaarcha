/* app.js - Kharcha Split UI logic (API contract v1.1 shapes) */
(function () {
  const API = window.KharchaAPI;

  const CATEGORY_EMOJI = { chai: "C", food: "F", trip: "T", other: "O" };
  const CATEGORY_LABEL = { chai: "Chai", food: "Khana", trip: "Trip", other: "Other" };

  const fmt = paise => "₹" + ((paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  let hasLoaded = false;
  let members = [];       // [{id, name}]
  let expenses = [];      // contract Expense objects
  let balances = [];      // contract Balance objects
  let settlements = [];   // contract Settlement objects
  let splitMode = "equal";
  let payerId = null;
  let category = "other";

  // ---------- DOM ----------
  const $ = id => document.getElementById(id);
  const form = $("expense-form");
  const fDesc = $("f-desc"), fAmount = $("f-amount");
  const fPayer = $("f-payer"), fSplitMode = $("f-splitmode"), fCategory = $("f-category");
  const customSplit = $("custom-split"), customInputs = $("custom-inputs"), customHint = $("custom-hint");
  const formError = $("form-error");
  const listEl = $("expense-list"), emptyMsg = $("empty-msg"), expCount = $("exp-count");
  const badge = $("backend-badge");
  const settleBtn = $("settle-btn"), settleLine = $("settle-line");
  const balanceCard = $("balance-card");

  function showError(e) {
    formError.textContent = e.message;
    formError.hidden = false;
    if (API.getMode() !== "live") {
      badge.textContent = "Offline";
      badge.className = "badge badge-local";
      badge.title = "Backend unavailable. No automatic local save.";
      $("connection-status").textContent = hasLoaded
        ? "Offline: neeche pichhli baar load hua hisaab hai. Abhi ka balance verify nahi hua."
        : "Backend unavailable: balances aur expenses abhi maloom nahi. Backend chala kar reload karo.";
      $("connection-status").hidden = false;
      if (!hasLoaded) {
        balanceCard.hidden = true;
        $("expense-section").hidden = true;
      }
    }
  }

  // ---------- Seg controls ----------
  function renderPayer() {
    fPayer.innerHTML = "";
    members.forEach(m => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "seg-btn" + (m.id === payerId ? " active" : "");
      b.textContent = m.name;
      b.onclick = () => { payerId = m.id; renderPayer(); };
      fPayer.appendChild(b);
    });
  }

  function renderCategory() {
    fCategory.innerHTML = "";
    API.CATEGORIES.forEach(c => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "seg-btn" + (c === category ? " active" : "");
      b.textContent = CATEGORY_LABEL[c];
      b.onclick = () => { category = c; renderCategory(); };
      fCategory.appendChild(b);
    });
  }

  [...fSplitMode.children].forEach(b => {
    b.onclick = () => {
      splitMode = b.dataset.mode;
      [...fSplitMode.children].forEach(x => x.classList.toggle("active", x === b));
      customSplit.hidden = splitMode !== "custom";
      validateCustom();
    };
  });

  function renderCustomInputs() {
    customInputs.innerHTML = "";
    members.forEach(m => {
      const lab = document.createElement("label");
      lab.innerHTML = esc(m.name) + '<input type="number" min="0" step="0.01" data-member-id="' + m.id + '" placeholder="0">';
      customInputs.appendChild(lab);
      lab.querySelector("input").addEventListener("input", validateCustom);
    });
  }

  function validateCustom() {
    if (splitMode !== "custom") { customHint.textContent = ""; customHint.className = "hint"; return true; }
    const totalPaise = Math.round((parseFloat(fAmount.value) || 0) * 100);
    let sum = 0;
    customInputs.querySelectorAll("input").forEach(i => sum += Math.round((parseFloat(i.value) || 0) * 100));
    const diff = totalPaise - sum;
    if (diff === 0 && totalPaise > 0) {
      customHint.textContent = "Perfect, total match ho gaya.";
      customHint.className = "hint";
      return true;
    }
    customHint.textContent = "Abhi " + fmt(Math.abs(diff)) + (diff > 0 ? " baaki hai" : " zyada ho gaya");
    customHint.className = "hint bad";
    return false;
  }
  fAmount.addEventListener("input", validateCustom);

  // ---------- Render ----------
  function memberName(id) {
    const m = members.find(x => x.id === id);
    return m ? m.name : "?";
  }

  function render() {
    hasLoaded = true;
    balanceCard.hidden = false;
    $("expense-section").hidden = false;
    $("connection-status").hidden = true;
    // Balance rows
    document.querySelectorAll(".balance-row").forEach(r => r.remove());
    balances.forEach(b => {
      const row = document.createElement("div");
      row.className = "balance-row";
      const net = b.net_paise;
      row.innerHTML =
        '<span class="balance-name">' + esc(b.name) + "</span>" +
        '<span class="balance-amount ' + (net > 0 ? "pos" : net < 0 ? "neg" : "") + '">' +
        (net > 0 ? "+" : net < 0 ? "−" : "") + fmt(Math.abs(net)) + "</span>" +
        '<span class="balance-label">' + (net > 0 ? "milne hain" : net < 0 ? "dene hain" : "settled") + "</span>";
      balanceCard.insertBefore(row, settleLine);
    });

    // Settle line (from backend suggestions / local greedy)
    if (!settlements.length) {
      settleLine.textContent = "Sab settled hai, kisi ka kuch nahi banta";
      settleBtn.hidden = expenses.length === 0;
    } else {
      settleLine.textContent = settlements
        .map(s => s.to_name + " ko " + s.from_name + " se " + fmt(s.amount_paise) + " milne hain")
        .join("; ");
      settleBtn.hidden = false;
    }

    // List
    expCount.textContent = expenses.length;
    emptyMsg.style.display = expenses.length ? "none" : "block";
    listEl.innerHTML = "";
    expenses.forEach(e => {
      const li = document.createElement("li");
      li.className = "expense-item";
      let dateStr = "";
      try {
        dateStr = new Date(e.date + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
      } catch (x) {}
      const shareBits = e.shares.map(s => esc(memberName(s.member_id).split(" ")[0]) + " " + fmt(s.amount_paise)).join(", ");
      li.innerHTML =
        '<div class="exp-emoji">' + (CATEGORY_EMOJI[e.category] || CATEGORY_EMOJI.other) + "</div>" +
        '<div class="exp-main"><div class="exp-desc">' + esc(e.description) + "</div>" +
        '<div class="exp-meta">' + esc(memberName(e.paid_by)) + " ne diya • " + dateStr + " • " + shareBits + "</div></div>" +
        '<div class="exp-amount">' + fmt(e.amount_paise) + "</div>" +
        '<button class="exp-del" title="Hatao">✕</button>';
      li.querySelector(".exp-del").onclick = async () => {
        if (!confirm("Ye kharcha delete karna hai?")) return;
        li.querySelector(".exp-del").disabled = true;
        try { await API.deleteExpense(e.id); await refresh(); }
        catch (e) { showError(e); }
        finally { if (li.isConnected) li.querySelector(".exp-del").disabled = false; }
      };
      listEl.appendChild(li);
    });

    // Badge
    const live = API.getMode() === "live";
    badge.textContent = live ? "Live" : "Local";
    badge.className = "badge " + (live ? "badge-live" : "badge-local");
    badge.title = live ? "Backend API connected" : "Backend nahi mila, data isi device pe save ho raha hai";
  }

  async function refresh() {
    members = await API.listMembers();
    if (!members.find(m => m.id === payerId)) payerId = members[0] && members[0].id;
    expenses = await API.listExpenses();
    balances = await API.balances();
    settlements = await API.settlements();
    renderPayer();
    renderCategory();
    renderCustomInputs();
    render();
  }

  // ---------- Events ----------
  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    formError.hidden = true;

    const desc = fDesc.value.trim();
    const amountPaise = Math.round((parseFloat(fAmount.value) || 0) * 100);
    if (!desc) { formError.textContent = "Kharcha kya tha, woh toh likho."; formError.hidden = false; return; }
    if (!(amountPaise > 0)) { formError.textContent = "Amount sahi daalo."; formError.hidden = false; return; }

    let split;
    if (splitMode === "equal") {
      split = { type: "equal", member_ids: members.map(m => m.id) };
    } else {
      if (!validateCustom()) {
        formError.textContent = "Custom split ka total amount ke barabar hona chahiye.";
        formError.hidden = false;
        return;
      }
      split = { type: "exact", shares: [] };
      customInputs.querySelectorAll("input").forEach(i => {
        split.shares.push({ member_id: parseInt(i.dataset.memberId, 10), amount_paise: Math.round((parseFloat(i.value) || 0) * 100) });
      });
    }

    $("add-btn").disabled = true;
    try {
      await API.addExpense({ description: desc, amount_paise: amountPaise, paid_by: payerId, category, split });
    } catch (e) {
      showError(e);
      return;
    } finally { $("add-btn").disabled = false; }
    form.reset();
    payerId = members[0] && members[0].id;
    splitMode = "equal";
    [...fSplitMode.children].forEach(x => x.classList.toggle("active", x.dataset.mode === "equal"));
    customSplit.hidden = true;
    category = "other";
    renderPayer();
    renderCategory();
    renderCustomInputs();
    try { await refresh(); } catch(e) { showError(e); }
  });

  settleBtn.onclick = async () => {
    if (!confirm("Demo reset: saare kharchay delete ho jayenge (live mode mein members bhi, woh wapas ban jayenge). Ye asli settlement nahi hai, sirf demo data saaf karta hai. Pakka?")) return;
    settleBtn.disabled = true;
    try {
    const names = members.map(m => m.name);
    await API.reset();
    if (API.getMode() === "live") {
      // /reset members bhi wipe kar deta hai, wapas bana do
      for (const n of names) await API.addMember(n);
    }
    await refresh();
    } catch(e) { showError(e); }
    finally { settleBtn.disabled = false; }
  };

  // Demo mode: ?demo ho aur koi expense na ho toh backend ka dummy data load karo.
  async function seedDemoIfNeeded() {
    if (!new URLSearchParams(location.search).has("demo")) return;
    const existing = await API.listExpenses();
    if (existing.length) return;
    await API.seed();
  }

  async function start() {
    await seedDemoIfNeeded();
    const existingMembers = await API.listMembers();
    if (!existingMembers.length) {
      // Serverless: another instance may have created them already, so ignore "already exists".
      for (const n of ["Tushar", "Nigamananda"]) {
        try { await API.addMember(n); } catch (e) { /* already exists elsewhere, fine */ }
      }
    }
    await refresh();
  }
  start().catch(showError);
})();
