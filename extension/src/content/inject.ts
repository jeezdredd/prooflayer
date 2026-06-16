document.addEventListener("contextmenu", (e) => {
  const target = e.target as HTMLElement;
  const img = target.closest("img");
  if (img) {
    chrome.runtime.sendMessage({ type: "SET_IMAGE_URL", url: img.src });
  }
});
