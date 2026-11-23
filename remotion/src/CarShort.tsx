import React from 'react';
import {AbsoluteFill, Composition, Img, registerRoot, useCurrentFrame} from 'remotion';
import {FlipClock, Tag} from './FlipClock';
import {End, Stat} from './Short';
import {DISPLAY, INK, PAPER, TEXT, back, clamp} from './theme';

export type CarFrame = {
  phase: 'drive' | 'hold' | 'real' | 'black' | 'end';
  local: number;
  image?: string;
  kmh: number;
  initial: number;
  g: number | null;
  slow: number;
  since: number;
  contactFrame: number;
  cabinCm: number;
};
type Props = {frames: CarFrame[]; base: string; ui: boolean; maxSpeed: number};
const scale = .7;
const label = {fontFamily: TEXT, fontWeight: 800, color: PAPER, lineHeight: 1, letterSpacing: '-0.02em'} as const;
const shadow = 'drop-shadow(0 2px 5px rgba(0,0,0,.6)) drop-shadow(0 0 22px rgba(0,0,0,.5))';

const CarShort: React.FC<Props> = ({frames,base,ui,maxSpeed}) => {
  const frame = useCurrentFrame();
  const d = frames[frame];
  if (!d || d.phase === 'black') return <AbsoluteFill style={{background: INK}}/>;
  if (d.phase === 'end') return <End k={d.local} numberText={String(maxSpeed)} caption="km/h at impact"/>;
  const values = Array.from({length: 6}, (_,i) =>
    Math.min(9.9999,Math.abs(frames[frame-Math.min(i,d.local)].since)).toFixed(4));
  const contactAge = d.local - d.contactFrame;
  let tag: string | null = null;
  let age = d.local;
  if (d.phase === 'real') tag = 'real speed ▶';
  else if (contactAge >= 0 && contactAge < 18 && d.phase === 'drive') {
    tag = 'wall contact'; age = contactAge;
  } else if (d.local < 20 && d.phase === 'drive') tag = `${d.initial} km/h`;
  const g = d.g === null ? null : Math.abs(d.g);
  return <AbsoluteFill style={{background: INK}}>
    <Img src={base + '/' + d.image} style={{width:'100%',height:'100%',objectFit:'fill'}}/>
    {ui && <AbsoluteFill style={{filter:shadow}}>
      {d.phase === 'hold' ? <div style={{position:'absolute',left:48,top:124}}>
        <div style={{...label,fontSize:42}}>cabin lost</div>
        <div style={{...label,fontFamily:DISPLAY,fontSize:112}}>{d.cabinCm.toFixed(1)} <span style={{fontFamily:TEXT,fontSize:34}}>cm</span></div>
      </div> : <>
        <div style={{position:'absolute',left:48,top:124}}>
          <div style={{...label,fontSize:60*scale,marginBottom:22*scale}}>{d.since < 0 ? 'impact in' : 'since impact'}</div>
          <FlipClock values={values} h={156*scale}/>
        </div>
        <div style={{position:'absolute',right:44,top:124+238*scale-(152*scale+8),display:'flex',gap:34*scale,alignItems:'flex-end'}}>
          <Stat s={scale} name="speed" value={String(Math.round(d.kmh))} unit="km/h"/>
          <Stat s={scale} name="g-force" value={g === null ? '–' : g < 9.95 ? g.toFixed(1) : String(Math.round(g))} unit="g" hot={g !== null && g >= 30}/>
          <Stat s={scale} name="slow-mo" value={`${Math.round(d.slow)}×`}/>
        </div>
      </>}
      {tag && <div style={{position:'absolute',right:44,top:312,transformOrigin:'100% 50%',transform:`scale(${scale*back(Math.min(1,(age+1)/6))}) rotate(-2deg)`,
        opacity:d.phase==='real'?1:clamp((19-age)/5)}}>
        <Tag size={56}>{tag}</Tag>
      </div>}
    </AbsoluteFill>}
  </AbsoluteFill>;
};

registerRoot(() => <Composition id="CarShort" component={CarShort} fps={30} width={1080} height={1920}
  durationInFrames={1} defaultProps={{frames:[] as CarFrame[],base:'',ui:true,maxSpeed:0}}
  calculateMetadata={({props})=>({durationInFrames:Math.max(1,props.frames.length)})}/>);
