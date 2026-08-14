/*
 * Options page (Cài đặt): cau hinh tham so quet cho content script.
 *   - fb_post_count: so bai co binh luan cong khai can tim (1-50)
 *   - fb_load_wait: thoi gian cho lazy-load moi lan cuon (500-10000ms)
 * Container script doc 2 key nay truc tiep tu chrome.storage.local.
 */

const POST_COUNT_KEY = "fb_post_count";
const LOAD_WAIT_KEY = "fb_load_wait";
const DEFAULT_COUNT = 5;
const DEFAULT_WAIT = 3000;

const countInput = document.getElementById("postCount");
const loadWaitInput = document.getElementById("loadWait");
const saveButton = document.getElementById("save");
const resetButton = document.getElementById("reset");
const statusEl = document.getElementById("status");

/**
 * Hien thi text trang thai + class mau cho vung status.
 *
 * @param {string} text - Noi dung trang thai
 * @param {string} [className] - Class mau (vd "ok", "error")
 */
function setStatus(text, className) {
  statusEl.textContent = text;
  statusEl.className = className || "";
}

/**
 * Doc gia tri dang luu va do vao cac input.
 *
 * Logic:
 *   - Doc 2 key cung luc, chi gan khi co gia tri hop le
 */
function loadFromStorage() {
  chrome.storage.local.get([POST_COUNT_KEY, LOAD_WAIT_KEY]).then((data) => {
    if (data[POST_COUNT_KEY]) countInput.value = data[POST_COUNT_KEY];
    if (data[LOAD_WAIT_KEY]) loadWaitInput.value = data[LOAD_WAIT_KEY];
  });
}

/**
 * Kiem tra + luu gia tri 2 input vao storage.
 *
 * Logic:
 *   - Validate tuong tự content script (count 1-50, wait 500-10000)
 *   - Loi -> hien status error, khong luu
 */
function saveSettings() {
  const count = parseInt(countInput.value, 10);
  if (!count || count < 1 || count > 50) {
    setStatus("So bai phai tu 1 den 50 - chua luu.", "error");
    return;
  }
  const wait = parseInt(loadWaitInput.value, 10);
  if (!wait || wait < 500 || wait > 10000) {
    setStatus("Thoi gian cho load phai trong 500-10000ms - chua luu.", "error");
    return;
  }
  chrome.storage.local.set({ [POST_COUNT_KEY]: count, [LOAD_WAIT_KEY]: wait }).then(() => {
    setStatus("Da luu: " + count + " bai, cho load " + wait + "ms. Ap dung tu lan quet tiep theo.", "ok");
  });
}

saveButton.addEventListener("click", saveSettings);

resetButton.addEventListener("click", () => {
  countInput.value = DEFAULT_COUNT;
  loadWaitInput.value = DEFAULT_WAIT;
  chrome.storage.local.remove([POST_COUNT_KEY, LOAD_WAIT_KEY]).then(() => {
    setStatus("Da khoi phuc mac dinh (5 bai, 3000ms).", "ok");
  });
});

loadFromStorage();