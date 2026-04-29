console.log("script.js loaded ✅");

const chatbox = document.getElementById("chatbox");
const cards = document.getElementById("cards");
const msg = document.getElementById("msg");

const tagBar = document.getElementById("tagBar");
const tagInput = document.getElementById("tagInput");
const searchInput = document.getElementById("searchInput");

function escapeHtml(str){
  return String(str)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function addBubble(text, who){
  if(!chatbox) return;
  const div = document.createElement("div");
  div.className = `bubble ${who}`;
  div.textContent = text;
  chatbox.appendChild(div);
  chatbox.scrollTop = chatbox.scrollHeight;
}

msg?.addEventListener("keydown", (e)=>{
  if(e.key === "Enter"){
    e.preventDefault();
    sendMsg();
  }
});

async function sendMsg(){
  const text = (msg?.value || "").trim();
  if(!text) return;

  addBubble(text, "user");

  try{
    const res = await fetch("/chat",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({msg:text})
    });
    const data = await res.json();

    if(data.response){
      addBubble(data.response, "bot");
    }

    if(!text.startsWith("?") && !text.endsWith("?")){
      loadMemories();
    }
  }catch{
    addBubble("Server/Network error ⚠️", "bot");
  }

  msg.value = "";
}
window.sendMsg = sendMsg;

async function loadMemories(){
  try{
    const res = await fetch("/all");
    const data = await res.json();
    showCards(data);
  }catch{
    showCards([]);
  }
}
window.loadMemories = loadMemories;

// live search
if (searchInput) {
  let tmr = null;

  searchInput.addEventListener("keydown", (e)=>{
    if(e.key === "Enter") e.preventDefault();
  });

  searchInput.addEventListener("input", () => {
    clearTimeout(tmr);

    tmr = setTimeout(async () => {
      const q = searchInput.value.trim();
      if (!q) {
        loadMemories();
        return;
      }

      try{
        const res = await fetch("/search?q=" + encodeURIComponent(q));
        const data = await res.json();
        showCards(data);
      }catch{
        showCards([]);
      }
    }, 200);
  });
}

// tag bar
function toggleTagBar(){
  if(!tagBar) return;
  tagBar.classList.toggle("hidden");
  if(!tagBar.classList.contains("hidden")) tagInput?.focus();
}
window.toggleTagBar = toggleTagBar;

async function applyTag(){
  const t = (tagInput?.value || "").trim().replace("#","");
  if(!t) return;

  try{
    const res = await fetch("/tag/" + encodeURIComponent(t));
    const data = await res.json();
    showCards(data);
  }catch{
    showCards([]);
  }
}
window.applyTag = applyTag;

function clearTag(){
  if(tagInput) tagInput.value = "";
  loadMemories();
}
window.clearTag = clearTag;

// =======================
// SHOW CARDS (UPDATED)
// =======================
function showCards(data){
  if(!cards) return;

  if (!Array.isArray(data)) data = [];
  cards.innerHTML = "";

  if(data.length === 0){
    cards.innerHTML = `<div class="card"><div class="text">No memories found</div></div>`;
    return;
  }

  data.forEach(m=>{
    const tag = (m.tags && m.tags.length) ? m.tags[0] : "#general";
    const date = m.date || "";
    const text = m.text || "";
    const pinned = m.pinned || false;

    const el = document.createElement("div");
el.className = "card" + (pinned ? " pinned" : "");
    el.dataset.id = m.id || "";

    el.innerHTML = `
      <div class="text">
        ${pinned ? "📌 " : ""}${escapeHtml(text)}
      </div>

      <div class="meta">
        <span class="badge">${escapeHtml(tag)}</span>
        <span>${escapeHtml(date)}</span>
      </div>

      <div class="card-actions">
        <button class="btn btn-pin" data-action="pin">
          ${pinned ? "Unpin" : "Pin"}
        </button>
        <button class="btn btn-edit" data-action="edit">Edit</button>
        <button class="btn btn-del" data-action="delete">Delete</button>
      </div>
    `;

    cards.appendChild(el);
  });
}

// =======================
// CLICK HANDLER (UPDATED)
// =======================
cards?.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if(!btn) return;

  const card = btn.closest(".card");
  if(!card) return;

  const action = btn.dataset.action;
  const id = card.dataset.id;

  if(!id) return;

  // ⭐ PIN
  if(action === "pin"){
    await fetch("/pin/" + encodeURIComponent(id), { method:"PUT" });
    loadMemories();
    return;
  }

  // DELETE
  if(action === "delete"){
    await fetch("/delete/" + encodeURIComponent(id), { method:"DELETE" });
    loadMemories();
    return;
  }

  // EDIT
  if(action === "edit"){
    const oldText = card.querySelector(".text")?.textContent || "";
    const newText = prompt("Update memory:", oldText);
    if(!newText || !newText.trim()) return;

    await fetch("/edit/" + encodeURIComponent(id), {
      method:"PUT",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ new_text: newText.trim() })
    });

    loadMemories();
  }
});

// summary/calendar
async function getSummary(){
  const res = await fetch("/summary");
  const data = await res.json();
  addBubble(data.summary || "Nothing yet", "bot");
}
window.getSummary = getSummary;

async function getCalendar(){
  const res = await fetch("/calendar");
  const data = await res.json();
  addBubble(data.calendar || "No calendar items", "bot");
}
window.getCalendar = getCalendar;

// THEME
(function () {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
    btn.textContent = theme === "dark" ? "Light" : "Dark";
  }

  const saved = localStorage.getItem("theme") || "dark";
  applyTheme(saved);

  btn.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    applyTheme(current === "dark" ? "light" : "dark");
  });
})();

// initial
loadMemories();