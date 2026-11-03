/** Format an API timestamp (UTC, possibly without offset) in the user's local time. */
export function formatDate(iso) {
  if (!iso) return '';
  const hasZone = /Z$|[+-]\d{2}:?\d{2}$/.test(iso);
  const d = new Date(hasZone ? iso : `${iso}Z`);
  return d.toLocaleString('es-AR', { dateStyle: 'medium', timeStyle: 'short' });
}

/**
 * True when the input reads as words (a word problem, "x al cuadrado menos 4") rather than
 * a formula: it is then shown as text, since KaTeX would render it as italic math letters.
 */
export function isPlainText(input) {
  const withoutCommands = (input || '').replace(/\[a-zA-Z]+(\{[^}]*\})?/g, ' ');
  return /[a-záéíóúñ]{4,}/i.test(withoutCommands) || /(^|\s)(más|menos|por|de|la|el)(\s|$)/i.test(withoutCommands);
}
