(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.connectorStatus = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const HEALTHY_STATUSES = new Set(['available', 'imported', 'available_media_signal_only']);
  const PENDING_STATUSES = new Set(['missing_credential', 'not_imported']);

  function classifyConnectorStatus(status) {
    if (HEALTHY_STATUSES.has(status)) return 'healthy';
    if (PENDING_STATUSES.has(status)) return 'pending';
    return 'unknown';
  }

  return { HEALTHY_STATUSES, PENDING_STATUSES, classifyConnectorStatus };
});
