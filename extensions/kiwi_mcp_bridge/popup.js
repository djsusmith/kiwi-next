const statusEl = document.getElementById("status");
const wsUrlEl = document.getElementById("wsUrl");
const saveBtn = document.getElementById("saveBtn");

chrome.runtime.sendMessage({ type: "get_status" }, (resp) => {
  if (resp) {
    statusEl.textContent = resp.state;
    wsUrlEl.value = resp.wsUrl || "ws://127.0.0.1:9223";
  }
});

saveBtn.addEventListener("click", async () => {
  await chrome.storage.local.set({ wsUrl: wsUrlEl.value.trim() });
  chrome.runtime.sendMessage({ type: "reconnect" }, () => {
    statusEl.textContent = "reconnecting...";
  });
});
