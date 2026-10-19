/**
 * Contract text extracted from Word keeps Symbol/Wingdings glyphs as private-use code points
 * (U+F0xx) that web fonts cannot draw, so they render as empty boxes. Map the known ones to
 * their Unicode look-alike and line separators to newlines. Every replacement is one UTF-16
 * unit, so evidence character offsets still line up with the displayed quote.
 */
const SYMBOL_FONT: Record<string, string> = {
  "\uf0b7": "\u2022", // Symbol bullet
  "\uf0a7": "\u25aa", // Wingdings small square
  "\uf06c": "\u25cf", // Wingdings filled circle
  "\uf06e": "\u25a0", // Wingdings filled square
  "\uf076": "\u2756", // Wingdings diamond
  "\uf0d8": "\u27a2", // Wingdings arrowhead
  "\uf0fc": "\u2713", // Wingdings check mark
  "\uf0fe": "\u2611", // Wingdings checked box
  "\uf02d": "-", // Symbol minus
  "\uf02b": "+", // Symbol plus
  "\u2028": "\n", // line separator
  "\u2029": "\n", // paragraph separator
};

/** Unknown private-use glyphs become U+FFFD, which every font draws, instead of a blank box. */
export function displayText(text: string): string {
  return text.replace(/[\ue000-\uf8ff\u2028\u2029]/g, (ch) => SYMBOL_FONT[ch] ?? "\ufffd");
}
