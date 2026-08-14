/*
 * Popup: hien thi ket qua + dieu khien quet.
 *   - Nut "Quet ngay" -> gui AUTO_SCAN toi content script: tu cuon trang
 *     thu thap CONG DON (loc trung), nhan tien trinh qua FB_SCAN_PROGRESS.
 *     Tham so (so bai, thoi gian cho load) doc tu storage - cau hinh trong
 *     trang Cài đặt (options page) mo tu nut "Cài đặt".
 *   - Nut "Tai file txt" tai fb_posts_content.txt va nut "Xoa du lieu".
 *   - Nut "Dong bo len server": gui bai viet da quet len public URL web app;
 *     sau moi "Quet ngay" cung TU DONG dong bo (neu da cau hinh Server URL trong "Cai dat").
 */

const STORAGE_KEY = "fb_posts";
const API_URL_KEY = "fb_api_url";

const buttonDownload = document.getElementById("download");
const buttonClear = document.getElementById("clear");
const buttonScan = document.getElementById("scan");
const buttonSettings = document.getElementById("settings");
const buttonSync = document.getElementById("sync");
const statusEl = document.getElementById("status");
const syncStatusEl = document.getElementById("syncStatus");
const resultEl = document.getElementById("result");

/**
 * Hien banner rieng cho ket qua dong bo len server (xanh = thanh cong, do = that bai).
 *
 * @param {string} text - Noi dung thong bao
 * @param {string} className - "ok" hoac "error"
 */
function showSyncBanner(text, className) {
  syncStatusEl.textContent = text;
  syncStatusEl.className = "show " + (className || "");
}

/**
 * Hien thi text trang thai + class mau cho vung status cua popup.
 *
 * Logic:
 *   - Ghi textContent truc tiep (an toan, khong injection)
 *   - className mac dinh "" neu khong truyen (reset mau cu)
 *
 * @param {string} text - Noi dung trang thai
 * @param {string} [className] - Class mau (vd "ok", "error")
 */
function setStatus(text, className) {
  statusEl.textContent = text;
  statusEl.className = className || "";
}

/**
 * Render danh sach bai viet vao popup (url + badge trang thai + preview).
 *
 * Logic:
 *   - Moi bai tao 3 the: url, badge (LOI / DA LAY NOI DUNG / CHUA LAY),
 *     preview 120 ky tu dong dau cua content
 *   - Doi mau badge theo trang thai: error/wait/ok
 *
 * @param {Array} posts - Danh sach bai tu chrome.storage.local
 */
function render(posts) {
  resultEl.innerHTML = "";
  (posts || []).forEach((post) => {
    const div = document.createElement("div");
    div.className = "item";
    const urlDiv = document.createElement("div");
    urlDiv.className = "url";
    urlDiv.textContent = post.url;
    const status = document.createElement("div");
    status.className = "badge " + (post.error ? "badge-error" : post.content ? "badge-ok" : "badge-wait");
    status.textContent = post.error
      ? "LOI: " + post.error
      : post.content
        ? "DA LAY NOI DUNG (" + post.content.length + " ky tu" +
          (post.commentCount ? ", " + post.commentCount + " binh luan" : "") + ")"
        : "CHUA LAY NOI DUNG";
    const preview = document.createElement("div");
    preview.className = "preview";
    preview.textContent = post.content ? post.content.split("\n")[0].slice(0, 120) : "";
    div.appendChild(urlDiv);
    div.appendChild(status);
    div.appendChild(preview);
    resultEl.appendChild(div);
  });
}

/**
 * Tai 1 file text xuong Downloads bang data URL.
 *
 * Logic:
 *   - Ma hoa content thanh data:text/plain UTF-8 qua encodeURIComponent
 *   - Goi chrome.downloads.download (khong hien hop thoai saveAs)
 *
 * @param {string} filename - Ten file xuat ra (vd fb_posts_content.txt)
 * @param {string} content - Noi dung file
 */
function downloadFile(filename, content) {
  const dataUrl = "data:text/plain;charset=utf-8," + encodeURIComponent(content);
  chrome.downloads.download({ url: dataUrl, filename, saveAs: false });
}

/**
 * Thanh text tai file: dinh dang TXT chuan (=== BAI N ===, URL, NOI DUNG, BINH LUAN).
 *
 * Logic:
 *   - Binh luan: uu tien post.comments, fallback trich tu post.content
 *     (bo dong "--- BINH LUAN CONG KHAI ---" va dong trong)
 *   - Noi dung bai: post.postText hoac content, moi dong them tien to 2 khoang trang
 *
 * @param {Array} posts - Danh sach bai viet
 * @returns {string} Noi dung file TXT
 */
function buildOutputText(posts) {
  return posts.map((post, index) => {
    const comments = Array.isArray(post.comments) && post.comments.length > 0
      ? post.comments.map((c, i) => (i + 1) + ". " + c).join("\n")
      : post.content
        ? post.content.split("\n").filter((l) => l && !l.startsWith("---")).slice(1).map((l, i) => (i + 1) + ". " + l).join("\n")
        : "(khong co binh luan)";
    const body = post.postText || post.content || "(khong lay duoc noi dung)";
    return [
      "=== BAI " + (index + 1) + " ===",
      "URL: " + post.url,
      "NOI DUNG:",
      body.split("\n").map((l) => "  " + l).join("\n"),
      "--- BINH LUAN ---",
      comments,
      "",
    ].join("\n");
  }).join("\n");
}

/**
 * Doc bai viet tu storage, render lai popup, cap nhat trang thai
 * nut Tai file / Xoa du lieu.
 *
 * Logic:
 *   - Co bai: render danh sach, mo 2 nut, in tong so binh luan
 *   - Khong co: hien huong dan mo trang group (khong phai loi)
 */
function refreshFromStorage() {
  chrome.storage.local.get(STORAGE_KEY).then((data) => {
    const posts = data[STORAGE_KEY] || [];
    const hasPosts = posts.length > 0;
    buttonDownload.disabled = !hasPosts;
    buttonClear.disabled = !hasPosts;
    buttonSync.disabled = !hasPosts;
    if (hasPosts) {
      render(posts);
      const totalComments = posts.reduce((sum, p) => sum + (p.commentCount || 0), 0);
      setStatus(
        "Da co " + posts.length + " bai viet, tong " + totalComments + " binh luan cong khai.",
        "ok"
      );
    } else {
      render(posts);
      setStatus("Chua co du lieu. Mo/lam moi (F5) trang group bat ky.", "error");
    }
  }).catch(() => {});
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes[STORAGE_KEY]) {
    refreshFromStorage();
  }
});

/**
 * Lay danh sach bai viet dang luu trong storage.
 *
 * @returns {Promise<Array>} Danh sach bai (rong neu chua co)
 */
function downloadPosts() {
  return chrome.storage.local.get(STORAGE_KEY).then((data) => data[STORAGE_KEY] || []);
}

buttonDownload.addEventListener("click", async () => {
  const posts = await downloadPosts();
  if (posts.length === 0) {
    setStatus("Chua co du lieu de tai.", "error");
    return;
  }
  downloadFile("fb_posts_content.txt", buildOutputText(posts));
  setStatus("Da tai fb_posts_content.txt (Downloads).", "ok");
});

buttonClear.addEventListener("click", () => {
  chrome.storage.local.remove(STORAGE_KEY).then(() => {
    refreshFromStorage();
    setStatus("Da xoa toan bo du lieu da quet.", "ok");
  });
});

buttonSettings.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

/* --- Dong bo du lieu len server (public URL web app) --------------------- */

/**
 * Lay Server URL da cau hinh tu storage (key fb_api_url).
 *
 * @returns {Promise<string|null>} URL dang https://.../api/extension/ingest hoac null
 */
async function getServerUrl() {
  const data = await chrome.storage.local.get(API_URL_KEY);
  const url = (data[API_URL_KEY] || "").trim();
  return url || null;
}

/**
 * Mo ta chi tiet loi HTTP: gan y nghia cho status + kem chi tiet tu server.
 *
 * @param {number} status - Ma HTTP tra ve
 * @param {string} bodyText - Noi dung response (de trich loi tu server)
 * @returns {string} Chuoi mo ta loi day du
 */
function describeHttpError(status, bodyText) {
  let detail = "";
  if (bodyText) {
    try {
      const j = JSON.parse(bodyText);
      detail = j && (j.error || j.detail || j.message);
      if (typeof detail === "object") detail = JSON.stringify(detail);
    } catch (_e) {
      detail = bodyText.slice(0, 160);
      if (bodyText.length > 160) detail += "...";
    }
  }
  const map = {
    400: "du lieu gui len khong hop le (payload khong phai JSON object)",
    401: "chua xac thuc - server moi them auth?",
    403: "server tu choi truy cap (CORS / auth)",
    404: "khong tim thay API - kiem tra lai duong dan (phai la .../api/extension/ingest)",
    405: "phuong thuc sai - API yeu cau POST, khong phai GET/PUT",
    413: "du lieu qua lon - giam so bai/binh luan roi gui lai",
    429: "gui qua nhieu lan - cho mot luc roi thu lai",
    500: "server loi noi bo (xem log web app de biet them)",
    502: "server khong phan hoi - tunnel/gateway loi",
    503: "server dang khoi dong hoac qua tai khan hoi",
  };
  let msg = "HTTP " + status + " - " + (map[status] || "loi khong xac dinh");
  if (detail) msg += "\nChi tiet server: " + detail;
  return msg;
}

/**
 * Gui danh sach bai viet len server qua POST /api/extension/ingest.
 *
 * Logic:
 *   - Mo ta moi bai: url, postText, comments (mang), commentCount, content
 *   - Fetch kem CORS (server da tra Access-Control-Allow-Origin: *)
 *   - Timeout 30s; loi HTTP gan chi tiet; response khong hop le bao ro rang
 *
 * @param {Array} posts - Danh sach bai tu storage
 * @returns {Promise<Object>} JSON tra ve tu server (status, stored_new, ...)
 */
async function uploadPosts(posts) {
  const url = await getServerUrl();
  if (!url) throw new Error("chua cau hinh Server URL (mo 'Cai dat').");
  const items = posts.map((p) => ({
    url: p.url,
    postText: p.postText || "",
    comments: Array.isArray(p.comments) ? p.comments : [],
    commentCount: p.commentCount || (Array.isArray(p.comments) ? p.comments.length : 0),
    content: p.content || "",
  }));

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  let resp = null;
  let bodyText = "";
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "AnhDuy AUTO-BOT", items }),
      signal: controller.signal,
    });
    bodyText = await resp.text();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err && err.name === "AbortError") {
      throw new Error("qua 30 giay server khong phan hoi. Kiem tra Server URL, internet va tunnel (gradio.live) con hoat dong.");
    }
    const detail = err && err.message ? err.message : String(err);
    throw new Error(
      "loi ket noi: " + detail +
      "\nKiem tra: (1) Server URL dung dang https://.../api/extension/ingest, " +
      "(2) web app dang chay va co mang, " +
      "(3) CORS - server phai tra 'Access-Control-Allow-Origin' khi nhan OPTIONS."
    );
  }
  clearTimeout(timeoutId);

  if (!resp.ok) {
    throw new Error(describeHttpError(resp.status, bodyText));
  }
  try {
    return JSON.parse(bodyText);
  } catch (_e) {
    throw new Error("response khong phai JSON: " + bodyText.slice(0, 160));
  }
}

/**
 * Doc bai tu storage roi gui len server. Tra ve chuoi mo ta ket qua.
 *
 * @returns {Promise<string>} Chuoi trang thai (da gui bao nhieu bai...)
 */
async function syncToServer() {
  const posts = await downloadPosts();
  if (posts.length === 0) return "Khong co bai nao de dong bo.";
  const result = await uploadPosts(posts);
  return (
    "Da gui " + result.received_posts + " bai / " + result.received_comments +
    " binh luan len server (luu moi " + result.stored_new + ", trung " +
    result.duplicates_skipped + ", canh bao " + result.alerts_triggered + ")."
  );
}

buttonSync.addEventListener("click", async () => {
  buttonSync.disabled = true;
  try {
    showSyncBanner("Dang gui len server...", "");
    const msg = await syncToServer();
    showSyncBanner("✅ " + msg, "ok");
    setStatus(msg, "ok");
  } catch (err) {
    showSyncBanner("❌ Dong bo that bai: " + err.message, "error");
    setStatus("Dong bo loi: " + err.message, "error");
  } finally {
    buttonSync.disabled = false;
  }
});

/**
 * Nhan tien trinh auto-scroll tu content script (FB_SCAN_PROGRESS).
 *
 * Logic:
 *   - Content script gui sau moi lan luu (count = so bai da gop)
 *   - Popup chi cap nhat status; danh sach tu render qua storage.onChanged
 */
chrome.runtime.onMessage.addListener((message) => {
  if (message && message.type === "FB_SCAN_PROGRESS") {
    setStatus(
      "Dang cuon & thu thap... " + message.count + " bai, " +
      message.totalComments + " binh luan (lan cuon " + (message.scrolls || 1) + ")",
      "ok"
    );
  }
});

buttonScan.addEventListener("click", async () => {
  buttonScan.disabled = true;
  setStatus("Dang cuon & thu thap...", "ok");
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs && tabs.length > 0 ? tabs[0] : null;
    if (!tab || !tab.url || !tab.url.includes("facebook.com/groups/")) {
      setStatus("Tab hien tai KHONG phai trang group - mo group roi bam Quet.", "error");
      return;
    }
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "PING" });
    } catch (_err) {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
    }
    // Tham so (so bai, thoi gian cho load) content script tu doc tu storage
    const resp = await chrome.tabs.sendMessage(tab.id, { type: "AUTO_SCAN" });
    if (resp && resp.count > 0) {
      const scanText =
        "Group " + (resp.groupId || "?") + ": xong - " + resp.count + " bai (" +
        resp.totalComments + " binh luan). Ngung: " + resp.stopped +
        " sau " + resp.scrolls + " lan cuon. Da luu cong don.";
      setStatus(scanText, "ok");
      // Tu dong gui noi dung da quet len server (neu da cau hinh Server URL)
      try {
        const syncMsg = await syncToServer();
        showSyncBanner("✅ Dong bo len server thanh cong: " + syncMsg, "ok");
      } catch (syncErr) {
        showSyncBanner("❌ Dong bo that bai: " + syncErr.message, "error");
      }
    } else {
      const dbg = (resp && resp.debug) || {};
      setStatus(
        "Quet xong: KHONG co bai nao co binh luan cong khai." +
        " [debug: group=" + (resp ? resp.groupId : "?") +
        " mountRoots=" + dbg.rootCount + " feed=" + dbg.feedCount +
        " articles=" + dbg.articleCount + " comments=" + dbg.commentCount +
        " containers=" + dbg.containers + " mountPath=" + dbg.mountFound + "]",
        "error"
      );
    }
  } catch (err) {
    setStatus("Loi quet: " + err.message, "error");
  } finally {
    buttonScan.disabled = false;
  }
});

refreshFromStorage();