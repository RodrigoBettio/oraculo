document.getElementById("open-sim-btn").addEventListener("click", () => {
  chrome.tabs.create({ url: chrome.runtime.getURL("test_simulator.html") });
});

document.getElementById("open-meet-btn").addEventListener("click", () => {
  chrome.tabs.create({ url: "https://meet.google.com/new" });
});
