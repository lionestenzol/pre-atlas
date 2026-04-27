async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function send(type) {
  return new Promise(async (res) => {
    const tab = await activeTab();
    chrome.tabs.sendMessage(tab.id, { type }, (reply) => res(reply || {}));
  });
}

async function refresh() {
  const r = await send('status');
  document.getElementById('scope').textContent = r.scope || '(content script not loaded — refresh the page)';
  document.getElementById('count').textContent = r.count != null ? r.count : '—';
  document.getElementById('toggle').textContent = r.on ? 'turn off' : 'turn on';
}

document.getElementById('toggle').addEventListener('click', async () => {
  await send('toggle');
  refresh();
});
document.getElementById('export').addEventListener('click', async () => {
  await send('export');
});
document.getElementById('clear').addEventListener('click', async () => {
  if (!confirm('Clear all labels on this page?')) return;
  await send('clear');
  refresh();
});

refresh();
