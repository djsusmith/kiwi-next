const DEFAULT_WS_URL = "ws://127.0.0.1:9223";

let socket = null;
let connectionState = "disconnected";

async function getWsUrl() {
  const data = await chrome.storage.local.get({ wsUrl: DEFAULT_WS_URL });
  return data.wsUrl;
}

const attachedTabs = new Set();

async function ensureDebuggerAttached(tabId) {
  if (attachedTabs.has(tabId)) return;
  try {
    await chrome.debugger.attach({ tabId }, "1.3");
    attachedTabs.add(tabId);
  } catch (err) {
    if (!String(err?.message || err).includes("Already attached")) {
      throw err;
    }
    attachedTabs.add(tabId);
  }
}

chrome.debugger?.onDetach?.addListener((source) => {
  if (source?.tabId) attachedTabs.delete(source.tabId);
});

chrome.debugger?.onEvent?.addListener((source, method, params) => {
  if (socket && socket.readyState === WebSocket.OPEN && source?.tabId) {
    socket.send(
      JSON.stringify({
        type: "cdp_event",
        tabId: source.tabId,
        method,
        params,
      })
    );
  }
});

async function handleToolCall(msg) {
  const { id, method, params = {} } = msg;
  try {
    let result;
    switch (method) {
      case "list_tabs": {
        const tabs = await chrome.tabs.query({});
        result = tabs.map((t) => ({
          id: t.id,
          url: t.url,
          title: t.title,
          active: t.active,
        }));
        break;
      }
      case "navigate": {
        const tabId = params.tabId ?? (await getActiveTabId());
        const updated = await chrome.tabs.update(tabId, { url: params.url });
        result = { id: updated.id, url: updated.url };
        break;
      }
      case "new_tab": {
        const created = await chrome.tabs.create({
          url: params.url || "about:blank",
          active: params.active ?? true,
        });
        result = { id: created.id, url: created.url, title: created.title };
        break;
      }
      case "close_tab": {
        const tabId = params.tabId ?? (await getActiveTabId());
        await chrome.tabs.remove(tabId);
        result = { closed: tabId };
        break;
      }
      case "eval_js": {
        const tabId = params.tabId ?? (await getActiveTabId());
        await ensureDebuggerAttached(tabId);
        const evalRes = await chrome.debugger.sendCommand(
          { tabId },
          "Runtime.evaluate",
          {
            expression: params.code || "null",
            returnByValue: true,
            awaitPromise: true,
          }
        );
        if (evalRes?.exceptionDetails) {
          throw new Error(
            evalRes.exceptionDetails.text || "JS evaluation exception"
          );
        }
        result = evalRes?.result?.value ?? null;
        break;
      }
      case "cdp_send": {
        const tabId = params.tabId ?? (await getActiveTabId());
        await ensureDebuggerAttached(tabId);
        result = await chrome.debugger.sendCommand(
          { tabId },
          params.cdpMethod,
          params.cdpParams || {}
        );
        break;
      }
      case "capture_screenshot": {
        const dataUrl = await chrome.tabs.captureVisibleTab(null, {
          format: "png",
        });
        result = { dataUrl };
        break;
      }
      default:
        throw new Error(`Unknown MCP method: ${method}`);
    }
    return { id, result };
  } catch (err) {
    return { id, error: { message: String(err?.message || err) } };
  }
}

async function getActiveTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("No active tab found");
  return tab.id;
}

async function connect() {
  if (socket && socket.readyState === WebSocket.OPEN) return;
  const url = await getWsUrl();
  connectionState = "connecting";
  try {
    socket = new WebSocket(url);
    socket.onopen = () => {
      connectionState = "connected";
    };
    socket.onmessage = async (event) => {
      const msg = JSON.parse(event.data);
      const reply = await handleToolCall(msg);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(reply));
      }
    };
    socket.onclose = () => {
      connectionState = "disconnected";
      setTimeout(connect, 5000);
    };
    socket.onerror = () => {
      connectionState = "error";
    };
  } catch {
    connectionState = "error";
    setTimeout(connect, 5000);
  }
}

chrome.runtime.onMessage.addListener((req, _sender, sendResponse) => {
  if (req?.type === "get_status") {
    getWsUrl().then((wsUrl) => sendResponse({ state: connectionState, wsUrl }));
    return true;
  }
  if (req?.type === "reconnect") {
    if (socket) socket.close();
    connect().then(() => sendResponse({ ok: true }));
    return true;
  }
  return false;
});

connect();
