export type Palabra = {texto: string; ini: number; fin: number};
export type Equipo = {abbr: string; apodo: string; ciudad: string; color: string; color2: string};
export type Escena = {
  tipo: string;
  props: any;
  ini: number;
  dur: number;
  palabras: Palabra[];
  cues: Record<string, number>;
};
export type Datos = {
  game_id: number;
  marca: string;
  simulaciones: number;
  fecha: string;
  fps: number;
  duracion: number;
  equipos: {home: Equipo; away: Equipo};
  cinta: {gana: string; por: number}[];
  escenas: Escena[];
};
