(() => {
"use strict";
// DesignQR city correspondence, MIT, commit a75f5749a8abef289899b1b87898af7124b054a4. See bundled license.
const mix = (a,b,t) => a+(b-a)*t;
function ease(t, from=0, to=1) {
  const v=Math.max(0,Math.min(1,(t-from)/(to-from)));
  return v*v*(3-2*v);
}
const faces=[
  [[0,3,2,1],.55],[[4,5,6,7],1.16],[[0,4,5,1],1.0],
  [[1,5,6,2],.74],[[2,6,7,3],.59],[[3,7,4,0],.91]
];
const brickFaces=[
  faces[0],[[4,5,6,7],.89],[[0,1,5,4],1.13],
  [[1,2,6,5],.73],[[2,3,7,6],.84],[[3,0,4,7],.94]
];
const flare=[255,231,189];
const turn = 2 * Math.PI;
const stars = Array.from({length: 100}, (_, i) => ({
  x: ((i * 173 + 179) % 997) / 997,
  y: ((i * i * 73 + 19) % 991) / 991,
  brightness: .16 + ((i * 43) % 65) / 100,
}));

function spaceBackdrop(ctx, width, height, progress) {
  const opacity = 1 - ease(progress, .14, .66);
  const light = ctx.createRadialGradient(
    width * .47, height * .45, 0, width * .47, height * .45, width * .59
  );
  light.addColorStop(0, 'rgba(38,63,93,.87)');
  light.addColorStop(.53, 'rgba(23,37,65,.55)');
  light.addColorStop(1, 'rgba(8,13,25,0)');
  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.fillStyle = light;
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#b8d6ff';
  for (const [i, star] of stars.entries()) {
    ctx.globalAlpha = opacity * star.brightness;
    const size = Math.max(.6, width * (i % 9 ? .0012 : .00225));
    ctx.fillRect(width * star.x, height * star.y, size, size);
  }
  ctx.restore();
}
const effectStyles = {
  nebula: {colors:['#ffcb83','#e79758','#dfafed'], radius:.61, tilt:.57, rate:.44, count:78, orbit:true},
  rings: {colors:['#ffe8ad','#ffae5e','#b5cafa'], radius:.59, tilt:.27, rate:.39, count:71, orbit:true},
  bricks: {colors:['#dc2642','#2765cc','#d49215'], rate:1.35, count:22},
  petals: {colors:['#e32f62','#ff86ab','#5278cf'], rate:.90, count:17},
  'flight-grid': {rate:1.35,count:18},
  'file-stack': {rate:1.15,count:0},
  'print-development': {rate:1,count:0},
  'crank-pixels': {rate:.6,count:0},
  'brand-sheen': {colors:['#dff7ff','#718ca1','#67b8d4'], rate:.84, count:12},
  'product-studio': {colors:['#e6fbff','#7299b5','#61b4d4'], rate:1.02, count:12}
};

function projectScene(width,height,scale,{yaw,pitch,shift=[0,0]},flatten=0) {
  const c=Math.cos(yaw*(1-flatten)), s=Math.sin(yaw*(1-flatten));
  const cp=Math.cos(pitch*(1-flatten)), sp=Math.sin(pitch*(1-flatten));
  return (x,y,z) => {
    const ax=x*c+y*s, ay=y*c-x*s;
    const depth=ay*cp+z*sp;
    const perspective=1/(1-depth*.53*(1-flatten));
    return [width*(.5+shift[0]*(1-flatten))+ax*scale*perspective,
      height*(.5+shift[1]*(1-flatten))+(z*cp-ay*sp)*scale*perspective,depth];
  };
}

function layerSlide(clock, period) {
  const time=clock % period;
  const smooth=(value,start,end)=>{
    const u=Math.max(0,Math.min(1,(value-start)/(end-start)));
    return u*u*u*(10+u*(-15+6*u));
  };
  const beat=(start,open,close,end)=>smooth(time,start,open)*(1-smooth(time,close,end));
  return {
    near:beat(.04,.60,.88,1.82),
    far:beat(.12,.77,1.05,2.19),
    side:beat(.05,.70,1.01,2.35),
  };
}

function stagedView(orbit,composition,clock) {
  const [,x,y]=composition.frame;
  const [yaw,pitch,heave,period]=composition.camera;
  if (composition.motion==='layer-slide') {
    const {side}=layerSlide(clock,period);
    return {yaw:orbit.yaw+yaw*side,pitch:orbit.pitch+pitch*side,shift:[x-.035*side,y]};
  }
  const beat=clock*turn/period;
  const rise=.5-.5*Math.cos(beat);
  return {yaw:orbit.yaw+yaw*Math.sin(beat)*(.58+.42*rise),pitch:orbit.pitch+pitch*Math.sin(beat*2),
    shift:[x+heave*.54*Math.sin(beat),y-heave*(rise-.24)]};
}

function stageGlow(ctx,x,y,radius,hot,warm,clear) {
  const glow=ctx.createRadialGradient(x,y,0,x,y,radius);
  glow.addColorStop(0,hot); glow.addColorStop(.47,warm); glow.addColorStop(1,clear);
  ctx.fillStyle=glow;
  ctx.fillRect(0,0,ctx.canvas.width,ctx.canvas.height);
}

function paintSky(ctx,project,beat,front) {
  const {width:w,height:h}=ctx.canvas;
  if (!front) {
    const wash=ctx.createLinearGradient(0,0,w*.37,h);
    wash.addColorStop(0,'#174b64');
    wash.addColorStop(.59,'#377e86');
    wash.addColorStop(1,'#cd9d65');
    ctx.fillStyle=wash;
    ctx.fillRect(0,0,w,h);
    stageGlow(ctx,w*.80,h*.41,w*.74,'#ffe2a885','#e9b7813c','#ffdfac00');
    for (let ridge=0;ridge<3;ridge++) {
      const level=.65+.096*ridge;
      const shift=Math.sin(beat)*(.035+.025*ridge);
      const mist=ctx.createLinearGradient(0,h*(level-.11),w*.24,h);
      mist.addColorStop(0,['#78aba7','#488b8f','#306b71'][ridge]);
      mist.addColorStop(1,['#4f858c','#306d77','#1b4956'][ridge]);
      ctx.fillStyle=mist;
      ctx.beginPath(); ctx.moveTo(0,h*(level-.06));
      for (let i=0;i<=40;i++) {
        const x=i/40;
        const peaks=.07*Math.sin(x*12+ridge*2.18+shift*10)+.021*Math.cos(x*35-ridge);
        ctx.lineTo(w*x,h*(level+peaks));
      }
      ctx.lineTo(w,h); ctx.lineTo(0,h); ctx.fill();
    }
  }
  for (let i=front ? 6:0;i<(front ? 9:6);i++) {
    const behind=front ? .35:-.34;
    const z=front ? .38+i*.034:-.41+i*.055;
    const x=Math.sin(i*2.37+beat)*(.54+.013*i);
    const [px,py]=project(x,behind,z+.022*Math.sin(2*beat+i));
    const size=w*(front ? .20:.17);
    const vapor=ctx.createRadialGradient(px,py,0,px,py,size);
    vapor.addColorStop(0,front ? '#fff3d469':'#d6efe58a');
    vapor.addColorStop(.53,front ? '#b1ddce2b':'#cae3c53f');
    vapor.addColorStop(1,'#d6efe500');
    ctx.save(); ctx.translate(px,py); ctx.scale(1,.29);
    ctx.translate(-px,-py); ctx.fillStyle=vapor;
    ctx.fillRect(px-size,py-size,2*size,2*size); ctx.restore();
  }
}

function paintLightbox(ctx,beat,front) {
  const {width:w,height:h}=ctx.canvas;
  if (!front) {
    const wall=ctx.createLinearGradient(0,0,w,h);
    wall.addColorStop(0,'#475d6d'); wall.addColorStop(.38,'#253845'); wall.addColorStop(1,'#101820');
    ctx.fillStyle=wall; ctx.fillRect(0,0,w,h);
    stageGlow(ctx,w*.29,h*.24,w*.73,'#bbd7e05e','#688b9b38','#25384500');
    for (let i=0;i<4;i++) {
      const x=(.05+i*.255+.071*Math.sin(beat))*w;
      const panel=ctx.createLinearGradient(x,h*.36,x+w*.18,h*.45);
      panel.addColorStop(0,'#b7d8ec00'); panel.addColorStop(.85,'#b7d8ec19'); panel.addColorStop(1,'#c8e2e236');
      ctx.fillStyle=panel; ctx.beginPath(); ctx.moveTo(x-w*.2,0);
      ctx.lineTo(x+w*.04,0); ctx.lineTo(x+w*.33,h); ctx.lineTo(x+w*.11,h); ctx.fill();
    }
    ctx.strokeStyle='#bfd2db33'; ctx.lineWidth=w*.002;
    ctx.beginPath(); ctx.moveTo(0,h*.73); ctx.lineTo(w,h*.57); ctx.stroke();
  }
  const x=w*(.48+.48*Math.cos(beat));
  const line=ctx.createLinearGradient(x-w*.15,0,x+w*.15,0);
  line.addColorStop(0,'#c4e7fe00'); line.addColorStop(.69,'#d6efff00');
  line.addColorStop(.75,front ? '#d6efff1d':'#d6efff71');
  line.addColorStop(1,'#c4e7fe00');
  ctx.save(); ctx.transform(1,0,.35,1,0,0); ctx.fillStyle=line;
  ctx.fillRect(x-w*.15,0,w*.30,h); ctx.restore();
  if (front) {
    const bottom=ctx.createLinearGradient(0,h*.85,0,h);
    bottom.addColorStop(0,'#c4e7fe00'); bottom.addColorStop(1,'#c4e7fe17');
    ctx.fillStyle=bottom; ctx.fillRect(0,h*.85,w,h*.15);
  }
}

function paintDawn(ctx,project,beat,front) {
  const {width:w,height:h}=ctx.canvas;
  const shimmer=.5-.5*Math.cos(beat);
  const layerAlpha=ctx.globalAlpha;
  if (!front) {
    const glow=ctx.createLinearGradient(0,h,w,h*.09);
    glow.addColorStop(0,'#120e2b'); glow.addColorStop(.58,'#312056'); glow.addColorStop(1,'#631f56');
    ctx.fillStyle=glow; ctx.fillRect(0,0,w,h);
    stageGlow(ctx,w*(.73+.04*Math.sin(beat)),h*.24,w*.76,'#ffb57651','#d5638a32','#d5638a00');
    for (let i=0;i<6;i++) {
      const x=(.78+i*.035+.058*Math.sin(beat))*w;
      const y=(.52+i*.072)*h;
      const ray=ctx.createLinearGradient(x,h*.12,w*.01,y);
      ray.addColorStop(0,'#ffa76c49'); ray.addColorStop(.42,'#ee6c6029'); ray.addColorStop(1,'#b24fee00');
      ctx.fillStyle=ray; ctx.beginPath(); ctx.moveTo(w*.98,h*.07);
      ctx.lineTo(x,h*.20); ctx.lineTo(w*.03,y); ctx.lineTo(-w*.05,y+h*.028); ctx.fill();
    }
  }
  for (let i=front ? 20:0;i<(front ? 32:20);i++) {
    const star=stars[i];
    const a=beat+star.x*turn;
    const radius=(.30+.57*star.y)*(.87+.20*Math.sin(a*2));
    const x=Math.cos(a)*radius, z=Math.sin(a)*radius*.79+.045;
    const [px,py]=project(x,front ? .23:-.38,z);
    const [nx,ny]=project(x+.033,front ? .23:-.38,z-.045);
    const streak=ctx.createLinearGradient(px,py,nx,ny);
    streak.addColorStop(0,front ? '#ffd7aa9a':'#ffb9a443'); streak.addColorStop(1,'#ffd7aa00');
    ctx.strokeStyle=streak; ctx.lineWidth=w*(.001+star.brightness*.003);
    ctx.globalAlpha=layerAlpha*(.87+.13*shimmer);
    ctx.beginPath(); ctx.moveTo(px,py); ctx.lineTo(nx,ny); ctx.stroke();
  }
}

function paintGallery(ctx,beat,front) {
  const {width:w,height:h}=ctx.canvas;
  const x=w*(.5+.024*Math.sin(beat));
  const y=h*.811;
  if (!front) {
    const room=ctx.createLinearGradient(0,0,w*.70,h);
    room.addColorStop(0,'#122d40'); room.addColorStop(.56,'#26586b'); room.addColorStop(1,'#123144');
    ctx.fillStyle=room; ctx.fillRect(0,0,w,h);
    stageGlow(ctx,w*.39,h*.27,w*.71,'#a2dce075','#81d4d94c','#81d4d900');
    ctx.strokeStyle='#a7e0e154'; ctx.lineWidth=w*.002;
    for (const radius of [.38,.46,.53]) {
      ctx.beginPath();
      ctx.ellipse(x,h*.435,w*radius,h*(radius+.045),-.12,3.44+beat*.037,6.41+beat*.037);
      ctx.stroke();
    }
    const dais=ctx.createLinearGradient(x-w*.28,y,x+w*.27,y+h*.09);
    dais.addColorStop(0,'#2b6174'); dais.addColorStop(.55,'#1d4357'); dais.addColorStop(1,'#102c42');
    ctx.fillStyle=dais;
    ctx.beginPath(); ctx.ellipse(x,y+h*.042,w*.323,h*.068,0,0,turn); ctx.fill();
    ctx.fillRect(x-w*.323,y,w*.646,h*.042);
    const surface=ctx.createLinearGradient(x,y-h*.067,x,y+h*.07);
    surface.addColorStop(0,'#609cab'); surface.addColorStop(1,'#316478');
    ctx.fillStyle=surface; ctx.strokeStyle='#a0d3dc68';
    ctx.beginPath(); ctx.ellipse(x,y,w*.323,h*.068,0,0,turn); ctx.fill(); ctx.stroke();
    ctx.save(); ctx.translate(x,y); ctx.scale(1,.24);
    const radius=w*.256;
    const shadow=ctx.createRadialGradient(0,0,0,0,0,radius);
    shadow.addColorStop(0,'#142b3ec9'); shadow.addColorStop(1,'#142b3e00');
    ctx.fillStyle=shadow; ctx.fillRect(-radius,-radius,2*radius,2*radius);
    ctx.restore();
  }
  for (let i=front ? 9:0;i<(front ? 15:9);i++) {
    const star=stars[i];
    const angle=star.x*turn+beat*.25;
    const px=x+Math.cos(angle)*w*(.37+.13*star.y);
    const py=h*(.31+.54*star.y)+Math.sin(angle)*h*.085;
    ctx.fillStyle=front ? '#c2edf199':'#b4e7ed56';
    ctx.beginPath(); ctx.arc(px,py,w*(.0015+star.brightness*.0023),0,turn); ctx.fill();
  }
}

function paintStage(ctx,composition,project,clock,p,front) {
  const opacity=1-ease(p,.035,.59);
  if (opacity<=0) return;
  const {width:w,height:h}=ctx.canvas;
  const {environment,hue,accent,background}=composition;
  const rgba=(rgb,a)=>`rgba(${rgb},${a})`;
  const beat=clock*turn/composition.camera[3];
  const slide=composition.motion==='layer-slide';
  const rise=slide ? layerSlide(clock,composition.camera[3]).side :
    .5-.5*Math.cos(beat);
  const lx=w*(.38+(slide ? .13*rise : .22*Math.sin(beat)));
  const ly=h*(.34-(slide ? 0 : .15)*rise);
  ctx.save();
  ctx.globalAlpha=opacity;
  if (environment==='display') {
    if (!front) {
      ctx.fillStyle=rgba(background,1);
      ctx.fillRect(0,0,w,h);
      stageGlow(ctx,lx,ly,w*.86,'#ffffffd9','#ffffff63','#ffffff00');
      const [bottom,clearance]=composition.grounding;
      const [, , heave]=composition.camera;
      const [sx,sy]=project(0,0,bottom+clearance+heave*(rise-.24));
      const radius=Math.min(w,h)*(.31+.05*rise*clearance);
      ctx.translate(sx,sy+h*.009);
      ctx.scale(1,clearance ? .19 : .13);
      const shade=ctx.createRadialGradient(0,0,0,0,0,radius);
      shade.addColorStop(0,rgba([31,31,44],clearance ? .23-.064*rise : .32));
      shade.addColorStop(.42,rgba([31,31,44],clearance ? .12 : .18));
      shade.addColorStop(1,'#1f1f2c00');
      ctx.fillStyle=shade;
      ctx.fillRect(-radius,-radius,2*radius,2*radius);
    }
    ctx.restore();
    return;
  }
  if (environment==='download') {
    if (!front) {
      ctx.fillStyle=rgba(background,1);
      ctx.fillRect(0,0,w,h);
      const glow=ctx.createRadialGradient(lx,ly*.8,0,lx,ly*.8,w*.66);
      glow.addColorStop(0,'#fffafb');
      glow.addColorStop(1,'#fffafb00');
      ctx.fillStyle=glow;
      ctx.fillRect(0,0,w,h);
      const [sx,sy]=project(0,0,.416);
      ctx.translate(sx,sy+h*.012);
      ctx.scale(1,.25);
      const shade=ctx.createRadialGradient(0,0,0,0,0,w*.23);
      shade.addColorStop(0,'#926b8854');
      shade.addColorStop(1,'#926b8800');
      ctx.fillStyle=shade;
      ctx.fillRect(-w*.23,-w*.23,w*.46,w*.46);
    }
    ctx.restore();
    return;
  }
  if (environment==='sky' || environment==='lightbox' || environment==='dawn' || environment==='gallery') {
    if (environment==='sky') paintSky(ctx,project,beat,front);
    else if (environment==='lightbox') paintLightbox(ctx,beat,front);
    else if (environment==='dawn') paintDawn(ctx,project,beat,front);
    else paintGallery(ctx,beat,front);
    ctx.restore();
    return;
  }
  if (!front) {
    ctx.fillStyle=rgba(background,1);
    ctx.fillRect(0,0,w,h);
    const halo=ctx.createRadialGradient(lx,ly,0,lx,ly,w*.83);
    halo.addColorStop(0,rgba(hue,environment==='canopy' ? .57 : .42+.19*rise));
    halo.addColorStop(.38,rgba(accent,.22));
    halo.addColorStop(1,rgba(accent,0));
    ctx.fillStyle=halo;
    ctx.fillRect(0,0,w,h);
  }
  if (environment==='portal') {
    if (!front) {
      const pulse=rise;
      for (let i=0;i<5;i++) {
        const radius=(.29+i*.073)*w;
        ctx.lineWidth=(i===0 ? .005 : .0015)*w;
        const ring=ctx.createLinearGradient(w*.15,h*.18,w*.81,h*.82);
        ring.addColorStop(0,rgba([210,205,255],.43));
        ring.addColorStop(.46,rgba(hue,.14+pulse*.20));
        ring.addColorStop(1,rgba(accent,.025));
        ctx.strokeStyle=ring;
        ctx.beginPath();
        ctx.ellipse(w*.51,h*.43,radius*.98,radius*1.21,-.48,beat+i*.57,beat+i*.57+turn*.82);
        ctx.stroke();
      }
    }
    // Split each orbit at the camera plane so the sweep passes behind and in front of the object.
    for (let lane=0;lane<2;lane++) {
      const tail=(lane===0 ? beat : -beat)+lane*2.23+.5;
      const position=a=>project(Math.cos(a)*(.55+lane*.035),Math.sin(a)*(.47+lane*.027),
        .135+lane*.05+Math.sin(a+.6*lane)*(.16+lane*.031));
      // Group the taper in four strokes to keep the animation on the frame budget.
      for (let band=0;band<4;band++) {
        const strength=(band+1)/4;
        ctx.lineCap='round';
        ctx.beginPath();
        for (let i=0;i<7;i++) {
          const lead=tail+(band*7+i-27)*.082;
          const [x,y,d]=position(lead);
          const [nx,ny,nd]=position(lead+.083);
          if ((d+nd>0)!==front) continue;
          ctx.moveTo(x,y); ctx.lineTo(nx,ny);
        }
        ctx.lineWidth=w*.029*strength;
        ctx.strokeStyle=rgba(hue,strength*.19);
        ctx.stroke();
        ctx.lineWidth=w*.005*(.45+strength);
        ctx.strokeStyle=rgba(lane===1 ? [221,190,255] : [194,224,255],strength*(.53+.44*rise));
        ctx.stroke();
      }
    }
  } else if (environment==='canopy') {
    if (!front) {
      // Soft oblique light filters through the canopy before it reaches the leaves.
      for (let i=0;i<4;i++) {
        const offset=(.09+i*.135)*w+Math.sin(beat+i)*w*.035;
        const ray=ctx.createLinearGradient(offset,-h*.08,offset+w*.33,h*.85);
        ray.addColorStop(0,rgba(hue,.37)); ray.addColorStop(1,rgba(hue,0));
        ctx.fillStyle=ray;
        ctx.beginPath(); ctx.moveTo(offset,-h*.08); ctx.lineTo(offset+w*.05,-h*.08);
        ctx.lineTo(offset+w*.62,h*.9); ctx.lineTo(offset+w*.49,h*.9); ctx.fill();
      }
    }
  } else {
    const belt=.5+.60*Math.sin(beat-.58);
    const level=(belt-.14)*h;
    if (!front) {
      ctx.strokeStyle=rgba(hue,.16);
      ctx.lineWidth=w*.0013;
      for (let i=-3;i<=11;i++) {
        ctx.beginPath(); ctx.moveTo(i*w*.145,0); ctx.lineTo((i-.8)*w*.145,h); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0,i*h*.125); ctx.lineTo(w,(i-.63)*h*.125); ctx.stroke();
      }
    }
    const panel=ctx.createLinearGradient(0,level-h*.052,0,level+h*.054);
    panel.addColorStop(0,rgba(hue,0)); panel.addColorStop(.56,rgba(hue,front ? .14:.4));
    panel.addColorStop(.70,rgba([203,231,255],front ? .46:.83)); panel.addColorStop(1,rgba(hue,0));
    ctx.fillStyle=panel;
    const left=front ? w*.24 : -w*.1, span=front ? w*.68 : w*1.2;
    ctx.save(); ctx.transform(1,-.14,0,1,0,w*.11);
    ctx.fillRect(left,level-h*.052,span,h*.106); ctx.restore();
  }
  for (let i=front?38:0;i<(front?58:38);i++) {
    const star=stars[i];
    const radius=front ? .51+star.y*.19 : .38+star.y*.25;
    const angle=star.x*turn+beat*(front ? 1 : -1);
    const [x,y]=project(Math.sin(angle)*radius,(front ? .18:-.32)+Math.cos(angle)*.19,
      .58-star.brightness*1.04+.13*Math.sin(beat+i));
    const bright=(.2 + .76*Math.sin(beat+i)**2)*star.brightness;
    ctx.fillStyle=rgba(i%4 ? hue : [234,244,255],bright);
    ctx.beginPath();
    const size=w*(front ? .004:.0022)*(star.brightness+.22);
    if (front && environment==='canopy') ctx.ellipse(x,y,size*1.8,size,-angle,0,turn);
    else ctx.arc(x,y,size,0,turn);
    ctx.fill();
  }
  ctx.restore();
}

function studioBackdrop(ctx,kind,opacity,custom) {
  const {width:w,height:h}=ctx.canvas;
  const stops = {
    nebula:['#773b28','#180f19'],
    bricks:['#fff9da','#dfcda5'],
    petals:['#fffafa','#efbbd3'],
    rings:['#4b3040','#101329'],
    'flight-grid':['#163b4d','#040810'],
    'file-stack':['#f5f8ff','#9bb9e7'],
    'print-development':['#feeed5','#b07c64'],
    'crank-pixels':['#ecf3d8','#638279'],
    'service-guide':['#24496b','#050b18'],
    'reception-desk':['#396970','#0b1d29'],
    'living-garden':['#527c6b','#091f24'],
    'handheld-display':['#776244','#241c20'],
    'brand-sheen':['#dce7ec','#839ba8'],
    'product-studio':['#edf9ff','#7695b2']
  };
  const [light, edge] = custom ? custom.map(color=>`rgb(${color})`) : stops[kind];
  const glow = ctx.createRadialGradient(w*.47,h*.40,w*.06,w*.51,h*.46,w*.72);
  glow.addColorStop(0,light);
  glow.addColorStop(1,edge);
  ctx.save();
  ctx.globalAlpha=opacity;
  ctx.fillStyle=glow;
  ctx.fillRect(0,0,w,h);
  if (kind==='print-development') {
    const surface=ctx.createLinearGradient(0,h*.78,0,h);
    surface.addColorStop(0,'#eac9a600');
    surface.addColorStop(.22,'#e2b6947a');
    surface.addColorStop(1,'#85523b80');
    ctx.fillStyle=surface;
    ctx.fillRect(0,h*.78,w,h*.22);
  }
  if (kind==='service-guide') {
    const sidelights=ctx.createLinearGradient(w*.06,h*.02,w*.77,h*.82);
    for (const [offset,color] of [[0,'#ffbc9b25'],[.22,'#ffa7730d'],[.46,'#72e5eb14'],[1,'#04081800']])
      sidelights.addColorStop(offset,color);
    ctx.fillStyle=sidelights;
    ctx.fillRect(0,0,w,h);
  }
  if (kind==='reception-desk') {
    const wash=ctx.createRadialGradient(w*.23,h*.18,w*.035,w*.23,h*.18,w*.62);
    wash.addColorStop(0,'#a6b88131');
    wash.addColorStop(1,'#a6b88100');
    ctx.fillStyle=wash;
    ctx.fillRect(0,0,w,h);
  }
  if (kind==='flight-grid') {
    const haze=ctx.createLinearGradient(0,h*.23,w*.21,h*.75);
    haze.addColorStop(0,'#48b9e500');
    haze.addColorStop(.52,'#44cbe229');
    haze.addColorStop(1,'#44cbe200');
    ctx.fillStyle=haze;
    ctx.fillRect(0,0,w,h);
    for (const star of stars) {
      if (star.y>.56) continue;
      ctx.globalAlpha=opacity*star.brightness*.56;
      ctx.fillStyle='#b3eafb';
      ctx.fillRect(star.x*w,star.y*h,star.brightness*2+.5,1);
    }
  } else if (kind==='petals' || kind==='bricks') {
    // Deliberately irregular spacing keeps the texture separate from the code.
    ctx.fillStyle=kind==='petals'?'rgba(189,53,108,.16)':'rgba(91,73,26,.12)';
    for (const dot of stars) {
      const x=dot.x*w, y=dot.y*h;
      if (Math.abs(x-w*.5)<w*.27 && Math.abs(y-h*.5)<h*.34) continue;
      const size=1+dot.brightness*3;
      ctx.beginPath();
      ctx.arc(x,y,size,0,turn);
      ctx.fill();
    }
  } else if (kind==='brand-sheen' || kind==='product-studio') {
    const grid=w*.055;
    ctx.strokeStyle='rgba(31,65,89,.12)';
    ctx.lineWidth=1;
    ctx.beginPath();
    for (let x=grid;x<w;x+=grid) {ctx.moveTo(x,0);ctx.lineTo(x,h);}
    for (let y=grid;y<h;y+=grid) {ctx.moveTo(0,y);ctx.lineTo(w,y);}
    ctx.stroke();
    // Two partial framing marks, outside the subject and away from QR finder shapes.
    ctx.strokeStyle='rgba(232,249,255,.85)';
    ctx.lineWidth=2;
    for (const sign of [-1,1]) {
      const x=w*(.5+sign*.40), y=h*(.5+sign*.33);
      ctx.beginPath();
      ctx.moveTo(x-sign*w*.065,y);
      ctx.lineTo(x,y);
      ctx.lineTo(x,y-sign*h*.07);
      ctx.stroke();
    }
  }
  ctx.restore();
}

function paintSubjectEffects(ctx,kind,style,points,angle,strength,pose,opacity) {
  const {width:w,height:h}=ctx.canvas;
  if (kind==='petals') {
    for (const [i,point] of points.entries()) {
      const drift=(point.y+angle*(.064+point.brightness*.048))%1;
      const side=i%2 ? 1 : -1;
      const x=w*(.5+side*(.30+point.x*.15)+.028*Math.sin(i+angle*1.15)+
        .045*strength*Math.sin(pose.yaw));
      const y=h*(.04+drift*.92);
      const size=w*(.011+point.brightness*.012)*(1+strength*.40);
      ctx.save();
      ctx.translate(x,y);
      ctx.rotate(angle*.82+i*1.8+pose.pitch*.6);
      ctx.fillStyle=style.colors[i%3];
      ctx.globalAlpha=opacity*(.30+.47*Math.sin(Math.PI*drift));
      ctx.beginPath();
      ctx.moveTo(0,-size*.96);
      ctx.bezierCurveTo(size*.92,-size*.61,size*.58,size*.86,0,size*.86);
      ctx.bezierCurveTo(-size*.78,size*.42,-size*.65,-size*.42,0,-size*.96);
      ctx.fill();
      ctx.strokeStyle='#fff7fa';
      ctx.lineWidth=1.3;
      ctx.beginPath();
      ctx.moveTo(-size*.12,size*.48);
      ctx.quadraticCurveTo(size*.28,0,0,-size*.55);
      ctx.stroke();
      ctx.restore();
    }
    return;
  }

  if (kind==='bricks') {
    for (const [i,point] of points.entries()) {
      const phase=(point.y+angle*(.31+point.brightness*.2))%1;
      const air=4*phase*(1-phase);
      const side=i%2 ? 1 : -1;
      const x=w*(.5+side*(.23+point.x*.18+phase*.065));
      const y=h*(.79+point.y*.09-air*(.056+point.brightness*.16+strength*.085));
      const size=w*(.010+point.brightness*.022)*(1+strength*.26);
      ctx.save();
      ctx.translate(x,y);
      ctx.rotate((phase-.5)*1.7+point.x+Math.sin(pose.yaw)*.32);
      ctx.fillStyle=style.colors[i%3];
      ctx.globalAlpha=opacity*(.16+air*.77);
      ctx.fillRect(-size/2,-size/2,size*1.25,size*.85);
      ctx.fillStyle='#fff9df';
      ctx.globalAlpha*=.76;
      ctx.fillRect(-size*.34,-size*.43,size*.34,size*.16);
      ctx.fillRect(size*.16,-size*.43,size*.34,size*.16);
      ctx.restore();
    }
    return;
  }

  const product=kind==='product-studio';
  const pulse=.5+.5*Math.sin(angle*1.5);
  for (const side of [-1,1]) {
    const lateral=.30+.086*pulse+.052*strength*Math.sin(pose.yaw)*side;
    const x=w*(.5+side*lateral);
    const y=h*(product?.68:.61);
    const width=w*(product?.105:.15)*(1+strength*.22);
    const height=h*(product?.41:.25);
    ctx.save();
    ctx.translate(x,y);
    ctx.rotate(product ? .10*side : -.64);
    const light=ctx.createRadialGradient(0,0,0,0,0,w*.11);
    light.addColorStop(0,style.colors[side===1?0:2]);
    light.addColorStop(1,style.colors[side===1?0:2]+'00');
    ctx.scale(1,height/width);
    ctx.globalAlpha=opacity*(.36+pulse*.34+strength*.13);
    ctx.fillStyle=light;
    ctx.fillRect(-width,-w*.13,width*2,w*.26);
    ctx.restore();
  }
  for (const [i,point] of points.entries()) {
    const side=i%2 ? 1 : -1;
    const phase=(point.y+angle*.11)%1;
    const x=w*(.5+side*(.32+point.x*.135));
    const y=h*(.22+phase*.58);
    ctx.globalAlpha=opacity*(.26+strength*.22)*Math.sin(Math.PI*phase);
    ctx.fillStyle=style.colors[i%3];
    ctx.fillRect(x,y,w*(.012+.022*point.brightness),product?1.5:2.5);
  }
  ctx.globalAlpha=1;
}

const landingLights = [
  [-.39,.045],[-.32,.058],[-.25,.071],[-.18,.084],[-.11,.097],[-.04,.11],
  [.03,.123],[.10,.136],[.17,.149],[.24,.162],[.31,.175],[.38,.188],
];

// The landing site shares the camera with the QR cells, down to its cliff faces.
function buildLandingSite() {
  const sectors=44, rings=13;
  const surface=(a,r)=>{
    const edge=.515+.035*Math.sin(3*a+.7)+.018*Math.cos(7*a);
    const x=Math.cos(a)*r*edge, y=Math.sin(a)*r*edge*.76;
    const peak=(px,py)=>Math.exp(-48*((x-px)**2+(y-py)**2));
    const height=(.113*peak(-.28,-.16)+.122*peak(.31,-.23)+.035*peak(.11,.30))*
      (.80+.20*Math.sin(119*x+68*y));
    return [x,y,.355-height];
  };
  const rows=Array.from({length:rings+1},(_,i)=>
    Array.from({length:sectors},(_,j)=>surface(j*turn/sectors,i/rings)));
  const facets=[];
  for (let i=1;i<=rings;i++) {
    for (let j=0;j<sectors;j++) {
      const next=(j+1)%sectors;
      const a=rows[i][j], b=rows[i][next], c=rows[i-1][j], d=rows[i-1][next];
      facets.push([a,b,c],[b,d,c]);
    }
  }
  const rim=rows[rings];
  const walls=rim.map((point,j)=>{
    const next=rim[(j+1)%sectors];
    const foot=([x,y,z])=>[x*.88,y*.88,z+.083];
    return [point,next,foot(next),foot(point)];
  });
  return {facets,walls};
}

let landingSite;
function paintLandingSite(ctx,project,opacity) {
  landingSite ||= buildLandingSite();
  const {facets,walls}=landingSite;
  const panels=[...facets,...walls].map((facet,index)=>{
    const points=facet.map(point=>project(...point));
    const depth=points.reduce((sum,p)=>sum+p[2],0)/points.length;
    const elevation=facet.reduce((sum,p)=>sum+.355-p[2],0)/facet.length;
    const band=Math.floor(elevation*48)*4;
    const texture=(index*73%31)/31*8;
    const lighting=texture+25*(depth+.60);
    const color=facet.length===4
      ? [11+lighting*.5,25+lighting*.70,36+lighting]
      : [12+lighting+band*.55,29+lighting+band*.75,45+lighting+band];
    return {points,depth,color:'rgb('+color.map(Math.round).join(',')+')'};
  }).sort((a,b)=>a.depth-b.depth);
  ctx.save();
  ctx.globalAlpha=opacity;
  ctx.lineWidth=.9;
  for (const {points, color} of panels) {
    ctx.beginPath();
    ctx.moveTo(...points[0].slice(0,2));
    for (const [x,y] of points.slice(1)) ctx.lineTo(x,y);
    ctx.closePath();
    ctx.fillStyle=ctx.strokeStyle=color;
    ctx.fill();
    ctx.stroke();
  }
  const [first,last]=[landingLights[0],landingLights.at(-1)];
  ctx.beginPath();
  for (const [point,offset] of [[first,-.031],[last,-.031],[last,.031],[first,.031]]) {
    const [x,y]=project(point[0],point[1]+offset,.354);
    ctx.lineTo(x,y);
  }
  ctx.closePath();
  ctx.fillStyle='#142535';
  ctx.fill();
  for (const offset of [-.031,.031]) {
    ctx.beginPath();
    const corners=landingLights.map(([x,y])=>project(x,y+offset,.354));
    ctx.moveTo(corners[0][0],corners[0][1]);
    for(const [x,y] of corners.slice(1)) ctx.lineTo(x,y);
    ctx.strokeStyle='#589baf';
    ctx.lineWidth=1.15;
    ctx.stroke();
  }
  ctx.beginPath();
  for (const [x,y] of landingLights.slice(1,-1)) {
    const start=project(x-.016,y-.003,.354);
    const end=project(x+.016,y+.003,.354);
    ctx.moveTo(start[0],start[1]);
    ctx.lineTo(end[0],end[1]);
  }
  ctx.strokeStyle='#98c0cc';
  ctx.stroke();
  ctx.restore();
}

function paintFlightLights(ctx,points,pose,progress,angle,strength) {
  const {width:w,height:h}=ctx.canvas;
  const project=projectScene(w,h,Math.min(w,h)*.79,pose,ease(progress,.32,1));
  const fade=1-ease(progress,.10,.57);
  const padFade=1-ease(progress,.025,.30);
  const [cueX,cueY]=project(-.005,.11,.35);
  const wash=ctx.createRadialGradient(cueX,cueY,1,cueX,cueY,w*.34);
  wash.addColorStop(0,'#42dfff77');
  wash.addColorStop(.53,'#3888b22a');
  wash.addColorStop(1,'#3888b200');
  ctx.fillStyle=wash;
  ctx.globalAlpha=padFade*(.38+.14*Math.sin(angle*1.12)+strength*.13);
  ctx.fillRect(cueX-w*.34,cueY-w*.34,w*.68,w*.68);
  for (const [i,[x,y]] of landingLights.entries()) {
    const [sx,sy]=project(x,y,.350);
    const pulse=.38+.62*Math.max(0,Math.cos(i*.61-angle*5));
    ctx.globalAlpha=padFade*(.38+.57*pulse);
    ctx.shadowColor='#ffb863';
    ctx.shadowBlur=9+pulse*8;
    ctx.fillStyle='#ffcf86';
    ctx.fillRect(sx-2,sy-1,4,2.4);
  }
  ctx.shadowBlur=0;

  for (const [i,light] of points.entries()) {
    const {x,z,h:depth}=light;
    const [sx,sy]=project(x,depth,z);
    const phase=(angle*.36+i*.173)%1;
    const pulse=.24+.76*Math.sin(Math.PI*phase)**8;
    const halo=w*(.008+.022*pulse);
    const glow=ctx.createRadialGradient(sx,sy,0,sx,sy,halo);
    glow.addColorStop(0,'#d9fdffdf');
    glow.addColorStop(.22,'#72edfb94');
    glow.addColorStop(1,'#52edff00');
    ctx.globalAlpha=fade*(.25+pulse*.64);
    ctx.fillStyle=glow;
    ctx.fillRect(sx-halo,sy-halo,halo*2,halo*2);

    // A short burst rises from its runway position toward the matching light cell.
    const launch=fade*Math.sin(Math.PI*phase)*(strength*.54+.14+pulse*.16);
    const takeoff=Math.max(-.39,Math.min(.38,x*.81));
    const runwayDepth=.115+takeoff*.186;
    const trailPhase=phase*(.83-strength*.17);
    const tip=project(mix(takeoff,x,phase),mix(runwayDepth,depth,phase),mix(.35,z,phase));
    const tail=project(mix(takeoff,x,trailPhase),mix(runwayDepth,depth,trailPhase),mix(.35,z,trailPhase));
    ctx.globalAlpha=Math.min(.86,launch);
    ctx.strokeStyle=i%5?'#62dfffff':'#ffbc76';
    ctx.lineWidth=1.25+strength*1.15;
    ctx.beginPath();
    ctx.moveTo(...tail.slice(0,2));
    ctx.lineTo(...tip.slice(0,2));
    ctx.stroke();
    ctx.fillStyle='#e6ffff';
    ctx.fillRect(tip[0]-1,tip[1]-1,2,2);
  }
  ctx.globalAlpha=1;
}

function inProjectedRect(ctx, project, x, y, z, width, height, lift, paint) {
  const a=project(x,y,z), b=project(x+width,y,z), c=project(x,y+lift,z+height);
  ctx.save();
  ctx.transform(b[0]-a[0],b[1]-a[1],c[0]-a[0],c[1]-a[1],a[0],a[1]);
  paint();
  ctx.restore();
}

function paintFileStack(ctx, pose, angle, strength, opacity, direction) {
  const {width:w,height:h}=ctx.canvas;
  const project=projectScene(w,h,w*.79,pose);
  const show=.68+.32*Math.sin(angle*1.12);
  const spread=show*.046+strength*.068;
  const files=[
    {x:-.56,z:-.30,depth:-.19,shift:-1,tint:'#a1c4f8',paper:'#e8f2ff',title:'IMAGE'},
    {x:.29,z:-.23,depth:-.12,shift:1,tint:'#a3a5ef',paper:'#eeedff',title:'DOC'},
    {x:-.41,z:.16,depth:-.31,shift:-.7,tint:'#93b8eb',paper:'#f4f5ff',title:'FILE'}
  ];
  files.sort((a,b)=>project(a.x,a.depth,a.z)[2]-project(b.x,b.depth,b.z)[2]);
  for (const [i,file] of files.entries()) {
    const slide=spread*file.shift+direction*strength*.019;
    const z=file.z+Math.sin(angle*1.7+i*.85)*.024;
    inProjectedRect(ctx,project,file.x+slide,file.depth,z,.228,.28,.065,()=>{
      ctx.globalAlpha=opacity*.54;
      ctx.fillStyle='#335585';
      ctx.fillRect(.045,.075,1,1);
      ctx.globalAlpha=opacity*.93;
      ctx.fillStyle=file.paper;
      ctx.fillRect(0,0,1,1);
      ctx.fillStyle=file.tint;
      ctx.fillRect(0,0,1,.19);
      ctx.fillStyle='#274577';
      if (Math.cos(pose.yaw)>0) {
        ctx.font='600 .072px monospace';
        ctx.fillText(file.title,.090,.123);
      }
      ctx.fillStyle=file.tint;
      ctx.fillRect(.09,.27,.82,.36);
      ctx.fillStyle='#536c9d';
      for (let line=0;line<3;line++) ctx.fillRect(.09,.72+.07*line,.73-.11*line,.014);
    });
  }
}

function paintInstantPrint(ctx, pose, angle, strength, opacity) {
  const {width:w,height:h}=ctx.canvas;
  const project=projectScene(w,h,w*.79,pose);
  const phase=(angle+.68)%6.3;
  const eject=Math.max(ease(phase,.25,1.72)*(1-ease(phase,5.04,6.26)),strength*.40);
  const exposure=ease(phase,1.38,3.96);
  if (eject>.014) {
    const length=.265*Math.min(1,eject+strength*.084);
    inProjectedRect(ctx,project,-.215,.202,.246,.430,length,length*.30,()=>{
      ctx.globalAlpha=opacity*.98;
      ctx.fillStyle='#fcf4e2';
      ctx.fillRect(0,0,1,1);
      ctx.fillStyle='#362c42';
      ctx.fillRect(.065,.08,.870,.68);
      ctx.save();
      ctx.beginPath();
      ctx.rect(.065,.08,.870,.68);
      ctx.clip();
      ctx.globalAlpha=opacity*exposure;
      const sky=ctx.createLinearGradient(0,.08,0,.76);
      sky.addColorStop(0,'#424870');
      sky.addColorStop(.72,'#e17651');
      sky.addColorStop(1,'#fac18b');
      ctx.fillStyle=sky;
      ctx.fillRect(.065,.08,.870,.68);
      ctx.fillStyle='#ffe0a4';
      ctx.beginPath();
      ctx.ellipse(.65,.40,.095,.16,0,0,turn);
      ctx.fill();
      ctx.fillStyle='#5b3c51';
      ctx.beginPath();
      ctx.moveTo(.04,.66);
      ctx.lineTo(.28,.44);
      ctx.lineTo(.51,.64);
      ctx.lineTo(.76,.55);
      ctx.lineTo(.97,.73);
      ctx.lineTo(.97,.81);
      ctx.lineTo(.04,.81);
      ctx.fill();
      ctx.restore();
      ctx.globalAlpha=opacity*.7;
      ['#a93936','#d3743c','#d8ac4e','#708d52','#527fa1'].forEach((color,i)=>{
        ctx.fillStyle=color;
        ctx.fillRect(.065+i*.024,.865,.024,.033);
      });
    });
  }
  const flash=Math.max(0,1-Math.abs(phase-.46)*7);
  if (flash && Math.cos(pose.yaw)>.18) {
    const light=project(.235,.150,-.339);
    const radius=w*(.080+.045*strength);
    const glow=ctx.createRadialGradient(light[0],light[1],0,light[0],light[1],radius);
    glow.addColorStop(0,'#fff5d6');
    glow.addColorStop(.35,'#ffe7ad96');
    glow.addColorStop(1,'#ffe7ad00');
    ctx.globalAlpha=flash*opacity*.67;
    ctx.fillStyle=glow;
    ctx.fillRect(light[0]-radius,light[1]-radius,2*radius,2*radius);
    ctx.globalAlpha=1;
  }
}

function paintHandheld(ctx, pose, angle, strength, crank, opacity) {
  const {width:w,height:h}=ctx.canvas;
  const project=projectScene(w,h,w*.79,pose);
  const front=Math.cos(pose.yaw)*Math.cos(pose.pitch);
  ctx.save();
  ctx.globalAlpha=opacity;
  if (front>.16) {
    inProjectedRect(ctx,project,-.327,.152,-.321,.655,.411,0,()=>{
      ctx.fillStyle='#1c211e';
      ctx.beginPath();
      ctx.roundRect(0,0,1,1,[.048,.048,.061,.061]);
      ctx.fill();
      ctx.fillStyle='#c4c9ae';
      ctx.fillRect(.048,.094,.904,.797);
      ctx.fillStyle='#a8b59c';
      for(let y=0;y<17;y++) ctx.fillRect(.048,.097+y*.047,.904,.007);
      const px=(x,y,col='#28372d')=>{
        ctx.fillStyle=col;
        ctx.fillRect(.087+x*.028,.139+y*.042,.026,.038);
      };
      // Original monochrome pixel terrain and readout advance with the physical lever.
      const scroll=angle*5+crank*5;
      for(let x=0;x<30;x++) {
        const floor=9+Math.round(2*Math.sin(x*.36+scroll*.16)+Math.sin(x*.59-scroll*.22));
        for(let y=floor;y<15;y++) {
          if (y===floor || (x*3+y)%5===0) px(x,y,y===floor?'#28372d':'#798970');
        }
        if (x%3===0 && x/3<(scroll%10+10)%10) px(x,1);
      }
      const travel=Math.floor(12+Math.sin(crank*.9)*8);
      for (const [dx,dy] of [[0,0],[1,-1],[1,0],[2,0],[1,1]]) px(travel+dx,5+dy);
      px(27,1); px(28,1); px(27,2);
      ctx.fillStyle='#ffffff32';
      ctx.beginPath();ctx.moveTo(.054,.098);ctx.lineTo(.59,.098);
      ctx.lineTo(.43,.89);ctx.lineTo(.054,.89);ctx.closePath();ctx.fill();
    });
    inProjectedRect(ctx,project,-.273,.155,.144,.174,.174,0,()=>{
      for (const [offset,color] of [[.048,'#a96724'],[0,'#ffe182']]) {
        ctx.fillStyle=color;
        ctx.beginPath();
        ctx.roundRect(.33,.02+offset,.34,.89,.06);
        ctx.roundRect(.05,.31+offset,.90,.32,.06);
        ctx.fill();
      }
      ctx.fillStyle='#e6aa3d';
      ctx.fillRect(.36,.34,.28,.26);
    });
    for(const [x,z] of [[.098,.202],[.239,.155]]) {
      inProjectedRect(ctx,project,x,.155,z,.10,.10,0,()=>{
        for(const [y,r,color] of [[.54,.48,'#a96a26'],[.44,.45,'#ffe488'],[.36,.31,'#f7c557']]) {
          ctx.fillStyle=color;
          ctx.beginPath();ctx.arc(.50,y,r,0,turn);ctx.fill();
        }
      });
    }
    for(const [x,z] of [[-.356,-.345],[.32,-.345],[-.356,.303],[.32,.303]]) {
      inProjectedRect(ctx,project,x,.140,z,.038,.038,0,()=>{
        ctx.fillStyle='#e4d8aa';
        ctx.beginPath();ctx.arc(.5,.5,.48,0,turn);ctx.fill();
        ctx.fillStyle='#7a6239';ctx.fillRect(.22,.42,.56,.16);
      });
    }
  }
  const side=Math.sin(-pose.yaw)*Math.cos(pose.pitch);
  if (Math.abs(side)>.28) {
    const sign=Math.sign(side);
    const onSide=(y,x,z)=>project(x,y,z);
    const x=sign*.404;
    const inset=(y,z,width,height,tint)=>inProjectedRect(ctx,onSide,y,x,z,width,height,0,()=>{
      ctx.fillStyle='#936223';
      ctx.beginPath();ctx.roundRect(0,0,1,1,.16);ctx.fill();
      ctx.fillStyle=tint;
      ctx.beginPath();ctx.roundRect(.12,.12,.76,.69,.15);ctx.fill();
    });
    if(sign<0) {
      inset(-.088,-.158,.095,.235,'#715331');
      inset(-.049,.199,.108,.041,'#493d2d');
    } else {
      inset(.027,-.259,.086,.132,'#523c27');
      inset(-.062,.135,.102,.096,'#c68f2c');
    }
  }
  if (side>-.36 || front>.52) {
    const y=.05+Math.sin(crank)*.154, z=-.049+Math.cos(crank)*.154;
    const elbow=project(.459,y,z), end=project(.569,y,z);
    const base=project(.406,.05,-.049), hub=project(.456,.05,-.049);
    const stroke=(from,to,color,size)=>{
      ctx.strokeStyle=color;ctx.lineWidth=w*size;ctx.lineCap='round';
      ctx.beginPath();ctx.moveTo(from[0],from[1]);ctx.lineTo(to[0],to[1]);ctx.stroke();
    };
    if(strength>.13 && side>-.18) {
      for(let i=1;i<=4;i++) {
        const tail=crank-i*.16;
        ctx.globalAlpha=opacity*Math.min(strength,1)*(.26-i*.046);
        stroke(project(.465,.05+Math.sin(tail)*.154,-.049+Math.cos(tail)*.154),
          project(.567,.05+Math.sin(tail)*.154,-.049+Math.cos(tail)*.154),'#fff1ab',.023);
      }
    }
    ctx.globalAlpha=opacity;
    stroke(base,hub,'#6d532b',.027);stroke(hub,elbow,'#272f29',.023);
    stroke(hub,elbow,'#bdd0bb',.009);
    stroke(elbow,end,'#a55d1b',.040);stroke(elbow,end,'#ffc949',.032);
    stroke(elbow,end,'#ffeb9a',.012);
  }
  if(front<-.50) {
    inProjectedRect(ctx,project,-.181,-.151,-.059,.36,.125,0,()=>{
      ctx.fillStyle='#604a32';
      for(let col=0;col<8;col++) {
        ctx.beginPath();
        ctx.roundRect(.07+col*.111,.285,.048,.52,.026);ctx.fill();
      }
    });
  }
  ctx.restore();
}

function paintSignalTide(ctx,pose,angle,strength,opacity) {
  if (!opacity) return;
  const {width:w,height:h}=ctx.canvas;
  const project=projectScene(w,h,w*.667,pose);
  const [x,y]=project(.028,-.082,-.391);
  const radius=w*(.092+.009*Math.sin(2.1*angle));
  const glow=ctx.createRadialGradient(x,y,w*.022,x,y,radius);
  glow.addColorStop(0,'#fff3ca55');
  glow.addColorStop(.23,'#ffc8753b');
  glow.addColorStop(.55,'#ffb95c13');
  glow.addColorStop(1,'#ffb95c00');
  ctx.globalAlpha=opacity*(.72+.16*Math.sin(angle*3));
  ctx.fillStyle=glow;
  ctx.fillRect(x-radius,y-radius,2*radius,2*radius);

  // The light approaches the guide along the stone inlay on the front of the plinth.
  // The moving trace fades as this side turns away, leaving the real inlay visible.
  const facing=ease(Math.cos(pose.yaw+.29),.55,.96);
  const location=(angle*.42)%1;
  for (let j=0;j<8;j++) {
    const t=location-j*.016;
    if (t<0 || t>1) continue;
    const [sx,sy]=project(-.33+.34*t,.283-.10*t+.063*Math.sin(Math.PI*t),.276);
    const fade=ease(t,0,.14)*(1-ease(t,.82,1));
    ctx.globalAlpha=opacity*facing*fade*(.89-j*.092);
    ctx.shadowBlur=w*(.016+strength*.009);
    ctx.shadowColor='#ffd280';
    ctx.fillStyle='#ffe4a9';
    ctx.beginPath();
    ctx.arc(sx,sy,w*(.0035-j*.00034),0,turn);
    ctx.fill();
  }
  ctx.shadowBlur=0;
  ctx.globalAlpha=1;
}

function makeEffects(stage,canvas,kind,motion,tiles) {
  if (kind==='ribbon') kind='petals';
  const style=kind==='signal-tide' ? {count:0, rate:.70} : effectStyles[kind];
  if (!style) return null;
  const layer=document.createElement('canvas');
  layer.width=canvas.width;
  layer.height=canvas.height;
  layer.dataset.qrEffects=kind;
  layer.setAttribute('aria-hidden','true');
  // Inline positioning keeps older exported CSS compatible with this runtime.
  layer.style.cssText='position:absolute;inset:0;pointer-events:none;width:100%;height:100%;';
  stage.style.position='relative';
  stage.append(layer);
  const ctx=layer.getContext('2d');
  const {width:w,height:h}=layer;
  const colors=style.colors;
  const {orbit}=style;
  const points = kind==='flight-grid'
    ? Array.from({length:style.count},(_,i)=>tiles[Math.floor((i+.5)*tiles.length/style.count)].source)
    : stars.slice(0,style.count);
  let strength=0, previous=0, angle=0, active=false, lastDirection=1, effectFrame=0;
  let crank=-.61;
  let visible=false, pose={yaw:0,pitch:0}, progress=0;
  let lastX=.5, lastY=.5;
  const echoes=[];
  const observer=new IntersectionObserver(([entry])=>{
    visible=entry.isIntersecting;
    schedule();
  });
  observer.observe(stage);

  function schedule() {
    if (!effectFrame && visible && progress < .84 && !motion.matches)
      effectFrame=requestAnimationFrame(paint);
  }

  function paint(time) {
    effectFrame=0;
    if (!visible || progress>=.84 || motion.matches) return;
    ctx.clearRect(0,0,w,h);
    const dt=previous ? Math.min(.045,(time-previous)/1000) : 0;
    previous=time;
    strength*=Math.pow(active?.45:.13,dt);
    angle+=dt*(style.rate+strength*(orbit ? lastDirection*1.6 : .72));
    const opacity=1-ease(progress,.18,.84);
    if (kind==='signal-tide') {
      paintSignalTide(ctx,pose,angle,strength,1-ease(progress,.025,.28));
      schedule();
      return;
    }
    if (kind==='crank-pixels') {
      paintHandheld(ctx,pose,angle,strength,crank+.22*Math.sin(angle*2),opacity);
      layer.dataset.crankAngle=crank.toFixed(4);
      schedule();
      return;
    }
    if (kind==='file-stack' || kind==='print-development') {
      if (kind==='file-stack') paintFileStack(ctx,pose,angle,strength,opacity,lastDirection);
      else paintInstantPrint(ctx,pose,angle,strength,opacity);
      schedule();
      return;
    }
    if (kind==='flight-grid') {
      paintFlightLights(ctx,points,pose,progress,angle,strength);
      schedule();
      return;
    }
    if (!orbit) {
      paintSubjectEffects(ctx,kind,style,points,angle,strength,pose,opacity);
      schedule();
      return;
    }
    const project=projectScene(w,h,w*.78,pose);
    const getPoint=(theta,r,z=0)=>project(Math.cos(theta)*r,Math.sin(theta)*r,
      Math.cos(theta)*r*style.tilt+z);
    ctx.lineCap='round';
    {
      for (const [i, point] of points.entries()) {
        const x=w*((point.x+angle*(.012+i%4*.002)+pose.yaw*.035+100)%1);
        const y=h*((point.y+angle*.018+pose.pitch*.08+100)%1);
        const pulse=.52+.48*Math.sin(angle*3+i*1.71);
        const size=(i%11===0?2.5:1.35)*(1+strength*.42);
        ctx.globalAlpha=opacity*(.11+pulse*.52)*point.brightness;
        ctx.fillStyle=colors[i%3];
        ctx.beginPath();
        ctx.arc(x,y,size,0,turn);
        ctx.fill();
        if (i%11===0) {
          ctx.fillRect(x-size*.28,y-size*2.8,size*.56,size*5.6);
          ctx.fillRect(x-size*2.6,y-size*.28,size*5.2,size*.56);
        }
      }
    }

    // Traces follow the same camera as the blocks. Front halves are brightest.
    for (let i=0;i<3;i++) {
      const theta=angle*(i===1?-.82:1)+i*2.1;
      const radius=style.radius-(i%2)*.07;
      const tail=.80+strength*1.2;
      for (let j=0;j<20;j++) {
        const direction=i===1?-1:1;
        const a=getPoint(theta-direction*tail*(1-j/20),radius,.035*(i-1));
        const b=getPoint(theta-direction*tail*(1-(j+1)/20),radius,.035*(i-1));
        const front=ease(b[2],-.04,.26);
        // Keep the rear trace outside the silhouette for clear lettering and faces.
        if (front<.22 && Math.hypot(b[0]-w/2,b[1]-h/2)<w*.28) continue;
        ctx.globalAlpha=opacity*(.16+.68*front)*(j/20)**1.6;
        ctx.strokeStyle=colors[i];
        ctx.lineWidth=1.6+front*1.6+strength*2.6;
        ctx.beginPath();
        ctx.moveTo(a[0],a[1]);
        ctx.lineTo(b[0],b[1]);
        ctx.stroke();
      }
      const tip=getPoint(theta,radius,.035*(i-1));
      if (tip[2]>-.06) {
        const halo=ctx.createRadialGradient(tip[0],tip[1],0,tip[0],tip[1],14+strength*13);
        halo.addColorStop(0,colors[i]);
        halo.addColorStop(1,colors[i]+'00');
        ctx.globalAlpha=opacity*.90;
        ctx.fillStyle=halo;
        const size=18+strength*13;
        ctx.fillRect(tip[0]-size,tip[1]-size,size*2,size*2);
      }
    }
    for (const [i,point] of points.slice(0,26).entries()) {
      const theta=point.x*turn+angle*(.78+point.y*.51)*(i%3===0?-1:1);
      const radius=style.radius+(.5-point.y)*.28;
      const [x,y,depth]=getPoint(theta,radius);
      if (depth<.035 && Math.hypot(x-w/2,y-h/2)<w*.34) continue;
      const size=(2.3+point.y*5.5)*(1+strength*.52);
      ctx.save();
      ctx.translate(x,y);
      ctx.rotate(theta+pose.yaw*.6);
      ctx.fillStyle=colors[i%3];
      ctx.globalAlpha=opacity*(.21+ease(depth,-.45,.45)*.59);
      ctx.beginPath();
      ctx.ellipse(0,0,size*.45,size*.44,0,0,turn);
      ctx.fill();
      ctx.restore();
    }
    for (let i=echoes.length-1;i>=0;i--) {
      const drop=echoes[i];
      drop.life-=dt*1.5;
      if (drop.life <= 0) { echoes.splice(i,1); continue; }
      ctx.strokeStyle=colors[drop.color];
      ctx.lineWidth=3*drop.life;
      ctx.globalAlpha=opacity*drop.life**2*.61;
      ctx.beginPath();
      ctx.moveTo(drop.x,drop.y);
      ctx.quadraticCurveTo(drop.x-drop.vx*11,drop.y+17,drop.x-drop.vx*23,drop.y+41);
      ctx.stroke();
    }
    ctx.globalAlpha=1;
    schedule();
  }

  function clear() {
    cancelAnimationFrame(effectFrame);
    effectFrame=0;
    previous=0;
    echoes.length=0;
    ctx.clearRect(0,0,w,h);
  }

  function settleStill() {
    clear();
    if (kind==='crank-pixels' && progress<.84)
      paintHandheld(ctx,pose,0,0,-.61,1-ease(progress,.18,.84));
  }
  motion.addEventListener('change',()=>{ if (motion.matches) settleStill(); else schedule(); });
  return {
    update(next,p) {
      pose={...next};
      progress=p;
      if (motion.matches) settleStill();
      else if (p>=.84) clear();
      else schedule();
    },
    drag(dx,dy,point) {
      if (motion.matches || progress!==0) return;
      active=true;
      lastDirection=Math.sign(dx)||lastDirection;
      if (kind==='crank-pixels') crank+=(dx+dy*.33)*6;
      strength=Math.min(1.6,strength+Math.hypot(dx,dy)*1.05);
      if (point) [lastX,lastY]=point;
      if (orbit && echoes.length<36) {
        echoes.push({x:lastX*w,y:lastY*h,vx:lastDirection*(1+strength),life:1,color:echoes.length%3});
      }
      schedule();
    },
    release() { active=false; },
    stop() { visible=false; observer.disconnect(); clear(); }
  };
}

const stationary=[0,0,0,0];
const deskLight=[64,250,212];

function prepareMesh(data) {
  if (!data) return null;
  const [vertices,triangles,palette,fragments,reception,vertexColors,reliefInk,reliefNormals]=data;
  const actions=reception ? vertices.map(()=>stationary) : null;
  if (reception) for (const [first,end,...action] of reception[0]) actions.fill(action,first,end);
  const facets=triangles.map(([a,b,c,color],index)=>{
    const [u,v,w]=[vertices[a],vertices[b],vertices[c]];
    const [x,y,z]=v.map((p,i)=>p-u[i]), [i,j,k]=w.map((p,l)=>p-u[l]);
    const cross=[y*k-z*j,z*i-x*k,x*j-y*i];
    const len=Math.hypot(...cross)||1;
    return {a,b,c,color:palette[color],normal:cross.map(p=>p/len),fragment:fragments?.[index]};
  });
  return {vertices,facets,fragments,actions,vertexColors,reliefInk,reliefNormals,button:reception?.[1]};
}

function sceneFlights(scene) {
  const flights=[];
  for (const {source:s,target:t} of scene.tiles) {
    const [x,y,z]=[s.x,s.h,s.z];
    let launch, bend, lift;
    if (scene.studio) {
      const {family}=scene.studio;
      const order=family==='canopy' ? ease(z,-.43,.4) :
        family==='instrument' ? 1-ease(x,-.45,.46) : 1-ease(y,-.27,.32);
      launch=.012+.37*order+.055*ease(z,.12,.39);
      bend=family==='canopy' ? y*.48 : (x<0 ? -.16 : .16);
      lift=family==='companion' ? .12+.1*order : .11+.16*order;
    } else if (scene.artScene==='living-garden') {
      // Lead from the leaf tips, then spiral out over the island.
      launch=.09 + .43*ease(z,-.42,.38);
      bend=(y+.14)*.56;
      lift=.14 + .12*ease(z,-.42,.28);
    } else if (scene.artScene==='service-guide' || scene.artScene==='reception-desk') {
      // Route outward in two signal lanes, with the console following last.
      launch=.09 + .31*(1-ease(y,-.27,.32)) + .13*ease(z,.14,.34);
      bend=(x<0?-1:1)*.22;
      lift=.10 + .065*ease(Math.abs(x),0,.42);
    } else {
      // Roll the level from the screen toward the far side of the handheld.
      launch=.086 + .32*(1-ease(x,-.44,.47)) + .095*ease(z,.03,.33);
      bend=(.15-z)*.46;
      lift=.19;
    }
    flights[s.id]={anchor:[x,y,z],destination:[t.x,0,t.z],launch,bend,lift,action:s.action};
  }
  return flights;
}

// A negative gain identifies the drag channel. The action vector layout is shared by mesh and fragments.
const responseOf=(action,activation,partTravel,idle=0)=>
  action[3]<0 ? partTravel : action[3]>1 ? .5-.5*Math.cos(idle+turn*(action[3]-1)) : activation;
const actionGlow=action=>Math.abs(action[3]>1 ? action[3]-1 : action[3]);

function flightAt(flight,p,activation=0,partTravel=0,action=flight.action || stationary,idle=0) {
  const travel=ease(p,flight.launch,.96);
  const arc=Math.sin(Math.PI*travel);
  const sweep=[flight.bend,flight.bend*.32,-flight.lift];
  const response=responseOf(action,activation,partTravel,idle);
  return flight.anchor.map((value,i)=>mix(value+action[i]*response,flight.destination[i],travel)+arc*sweep[i]);
}

function paintSceneAir(ctx,kind,project,p,flights,spark) {
  const opacity=1-ease(p,.36,.67);
  if (opacity===0 || (kind==='reception-desk' && p===0)) return;
  const [r,g,b] = spark || {
    'service-guide':[133,224,253],
    'reception-desk':[128,241,219],
    'living-garden':[255,221,145],
    'handheld-display':[248,201,118]
  }[kind];
  ctx.save();
  for (const [i,point] of stars.entries()) {
    const angle=point.x*turn+p*(kind==='living-garden' ? 1.9 : .7);
    const radius=.32+point.y*.25;
    const [x,y]=project(Math.sin(angle)*radius,Math.cos(angle)*radius,
      .35-.84*point.brightness+p*.22);
    const size=point.brightness*(i%12===0 ? 3.35 : 1.25);
    ctx.fillStyle='rgba('+r+','+g+','+b+','+opacity*point.brightness*.70+')';
    ctx.beginPath();
    ctx.arc(x,y,size,0,turn);
    ctx.fill();
  }
  // Trace a sparse subset of the actual fragment paths during the release.
  const trace=ease(p,.16,.34)*(1-ease(p,.49,.68));
  if (trace>0) {
    ctx.lineWidth=1.2;
    ctx.strokeStyle='rgba('+r+','+g+','+b+','+trace*.34+')';
    const interval=Math.ceil(flights.length/30);
    for (let i=7;i<flights.length;i+=interval) {
      const flight=flights[i];
      if (p<=flight.launch+.05) continue;
      ctx.beginPath();
      for (let k=0;k<=8;k++) {
        const sample=Math.max(flight.launch,p-.17+k*.17/8);
        const [x,y]=project(...flightAt(flight,sample));
        if (k===0) ctx.moveTo(x,y);
        else ctx.lineTo(x,y);
      }
      ctx.stroke();
    }
  }
  ctx.restore();
}

function studioMesh(mesh,width,height,graphics) {
  const surface=document.createElement('canvas');
  surface.width=width;
  surface.height=height;
  const gl=surface.getContext('webgl',{alpha:true,antialias:true,depth:true});
  if (!gl) return null;
  const shader=(type,source)=>{
    const item=gl.createShader(type);
    gl.shaderSource(item,source);
    gl.compileShader(item);
    return item;
  };
  const vertex=shader(gl.VERTEX_SHADER,`
    attribute vec3 position;
    attribute vec3 normal;
    attribute vec3 material;
    attribute vec3 anchor;
    attribute vec3 destination;
    attribute vec4 timing;
    attribute vec3 codeInk;
    attribute vec4 action;
    uniform vec2 scale;
    uniform vec3 camera;
    uniform vec2 offset;
    uniform float idle;
    uniform float progress;
    uniform float activation;
    uniform float partTravel;
    uniform vec3 actionLight;
    uniform mediump float wallDepth;
    varying vec3 tint;
    varying vec3 direction;
    varying vec3 objectPoint;
    varying float reliefFace;
    varying float flatShade;
    varying float alive;
    varying float wallPosition;
    void main() {
      float c=cos(camera.x), s=sin(camera.x), cp=cos(camera.y), sp=sin(camera.y);
      float response=action.w<0.0 ? partTravel : (action.w>1.0 ? .5-.5*cos(idle+6.2831853*(action.w-1.0)) : activation);
      vec3 point=position;
      objectPoint=position;
      reliefFace=timing.w==-1.0 || timing.w==-2.0 ? 1.0 : 0.0;
      wallPosition=timing.w<-1.5 ? float(timing.w==-3.0) : -1.0;
      tint=material;
      flatShade=0.0;
      alive=1.0;
      if (timing.x>=0.0) {
        float t=smoothstep(timing.x,.96,progress);
        response*=1.0-t;
        float sweep=sin(3.14159265*t);
        vec3 path=mix(anchor,destination,t)+sweep*vec3(timing.y,.32*timing.y,-timing.z);
        vec3 local=position-anchor;
        if (timing.w>0.0) {
          float emerge=smoothstep(timing.x+.07,timing.x+.22,progress);
          flatShade=smoothstep(.64,.99,progress);
          local*=emerge*vec3(1.0,1.0-flatShade*.999,1.0);
          alive=emerge;
          tint=mix(material,codeInk,smoothstep(.52,.94,progress));
        } else {
          float contract=1.0-smoothstep(timing.x+.025,timing.x+.22,progress);
          local*=contract;
          alive=contract;
        }
        point=path+local;
      }
      point+=action.xyz*response;
      tint=mix(tint,actionLight,abs(action.w>1.0 ? action.w-1.0 : action.w)*response);
      if (wallDepth>0.0 && timing.w<=0.0 && position.y<0.0) {
        // Front stays anchored. Extend the already tapered rear in proportion
        // to its local thickness so fine contour details keep their shape.
        point.y-=alive*wallDepth*min(1.0,-position.y/.046);
      }
      vec3 p=vec3(point.x*c+point.y*s, point.y*c-point.x*s, point.z);
      float depth=p.y*cp+p.z*sp;
      float w=1.0-.53*depth*camera.z;
      gl_Position=vec4(vec2(p.x*scale.x, (p.y*sp-p.z*cp)*scale.y)+offset*w, -.78*depth, w);
      float nx=normal.x*c+normal.y*s, ny=normal.y*c-normal.x*s;
      direction=vec3(nx,ny*cp+normal.z*sp,normal.z*cp-ny*sp);
    }`);
  const fragment=shader(gl.FRAGMENT_SHADER,`
    precision mediump float;
    uniform bool signal;
    uniform vec3 keyLight;
    uniform vec3 lightTint;
    uniform sampler2D reliefInk;
    uniform vec2 reliefSize;
    uniform bool texturedRelief;
    uniform mediump float wallDepth;
    varying vec3 tint;
    varying vec3 direction;
    varying vec3 objectPoint;
    varying float reliefFace;
    varying float flatShade;
    varying float alive;
    varying float wallPosition;
    void main() {
      if (alive<=.0001) discard;
      vec3 n=normalize(direction);
      float key=smoothstep(-.15,.92,dot(n,keyLight));
      float rim=max(0.0,dot(n,vec3(.68,-.36,-.58)));
      float fill=.5+.5*dot(n,vec3(.15,.2,-.94));
      float highlight=.068*pow(max(0.0,dot(n,vec3(-.31,.84,-.35))),10.0);
      vec3 color=tint*(.46+.43*key+.17*fill+.095*rim)+highlight+lightTint*(.012+.105*rim*rim);
      if (texturedRelief && reliefFace>.88) {
        vec4 logo=texture2D(reliefInk,objectPoint.xz/reliefSize+.5);
        float covered=smoothstep(.38,.87,logo.a)*smoothstep(.88,1.,reliefFace);
        vec3 painted=logo.rgb*(.76+.19*key+.10*fill)+.31*highlight+.037*lightTint*rim;
        color=mix(color,painted,covered);
      }
      if (wallPosition>=0.0) {
        float shoulder=1.0-smoothstep(.04,.46,wallPosition);
        float satin=pow(max(0.0,dot(n,normalize(vec3(-.68,.42,-.53)))),6.0);
        float reveal=smoothstep(0.0,.060,wallDepth);
        color=mix(color,color*(1.0+.15*shoulder-.09*wallPosition)
                  +vec3(.045,.048,.052)*shoulder*satin,reveal);
      }
      if (signal) {
        vec3 teal=vec3(.16,.52,.62);
        vec3 amber=vec3(1.,.64,.32);
        float edge=pow(1.-abs(n.y),2.);
        float satin=pow(max(0.0,dot(n,vec3(-.30,.88,-.36))),11.);
        float flow=sin(40.*objectPoint.z+7.*sin(objectPoint.x*6.)+5.*objectPoint.y);
        float layers=.62+.38*smoothstep(-.7,1.,flow);
        float metallic=smoothstep(.10,.50,tint.b-tint.r)+smoothstep(.20,.58,tint.r-tint.b);
        float top=1.-smoothstep(.08,.34,objectPoint.z);
        float spec=.18*(.38+.62*metallic);
        color=tint*(.36+.63*key+.18*rim+.11*layers)*(.88+.12*top)
              + teal*(edge*.20+rim*.07)+amber*satin*spec
              + vec3(.05,.17,.19)*layers*top*metallic;
      }
      gl_FragColor=vec4(mix(color,tint,flatShade),1.0);
    }`);
  const program=gl.createProgram();
  gl.attachShader(program,vertex);
  gl.attachShader(program,fragment);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program,gl.LINK_STATUS)) return null;
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  gl.useProgram(program);
  const textureReady=gl.getUniformLocation(program,'texturedRelief');
  if (mesh.reliefInk) {
    const [source,width,height]=mesh.reliefInk;
    const texture=gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D,texture);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array(4));
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.uniform2f(gl.getUniformLocation(program,'reliefSize'),width,height);
    const image=new Image();
    image.onload=()=>{
      gl.bindTexture(gl.TEXTURE_2D,texture);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);
      gl.uniform1i(textureReady,1);
    };
    image.src=source;
  }
  gl.enable(gl.DEPTH_TEST);
  gl.enable(gl.CULL_FACE);

  const values=[];
  const staticTiming={anchor:[0,0,0],destination:[0,0,0],launch:-1,bend:0,lift:0};
  function push(point,normal,color,flight,cell,ink,action=stationary) {
    const {anchor,destination,launch,bend,lift}=flight;
    values.push(...point,...normal,...color.map(x=>x/255),
      ...anchor,...destination,launch,bend,lift,cell,...ink.map(x=>x/255),...action);
  }
  const nearby=mesh.vertices.map(()=>[]);
  const composition=graphics.scene.studio?.composition;
  const extendsWall=composition?.motion==='layer-slide';
  for (const {a,b,c,normal} of mesh.facets) {
    for (const i of [a,b,c]) if (!mesh.reliefNormals?.[i]) nearby[i].push(normal);
  }
  for (const {a,b,c,color,normal,fragment} of mesh.facets) {
    const indices=[a,b,c];
    const side=extendsWall && indices.some(i=>mesh.vertices[i][1]>0)
      && indices.some(i=>mesh.vertices[i][1]<0);
    for (const i of indices) {
      const blend=[0,0,0];
      for (const n of nearby[i]) {
        const agreement=n[0]*normal[0]+n[1]*normal[1]+n[2]*normal[2];
        if (agreement>.78) for (let j=0;j<3;j++) blend[j]+=n[j]*agreement;
      }
      const length=Math.hypot(...blend)||1;
      const ink=mesh.vertexColors?.[i];
      const point=mesh.vertices[i];
      const surface=side ? (point[1]>0 ? -2 : -3) : ink && point[1]>0 ? -1 : 0;
      push(point,mesh.reliefNormals?.[i] || blend.map(x=>x/length),ink || color,
        graphics.flights?.[fragment] || staticTiming,surface,color,mesh.actions?.[i]);
    }
  }
  if (graphics.flights) {
    const size=.5/graphics.scene.n;
    const normals=[[0,-1,0],[0,1,0],[0,0,-1],[1,0,0],[0,0,1],[-1,0,0]];
    for (const {source,target} of graphics.tiles) {
      const flight=graphics.flights[source.id];
      const [x,y,z]=flight.anchor;
      const d=.65*size;
      const corners=[
        [x-size,y-d,z-size],[x+size,y-d,z-size],[x+size,y-d,z+size],[x-size,y-d,z+size],
        [x-size,y+d,z-size],[x+size,y+d,z-size],[x+size,y+d,z+size],[x-size,y+d,z+size]
      ];
      const ink=target.dark ? graphics.targetInk(target.r,target.c) : [255,255,255];
      for (const [index,[[a,b,c,e]]] of faces.entries()) {
        for (const i of [a,c,b,a,e,c]) push(corners[i],normals[index],source.color,flight,1,ink,flight.action);
      }
    }
  }
  gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.STATIC_DRAW);
  let offset=0;
  for (const [name,length] of [['position',3],['normal',3],['material',3],['anchor',3],
    ['destination',3],['timing',4],['codeInk',3],['action',4]]) {
    const location=gl.getAttribLocation(program,name);
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location,length,gl.FLOAT,false,104,offset*4);
    offset+=length;
  }
  const size=gl.getUniformLocation(program,'scale');
  const camera=gl.getUniformLocation(program,'camera');
  const offsetUniform=gl.getUniformLocation(program,'offset');
  const idleUniform=gl.getUniformLocation(program,'idle');
  const keyUniform=gl.getUniformLocation(program,'keyLight');
  const tintUniform=gl.getUniformLocation(program,'lightTint');
  const progress=gl.getUniformLocation(program,'progress');
  const response=gl.getUniformLocation(program,'activation');
  const travel=gl.getUniformLocation(program,'partTravel');
  const wallDepth=gl.getUniformLocation(program,'wallDepth');
  const actionLight=graphics.scene.studio?.spark || deskLight;
  gl.uniform3f(gl.getUniformLocation(program,'actionLight'),...actionLight.map(channel=>channel/255));
  gl.uniform1i(gl.getUniformLocation(program,'signal'),Number(graphics.scene.artScene==='service-guide'));
  const defaultLight=[-.34,.53,-.65];
  return (ctx,scale,orbit,flatten,p,activation=0,partTravel=0,idle=0,slide=null)=>{
    if (gl.isContextLost()) return false;
    gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    gl.uniform2f(size,2*scale/ctx.canvas.width,2*scale/ctx.canvas.height);
    const volume=1-flatten;
    gl.uniform3f(camera,orbit.yaw*volume,orbit.pitch*volume,volume);
    const [x,y]=orbit.shift || [0,0];
    gl.uniform2f(offsetUniform,2*x*volume,-2*y*volume);
    gl.uniform1f(idleUniform,idle);
    const [lightX,lightY,lightZ]=composition?.light || defaultLight;
    const lightSweep=slide ? .38*slide.side : composition ? .45*Math.sin(idle) : 0;
    gl.uniform3f(keyUniform,lightX+lightSweep,lightY,lightZ);
    gl.uniform3f(tintUniform,...(composition ? composition.hue.map(x=>x/255*volume) : [0,0,0]));
    gl.uniform1f(progress,p);
    gl.uniform1f(response,activation);
    gl.uniform1f(travel,partTravel);
    const depth=.032*(slide?.near || 0)+.042*(slide?.far || 0);
    gl.uniform1f(wallDepth,(1-ease(p,.015,.26))*depth);
    gl.drawArrays(gl.TRIANGLES,0,values.length/26);
    ctx.drawImage(surface,0,0,ctx.canvas.width,ctx.canvas.height);
    return true;
  };
}

function drawMesh(ctx,mesh,project,orbit,studio=false,flights=null,p=0,activation=0,partTravel=0,actionLight=deskLight,idle=0,keyLight=null) {
  const actionAt=index=>mesh.actions?.[index] || stationary;
  const points=mesh.vertices.map((v,index)=>{
    const action=actionAt(index);
    const response=responseOf(action,activation,partTravel,idle);
    return project(...v.map((value,i)=>value+action[i]*response));
  });
  const moving=flights && p>0 ? flights.map(flight=>({
    center:flightAt(flight,p), size:1-ease(p,flight.launch+.025,flight.launch+.22)
  })) : null;
  const c=Math.cos(orbit.yaw), s=Math.sin(orbit.yaw);
  const facets=[];
  for (const {a,b,c:index,color,normal:[nx,ny,nz],fragment} of mesh.facets) {
    let vertices=[points[a],points[b],points[index]];
    const move=moving?.[fragment];
    const action=actionAt(a);
    const response=responseOf(action,activation,partTravel,idle);
    if (move) {
      if (move.size<.002) continue;
      const flight=flights[fragment];
      const {anchor}=flight;
      const center=response ? flightAt(flight,p,activation,partTravel,action,idle) : move.center;
      vertices=[a,b,index].map(index=>project(...mesh.vertices[index].map((value,i)=>
        center[i]+(value-anchor[i])*move.size)));
    }
    const [u,v,w]=vertices;
    const face=(v[0]-u[0])*(w[1]-u[1])-(v[1]-u[1])*(w[0]-u[0]);
    if (studio && face>=0) continue;
    const direction=face<0?1:-1;
    const localX=(nx*c+ny*s)*direction, localY=(ny*c-nx*s)*direction, localZ=nz*direction;
    const [lx,ly,lz]=keyLight || [-.29,.42,-.60];
    const light=Math.max(0,localX*lx+localY*ly+localZ*lz);
    const rim=Math.max(0,.66*localX+.20*localY-.42*localZ);
    const material=studio ? .57+.55*light+.21*rim : .77+.30*light;
    const shine=(studio ? .12 : .19)*Math.max(0,(-localX*.32+localY*.74-localZ*.31))**10;
    const glow=actionGlow(action)*response*(move ? 1-ease(p,flights[fragment].launch,.96) : 1);
    const rgb=color.map((channel,i)=>Math.round(Math.min(255,mix(channel,actionLight[i],glow)*material+255*shine)));
    facets.push({u,v,w,depth:(u[2]+v[2]+w[2])/3,color:'rgb('+rgb.join(',')+')'});
  }
  facets.sort((a,b)=>a.depth-b.depth);
  for (const {u,v,w,color} of facets) {
    ctx.beginPath();
    ctx.moveTo(u[0],u[1]); ctx.lineTo(v[0],v[1]); ctx.lineTo(w[0],w[1]); ctx.closePath();
    ctx.fillStyle=ctx.strokeStyle=color;
    // Cover sub-pixel cracks between adjacent faces of the plastic surface.
    ctx.lineWidth=.55;
    ctx.stroke();
    ctx.fill();
  }
}

function sceneInk(scene,ink,finderInk,accentInk) {
  return (r,c) => {
    const n=scene.n;
    if (finderInk && ((r<7 && (c<7 || c>=n-7)) || (r>=n-7 && c<7))) return finderInk;
    if (scene.inkGradient) {
      const weight=Math.max(0,Math.min(1,(2*c+r-.60*n)/(1.82*n)));
      return ink.map((value,i)=>Math.round(mix(value,accentInk[i],weight)));
    }
    return accentInk && 2*c+r>=2*n ? accentInk : ink;
  };
}

function drawScene(ctx, graphics, p, orbit, activation=0, partTravel=0, clock=0) {
  const {scene, tiles, theme, ink, finderInk, accentInk, mesh, drawStudio}=graphics;
  const {targetInk,flights}=graphics;
  const inSpace = scene.style === "planet";
  const surfaceFaces = scene.style === "brick" || scene.solid ? brickFaces : faces;
  const {width,height}=ctx.canvas;
  const cx=width/2, cy=height/2;
  const art=graphics.art;
  const extent=Math.min(width,height);
  const size=art ? extent*scene.heroArt.matrixFraction/scene.n : Math.floor(extent/(scene.n+8));
  const origin={x:Math.floor(cx-size*scene.n/2),y:Math.floor(cy-size*scene.n/2)};
  const flatten=flights ? ease(p,.28,.96) : ease(p,.32,1);
  const background=theme.map(c=>Math.round(mix(c,255,ease(p,.49,1))));
  ctx.fillStyle='rgb('+background.join(',')+')';
  ctx.fillRect(0,0,width,height);
  if (p>=.999999) {
    if (art) {
      ctx.drawImage(art,0,0,width,height);
      return;
    }
    for (const {target} of tiles) {
      if (target.dark) {
        ctx.fillStyle='rgb('+targetInk(target.r,target.c).join(',')+')';
        ctx.fillRect(origin.x+target.c*size,origin.y+target.r*size,size,size);
      }
    }
    return;
  }
  const composition=scene.studio?.composition;
  const idle=composition ? clock*turn/composition.camera[3] : 0;
  const slide=composition?.motion==='layer-slide' ? layerSlide(clock,composition.camera[3]) : null;
  if (composition) orbit=stagedView(orbit,composition,clock);
  const viewScale=composition ? composition.frame[0] : scene.artScene==='service-guide' ? .667 : (inSpace ? .85 : .79);
  const scale=mix(Math.min(width,height)*viewScale,size*scene.n,flatten);
  const effect=scene.effect==='ribbon'?'petals':scene.effect;
  if (!composition && scene.artScene && p < .7) studioBackdrop(ctx,scene.artScene,1-ease(p,.17,.70),scene.studio?.background);
  else if (effectStyles[effect] && p < .7) studioBackdrop(ctx,effect,1-ease(p,.21,.70));
  if (inSpace && !scene.effect) spaceBackdrop(ctx, width, height, p);
  else if (effect==='flight-grid' && p<.30) {
    paintLandingSite(ctx,projectScene(width,height,scale,orbit),1-ease(p,.025,.30));
  } else if (!composition && p < .7 && effect!=='flight-grid' && !effectStyles[effect]?.orbit) {
    const desk=scene.artScene==='reception-desk';
    const floor=cy+height*(desk ? .346 : .24);
    const gradient=ctx.createRadialGradient(cx,floor,6,cx,floor,width*(desk ? .445 : .36));
    const [r,g,b]=desk ? [3,13,18] : [15,28,32];
    gradient.addColorStop(0,`rgba(${r},${g},${b},${(desk ? .56 : .21)*(1-ease(p,0,.7))})`);
    gradient.addColorStop(1,`rgba(${r},${g},${b},0)`);
    ctx.save();
    ctx.translate(cx,floor);
    ctx.scale(1,desk ? .20 : .30);
    ctx.translate(-cx,-floor);
    ctx.fillStyle=gradient;
    ctx.fillRect(0,-height,width,height*4);
    ctx.restore();
  }
  const travel=ease(p,.15,.83), vertical=ease(p,.25,1);
  const xyz=projectScene(width,height,scale,orbit,flatten);
  const meshOpacity=mesh && !flights ? 1-ease(p,.025,.23) : 0;
  if (composition) paintStage(ctx,composition,xyz,clock,p,false);
  if (flights) {
    if (!composition) paintSceneAir(ctx,scene.artScene,xyz,p,flights,scene.studio?.spark);
    if (drawStudio?.(ctx,scale,orbit,flatten,p,activation,partTravel,idle,slide)) {
      if (composition) paintStage(ctx,composition,xyz,clock,p,true);
      if (art && p>.91) {
        ctx.globalAlpha=ease(p,.91,1);
        ctx.drawImage(art,0,0,width,height);
        ctx.globalAlpha=1;
      }
      return;
    }
    drawMesh(ctx,mesh,xyz,orbit,true,flights,p,activation,partTravel,scene.studio?.spark,idle,composition?.light);
    if (composition) paintStage(ctx,composition,xyz,clock,p,true);
    if (p===0) return;
  } else if (meshOpacity===1) {
    if (!drawStudio?.(ctx,scale,orbit,flatten,p)) drawMesh(ctx,mesh,xyz,orbit,Boolean(scene.artScene));
    return;
  }
  const pulse = inSpace || scene.flare ? Math.sin(Math.PI*ease(p,.035,.69)) : 0;
  const visible=tiles.map(({source:s,target:t,motion:m})=>{
    if (flights) {
      const flight=flights[s.id];
      const [x,y,z]=flightAt(flight,p,activation,partTravel,flight.action,idle);
      const size=.5*ease(p,flight.launch+.07,flight.launch+.22)/scene.n;
      const dest=t.dark ? targetInk(t.r,t.c) : [255,255,255];
      const action=flight.action || stationary;
      const glow=actionGlow(action)*responseOf(action,activation,partTravel,idle)*(1-ease(p,flight.launch,.96));
      const actionLight=scene.studio?.spark || deskLight;
      const color=s.color.map((value,i)=>mix(mix(value,actionLight[i],glow),dest[i],ease(p,.52,.94)));
      return {x,y,z,w:size,d:.65*size*(1-ease(p,.64,.99)),color,hiddenFaces:0};
    }
    const settle=ease(p,m.settle,1);
    const twist = pulse * .24;
    const x=s.x+m.x*travel+(t.x-s.x-m.x)*settle + twist*s.h;
    const z=s.z+m.z*travel+(t.z-s.z-m.z)*settle + pulse*.13*s.z;
    const y=s.h*(1-vertical)+.022*Math.sin(Math.PI*ease(p,.08,.88)) - twist*s.x;
    const w=mix(s.w,1/scene.n,settle)/2;
    const d=mix(s.d,0,settle)/2;
    const glow = pulse * Math.max(0, 1 - Math.abs(s.z + .34 - p) * 13);
    const destination = t.dark ? targetInk(t.r,t.c) : [255,255,255];
    const color=s.color.map((a,j)=>Math.round(mix(mix(a, (scene.flare || flare)[j], glow*.73),destination[j],ease(p,.53,1))));
    return {x,z,y,w,d,color,hiddenFaces:p<=.15?s.hiddenFaces:0};
  }).filter(tile=>tile.w>.00005);
  const polygons=[];
  for (const tile of visible) {
    const {x,y,z,w,d,color,hiddenFaces}=tile;
    const corners=[
      xyz(x-w,y-d,z-w),xyz(x+w,y-d,z-w),xyz(x+w,y-d,z+w),xyz(x-w,y-d,z+w),
      xyz(x-w,y+d,z-w),xyz(x+w,y+d,z-w),xyz(x+w,y+d,z+w),xyz(x-w,y+d,z+w)
    ];
    for (let face=0;face<surfaceFaces.length;face++) {
      if (hiddenFaces & (1<<face)) continue;
      const [indices,light] = surfaceFaces[face];
      const pts=indices.map(i=>corners[i]);
      const [a,b,c]=pts;
      if ((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<=0) continue;
      const tint=color.map(i=>Math.min(255,Math.round(i*mix(light,1,flatten))));
      polygons.push({pts,color:'rgb('+tint.join(',')+')',depth:pts.reduce((sum,q)=>sum+q[2],0)/4});
    }
  }
  polygons.sort((a,b)=>a.depth-b.depth);
  ctx.save();
  ctx.globalAlpha=1-meshOpacity;
  for (const {pts,color} of polygons) {
    ctx.beginPath();
    ctx.moveTo(pts[0][0],pts[0][1]);
    for (const q of pts.slice(1)) ctx.lineTo(q[0],q[1]);
    ctx.closePath();
    ctx.fillStyle=color;
    ctx.fill();
  }
  ctx.restore();
  if (meshOpacity>0) {
    ctx.save();
    ctx.globalAlpha=meshOpacity;
    if (!drawStudio?.(ctx,scale,orbit,flatten,p)) drawMesh(ctx,mesh,xyz,orbit,Boolean(scene.artScene));
    ctx.restore();
  }
}

const reliefRest = {yaw: -.44, pitch: .26};
const planetRest = {yaw: -.31, pitch: .44};
const brickRest = {yaw: -.42, pitch: -.62};
const stageBackground = [232, 237, 245];

async function mount(host) {
  const stage = host.querySelector('.qr-blocks-stage');
  const canvas = stage.querySelector('canvas');
  const status = host.querySelector('.qr-blocks-status');
  const control = host.querySelector('[data-qr-switch]');
  const answer = host.querySelector('[data-qr-answer]');
  const transition = host.querySelector('[data-qr-transition]');
  const pause = host.querySelector('[data-qr-pause]');
  const art = stage.querySelector('.qr-blocks-art');
  const wechat = host.hasAttribute('data-qr-wechat');
  const openLabel = control.textContent;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const scene = JSON.parse(host.querySelector('script[type="application/json"]').textContent);
  const composition=scene.studio?.composition;
  const staged=composition?.motion==='layer-slide';
  if (art) await art.decode();
  const ctx = canvas.getContext('2d', {alpha: false, willReadFrequently: !composition});
  if (!ctx || !Array.isArray(scene.tiles)) {
    throw new Error('Invalid scene or unsupported canvas');
  }
  const {tiles,studio} = scene;
  const canDrag = !studio || Boolean(composition);
  const openStageLabel = stage.getAttribute('aria-label');
  if (studio) {
    host.dataset.studioFamily=studio.family;
  }
  if (tiles.length !== scene.n ** 2 || tiles.some(({target}) =>
    target.r < 0 || target.c < 0 || target.r >= scene.n || target.c >= scene.n ||
    Boolean(scene.matrix[target.r][target.c]) !== target.dark
  ) || new Set(tiles.map(({target}) => target.r * scene.n + target.c)).size !== tiles.length ||
    new Set(tiles.map(({source}) => source.id)).size !== tiles.length) {
    throw new Error('Incomplete or duplicate QR grid');
  }

  const isBrick = scene.style === 'brick';
  const rest = scene.pose ? {yaw:scene.pose[0],pitch:scene.pose[1]} :
    ({planet: planetRest, brick: brickRest}[scene.style] || reliefRest);
  const theme = scene.theme || {planet: [7,12,24], brick: [252,232,176]}[scene.style] || stageBackground;
  const mesh=prepareMesh(scene.mesh);
  const ink=scene.ink || [0,0,0];
  const targetInk=sceneInk(scene,ink,scene.finderInk,scene.accentInk);
  const flights=mesh?.fragments ? sceneFlights(scene) : null;
  const graphics={scene,tiles,theme,mesh,targetInk,flights,drawStudio:null,art};
  if (scene.artScene && mesh) graphics.drawStudio=studioMesh(mesh,canvas.width,canvas.height,graphics);
  const effects=makeEffects(stage,canvas,scene.artScene==='service-guide' ? 'signal-tide' : scene.effect,motion,tiles);
  const orbit = {...rest};
  const aim = {...rest};
  const departure = {...rest};
  const paintedOrbit = {...rest};
  let progress = 0;
  let from = 0;
  let target = 0;
  let start = 0;
  let duration = 0;
  let frame = 0;
  let failed = false;
  let gesture = null;
  let cleanMouseUp = false;
  let mouseClicks = 0;
  let lastTap = null;
  let studioRest = null;
  let deskOpen = false;
  let activation = 0;
  let deskFrom = 0;
  let deskStart = 0;
  let deskMoving = false;
  let touchStart = null;
  let clock = staged ? 0 : .55;
  let lastPaint = 0;
  let resumeTimer;
  let holding = false;
  let inView = true;
  let paused = false;
  const observer = composition && typeof IntersectionObserver !== 'undefined' ?
    new IntersectionObserver(([entry])=>{inView=entry.isIntersecting; queue();}) : null;
  observer?.observe(stage);
  const playing = () => composition && inView && !document.hidden && !motion.matches &&
    !paused && !(staged ? gesture || holding : gesture?.dragged) && canOrbit();
  function holdView(ms) {
    holding = true;
    clearTimeout(resumeTimer);
    resumeTimer = setTimeout(() => {holding=false; queue();},ms);
  }
  const wake = () => {
    lastPaint=0;
    if (pause) pause.hidden=motion.matches || failed;
    queue();
  };
  if (composition) {
    motion.addEventListener('change',wake);
    document.addEventListener('visibilitychange',wake);
  }

  function fallback(error) {
    failed = true;
    cancelAnimationFrame(frame);
    effects?.stop();
    observer?.disconnect();
    motion.removeEventListener('change',wake);
    document.removeEventListener('visibilitychange',wake);
    if (pause) pause.hidden=true;
    stage.hidden = true;
    control.hidden = true;
    if (answer) answer.hidden = transition.hidden = true;
    host.dataset.ready = 'false';
    status.textContent = '动画暂不可用，仍可使用原二维码。';
    console.error(error);
  }

  function queue() {
    if (!frame && !failed) frame = requestAnimationFrame(render);
  }

  function updateStatus(text) {
    if (status.textContent !== text) status.textContent = text;
  }

  function render() {
    frame = 0;
    try {
      // Use the same clock as toggle, including in lazily loaded previews.
      const now = performance.now();
      const t = duration ? Math.min(1, Math.max(0, (now - start) / duration)) : 1;
      const gather = studio && !staged && from === 0 && target === 1 ? .14 + .86*ease(t) : ease(t);
      progress = t === 1 ? target : mix(from, target, gather);
      if (deskMoving) {
        const elapsed=Math.max(0,Math.min(1,(now-deskStart)/440));
        activation=mix(deskFrom,Number(deskOpen),1-(1-elapsed)**3);
        deskMoving=elapsed<1;
      }
      if (t === 1 && target === 0) {
        for (const key of ['yaw', 'pitch']) {
          orbit[key] = Math.abs(orbit[key] - aim[key]) < .001 ? aim[key] : mix(orbit[key], aim[key], .2);
        }
      }
      const auto = playing();
      if (auto && lastPaint) clock+=Math.min(66,now-lastPaint)*.001;
      lastPaint=auto ? now : 0;
      const sceneClock=motion.matches ? (staged ? 0 : .55) : clock;
      const currentOrbit = progress > 0 ? departure : orbit;
      const rested = progress === 0 && orbit.yaw === rest.yaw && orbit.pitch === rest.pitch;
      if (!composition && scene.artScene && rested && activation===0) {
        // Reuse the initial frame so GPU and Canvas gradient dithering cannot change the reset picture.
        if (studioRest) ctx.putImageData(studioRest,0,0);
        else {
          drawScene(ctx, graphics, progress, currentOrbit);
          studioRest=ctx.getImageData(0,0,canvas.width,canvas.height);
        }
      } else drawScene(ctx, graphics, progress, currentOrbit, activation, 0, sceneClock);
      effects?.update(currentOrbit,progress);
      if (composition) {
        Object.assign(paintedOrbit, currentOrbit);
        host.dataset.motionTime=sceneClock.toFixed(3);
        if (staged) host.dataset.viewYaw=String(stagedView(currentOrbit,composition,sceneClock).yaw);
        if (staged) {
          const {near,far}=layerSlide(sceneClock,composition.camera[3]);
          host.dataset.layerNear=near.toFixed(4);
          host.dataset.layerFar=far.toFixed(4);
        }
      }
      host.dataset.progress = String(progress);
      host.dataset.yaw = String(currentOrbit.yaw);
      host.dataset.pitch = String(currentOrbit.pitch);
      host.dataset.rested = String(rested);
      canvas.dataset.tiles = String(tiles.length);

      if (answer) {
        answer.disabled = !canOrbit();
        transition.textContent = target===1 ? '播放复原' : '看完整转场';
        control.textContent = progress===1 ? '回到接待台' : openLabel;
      }
      if (progress === 1) updateStatus(wechat ? '用微信扫一扫' : '可扫描 · 双击或双点恢复');
      else if (answer && t === 1) updateStatus(deskOpen ? '接待台已开启' : '拖动看侧面，也可点台上的铜色接听键');
      else if (studio && !composition && t === 1) updateStatus('双击画面，打开彩色艺术码');
      else if (t === 1) updateStatus('按住拖动旋转 · 双击或双点切换');
      else updateStatus(target === 1 ? '方块收拢中' : '方块回到立体中');

      if (auto || t < 1 || deskMoving || (progress === 0 && (orbit.yaw !== aim.yaw || orbit.pitch !== aim.pitch))) queue();
    } catch (error) {
      fallback(error);
    }
  }

  function toggle(instant=false) {
    if (progress === 0) {
      Object.assign(departure, composition ? paintedOrbit : orbit);
      departure.yaw -= turn * Math.round((departure.yaw - rest.yaw) / turn);
    }
    from = progress;
    target = 1-target;
    if (target === 0) Object.assign(aim, composition ? departure : rest);
    // A composed scene returns to the angle the visitor chose.
    Object.assign(orbit, departure);
    start = performance.now();
    duration = instant || motion.matches ? 0 : (studio ? 1120 : flights ? 1880 : 1350) * Math.abs(target - from);
    if (staged) {
      lastPaint=0;
      if (!target) holdView(duration+370);
    }
    if (!answer) control.textContent = target === 1 ? '回到立体' : openLabel;
    stage.setAttribute('aria-label', target === 1
      ? '可扫描的二维码。双击、双点或按 Enter 或空格恢复立体。'
      : openStageLabel);
    if (instant || studio) {
      cancelAnimationFrame(frame);
      render();
    } else queue();
  }

  function canOrbit() {
    return target === 0 && progress === 0;
  }

  function toggleDesk() {
    if (!canOrbit()) return;
    deskOpen = !deskOpen;
    const goal=Number(deskOpen);
    deskFrom=mix(activation,goal,.14);
    activation=motion.matches ? goal : deskFrom;
    deskMoving=!motion.matches;
    deskStart=performance.now();
    const button=hotspot || answer;
    button.setAttribute('aria-pressed',String(deskOpen));
    if (answer) answer.textContent=deskOpen ? '收起接待台' : '按下接听';
    cancelAnimationFrame(frame);
    render();
  }

  function hitsDeskButton(event) {
    if (!answer || !canOrbit() || Math.cos(orbit.yaw)<.35 || Math.cos(orbit.pitch)<.35) return false;
    const bounds=canvas.getBoundingClientRect();
    const [x,y,z]=mesh.button;
    const [px,py]=projectScene(bounds.width,bounds.height,bounds.width*.79,orbit)(x,y,z+activation*.027);
    return Math.hypot(event.clientX-bounds.left-px,event.clientY-bounds.top-py)<Math.max(16,bounds.width*.05);
  }

  function rotate(yaw, pitch, point) {
    orbit.yaw += yaw;
    const pitchLimit = composition ? 1.2 : 1.43;
    orbit.pitch = Math.min(pitchLimit, Math.max(-pitchLimit, orbit.pitch + pitch));
    Object.assign(aim, orbit);
    effects?.drag(yaw,pitch,point);
    queue();
  }

  function startDrag(event) {
    if (!event.isPrimary || event.button !== 0 || gesture) return;
    cleanMouseUp = false;
    gesture = {
      id: event.pointerId, kind: event.pointerType,
      startX: event.clientX, startY: event.clientY, x: event.clientX, y: event.clientY,
      dragged: false, time: performance.now(),
    };
    if (staged) lastPaint=0;
    stage.setPointerCapture(event.pointerId);
  }

  function moveDrag(event) {
    if (gesture?.id !== event.pointerId) return;
    if (!gesture.dragged && Math.hypot(event.clientX - gesture.startX, event.clientY - gesture.startY) < 5) return;
    gesture.dragged = true;
    mouseClicks = 0;
    lastTap = null;
    if (canOrbit()) {
      host.dataset.dragging = 'true';
      const bounds=canvas.getBoundingClientRect();
      const scale=turn/(bounds.width*.84);
      rotate((event.clientX-gesture.x)*scale, (event.clientY-gesture.y)*scale, [
        (event.clientX-bounds.left)/bounds.width,(event.clientY-bounds.top)/bounds.height
      ]);
    }
    gesture.x = event.clientX;
    gesture.y = event.clientY;
  }

  function endDrag(event) {
    if (gesture?.id !== event.pointerId) return;
    const {kind, dragged, time} = gesture;
    gesture = null;
    lastPaint=0;
    if (staged && dragged) holdView(420);
    if (composition) queue();
    delete host.dataset.dragging;
    effects?.release();
    if (event.type !== 'pointerup') {
      mouseClicks = 0;
      lastTap = null;
      return;
    }
    if (dragged) return;
    if (hitsDeskButton(event)) {
      lastTap = null;
      mouseClicks = 0;
      toggleDesk();
      return;
    }
    if (kind === 'mouse') {
      cleanMouseUp = true;
    } else {
      const now = performance.now();
      if (composition && now - time > 370) {
        lastTap = null;
        return;
      }
      if (lastTap && now - lastTap.time <= 360 &&
          Math.hypot(event.clientX - lastTap.x, event.clientY - lastTap.y) <= 26) {
        lastTap = null;
        toggle();
      } else {
        lastTap = {time: now, x: event.clientX, y: event.clientY};
      }
    }
  }

  const download = host.parentElement.querySelector('[data-qr-download-states]');
  if (download) download.addEventListener('click', () => {
    const sheet = document.createElement('canvas');
    const cell = 300;
    sheet.width = cell * 3;
    sheet.height = (cell + 36) * 2;
    const context = sheet.getContext('2d', {alpha: false});
    const panel = document.createElement('canvas');
    panel.width = panel.height = cell;
    const panelContext = panel.getContext('2d', {alpha: false});
    context.fillStyle = '#fff';
    context.fillRect(0, 0, sheet.width, sheet.height);
    context.fillStyle = '#182842';
    context.font = '16px system-ui';
    const views = [
      ['立体',0,rest], [isBrick?'底面':'侧视',0,{yaw:.68,pitch:isBrick?1.10:.24}], ['收拢中',.5,rest],
      [isBrick?'砖红二维码':scene.ink?'着色二维码':'平面原码',1,rest], ['复原中',.65,rest], ['归位',0,rest],
    ];
    views.forEach(([label,p,view],i) => {
      drawScene(panelContext,graphics,p,view);
      const x = (i % 3) * cell;
      const y = Math.floor(i / 3) * (cell + 36);
      context.drawImage(panel,x,y);
      context.fillText(label,x+10,y+cell+23);
    });
    sheet.toBlob(blob => {
      if (!blob) return;
      const href = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = href;
      link.download = 'qr-blocks-six-states.png';
      link.click();
      setTimeout(() => URL.revokeObjectURL(href), 1000);
    });
  });
  if (!canDrag) {
    stage.addEventListener('pointerdown', event => {
      if (event.isPrimary && event.pointerType !== 'mouse') {
        touchStart={id:event.pointerId,x:event.clientX,y:event.clientY,time:performance.now()};
      }
    });
    stage.addEventListener('pointercancel', () => {touchStart=null; lastTap=null;});
    stage.addEventListener('pointerup', event => {
      if (event.pointerId!==touchStart?.id) return;
      const {x,y,time}=touchStart;
      touchStart=null;
      const now=performance.now();
      if (now-time>370 || Math.hypot(x-event.clientX,y-event.clientY)>15) {
        lastTap=null;
        return;
      }
      if (lastTap && now-lastTap.time<380 && Math.hypot(x-lastTap.x,y-lastTap.y)<=24) {
        lastTap=null;
        toggle();
      } else lastTap={x,y,time:now};
    });
  } else {
    stage.addEventListener('pointerdown', startDrag);
    stage.addEventListener('pointermove', moveDrag);
    stage.addEventListener('pointerup', endDrag);
    stage.addEventListener('pointercancel', endDrag);
    stage.addEventListener('lostpointercapture', endDrag);
  }
  stage.addEventListener('click', event => {
    if (event.detail === 0 && event.isTrusted) {
      toggle();
      return;
    }
    if (!canDrag) return;
    if (event.detail === 1) mouseClicks = 0;
    mouseClicks = cleanMouseUp ? mouseClicks + 1 : 0;
    cleanMouseUp = false;
  });
  stage.addEventListener('dblclick', event => {
    if (event.sourceCapabilities?.firesTouchEvents && studio) return;
    if (!canDrag || mouseClicks >= 2) toggle();
    mouseClicks = 0;
  });
  stage.addEventListener('keydown', event => {
    if (!canDrag || !canOrbit()) return;
    const change = {ArrowLeft: [-.30, 0], ArrowRight: [.30, 0], ArrowUp: [0, -.22], ArrowDown: [0, .22]}[event.key];
    if (!change) return;
    event.preventDefault();
    rotate(...change);
    effects?.release();
  });
  control.addEventListener('click', () => toggle(Boolean(answer)));
  pause?.addEventListener('click',()=>{
    paused=!paused;
    pause.textContent=paused ? '继续动效' : '暂停动效';
    wake();
  });
  answer?.addEventListener('click',toggleDesk);
  transition?.addEventListener('click',()=>toggle());
  canvas.addEventListener('contextlost', () => fallback(new Error('Canvas context lost')));
  // Initialize the transition draw path while the opening canvas is still hidden.
  if (composition && graphics.drawStudio && !motion.matches) {
    drawScene(ctx, graphics, .16, rest, 0, 0, clock);
  }
  render();
  if (!failed) {
    stage.hidden = false;
    control.hidden = false;
    if (answer) answer.hidden = transition.hidden = false;
    if (pause) pause.hidden=motion.matches;
    host.dataset.ready = 'true';
  }
}

for (const host of document.querySelectorAll('[data-qr-blocks]')) {
  mount(host).catch(error => {
    host.querySelector('.qr-blocks-status').textContent = '动画暂不可用，仍可使用原二维码。';
    console.error(error);
  });
}
})();
