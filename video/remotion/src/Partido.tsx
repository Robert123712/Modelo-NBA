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

const FONDO = '#F4F0E8';
const TINTA = '#161616';
const ROJO = '#D0103A';
const GRIS = '#8B8578';
const VERDE = '#1E9E57';
const TITULAR = 'Anton, sans-serif';
const TEXTO = "'Barlow Condensed', sans-serif";

const fuentes = `
@font-face { font-family: 'Anton'; src: url(${staticFile('fuentes/Anton.woff2')}) format('woff2'); }
@font-face { font-family: 'Barlow Condensed'; font-weight: 600; src: url(${staticFile('fuentes/BarlowCondensed-600.woff2')}) format('woff2'); }
@font-face { font-family: 'Barlow Condensed'; font-weight: 700; src: url(${staticFile('fuentes/BarlowCondensed-700.woff2')}) format('woff2'); }
`;

const miles = (n: number) => Math.round(n).toLocaleString('en-US');
// La liga decide de que carpeta salen fotos y logos; la fija `Partido` al empezar.
let LIGA = 'nba';
const foto = (id: number) => staticFile(`jugadores/${LIGA}/${id}.png`);
const logo = (abbr: string) => staticFile(`logos/${LIGA}/${abbr}.png`);

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

const Titulo: React.FC<{children: React.ReactNode; color?: string; top?: number; size?: number}> = ({
  children,
  color = ROJO,
  top = 150,
  size = 104,
}) => (
  <div
    style={{
      position: 'absolute', top, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR,
      fontSize: size, color, textTransform: 'uppercase', lineHeight: 1,
    }}
  >
    {children}
  </div>
);

const Foto: React.FC<{id: number; color: string; size: number}> = ({id, color, size}) => (
  <div
    style={{
      width: size, height: size, borderRadius: '50%', overflow: 'hidden', background: '#E6DFD2',
      border: `${Math.max(4, size / 50)}px solid ${color}`, flexShrink: 0, position: 'relative',
    }}
  >
    <Img
      src={foto(id)}
      style={{position: 'absolute', width: '138%', left: '-19%', top: '4%'}}
    />
  </div>
);

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
      <div style={{position: 'absolute', top: p.titulo ? 300 : 230, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        <div style={entrada(t, e.ini, 0.3, 0)}>
          <Foto id={p.athlete_id} color={p.color} size={470} />
        </div>
        <div style={{fontFamily: TITULAR, fontSize: 380, lineHeight: 0.95, color: p.color, marginTop: -70, transform: `scale(${golpe})`, textShadow: `0 0 0 ${FONDO}`, WebkitTextStroke: `10px ${FONDO}`, paintOrder: 'stroke fill'}}>
          {valor}
        </div>
        <div style={{fontFamily: TITULAR, fontSize: 76, color: TINTA, marginTop: 6, ...entrada(t, fin - 0.2)}}>{p.etiqueta}</div>
        <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 40, color: GRIS, marginTop: 10, textTransform: 'uppercase', letterSpacing: 1, ...entrada(t, fin)}}>{p.sub}</div>
        {p.pie ? (
          <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 46, color: TINTA, marginTop: 14, ...entrada(t, e.cues.promedio ?? fin + 0.6)}}>{p.pie}</div>
        ) : null}
      </div>
      {p.remate && sello ? (
        <div
          style={{
            position: 'absolute', top: 1215, left: 0, right: 0, display: 'flex', justifyContent: 'center',
            opacity: s, transform: `rotate(-8deg) scale(${2.2 - 1.2 * s})`,
          }}
        >
          <div style={{fontFamily: TITULAR, fontSize: 120, color: '#fff', background: TINTA, padding: '6px 40px', border: `8px solid ${FONDO}`}}>{p.remate}</div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const TituloEscena: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const n = Math.round(d.simulaciones * avance(t, e.ini + 0.9, 1.6));
  return (
    <AbsoluteFill>
      <Titulo color={TINTA} top={210} size={170}>{e.props.titulo}</Titulo>
      <div style={{position: 'absolute', top: 470, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 50}}>
        <Img src={logo(d.equipos.away.abbr)} style={{width: 330, ...entrada(t, e.ini + 0.1, 0.35, 0), transform: `translateX(${(1 - avance(t, e.ini + 0.1)) * -200}px)`}} />
        <div style={{fontFamily: TITULAR, fontSize: 90, color: ROJO}}>@</div>
        <Img src={logo(d.equipos.home.abbr)} style={{width: 330, opacity: avance(t, e.ini + 0.1), transform: `translateX(${(1 - avance(t, e.ini + 0.1)) * 200}px)`}} />
      </div>
      <div style={{position: 'absolute', top: 850, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontSize: 230, color: ROJO, lineHeight: 1}}>{miles(n)}</div>
      <div style={{position: 'absolute', top: 1090, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontSize: 96, color: TINTA}}>VECES</div>
    </AbsoluteFill>
  );
};

/** Orden fijo y revuelto de los fallos, para que no queden todos al final. */
const esFallo = (i: number, total: number, fallos: number) => {
  const paso = total / Math.max(fallos, 1);
  return fallos > 0 && Math.floor((i + paso / 2) / paso) !== Math.floor((i + paso / 2 - 1) / paso) && i < total;
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
  let vistosFallo = 0;
  const puntos = Array.from({length: total}, (_, i) => {
    const f = esFallo(i, total, fallos) && vistosFallo < fallos;
    if (f) vistosFallo++;
    return f;
  });
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', top: 170, left: 0, right: 0, textAlign: 'center', fontFamily: TEXTO, fontWeight: 700, fontSize: 54, color: GRIS, letterSpacing: 2}}>NUESTRO MODELO {(d.liga ?? 'nba').toUpperCase()} · ESTA TEMPORADA</div>
      <div style={{position: 'absolute', top: 240, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontSize: 300, lineHeight: 1, color: TINTA}}>
        {Math.round(aciertos * avance(t, cuenta - 1.2, 1.2))}
        <span style={{color: ROJO}}>-</span>
        {Math.round(fallos * avance(t, cuenta - 1.2, 1.2))}
      </div>
      <div style={{position: 'absolute', top: 600, left: (1080 - cols * (lado + 10)) / 2, width: cols * (lado + 10), display: 'flex', flexWrap: 'wrap', gap: 10}}>
        {puntos.map((f, i) => {
          const visto = i / total <= k;
          return (
            <div key={i} style={{width: lado, height: lado, borderRadius: 10, background: visto ? (f ? ROJO : VERDE) : '#E3DCCD', color: '#fff', fontFamily: TEXTO, fontWeight: 700, fontSize: lado * 0.72, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
              {visto ? (f ? '✕' : '✓') : ''}
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', top: 1200, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontSize: 70, color: TINTA, ...entrada(t, cuenta + 0.3)}}>
        <span style={{color: VERDE}}>{pct}%</span> DE ACIERTO AL GANADOR
      </div>
    </AbsoluteFill>
  );
};

const Resultado: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const p = e.props;
  const {home, away} = d.equipos;
  const cols = 40;
  const celda = 23;
  const ini = e.cues.cuenta ?? e.ini + 0.5;
  const k = interpolate(t, [e.ini + 0.3, ini + 3.2], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const n = Math.floor(k * p.muestra.length);
  const total = p.victorias.home + p.victorias.away;
  const parteAway = p.victorias.away / total;
  const ver = e.cues.veredicto ?? e.ini + e.dur - 1.5;
  const lado = (eq: Equipo, v: number, izq: boolean) => (
    <div style={{display: 'flex', alignItems: 'center', gap: 18, flexDirection: izq ? 'row' : 'row-reverse'}}>
      <Img src={logo(eq.abbr)} style={{width: 150}} />
      <div style={{fontFamily: TITULAR, fontSize: 130, color: eq.color, lineHeight: 1}}>{miles(v * k)}</div>
    </div>
  );
  return (
    <AbsoluteFill>
      <Titulo color={TINTA} top={170} size={92}>{p.titulo}</Titulo>
      <div style={{position: 'absolute', top: 320, left: (1080 - cols * (celda + 2)) / 2, width: cols * (celda + 2), display: 'flex', flexWrap: 'wrap', gap: 2}}>
        {p.muestra.split('').map((c: string, i: number) => (
          <div key={i} style={{width: celda, height: celda, borderRadius: 4, background: i < n ? (c === 'h' ? home.color : c === 'a' ? away.color : GRIS) : '#E6DFD2'}} />
        ))}
      </div>
      <div style={{position: 'absolute', top: 990, left: 50, right: 50, display: 'flex', justifyContent: 'space-between'}}>
        {lado(away, p.victorias.away, true)}
        {lado(home, p.victorias.home, false)}
      </div>
      <div style={{position: 'absolute', top: 1160, left: 60, right: 60, height: 26, borderRadius: 13, overflow: 'hidden', background: '#E6DFD2', display: 'flex'}}>
        <div style={{width: `${parteAway * 100 * k}%`, background: away.color}} />
        <div style={{flex: 1}} />
        <div style={{width: `${(1 - parteAway) * 100 * k}%`, background: home.color}} />
      </div>
      <div style={{position: 'absolute', top: 1215, left: 0, right: 0, textAlign: 'center', fontFamily: TITULAR, fontSize: 84, textTransform: 'uppercase', color: d.equipos[p.favorito as 'home' | 'away'].color, ...entrada(t, ver - 0.1)}}>{p.veredicto}</div>
    </AbsoluteFill>
  );
};

const Dato: React.FC<{valor: string; etiqueta: string; estilo?: React.CSSProperties}> = ({valor, etiqueta, estilo}) => (
  <div style={{background: '#fff', borderRadius: 18, padding: '18px 34px', textAlign: 'center', boxShadow: '0 4px 0 #E3DCCD', minWidth: 400, ...estilo}}>
    <div style={{fontFamily: TITULAR, fontSize: 120, color: ROJO, lineHeight: 1}}>{valor}</div>
    <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 38, color: TINTA, marginTop: 6, letterSpacing: 1}}>{etiqueta}</div>
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
  const alto = 330;
  return (
    <AbsoluteFill>
      <Titulo>{p.titulo}</Titulo>
      <div style={{position: 'absolute', top: 300, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 30, ...entrada(t, cMarc - 0.2)}}>
        <Img src={logo(away.abbr)} style={{width: 150}} />
        <div style={{fontFamily: TITULAR, fontSize: 150, color: TINTA, lineHeight: 1}}>
          <span style={{color: away.color}}>{p.marcador.away}</span>
          <span style={{color: GRIS, margin: '0 22px'}}>-</span>
          <span style={{color: home.color}}>{p.marcador.home}</span>
        </div>
        <Img src={logo(home.abbr)} style={{width: 150}} />
      </div>
      <div style={{position: 'absolute', top: 470, left: 0, right: 0, textAlign: 'center', fontFamily: TEXTO, fontWeight: 700, fontSize: 36, color: GRIS, letterSpacing: 2, ...entrada(t, cMarc)}}>MARCADOR PROMEDIO</div>
      <div style={{position: 'absolute', top: 560, left: 70, right: 70, height: alto, display: 'flex', alignItems: 'flex-end', gap: 6}}>
        {p.cuentas.map((c: number, i: number) => {
          const centro = p.desde + p.ancho * (i + 0.5);
          const cerrado = Math.abs(centro) <= (p.umbral_cerrado ?? 5);
          const color = centro < 0 ? away.color : centro > 0 ? home.color : GRIS;
          return (
            <div key={i} style={{flex: 1, height: `${(c / max) * 100 * crece}%`, background: color, borderRadius: '6px 6px 0 0', opacity: cerrado ? 1 : 1 - 0.55 * resalta}} />
          );
        })}
      </div>
      <div style={{position: 'absolute', top: 560 + alto + 12, left: 70, right: 70, display: 'flex', justifyContent: 'space-between', fontFamily: TEXTO, fontWeight: 700, fontSize: 34, letterSpacing: 1}}>
        <span style={{color: away.color}}>◀ GANA {away.apodo.toUpperCase()}</span>
        <span style={{color: home.color}}>GANA {home.apodo.toUpperCase()} ▶</span>
      </div>
      <div style={{position: 'absolute', top: 1010, left: 60, right: 60, display: 'flex', justifyContent: 'space-between'}}>
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
      <Titulo top={160} size={92}>{e.props.titulo}</Titulo>
      <div style={{position: 'absolute', top: 320, left: 60, right: 60, display: 'flex', flexDirection: 'column', gap: 36}}>
        {e.props.tarjetas.map((c: any, i: number) => (
          <div key={i} style={{background: '#fff', borderRadius: 24, padding: '30px 36px', display: 'flex', alignItems: 'center', gap: 36, boxShadow: '0 5px 0 #E3DCCD', ...entrada(t, (e.cues[`tarjeta${i}`] ?? e.ini) - 0.15)}}>
            <Foto id={c.athlete_id} color={c.color} size={270} />
            <div>
              <div style={{fontFamily: TITULAR, fontSize: 74, color: TINTA, textTransform: 'uppercase', lineHeight: 1.05}}>{c.jugador}</div>
              {c.lineas.map((l: any, j: number) => (
                <div key={j} style={{marginTop: 10}}>
                  <div style={{fontFamily: TITULAR, fontSize: j === 0 ? 96 : 84, color: c.color, lineHeight: 1}}>{l.valor}</div>
                  <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 32, color: GRIS, letterSpacing: 1}}>{l.etiqueta}</div>
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
        <circle cx={150} cy={150} r={r} fill="none" stroke="#E9E3D6" strokeWidth={34} />
        <circle cx={150} cy={150} r={r} fill="none" stroke={color} strokeWidth={34} strokeLinecap="round" strokeDasharray={`${(pct / 100) * largo} ${largo}`} />
      </svg>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: TITULAR, fontSize: 96, color: TINTA}}>{Math.round(pct)}%</div>
    </div>
  );
};

const Decide: React.FC<{e: Escena}> = ({e}) => {
  const t = useT();
  return (
    <AbsoluteFill>
      <Titulo>{e.props.titulo}</Titulo>
      <div style={{position: 'absolute', top: 330, left: 60, right: 60, display: 'flex', flexDirection: 'column', gap: 40}}>
        {e.props.medidores.map((m: any, i: number) => {
          const sube = e.cues[`sube${i}`] ?? e.ini + 3;
          const pct = m.base + (m.pct - m.base) * avance(t, sube - 0.5, 0.9);
          return (
            <div key={i} style={{background: '#fff', borderRadius: 24, border: `5px solid ${m.color}`, padding: '28px 40px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', ...entrada(t, (e.cues[`medidor${i}`] ?? e.ini) - 0.15)}}>
              <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: 400}}>
                <Foto id={m.athlete_id} color={m.color} size={210} />
                <div style={{fontFamily: TITULAR, fontSize: 70, color: TINTA, textTransform: 'uppercase', marginTop: 8, lineHeight: 1.05}}>{m.jugador}</div>
                <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 44, color: m.color}}>{m.evento}</div>
              </div>
              <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
                <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 36, color: GRIS, letterSpacing: 1, marginBottom: 6}}>{m.equipo.toUpperCase()}</div>
                <Medidor pct={pct} color={m.color} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Cierre: React.FC<{e: Escena; d: Datos}> = ({e, d}) => {
  const t = useT();
  const late = 1 + 0.03 * Math.sin((t - e.ini) * 5);
  return (
    <AbsoluteFill>
      <Titulo top={260} size={150}>{e.props.titulo}</Titulo>
      <div style={{position: 'absolute', top: 520, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 50}}>
        <Img src={logo(d.equipos.away.abbr)} style={{width: 340, transform: `scale(${late})`}} />
        <div style={{fontFamily: TITULAR, fontSize: 90, color: ROJO}}>VS</div>
        <Img src={logo(d.equipos.home.abbr)} style={{width: 340, transform: `scale(${2 - late})`}} />
      </div>
      <div style={{position: 'absolute', top: 960, left: 0, right: 0, textAlign: 'center', ...entrada(t, (e.cues.comenta ?? e.ini + 2) - 0.1)}}>
        <div style={{fontFamily: TITULAR, fontSize: 96, color: TINTA}}>{e.props.linea1}</div>
        <div style={{fontFamily: TEXTO, fontWeight: 700, fontSize: 52, color: GRIS, letterSpacing: 2, marginTop: 6}}>{e.props.linea2}</div>
      </div>
    </AbsoluteFill>
  );
};

// ---- Capas fijas -------------------------------------------------------------

/** Marca, fecha y la cinta con el resultado de cada simulacion. */
const Cinta: React.FC<{d: Datos; desde: number}> = ({d, desde}) => {
  const t = useT();
  if (t < desde) return null;
  const texto = d.cinta.map((c, i) => `SIM #${i + 1}  ${c.gana} +${c.por}`).join('   •   ');
  return (
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, opacity: avance(t, desde, 0.4)}}>
      <div style={{display: 'flex', justifyContent: 'space-between', padding: '44px 40px 8px', fontFamily: TEXTO, fontWeight: 700, fontSize: 30, color: GRIS, letterSpacing: 1}}>
        <span>@{d.marca}</span>
        <span>{miles(d.simulaciones)} SIMS · {d.fecha}</span>
      </div>
      <div style={{background: '#E9E3D6', padding: '6px 0', overflow: 'hidden', whiteSpace: 'nowrap'}}>
        <div style={{fontFamily: TEXTO, fontWeight: 600, fontSize: 28, color: '#6F695D', transform: `translateX(${1080 - (t - desde) * 150}px)`}}>{texto}</div>
      </div>
    </div>
  );
};

/** Subtitulos: frases cortas; la palabra aun no dicha espera en gris. */
const trozar = (palabras: Palabra[]) => {
  const grupos: Palabra[][] = [];
  let actual: Palabra[] = [];
  for (const p of palabras) {
    const letras = actual.reduce((s, x) => s + x.texto.length + 1, 0);
    if (actual.length && (actual.length >= 3 || letras + p.texto.length > 17)) {
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
    <div style={{position: 'absolute', top: 1440, left: 40, right: 40, textAlign: 'center', fontFamily: TITULAR, fontSize: 92, textTransform: 'uppercase', lineHeight: 1.05}}>
      {g.map((p, i) => (
        <span key={i} style={{color: TINTA, opacity: t >= p.ini - 0.04 ? 1 : 0.22, marginRight: i < g.length - 1 ? 22 : 0}}>{p.texto}</span>
      ))}
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
  // La cinta aparece cuando empieza a hablarse del resultado.
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
      {resultado && cierre.ini > resultado.ini ? (
        <Sequence from={cuadro(resultado.ini)} durationInFrames={cuadro(cierre.ini) - cuadro(resultado.ini)}>
          <Reloj.Provider value={resultado.ini}>
            <Cinta d={d} desde={resultado.ini} />
          </Reloj.Provider>
        </Sequence>
      ) : null}
      <Subtitulos d={d} />
    </AbsoluteFill>
  );
};
