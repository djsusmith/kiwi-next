const DEFAULT_WS_URL = "ws://127.0.0.1:9223";

let socket = null;
let connectionState = "disconnected";

async function getWsUrl() {
  const data = await chrome.storage.local.get({ wsUrl: DEFAULT_WS_URL });
  return data.wsUrl;
}

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
      case "eval_js": {
        const tabId = params.tabId ?? (await getActiveTabId());
        const execResults = await chrome.scripting.executeScript({
          target: { tabId },
          func: (code) => {
            // eslint-disable-next-line no-eval
            return eval(code);
          },
          args: [params.code || "null"],
        });
        result = execResults[0]?.result ?? null;
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
