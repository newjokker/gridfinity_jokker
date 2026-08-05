(function () {
  function labelFor(element) {
    const heading = element.tagName === 'A' ? element.querySelector('h2') : null;
    return (
      element.dataset.action ||
      element.getAttribute('aria-label') ||
      (heading && heading.textContent) ||
      element.textContent ||
      element.id ||
      element.tagName
    ).trim().replace(/\s+/g, ' ').slice(0, 50);
  }

  function record(action, details) {
    const body = JSON.stringify({action, details: details || {}});
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/action', new Blob([body], {type: 'application/json'}));
      return;
    }
    fetch('/api/action', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body,
      keepalive: true,
    }).catch(function () {});
  }

  document.addEventListener('click', function (event) {
    const target = event.target.closest('button, a[href], [role="button"]');
    if (!target || target.disabled) return;
    record(`点击：${labelFor(target)}`);
  }, true);
}());
