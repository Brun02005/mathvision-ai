/* eslint-disable react-refresh/only-export-components */
/**
 * Terms of service and privacy policy (Argentina). DRAFTS: they must be reviewed by a
 * lawyer and completed with the business data before charging real customers. Until
 * VITE_LEGAL_REVIEWED=true is set at build time, every page shows a visible warning.
 */
import { Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';

export const LEGAL = {
  name: import.meta.env.VITE_LEGAL_NAME || '[RAZÓN SOCIAL]',
  taxId: import.meta.env.VITE_LEGAL_TAX_ID || '[CUIT]',
  address: import.meta.env.VITE_LEGAL_ADDRESS || '[DOMICILIO]',
  email: import.meta.env.VITE_CONTACT_EMAIL || '[EMAIL DE CONTACTO]',
  reviewed: import.meta.env.VITE_LEGAL_REVIEWED === 'true',
  updated: '26 de octubre de 2026',
};

function Draft() {
  if (LEGAL.reviewed) return null;
  return (
    <div role="note" className="flex gap-2 text-sm text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
      <AlertTriangle size={16} className="shrink-0 mt-0.5" />
      <p><strong>Borrador.</strong> Este texto todavía no fue revisado por un abogado ni completado con los datos de la empresa.</p>
    </div>
  );
}

export function LegalLayout({ title, children }) {
  return (
    <div className="min-h-screen bg-background">
      <article className="max-w-3xl mx-auto px-4 py-10 space-y-6 text-gray-300 text-sm leading-relaxed">
        <Link to="/" className="text-primary text-sm hover:underline">← Volver a MathVision AI</Link>
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        <p className="text-xs text-gray-500">Última actualización: {LEGAL.updated}</p>
        <Draft />
        {children}
      </article>
    </div>
  );
}

const H = ({ children }) => <h2 className="text-base font-semibold text-white pt-2">{children}</h2>;

export function Terms() {
  return (
    <LegalLayout title="Términos y condiciones">
      <H>1. Quiénes somos</H>
      <p>MathVision AI es un servicio de {LEGAL.name}, CUIT {LEGAL.taxId}, con domicilio en {LEGAL.address}. Contacto: {LEGAL.email}.</p>

      <H>2. El servicio</H>
      <p>MathVision AI resuelve ejercicios de matemática y física y explica los pasos. Los resultados marcados como
        <strong> "Verificado"</strong> fueron calculados y comprobados por un motor de cálculo simbólico. Los marcados como
        <strong> "Resuelto con IA"</strong> los generó un modelo de inteligencia artificial y pueden contener errores. El servicio es
        una herramienta de estudio: revisá los resultados antes de usarlos en una evaluación o trabajo.</p>

      <H>3. Edad mínima</H>
      <p>El servicio es solo para personas mayores de 18 años. Al crear una cuenta declarás tener 18 años o más.</p>

      <H>4. Tu cuenta</H>
      <p>La cuenta es personal. Sos responsable de mantener la contraseña en secreto. No está permitido compartir la cuenta,
        revenderla ni usar programas automáticos para enviar ejercicios.</p>

      <H>5. Planes, precios y pagos</H>
      <p>El plan Gratis tiene un límite diario de ejercicios. El plan Pro es una suscripción mensual en pesos argentinos que se
        cobra por débito automático a través de Mercado Pago. No almacenamos los datos de tu tarjeta: los procesa Mercado Pago.
        Si el precio cambia, te avisamos por email con al menos 30 días de anticipación, y podés cancelar antes de que se aplique.
        El plan Pro tiene un límite diario de uso justo, pensado para frenar el uso automatizado, no el de una persona.</p>

      <H>6. Cancelación (botón de baja)</H>
      <p>Podés cancelar la suscripción cuando quieras desde <Link className="text-primary" to="/cuenta">Mi cuenta</Link>, sin
        trámites adicionales. Seguís teniendo el plan Pro hasta el final del período que ya pagaste, y no se hacen nuevos cobros.</p>

      <H>7. Derecho de arrepentimiento</H>
      <p>Tenés 10 días corridos desde la contratación para revocarla sin dar explicaciones (art. 34 de la Ley 24.240 de Defensa
        del Consumidor). Podés hacerlo desde el <Link className="text-primary" to="/arrepentimiento">Botón de arrepentimiento</Link>,
        sin necesidad de iniciar sesión. Te damos un código de seguimiento al instante y te devolvemos el total pagado.</p>

      <H>8. Uso aceptable</H>
      <p>No podés usar el servicio para atacarlo, sobrecargarlo, eludir los límites de los planes ni para fines ilegales.
        Podemos suspender cuentas que lo hagan.</p>

      <H>9. Responsabilidad</H>
      <p>Trabajamos para que el servicio funcione de forma continua y los resultados sean correctos, pero no podemos garantizar
        que nunca haya interrupciones o errores. Esto no limita los derechos que te da la Ley de Defensa del Consumidor.</p>

      <H>10. Cambios</H>
      <p>Si cambiamos estos términos, te avisamos por email antes de que entren en vigencia.</p>

      <H>11. Ley aplicable</H>
      <p>Estos términos se rigen por las leyes de la República Argentina. Como consumidor, podés reclamar ante los tribunales
        de tu domicilio y ante la autoridad de defensa del consumidor (Ventanilla Federal: www.argentina.gob.ar/produccion/defensadelconsumidor).</p>
    </LegalLayout>
  );
}

export function Privacy() {
  return (
    <LegalLayout title="Política de privacidad">
      <H>Responsable</H>
      <p>{LEGAL.name}, CUIT {LEGAL.taxId}, {LEGAL.address}. Contacto para temas de datos personales: {LEGAL.email}.</p>

      <H>Qué datos tratamos y para qué</H>
      <ul className="list-disc pl-5 space-y-1">
        <li><strong>Email y datos de inicio de sesión</strong>, para crear y proteger tu cuenta.</li>
        <li><strong>Los ejercicios que enviás y sus soluciones</strong>, para resolverlos y mostrarte tu historial. Se guardan hasta
          que los borres o elimines tu cuenta.</li>
        <li><strong>Fotos y PDF</strong>: se usan solo para leer el ejercicio y se eliminan inmediatamente después. No los guardamos.</li>
        <li><strong>Datos de uso</strong> (cantidad de ejercicios por día y su costo de procesamiento), para aplicar los límites de cada
          plan y sostener el servicio.</li>
        <li><strong>Pagos</strong>: los procesa Mercado Pago. Nosotros solo recibimos el estado de la suscripción y de cada pago, nunca
          los datos de tu tarjeta.</li>
        <li><strong>Registros técnicos</strong> (dirección IP, fecha y página solicitada), por seguridad y para resolver fallas. Se conservan
          por un tiempo limitado.</li>
      </ul>

      <H>Con quién los compartimos</H>
      <p>Solo con proveedores que necesitamos para dar el servicio, que los tratan por cuenta nuestra: Supabase (inicio de sesión y
        base de datos), Google (lectura de fotos y asistente de inteligencia artificial) y Mercado Pago (cobros). Algunos de estos
        proveedores almacenan datos fuera de la Argentina. No vendemos tus datos ni los usamos para publicidad.</p>

      <H>Navegador</H>
      <p>Guardamos en tu navegador la sesión iniciada y tus preferencias (por ejemplo, el modo Profesor o Examen). No usamos cookies
        de publicidad ni de seguimiento.</p>

      <H>Tus derechos</H>
      <p>Podés acceder a tus datos, corregirlos o pedir que los eliminemos. Podés borrar ejercicios desde el Historial y eliminar
        tu cuenta con todos sus datos desde <Link className="text-primary" to="/cuenta">Mi cuenta</Link>. Para cualquier otro pedido,
        escribinos a {LEGAL.email}.</p>
      <p className="text-xs text-gray-400 border-l-2 border-white/10 pl-3">
        El titular de los datos personales tiene la facultad de ejercer el derecho de acceso a los mismos en forma gratuita a
        intervalos no inferiores a seis meses, salvo que se acredite un interés legítimo al efecto conforme lo establecido en el
        artículo 14, inciso 3 de la Ley N° 25.326. La AGENCIA DE ACCESO A LA INFORMACIÓN PÚBLICA, en su carácter de Órgano de Control
        de la Ley N° 25.326, tiene la atribución de atender las denuncias y reclamos que interpongan quienes resulten afectados en
        sus derechos por incumplimiento de las normas vigentes en materia de protección de datos personales.
      </p>

      <H>Menores de edad</H>
      <p>El servicio no está dirigido a menores de 18 años y no recolectamos a sabiendas datos de menores.</p>

      <H>Seguridad</H>
      <p>Las contraseñas las gestiona el proveedor de inicio de sesión y nunca llegan a nuestros servidores. La comunicación viaja
        cifrada y cada usuario accede solo a sus propios datos.</p>
    </LegalLayout>
  );
}
