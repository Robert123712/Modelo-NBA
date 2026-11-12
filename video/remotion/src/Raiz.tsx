import {Composition} from 'remotion';
import datos from './datos.json';
import {Partido} from './Partido';
import type {Datos} from './tipos';

// Medio segundo de cola para que el cierre no se corte en seco.
const COLA = 0.5;

export const Raiz = () => (
  <Composition
    id="Partido"
    component={Partido}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={datos as unknown as Datos}
    calculateMetadata={({props}) => ({
      fps: props.fps,
      durationInFrames: Math.ceil((props.duracion + COLA) * props.fps),
    })}
  />
);
