/** Format an API timestamp (UTC, possibly without offset) in the user's local time. */
export function formatDate(iso) {
  if (!iso) return '';
  const hasZone = /Z$|[+-]\d{2}:?\d{2}$/.test(iso);
  const d = new Date(hasZone ? iso : `${iso}Z`);
  return d.toLocaleString('es-AR', { dateStyle: 'medium', timeStyle: 'short' });
}
