import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {Datos, Equipo, Escena, Palabra} from './tipos';

// Marca Edgebook: los mismos colores de la app (app/globals.css).
const FONDO = '#0d1419';
const TARJETA = '#182127';
const BORDE = '#2c3b42';
const APAGADO = '#223039';
const TINTA = '#e3ebef';
const GRIS = '#a2b3bc';
const MENTA = '#77c99a';
const MENTA_OSCURA = '#10251b';
const ROJO = '#e5606a';
const TITULAR = 'Sora, sans-serif';
const TEXTO = "'Space Grotesk', sans-serif";

const fuentes = `
@font-face { font-family: 'Sora'; font-weight: 800; src: url(${staticFile('fuentes/Sora-800.woff2')}) format('woff2'); }
@font-face { font-family: 'Space Grotesk'; font-weight: 300 700; src: url(${staticFile('fuentes/SpaceGrotesk.woff2')}) format('woff2'); }
`;

const miles = (n: number) => Math.round(n).toLocaleString('en-US');
// La liga decide de que carpeta salen fotos y logos; la fija `Partido` al empezar.
let LIGA = 'nba';
const foto = (id: number) => staticFile(`jugadores/${LIGA}/${id}.png`);
const logo = (abbr: string) => staticFile(`logos/${LIGA}/${abbr}.png`);

/** Sobre fondo oscuro, un azul marino o un vino de equipo se apagan: se les sube
 * la luz y la saturacion sin cambiarles el tono. */
const tono = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let l = (max + min) / 2;
  const d = max - min;
  let h = 0;
  let sat = 0;
  if (d > 0) {
    sat = d / (1 - Math.abs(2 * l - 1));
    h = max === r ? ((g - b) / d + 6) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  }
  if (sat > 0.15) sat = Math.min(1, sat * 1.1 + 0.12);
  l = Math.max(l, 0.56);
  return `hsl(${Math.round(h * 60)}, ${Math.round(sat * 100)}%, ${Math.round(l * 100)}%)`;
};

// Tiempo global en segundos: los `cue` del guion vienen en ese reloj.
const Reloj = React.createContext(0);
const useT = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return React.useContext(Reloj) + frame / fps;
};

/** Avance de 0 a 1 desde `ini`, en `dur` segundos, con salida suave. */
const avance = (t: number, ini: number, dur = 0.45) =>
  interpolate(t, [ini, ini + dur], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

const entrada = (t: number, ini: number, dur = 0.35, dy = 40): React.CSSProperties => {
  const a = avance(t, ini, dur);
  return {opacity: a, transform: `translateY(${(1 - a) * dy}px)`};
};

/** Titulo de escena: letrero inclinado en verde que entra de golpe. */
const Titulo: React.FC<{children: React.ReactNode; top?: number}> = ({children, top = 200}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = interpolate(frame / fps, [0.05, 0.4], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.6))});
  const largo = typeof children === 'string' ? children.length : 14;
  return (
    <div style={{position: 'absolute', top, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
      <div style={{position: 'relative', transform: `rotate(-2.5deg) scale(${0.6 + 0.4 * k})`, opacity: Math.min(1, k * 2)}}>
        <div style={{position: 'absolute', inset: 0, background: TINTA, borderRadius: 16, transform: 'translate(12px, 12px)', opacity: 0.16}} />
        <div
          style={{
            position: 'relative', fontFamily: TITULAR, fontWeight: 800, fontSize: largo > 16 ? 66 : largo > 12 ? 76 : 86,
            letterSpacing: -1, textTransform: 'uppercase', lineHeight: 1.1, whiteSpace: 'nowrap',
            color: MENTA_OSCURA, background: MENTA, padding: '10px 36px 12px', borderRadius: 16,
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
};

const Foto: React.FC<{id: number; color: string; size: number; brillo?: boolean}> = ({id, color, size, brillo}) => (
  <div
    style={{
      width: size, height: size, borderRadius: '50%', overflow: 'hidden', background: '#dfe7ea',
      border: `${Math.max(5, size / 40)}px solid ${tono(color)}`, flexShrink: 0, position: 'relative',
      boxShadow: brillo ? `0 0 ${size * 0.35}px ${tono(color)}` : 'none',
    }}
  >
    <Img src={foto(id)} style={{position: 'absolute', width: '138%', left: '-19%', top: '4%'}} />
  </div>
);

/** Logo sobre ficha blanca: asi ninguno se pierde contra el fondo oscuro. */
const Ficha: React.FC<{abbr: string; size: number; style?: React.CSSProperties}> = ({abbr, size, style}) => (
  <div
    style={{
      width: size, height: size, borderRadius: size * 0.24, background: '#ffffff', flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center', ...style,
    }}
  >
    <Img src={logo(abbr)} style={{width: '80%'}} />
  </div>
);

const tarjeta: React.CSSProperties = {background: TARJETA, border: `2px solid ${BORDE}`, borderRadius: 30, boxShadow: '0 18px 50px rgba(0,0,0,0.35)'};

// ---- Escenas ---------------------------------------------------------------

const Heroe: React.FC<{e: Escena}> = ({e}) => {
  const t = useT();
  const p = e.props;
  const fin = e.cues.numero ?? e.ini + 1.5;
  // El contador llega a su numero justo cuando la voz lo dice.
  const k = interpolate(t, [Math.max(e.ini + 0.15, fin - 1.6), fin], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.quad),
  });
  const valor = Math.round(p.desde + (p.hasta - p.desde) * k);
  const golpe = 1 + 0.12 * (1 - avance(t, fin, 0.3)) * (t >= fin ? 1 : 0);
  const sello = e.cues.remate;
  const s = sello ? avance(t, sello, 0.22) : 0;
  return (
    <AbsoluteFill>
      {p.titulo ? <Titulo>{p.titulo}</Titulo> : null}
      <div style={{position: 'absolute', top: p.titulo ? 340 : 230, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        <div style={{opacity: avance(t, e.ini, 0.3), transform: `scale(${0.7 + 0.3 * avance(t, e.ini, 0.4)})`}}>
          <Foto id={p.athlete_id} color={p.color} size={440} brillo />
        </div>
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 290, lineHeight: 1, color: TINTA, marginTop: -40, transform: `scale(${golpe})`, WebkitTextStroke: `14px ${FONDO}`, paintOrder: 'stroke fill', letterSpacing: -6}}>
          {valor}
        </div>
        <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 58, color: MENTA, letterSpacing: 3, marginTop: 4, ...entrada(t, fin - 0.2)}}>{p.etiqueta}</div>
        <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 36, color: GRIS, marginTop: 12, textTransform: 'uppercase', letterSpacing: 1, ...entrada(t, fin)}}>{p.sub}</div>
        {p.pie ? (
          <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 46, color: TINTA, marginTop: 34, padding: '20px 40px', borderRadius: 24, background: TARJETA, border: `3px solid ${MENTA}`, ...entrada(t, e.cues.promedio ?? fin + 0.6)}}>{p.pie}</div>
        ) : null}
      </div>
      {p.remate && sello ? (
        <div style={{position: 'absolute', top: 1200, left: 0, right: 0, display: 'flex', justifyContent: 'center', opacity: s, transform: `rotate(-5deg) scale(${2.2 - 1.2 * s})`}}>
          <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 84, color: '#fff', background: ROJO, padding: '10px 40px', borderRadius: 18}}>{p.remate}</div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const TituloEscena: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const n = Math.round(d.simulaciones * avance(t, e.ini + 0.7, 1.6));
  const a = avance(t, e.ini + 0.1);
  return (
    <AbsoluteFill>
      <Titulo top={250}>{e.props.titulo}</Titulo>
      <div style={{position: 'absolute', top: 420, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 44}}>
        <Ficha abbr={d.equipos.away.abbr} size={330} style={{opacity: a, transform: `translateX(${(1 - a) * -200}px)`}} />
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 80, color: MENTA}}>@</div>
        <Ficha abbr={d.equipos.home.abbr} size={330} style={{opacity: a, transform: `translateX(${(1 - a) * 200}px)`}} />
      </div>
      <div style={{position: 'absolute', top: 840, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 210, color: TINTA, lineHeight: 1, letterSpacing: -6}}>{miles(n)}</div>
      <div style={{position: 'absolute', top: 1070, left: 0, right: 0, textAlign: 'center', fontFamily: TEXTO, fontWeight: 700, fontSize: 76, color: MENTA, letterSpacing: 10}}>{e.props.unidad ?? 'VECES'}</div>
    </AbsoluteFill>
  );
};

/** Orden fijo y repartido de los fallos, para que no queden todos al final. */
const repartir = (total: number, fallos: number) => {
  const marca = new Array(total).fill(false);
  for (let k = 0; k < fallos; k++) marca[Math.min(total - 1, Math.floor(((k + 0.5) * total) / fallos))] = true;
  return marca as boolean[];
};

const Record: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const {aciertos, total, pct} = e.props;
  const fallos = total - aciertos;
  // Con pocos partidos, cuadros mas grandes.
  const cols = total > 110 ? 17 : total > 60 ? 12 : 10;
  const lado = Math.floor(940 / cols) - 10;
  const k = avance(t, e.ini + 0.4, 2.6);
  const cuenta = e.cues.numero ?? e.ini + 2;
  const puntos = React.useMemo(() => repartir(total, fallos), [total, fallos]);
  const filas = Math.ceil(total / cols);
  return (
    <AbsoluteFill>
      <Titulo>{e.props.titulo ?? `EL MODELO ${(d.liga ?? 'nba').toUpperCase()} DA LA CARA`}</Titulo>
      <div style={{position: 'absolute', top: 300, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 220, lineHeight: 1, color: TINTA, letterSpacing: -6}}>
        <span style={{color: MENTA}}>{Math.round(aciertos * avance(t, cuenta - 1.2, 1.2))}</span>
        <span style={{color: GRIS, margin: '0 10px'}}>-</span>
        {Math.round(fallos * avance(t, cuenta - 1.2, 1.2))}
      </div>
      <div style={{position: 'absolute', top: 580, left: (1080 - cols * (lado + 10)) / 2, width: cols * (lado + 10), display: 'flex', flexWrap: 'wrap', gap: 10}}>
        {puntos.map((f, i) => {
          const visto = i / total <= k;
          return (
            <div key={i} style={{width: lado, height: lado, borderRadius: lado * 0.24, background: visto ? (f ? ROJO : MENTA) : APAGADO, color: visto && !f ? MENTA_OSCURA : '#fff', fontFamily: TEXTO, fontWeight: 700, fontSize: lado * 0.62, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
              {visto ? (f ? '✕' : '✓') : ''}
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', top: 580 + filas * (lado + 10) + 34, left: 0, right: 0, textAlign: 'center', fontFamily: TEXTO, fontWeight: 700, fontSize: 56, color: TINTA, letterSpacing: 2, ...entrada(t, cuenta + 0.3)}}>
        <span style={{color: MENTA}}>{pct}%</span> DE ACIERTO AL GANADOR
      </div>
    </AbsoluteFill>
  );
};

const Resultado: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const p = e.props;
  const {home, away} = d.equipos;
  const cols = 50;
  const celda = 17;
  const ini = e.cues.cuenta ?? e.ini + 0.5;
  const k = interpolate(t, [e.ini + 0.3, ini + 1.6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const n = Math.floor(k * p.muestra.length);
  const parte = {away: p.victorias.away / d.simulaciones, home: p.victorias.home / d.simulaciones};
  const ver = e.cues.veredicto ?? e.ini + e.dur - 1.5;
  const m = p.marcador as {home: number; away: number} | undefined;
  const s = interpolate(t, [ver - 0.15, ver + 0.25], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(2))});
  const sube = avance(t, ver, 0.7);
  const lado = (l: 'home' | 'away', izq: boolean) => (
    <div style={{display: 'flex', alignItems: 'center', gap: 22, flexDirection: izq ? 'row' : 'row-reverse'}}>
      <Ficha abbr={d.equipos[l].abbr} size={120} />
      <div style={{textAlign: izq ? 'left' : 'right'}}>
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 112, color: tono(d.equipos[l].color), lineHeight: 1, letterSpacing: -3}}>{Math.round(parte[l] * 100 * k)}%</div>
        <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 30, color: GRIS, letterSpacing: 1, marginTop: 2}}>{miles(p.victorias[l] * k)} VICTORIAS</div>
      </div>
    </div>
  );
  const digito = (v: number, gana: boolean) => (
    <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 210, lineHeight: 1, letterSpacing: -8, color: gana ? TINTA : GRIS, textShadow: gana ? `0 0 60px ${MENTA}88` : 'none', minWidth: 250, textAlign: 'center'}}>{Math.round(v * sube)}</div>
  );
  return (
    <AbsoluteFill>
      <Titulo>{p.titulo}</Titulo>
      <div style={{position: 'absolute', top: 335, left: (1080 - cols * (celda + 3)) / 2, width: cols * (celda + 3), display: 'flex', flexWrap: 'wrap', gap: 3}}>
        {p.muestra.split('').map((c: string, i: number) => (
          <div key={i} style={{width: celda, height: celda, borderRadius: 4, background: i < n ? (c === 'h' ? tono(home.color) : c === 'a' ? tono(away.color) : GRIS) : APAGADO}} />
        ))}
      </div>
      <div style={{position: 'absolute', top: 765, left: 50, right: 50, display: 'flex', justifyContent: 'space-between'}}>
        {lado('away', true)}
        {lado('home', false)}
      </div>
      <div style={{position: 'absolute', top: 925, left: 50, right: 50, height: 24, borderRadius: 12, overflow: 'hidden', background: APAGADO, display: 'flex'}}>
        <div style={{width: `${parte.away * 100 * k}%`, background: tono(away.color)}} />
        <div style={{flex: 1}} />
        <div style={{width: `${parte.home * 100 * k}%`, background: tono(home.color)}} />
      </div>
      {m ? (
        <div style={{position: 'absolute', top: 990, left: 40, right: 40, ...tarjeta, border: `4px solid ${MENTA}`, borderRadius: 40, padding: '22px 28px 30px', opacity: Math.min(1, s * 1.5), transform: `scale(${0.7 + 0.3 * s})`, boxShadow: `0 0 90px ${MENTA}44`}}>
          <div style={{textAlign: 'center', fontFamily: TEXTO, fontWeight: 700, fontSize: 40, letterSpacing: 8, color: MENTA}}>MARCADOR PROMEDIO</div>
          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8}}>
            <Ficha abbr={away.abbr} size={150} />
            {digito(m.away, m.away > m.home)}
            <div style={{width: 40, height: 14, borderRadius: 7, background: MENTA}} />
            {digito(m.home, m.home > m.away)}
            <Ficha abbr={home.abbr} size={150} />
          </div>
        </div>
      ) : (
        <div style={{position: 'absolute', top: 1010, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 62, textTransform: 'uppercase', color: MENTA, ...entrada(t, ver - 0.1)}}>{p.veredicto}</div>
      )}
    </AbsoluteFill>
  );
};

const Dato: React.FC<{valor: string; etiqueta: string; estilo?: React.CSSProperties}> = ({valor, etiqueta, estilo}) => (
  <div style={{...tarjeta, padding: '22px 20px', textAlign: 'center', width: 465, ...estilo}}>
    <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 110, color: MENTA, lineHeight: 1}}>{valor}</div>
    <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 32, color: TINTA, marginTop: 8, letterSpacing: 1}}>{etiqueta}</div>
  </div>
);

const Cerrado: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const p = e.props;
  const {home, away} = d.equipos;
  const max = Math.max(...p.cuentas);
  const crece = avance(t, e.ini + 0.2, 1.0);
  const cMarc = e.cues.marcador ?? e.ini + 0.8;
  const cCerr = e.cues.cerrados ?? e.ini + 2.5;
  const cOt = e.cues.ot ?? e.ini + 5;
  const resalta = avance(t, cCerr, 0.4);
  const alto = 310;
  return (
    <AbsoluteFill>
      <Titulo>{p.titulo}</Titulo>
      <div style={{position: 'absolute', top: 310, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 34, ...entrada(t, cMarc - 0.2)}}>
        <Ficha abbr={away.abbr} size={130} />
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 130, color: TINTA, lineHeight: 1}}>
          <span style={{color: tono(away.color)}}>{p.marcador.away}</span>
          <span style={{color: GRIS, margin: '0 22px'}}>-</span>
          <span style={{color: tono(home.color)}}>{p.marcador.home}</span>
        </div>
        <Ficha abbr={home.abbr} size={130} />
      </div>
      <div style={{position: 'absolute', top: 462, left: 0, right: 0, textAlign: 'center', fontFamily: TEXTO, fontWeight: 500, fontSize: 34, color: GRIS, letterSpacing: 3, ...entrada(t, cMarc)}}>MARCADOR PROMEDIO</div>
      <div style={{position: 'absolute', top: 560, left: 70, right: 70, height: alto, display: 'flex', alignItems: 'flex-end', gap: 6}}>
        {p.cuentas.map((c: number, i: number) => {
          const centro = p.desde + p.ancho * (i + 0.5);
          const cerrado = Math.abs(centro) <= (p.umbral_cerrado ?? 5);
          const color = centro < 0 ? tono(away.color) : centro > 0 ? tono(home.color) : GRIS;
          return (
            <div key={i} style={{flex: 1, height: `${(c / max) * 100 * crece}%`, background: color, borderRadius: '6px 6px 0 0', opacity: cerrado ? 1 : 1 - 0.6 * resalta}} />
          );
        })}
      </div>
      <div style={{position: 'absolute', top: 560 + alto + 14, left: 70, right: 70, display: 'flex', justifyContent: 'space-between', fontFamily: TEXTO, fontWeight: 700, fontSize: 32, letterSpacing: 1}}>
        <span style={{color: tono(away.color)}}>◀ GANA {away.apodo.toUpperCase()}</span>
        <span style={{color: tono(home.color)}}>GANA {home.apodo.toUpperCase()} ▶</span>
      </div>
      <div style={{position: 'absolute', top: 1000, left: 60, right: 60, display: 'flex', justifyContent: 'space-between'}}>
        <Dato valor={`${p.cerrados}%`} etiqueta={p.etiqueta_cerrados ?? 'POR 5 PUNTOS O MENOS'} estilo={entrada(t, cCerr)} />
        <Dato valor={`${p.ot}%`} etiqueta="A TIEMPO EXTRA" estilo={entrada(t, cOt)} />
      </div>
    </AbsoluteFill>
  );
};

const Tarjetas: React.FC<{e: Escena}> = ({e}) => {
  const t = useT();
  return (
    <AbsoluteFill>
      <Titulo>{e.props.titulo}</Titulo>
      <div style={{position: 'absolute', top: 320, left: 50, right: 50, display: 'flex', flexDirection: 'column', gap: 34}}>
        {e.props.tarjetas.map((c: any, i: number) => (
          <div key={i} style={{...tarjeta, borderLeft: `14px solid ${tono(c.color)}`, padding: '30px 30px', display: 'flex', alignItems: 'center', gap: 32, ...entrada(t, (e.cues[`tarjeta${i}`] ?? e.ini) - 0.15)}}>
            <Foto id={c.athlete_id} color={c.color} size={250} />
            <div>
              <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: c.jugador.length > 15 ? 44 : 52, color: TINTA, lineHeight: 1.1}}>{c.jugador}</div>
              {c.lineas.map((l: any, j: number) => (
                <div key={j} style={{marginTop: 12}}>
                  <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: l.valor.length > 8 ? 52 : 80, color: j === 0 ? MENTA : TINTA, lineHeight: 1}}>{l.valor}</div>
                  <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 29, color: GRIS, letterSpacing: 1, marginTop: 2}}>{l.etiqueta}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const Medidor: React.FC<{pct: number; color: string; size?: number}> = ({pct, color, size = 300}) => {
  const r = size * 0.4;
  const largo = 2 * Math.PI * r;
  return (
    <div style={{position: 'relative', width: size, height: size}}>
      <svg width={size} height={size} style={{transform: 'rotate(-90deg)'}}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={APAGADO} strokeWidth={size * 0.113} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={size * 0.113} strokeLinecap="round" strokeDasharray={`${(pct / 100) * largo} ${largo}`} />
      </svg>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: size * 0.255, color: TINTA, letterSpacing: -2}}>{Math.round(pct)}%</div>
    </div>
  );
};

/** La llave con un solo jugador: el y su condicion arriba, el medidor grande abajo. */
const Llave: React.FC<{e: Escena}> = ({e}) => {
  const t = useT();
  const m = e.props.medidores[0];
  const entra = (e.cues.medidor0 ?? e.ini + 0.8) - 0.15;
  const sube = e.cues.sube0 ?? e.ini + 3;
  const k = avance(t, sube - 0.5, 0.9);
  const pct = m.base + (m.pct - m.base) * k;
  const salto = interpolate(t, [sube + 0.1, sube + 0.45], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(2.5))});
  return (
    <AbsoluteFill>
      <Titulo>{e.props.titulo}</Titulo>
      <div style={{position: 'absolute', top: 345, left: 50, right: 50, ...tarjeta, borderLeft: `14px solid ${tono(m.color)}`, padding: '26px 30px', display: 'flex', alignItems: 'center', gap: 34, ...entrada(t, entra)}}>
        <Foto id={m.athlete_id} color={m.color} size={270} brillo />
        <div>
          <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 36, color: GRIS, letterSpacing: 3}}>SI</div>
          <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: m.jugador.length > 10 ? 68 : 84, color: TINTA, lineHeight: 1.05, letterSpacing: -2}}>{m.jugador}</div>
          <div style={{display: 'inline-block', fontFamily: TEXTO, fontWeight: 700, fontSize: 38, color: MENTA_OSCURA, background: MENTA, padding: '8px 22px', borderRadius: 14, marginTop: 14}}>{m.evento}</div>
        </div>
      </div>
      <div style={{position: 'absolute', top: 720, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', ...entrada(t, entra + 0.25)}}>
        <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 46, color: TINTA, letterSpacing: 5, marginBottom: 14}}>{m.equipo.toUpperCase()}</div>
        <div style={{position: 'relative'}}>
          <Medidor pct={pct} color={k > 0.5 ? MENTA : tono(m.color)} size={470} />
          <div style={{position: 'absolute', top: -10, right: -150, fontFamily: TITULAR, fontWeight: 800, fontSize: 76, color: MENTA_OSCURA, background: MENTA, padding: '6px 26px', borderRadius: 22, opacity: Math.min(1, salto * 2), transform: `rotate(8deg) scale(${salto})`}}>+{Math.round(m.pct - m.base)}</div>
        </div>
        <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 38, color: GRIS, letterSpacing: 2, marginTop: 16, opacity: avance(t, sube, 0.3)}}>
          DE {Math.round(m.base)}% A <span style={{color: MENTA, fontWeight: 700}}>{Math.round(m.pct)}%</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Decide: React.FC<{e: Escena}> = ({e}) => {
  const t = useT();
  if (e.props.medidores.length === 1) return <Llave e={e} />;
  return (
    <AbsoluteFill>
      <Titulo>{e.props.titulo}</Titulo>
      <div style={{position: 'absolute', top: 320, left: 50, right: 50, display: 'flex', flexDirection: 'column', gap: 36}}>
        {e.props.medidores.map((m: any, i: number) => {
          const sube = e.cues[`sube${i}`] ?? e.ini + 3;
          const pct = m.base + (m.pct - m.base) * avance(t, sube - 0.5, 0.9);
          return (
            <div key={i} style={{...tarjeta, borderLeft: `14px solid ${tono(m.color)}`, padding: '28px 40px 28px 30px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', ...entrada(t, (e.cues[`medidor${i}`] ?? e.ini) - 0.15)}}>
              <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: 520}}>
                <Foto id={m.athlete_id} color={m.color} size={200} />
                <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 54, color: TINTA, marginTop: 10, lineHeight: 1.05}}>{m.jugador}</div>
                <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 34, color: MENTA, marginTop: 4, textAlign: 'center'}}>{m.evento}</div>
              </div>
              <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
                <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 32, color: GRIS, letterSpacing: 1, marginBottom: 8}}>{m.equipo.toUpperCase()}</div>
                <Medidor pct={pct} color={tono(m.color)} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** Gancho: el partido a la vista desde el primer cuadro y el pick en grande. */
const Gancho: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const p = e.props;
  const fav = p.favorito as 'home' | 'away';
  const pick = e.cues.pick ?? e.ini;
  const rem = e.cues.remate ?? e.ini + 1.6;
  const crece = 1 + 0.16 * avance(t, pick + 0.25, 0.5);
  const s = avance(t, rem, 0.25);
  const ficha = (lado: 'home' | 'away') => (
    <Ficha
      abbr={d.equipos[lado].abbr}
      size={360}
      style={{transform: `scale(${lado === fav ? crece : 2 - crece})`, opacity: lado === fav ? 1 : 1 - 0.45 * avance(t, pick + 0.25, 0.5), boxShadow: lado === fav ? `0 0 0 ${12 * avance(t, pick + 0.25, 0.5)}px ${MENTA}, 0 0 ${140 * avance(t, pick + 0.25, 0.5)}px ${MENTA}` : 'none'}}
    />
  );
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', top: 330, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 60}}>
        {ficha('away')}
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 70, color: GRIS}}>@</div>
        {ficha('home')}
      </div>
      <div style={{position: 'absolute', top: 820, left: 20, right: 20, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: p.linea1.length > 16 ? 104 : 128, color: TINTA, lineHeight: 1.02, letterSpacing: -4, textTransform: 'uppercase', opacity: avance(t, pick - 0.05, 0.15), transform: `scale(${1.5 - 0.5 * avance(t, pick - 0.05, 0.28)})`}}>{p.linea1}</div>
      {p.linea2 ? (
        <div style={{position: 'absolute', top: 1120, left: 0, right: 0, display: 'flex', justifyContent: 'center', opacity: s, transform: `rotate(-2.5deg) scale(${1.6 - 0.6 * s})`}}>
          <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 78, color: MENTA_OSCURA, background: MENTA, padding: '12px 40px', borderRadius: 20, textTransform: 'uppercase'}}>{p.linea2}</div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

/** Como se hizo: dos ingredientes y el contador de partidos jugados. */
const Explica: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const p = e.props;
  const cuenta = e.cues.cuenta ?? e.ini + 2.5;
  const n = Math.round(d.simulaciones * avance(t, cuenta - 0.9, 1.5));
  const k = avance(t, cuenta - 0.9, 2.2);
  const cols = 25;
  return (
    <AbsoluteFill>
      <Titulo>{p.titulo}</Titulo>
      <div style={{position: 'absolute', top: 345, left: 60, right: 60, display: 'flex', flexDirection: 'column', gap: 26}}>
        {p.pasos.map((x: string, i: number) => (
          <div key={i} style={{...tarjeta, padding: '30px 40px', display: 'flex', alignItems: 'center', gap: 30, ...entrada(t, (e.cues[`paso${i}`] ?? e.ini + i * 1.1) - 0.1)}}>
            <div style={{width: 76, height: 76, borderRadius: 38, background: MENTA, color: MENTA_OSCURA, fontFamily: TITULAR, fontWeight: 800, fontSize: 44, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{i + 1}</div>
            <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 50, color: TINTA, letterSpacing: 1}}>{x}</div>
          </div>
        ))}
      </div>
      <div style={{position: 'absolute', top: 715, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 230, color: MENTA, textShadow: `0 0 70px ${MENTA}55`, lineHeight: 1, letterSpacing: -6, opacity: avance(t, cuenta - 0.9, 0.3)}}>{miles(n)}</div>
      <div style={{position: 'absolute', top: 960, left: 0, right: 0, textAlign: 'center', fontFamily: TEXTO, fontWeight: 700, fontSize: 52, color: TINTA, letterSpacing: 6, opacity: avance(t, cuenta - 0.9, 0.3)}}>PARTIDOS SIMULADOS</div>
      <div style={{position: 'absolute', top: 1065, left: (1080 - cols * 36) / 2, width: cols * 36, display: 'flex', flexWrap: 'wrap', gap: 6}}>
        {Array.from({length: cols * 8}, (_, i) => (
          <div key={i} style={{width: 30, height: 30, borderRadius: 7, background: i / (cols * 8) < k ? MENTA : APAGADO, opacity: i / (cols * 8) < k ? 0.35 + 0.65 * ((i * 7919) % 10) / 10 : 1}} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

const Marca: React.FC<{size: number}> = ({size}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: size * 0.28}}>
    <div style={{width: size, height: size, borderRadius: size * 0.28, background: '#173e2a', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Arial, sans-serif', fontWeight: 700, fontStyle: 'italic', fontSize: size * 0.82, color: '#c5efa9', lineHeight: 1, paddingBottom: size * 0.1}}>e</div>
    <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: size * 0.62, color: TINTA, letterSpacing: -1}}>edgebook</div>
  </div>
);

const Cierre: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const p = e.props;
  const late = 1 + 0.03 * Math.sin((t - e.ini) * 5);
  const com = (e.cues.comenta ?? e.ini + 2) - 0.1;
  const palabra: string | undefined = p.palabra;
  // La palabra se "teclea" en la caja de comentario mientras la voz la pide.
  const letras = palabra ? Math.round(palabra.length * avance(t, com + 0.15, 0.6)) : 0;
  const cursor = Math.floor((t - e.ini) * 3) % 2 === 0;
  const golpe = interpolate(t, [(e.cues.pick ?? e.ini) - 0.05, (e.cues.pick ?? e.ini) + 0.3], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(2))});
  return (
    <AbsoluteFill>
      {p.pick ? (
        <div style={{position: 'absolute', top: 150, left: 0, right: 0, display: 'flex', justifyContent: 'center', opacity: Math.min(1, golpe * 2), transform: `rotate(-2.5deg) scale(${0.6 + 0.4 * golpe})`}}>
          <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: p.pick.length > 20 ? 62 : 72, color: MENTA_OSCURA, background: MENTA, padding: '14px 40px', borderRadius: 20, textTransform: 'uppercase', whiteSpace: 'nowrap', boxShadow: `0 0 80px ${MENTA}55`}}>{p.pick}</div>
        </div>
      ) : null}
      <div style={{position: 'absolute', top: p.pick ? 300 : 230, left: 40, right: 40, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: p.pick ? 92 : 112, color: TINTA, lineHeight: 1.05, whiteSpace: 'pre-line', letterSpacing: -3, opacity: p.pick ? avance(t, (e.cues.pregunta ?? e.ini) - 0.1, 0.3) : 1}}>{p.titulo}</div>
      <div style={{position: 'absolute', top: 530, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 44}}>
        <Ficha abbr={d.equipos.away.abbr} size={palabra ? 270 : 320} style={{transform: `scale(${late})`}} />
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 70, color: MENTA}}>VS</div>
        <Ficha abbr={d.equipos.home.abbr} size={palabra ? 270 : 320} style={{transform: `scale(${2 - late})`}} />
      </div>
      {palabra ? (
        <div style={{position: 'absolute', top: 850, left: 60, right: 60, ...entrada(t, com)}}>
          <div style={{...tarjeta, border: `4px solid ${MENTA}`, borderRadius: 60, padding: '20px 30px', display: 'flex', alignItems: 'center', gap: 24, boxShadow: `0 0 70px ${MENTA}44`}}>
            <div style={{width: 84, height: 84, borderRadius: 42, background: APAGADO, color: GRIS, fontFamily: TEXTO, fontWeight: 700, fontSize: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>TÚ</div>
            <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 76, color: TINTA, letterSpacing: 2, flex: 1}}>
              {palabra.slice(0, letras)}
              <span style={{color: MENTA, opacity: cursor ? 1 : 0}}>|</span>
            </div>
            <div style={{width: 84, height: 84, borderRadius: 42, background: MENTA, color: MENTA_OSCURA, fontFamily: TITULAR, fontWeight: 800, fontSize: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transform: `scale(${1 + 0.08 * Math.sin((t - e.ini) * 9)})`}}>↑</div>
          </div>
          <div style={{textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 60, color: MENTA, marginTop: 26, textTransform: 'uppercase'}}>{p.linea1}</div>
          <div style={{textAlign: 'center', fontFamily: TEXTO, fontWeight: 700, fontSize: 42, color: TINTA, letterSpacing: 2, marginTop: 6}}>{p.linea2}</div>
        </div>
      ) : (
        <div style={{position: 'absolute', top: 940, left: 0, right: 0, textAlign: 'center', ...entrada(t, com)}}>
          <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 72, color: MENTA}}>{p.linea1}</div>
          <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 44, color: GRIS, letterSpacing: 3, marginTop: 10}}>{p.linea2}</div>
        </div>
      )}
      <div style={{position: 'absolute', top: palabra ? 1235 : 1180, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, ...entrada(t, e.ini + 0.4)}}>
        <Marca size={88} />
        <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 34, color: GRIS, letterSpacing: 2}}>
          {d.record ? `Modelo ${(d.liga ?? 'nba').toUpperCase()}: ${d.record.aciertos}-${d.record.fallos} esta temporada` : p.lema ?? 'Research antes que ruido'}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Fondo vivo: resplandor de cada equipo y una cuadricula tenue. */
const Fondo: React.FC<{d: Datos}> = ({d}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const dx = Math.sin((frame / fps) * 0.6) * 70;
  const luz = (color: string, pos: React.CSSProperties, op: number) => (
    <div style={{position: 'absolute', width: 1300, height: 1300, borderRadius: '50%', background: `radial-gradient(circle, ${color} 0%, transparent 62%)`, opacity: op, ...pos}} />
  );
  return (
    <AbsoluteFill style={{background: FONDO, overflow: 'hidden'}}>
      {luz(tono(d.equipos.away.color), {left: -700 + dx, top: -350}, 0.2)}
      {luz(tono(d.equipos.home.color), {right: -700 - dx, top: 250}, 0.2)}
      {luz(MENTA, {left: -110, top: 1250 + dx}, 0.1)}
      <AbsoluteFill style={{backgroundImage: `linear-gradient(${BORDE} 1px, transparent 1px), linear-gradient(90deg, ${BORDE} 1px, transparent 1px)`, backgroundSize: '90px 90px', opacity: 0.22}} />
    </AbsoluteFill>
  );
};

/** Cambio de bloque: una franja verde cruza la pantalla. */
const Barrido: React.FC<{ini: number}> = ({ini}) => {
  const t = useT();
  const k = interpolate(t, [ini - 0.14, ini + 0.26], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  if (k <= 0 || k >= 1) return null;
  return (
    <div style={{position: 'absolute', top: -200, bottom: -200, left: -900 + k * 2500, width: 420, transform: 'skewX(-16deg)', display: 'flex'}}>
      <div style={{width: 90, background: TINTA, opacity: 0.5}} />
      <div style={{flex: 1, background: MENTA}} />
    </div>
  );
};

// ---- Capas fijas -------------------------------------------------------------

/** Marca arriba todo el video; la cinta de simulaciones entra con el resultado. */
const Cabecera: React.FC<{d: Datos; cinta: number; fin: number}> = ({d, cinta, fin}) => {
  const t = useT();
  if (t >= fin) return null;
  const texto = d.cinta.map((c, i) => `SIM #${i + 1}  ${c.gana} +${c.por}`).join('   ·   ');
  return (
    <div style={{position: 'absolute', top: 0, left: 0, right: 0}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '50px 44px 14px'}}>
        <Marca size={56} />
        <span style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 30, color: GRIS, letterSpacing: 1, display: 'flex', alignItems: 'center', gap: 16}}>
          {d.record ? (
            <span style={{color: MENTA, fontWeight: 700, border: `2px solid ${MENTA}`, borderRadius: 999, padding: '4px 18px', background: MENTA_OSCURA}}>MODELO {d.record.aciertos}-{d.record.fallos}</span>
          ) : null}
          {miles(d.simulaciones)} SIMS · {d.fecha}
        </span>
      </div>
      {t >= cinta ? (
        <div style={{background: TARJETA, borderTop: `1px solid ${BORDE}`, borderBottom: `1px solid ${BORDE}`, padding: '7px 0', overflow: 'hidden', whiteSpace: 'nowrap', opacity: avance(t, cinta, 0.4)}}>
          <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 27, color: MENTA, transform: `translateX(${1080 - (t - cinta) * 150}px)`}}>{texto}</div>
        </div>
      ) : null}
    </div>
  );
};

/** Subtitulos: frases cortas; la palabra que suena va en verde, la que falta espera en gris. */
const trozar = (palabras: Palabra[]) => {
  const grupos: Palabra[][] = [];
  let actual: Palabra[] = [];
  for (const p of palabras) {
    const letras = actual.reduce((s, x) => s + x.texto.length + 1, 0);
    if (actual.length && (actual.length >= 3 || letras + p.texto.length > 16)) {
      grupos.push(actual);
      actual = [];
    }
    actual.push(p);
    if (/[.,:?!…]$/.test(p.texto)) {
      grupos.push(actual);
      actual = [];
    }
  }
  if (actual.length) grupos.push(actual);
  return grupos;
};

const Subtitulos: React.FC<{d: Datos}> = ({d}) => {
  const t = useT();
  const grupos = React.useMemo(() => d.escenas.flatMap((e) => trozar(e.palabras)), [d]);
  let g = grupos[0];
  for (const x of grupos) if (x[0].ini - 0.08 <= t) g = x;
  if (!g || t > g[g.length - 1].fin + 0.6) return null;
  return (
    <div style={{position: 'absolute', top: 1450, left: 30, right: 30, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 66, textTransform: 'uppercase', lineHeight: 1.15, letterSpacing: -1, textShadow: `0 6px 0 ${FONDO}, 0 0 30px ${FONDO}`}}>
      {g.map((p, i) => {
        const sonando = t >= p.ini - 0.04 && t <= p.fin + 0.05;
        return (
          <span key={i} style={{display: 'inline-block', color: sonando ? MENTA : TINTA, opacity: t >= p.ini - 0.04 ? 1 : 0.25, transform: `scale(${sonando ? 1.06 : 1})`, margin: '0 16px'}}>{p.texto}</span>
        );
      })}
    </div>
  );
};

const ESCENAS: Record<string, React.FC<{e: Escena; d: Datos}>> = {
  gancho: Gancho,
  explica: Explica,
  heroe: Heroe,
  titulo: TituloEscena,
  record: Record,
  resultado: Resultado,
  cerrado: Cerrado,
  tarjetas: Tarjetas,
  decide: Decide,
  cierre: Cierre,
};

export const Partido: React.FC<Datos> = (d) => {
  LIGA = d.liga ?? 'nba';
  const {fps} = useVideoConfig();
  const cuadro = (s: number) => Math.round(s * fps);
  const resultado = d.escenas.find((e) => e.tipo === 'resultado');
  const cierre = d.escenas[d.escenas.length - 1];
  return (
    <AbsoluteFill style={{background: FONDO}}>
      <style>{fuentes}</style>
      <Fondo d={d} />
      <Audio src={staticFile('voz.wav')} />
      {d.escenas.map((e, i) => {
        const Comp = ESCENAS[e.tipo];
        const ultima = i === d.escenas.length - 1;
        return (
          <Sequence key={i} from={cuadro(e.ini)} durationInFrames={ultima ? undefined : cuadro(e.ini + e.dur) - cuadro(e.ini)}>
            <Reloj.Provider value={e.ini}>
              <Comp e={e} d={d} />
            </Reloj.Provider>
          </Sequence>
        );
      })}
      {d.escenas.slice(1).map((e, i) => (
        <Barrido key={i} ini={e.ini} />
      ))}
      <Cabecera d={d} cinta={resultado ? resultado.ini : Infinity} fin={cierre.ini} />
      <Subtitulos d={d} />
    </AbsoluteFill>
  );
};
