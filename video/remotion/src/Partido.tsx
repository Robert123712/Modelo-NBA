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

/** Sobre fondo oscuro, un azul marino o un negro de equipo no se ven: se aclaran. */
const tono = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  let [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  const luz = () => (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  for (let i = 0; i < 12 && luz() < 0.3; i++) {
    r = Math.round(r + (255 - r) * 0.14);
    g = Math.round(g + (255 - g) * 0.14);
    b = Math.round(b + (255 - b) * 0.14);
  }
  return `rgb(${r}, ${g}, ${b})`;
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

/** Titulo de escena: una etiqueta verde, no un letrero gigante. */
const Titulo: React.FC<{children: React.ReactNode; top?: number}> = ({children, top = 190}) => (
  <div style={{position: 'absolute', top, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
    <div
      style={{
        fontFamily: TEXTO, fontWeight: 700, fontSize: 46, letterSpacing: 4, textTransform: 'uppercase',
        color: MENTA_OSCURA, background: MENTA, padding: '10px 34px', borderRadius: 999,
      }}
    >
      {children}
    </div>
  </div>
);

const Foto: React.FC<{id: number; color: string; size: number}> = ({id, color, size}) => (
  <div
    style={{
      width: size, height: size, borderRadius: '50%', overflow: 'hidden', background: '#dfe7ea',
      border: `${Math.max(5, size / 40)}px solid ${tono(color)}`, flexShrink: 0, position: 'relative',
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

const tarjeta: React.CSSProperties = {background: TARJETA, border: `2px solid ${BORDE}`, borderRadius: 30};

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
      <div style={{position: 'absolute', top: p.titulo ? 310 : 230, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        <div style={entrada(t, e.ini, 0.3, 0)}>
          <Foto id={p.athlete_id} color={p.color} size={440} />
        </div>
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 290, lineHeight: 1, color: TINTA, marginTop: -40, transform: `scale(${golpe})`, WebkitTextStroke: `14px ${FONDO}`, paintOrder: 'stroke fill', letterSpacing: -6}}>
          {valor}
        </div>
        <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 58, color: MENTA, letterSpacing: 3, marginTop: 4, ...entrada(t, fin - 0.2)}}>{p.etiqueta}</div>
        <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 36, color: GRIS, marginTop: 12, textTransform: 'uppercase', letterSpacing: 1, ...entrada(t, fin)}}>{p.sub}</div>
        {p.pie ? (
          <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 44, color: TINTA, marginTop: 16, ...entrada(t, e.cues.promedio ?? fin + 0.6)}}>{p.pie}</div>
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
  const cols = 40;
  const celda = 22;
  const ini = e.cues.cuenta ?? e.ini + 0.5;
  const k = interpolate(t, [e.ini + 0.3, ini + 3.2], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const n = Math.floor(k * p.muestra.length);
  const total = p.victorias.home + p.victorias.away;
  const parteAway = p.victorias.away / total;
  const ver = e.cues.veredicto ?? e.ini + e.dur - 1.5;
  const lado = (eq: Equipo, v: number, izq: boolean) => (
    <div style={{display: 'flex', alignItems: 'center', gap: 20, flexDirection: izq ? 'row' : 'row-reverse'}}>
      <Ficha abbr={eq.abbr} size={124} />
      <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 92, color: tono(eq.color), lineHeight: 1, letterSpacing: -2}}>{miles(v * k)}</div>
    </div>
  );
  return (
    <AbsoluteFill>
      <Titulo>{p.titulo}</Titulo>
      <div style={{position: 'absolute', top: 320, left: (1080 - cols * (celda + 3)) / 2, width: cols * (celda + 3), display: 'flex', flexWrap: 'wrap', gap: 3}}>
        {p.muestra.split('').map((c: string, i: number) => (
          <div key={i} style={{width: celda, height: celda, borderRadius: 5, background: i < n ? (c === 'h' ? tono(home.color) : c === 'a' ? tono(away.color) : GRIS) : APAGADO}} />
        ))}
      </div>
      <div style={{position: 'absolute', top: 990, left: 50, right: 50, display: 'flex', justifyContent: 'space-between'}}>
        {lado(away, p.victorias.away, true)}
        {lado(home, p.victorias.home, false)}
      </div>
      <div style={{position: 'absolute', top: 1150, left: 60, right: 60, height: 26, borderRadius: 13, overflow: 'hidden', background: APAGADO, display: 'flex'}}>
        <div style={{width: `${parteAway * 100 * k}%`, background: tono(away.color)}} />
        <div style={{flex: 1}} />
        <div style={{width: `${(1 - parteAway) * 100 * k}%`, background: tono(home.color)}} />
      </div>
      <div style={{position: 'absolute', top: 1215, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 62, textTransform: 'uppercase', color: MENTA, ...entrada(t, ver - 0.1)}}>{p.veredicto}</div>
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

const Medidor: React.FC<{pct: number; color: string}> = ({pct, color}) => {
  const r = 120;
  const largo = 2 * Math.PI * r;
  return (
    <div style={{position: 'relative', width: 300, height: 300}}>
      <svg width={300} height={300} style={{transform: 'rotate(-90deg)'}}>
        <circle cx={150} cy={150} r={r} fill="none" stroke={APAGADO} strokeWidth={34} />
        <circle cx={150} cy={150} r={r} fill="none" stroke={color} strokeWidth={34} strokeLinecap="round" strokeDasharray={`${(pct / 100) * largo} ${largo}`} />
      </svg>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 76, color: TINTA}}>{Math.round(pct)}%</div>
    </div>
  );
};

const Decide: React.FC<{e: Escena}> = ({e}) => {
  const t = useT();
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

const Marca: React.FC<{size: number}> = ({size}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: size * 0.28}}>
    <div style={{width: size, height: size, borderRadius: size * 0.28, background: '#173e2a', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Arial, sans-serif', fontWeight: 700, fontStyle: 'italic', fontSize: size * 0.82, color: '#c5efa9', lineHeight: 1, paddingBottom: size * 0.1}}>e</div>
    <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: size * 0.62, color: TINTA, letterSpacing: -1}}>edgebook</div>
  </div>
);

const Cierre: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const late = 1 + 0.03 * Math.sin((t - e.ini) * 5);
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', top: 230, left: 40, right: 40, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 112, color: TINTA, lineHeight: 1.05, whiteSpace: 'pre-line', letterSpacing: -3}}>{e.props.titulo}</div>
      <div style={{position: 'absolute', top: 540, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 44}}>
        <Ficha abbr={d.equipos.away.abbr} size={320} style={{transform: `scale(${late})`}} />
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 70, color: MENTA}}>VS</div>
        <Ficha abbr={d.equipos.home.abbr} size={320} style={{transform: `scale(${2 - late})`}} />
      </div>
      <div style={{position: 'absolute', top: 940, left: 0, right: 0, textAlign: 'center', ...entrada(t, (e.cues.comenta ?? e.ini + 2) - 0.1)}}>
        <div style={{fontFamily: TITULAR, fontWeight: 800, fontSize: 72, color: MENTA}}>{e.props.linea1}</div>
        <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 44, color: GRIS, letterSpacing: 3, marginTop: 10}}>{e.props.linea2}</div>
      </div>
      <div style={{position: 'absolute', top: 1180, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, ...entrada(t, e.ini + 0.4)}}>
        <Marca size={96} />
        <div style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 34, color: GRIS, letterSpacing: 2}}>{e.props.lema ?? 'Research antes que ruido'}</div>
      </div>
    </AbsoluteFill>
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
        <span style={{fontFamily: TEXTO, fontWeight: 500, fontSize: 30, color: GRIS, letterSpacing: 1}}>{miles(d.simulaciones)} SIMS · {d.fecha}</span>
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
    <div style={{position: 'absolute', top: 1450, left: 30, right: 30, textAlign: 'center', fontFamily: TITULAR, fontWeight: 800, fontSize: 66, textTransform: 'uppercase', lineHeight: 1.1, letterSpacing: -1}}>
      {g.map((p, i) => {
        const sonando = t >= p.ini - 0.04 && t <= p.fin + 0.05;
        return (
          <span key={i} style={{color: sonando ? MENTA : TINTA, opacity: t >= p.ini - 0.04 ? 1 : 0.25, marginRight: i < g.length - 1 ? 18 : 0}}>{p.texto}</span>
        );
      })}
    </div>
  );
};

const ESCENAS: Record<string, React.FC<{e: Escena; d: Datos}>> = {
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
      <Cabecera d={d} cinta={resultado ? resultado.ini : Infinity} fin={cierre.ini} />
      <Subtitulos d={d} />
    </AbsoluteFill>
  );
};
