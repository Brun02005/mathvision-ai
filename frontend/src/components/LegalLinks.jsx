import { Link } from 'react-router-dom';

/** Links required to be visible from the home page (consumer law) plus terms and privacy. */
export default function LegalLinks({ className = '' }) {
  const link = 'hover:text-white transition-colors';
  return (
    <nav aria-label="Legales" className={`flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-500 ${className}`}>
      <Link className={`${link} font-semibold text-gray-400`} to="/arrepentimiento">Botón de arrepentimiento</Link>
      <Link className={link} to="/cuenta#baja">Botón de baja</Link>
      <Link className={link} to="/terminos">Términos</Link>
      <Link className={link} to="/privacidad">Privacidad</Link>
    </nav>
  );
}
