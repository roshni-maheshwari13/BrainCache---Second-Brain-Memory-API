const msgBox = document.getElementById("msgBox");
const tabLogin = document.getElementById("tabLogin");
const tabSignup = document.getElementById("tabSignup");
const submitBtn = document.getElementById("submitBtn");

let mode = "login"; // or "signup"

function showMsg(t){
  msgBox.textContent = t || "";
}

function setMode(m){
  mode = m;
  showMsg("");
  if(mode === "login"){
    tabLogin.classList.add("active");
    tabSignup.classList.remove("active");
    submitBtn.textContent = "Login";
  }else{
    tabSignup.classList.add("active");
    tabLogin.classList.remove("active");
    submitBtn.textContent = "Create Account";
  }
}

tabLogin.addEventListener("click", ()=>setMode("login"));
tabSignup.addEventListener("click", ()=>setMode("signup"));

submitBtn.addEventListener("click", async ()=>{
  showMsg("");
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  if(!username || !password){
    showMsg("Username & password required");
    return;
  }

  try{
    const url = mode === "login" ? "/login" : "/signup";
    const res = await fetch(url,{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({username, password})
    });
    const data = await res.json();
    if(data.ok && data.redirect) window.location = data.redirect;
    else showMsg(data.msg || "Failed");
  }catch(e){
    showMsg("Server/Network error");
  }
});

setMode("login");