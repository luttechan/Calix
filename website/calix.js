'use strict';
const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
if(!reduced.matches){
  document.documentElement.classList.add('motion-ready');
  const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target);}}},{threshold:.08,rootMargin:'0px 0px -25px 0px'});
  document.querySelectorAll('.reveal').forEach(item=>observer.observe(item));
  const product=document.querySelector('[data-parallax]');let waiting=false;
  function position(){const progress=Math.min(1,Math.max(0,window.scrollY/700));product.style.transform=`translateY(${progress*-16}px)`;waiting=false;}
  window.addEventListener('scroll',()=>{if(!waiting&&window.scrollY<1300){waiting=true;requestAnimationFrame(position);}},{passive:true});
}
let themeRequest=0;
const preview=document.querySelector('#theme-preview');
const themeLabels={pink:'핑크',sky:'스카이블루',mint:'민트',purple:'퍼플',dark:'다크'};
document.querySelectorAll('[data-theme]').forEach(button=>button.addEventListener('click',async()=>{
  const theme=button.dataset.theme;const request=++themeRequest;
  const image=new Image();image.src=`assets/home-${theme}.webp`;
  try{await image.decode();}catch{return;}
  if(request!==themeRequest)return;
  document.querySelectorAll('[data-theme]').forEach(item=>{const active=item===button;item.classList.toggle('active',active);item.setAttribute('aria-pressed',String(active));});
  preview.src=image.src;preview.alt=`Calix ${themeLabels[theme]} 테마`;
  document.querySelector('.theme-stage').dataset.activeTheme=theme;
  document.querySelector('.theme-status').textContent=`${themeLabels[theme]} 테마`;
}));
