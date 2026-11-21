import React from 'react';
import {Composition} from 'remotion';
import {Short} from './Short';
import data from './data.json';

export const Root: React.FC = () => (
	<Composition id="Short" component={Short} durationInFrames={data.frames.length} fps={30} width={1080} height={1920} defaultProps={{frameBase: 'http://127.0.0.1:8123', ui: true}} />
);
