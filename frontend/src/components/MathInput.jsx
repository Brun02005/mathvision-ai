/* eslint-disable react-refresh/only-export-components */
/**
 * Visual math editor (MathLive): the user types like in a notebook (fractions, powers,
 * integrals with their limits) and we get LaTeX. On phones a math keyboard opens.
 * Template buttons insert structures with empty boxes to fill (placeholders).
 */
import { useEffect, useImperativeHandle, useRef, forwardRef } from 'react';
import { MathfieldElement } from 'mathlive';

// Fonts are served by the app itself (public/mathlive/fonts): no third-party CDN, CSP stays closed
MathfieldElement.fontsDirectory = '/mathlive/fonts';
MathfieldElement.soundsDirectory = null;

// #? is an empty box the user fills; the cursor jumps to the first one
export const TEMPLATES = [
  { label: '∫ Integral', latex: '\\int #?\\,dx' },
  { label: '∫ₐᵇ Definida', latex: '\\int_{#?}^{#?} #?\\,dx' },
  { label: 'lím Límite', latex: '\\lim_{x\\to #?} #?' },
  { label: 'd/dx Derivada', latex: '\\frac{d}{dx}\\left(#?\\right)' },
  { label: 'a/b Fracción', latex: '\\frac{#?}{#?}' },
  { label: '√ Raíz', latex: '\\sqrt{#?}' },
  { label: 'xⁿ Potencia', latex: '^{#?}' },
  { label: 'Σ Serie', latex: '\\sum_{n=1}^{\\infty} #?' },
  { label: '|x| Módulo', latex: '\\left|#?\\right|' },
  { label: 'π', latex: '\\pi' },
  { label: '∞', latex: '\\infty' },
  { label: 'Matriz 2×2', latex: '\\begin{pmatrix}#?&#?\\\\#?&#?\\end{pmatrix}' },
];

/** True when some template box was left empty. */
export const hasEmptyBoxes = (latex) => /\\placeholder|#\?/.test(latex || '');

const MathInput = forwardRef(function MathInput({ value, onChange, onSubmit, label }, ref) {
  const field = useRef(null);
  const handlers = useRef({ onChange, onSubmit });
  handlers.current = { onChange, onSubmit };

  useImperativeHandle(ref, () => ({
    insert(latex) {
      const mf = field.current;
      mf.focus();
      mf.insert(latex, { selectionMode: 'placeholder', focus: true });
      handlers.current.onChange(mf.value);
    },
    focus() { field.current?.focus(); },
  }), []);

  useEffect(() => {
    const mf = field.current;
    mf.smartFence = true;
    mf.mathVirtualKeyboardPolicy = 'auto';
    const onInput = () => handlers.current.onChange(mf.value);
    const onKey = (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || !e.shiftKey)) {
        e.preventDefault();
        handlers.current.onSubmit?.();
      }
    };
    mf.addEventListener('input', onInput);
    // Capture phase: inside a subscript/superscript box MathLive consumes Enter itself
    mf.addEventListener('keydown', onKey, true);
    return () => {
      mf.removeEventListener('input', onInput);
      mf.removeEventListener('keydown', onKey, true);
    };
  }, []);

  // External changes (examples, clearing) update the editor
  useEffect(() => {
    const mf = field.current;
    if (mf && mf.value !== value) mf.value = value;
  }, [value]);

  return (
    <math-field
      ref={field}
      aria-label={label}
      className="block w-full min-h-[96px] bg-background/60 border border-white/10 rounded-xl px-4 py-3 text-2xl text-white focus-within:border-primary/60"
    />
  );
});

export default MathInput;
