import React from 'react';
import {Composition} from 'remotion';
import {EndCard} from './EndCard';
import {Episode} from './Episode';
import {TOTAL} from './timeline';

export const Root: React.FC = () => (
	<>
		<Composition id="Episode" component={Episode} durationInFrames={TOTAL} fps={30} width={1080} height={1920} defaultProps={{frameBase: 'http://127.0.0.1:8124', ui: true}} />
		<Composition id="EndCard" component={EndCard} durationInFrames={180} fps={30} width={1080} height={1920} defaultProps={{clockBase: 'http://127.0.0.1:8124/s20'}} />
	</>
);
