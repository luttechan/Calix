JSON.stringify((()=>{
 const rules={
  "video": [
    "movie",
    "ssz",
    "syncthink",
    "estage",
    "xenoglobal",
    "oncast",
    "screenlecture",
    "lecturecam",
    "readystream",
    "webstudio",
    "everlec",
    "movie360",
    "mp4",
    "zoom",
    "audio",
    "youtube",
    "remix",
    "metaverse_conference",
    "video_conference",
    "external_youtube",
    "external_video"
  ],
  "non_video": [
    "file",
    "pdf",
    "assignment",
    "quiz",
    "discussion",
    "page",
    "link",
    "url",
    "attachment",
    "text",
    "photoset",
    "external_url",
    "external_tool",
    "wiki_page",
    "sub_header",
    "subheader",
    "exam",
    "smart_attendance",
    "offline_attendance",
    "offline_exam",
    "syncslide",
    "ssslide",
    "howlimage",
    "website",
    "embed",
    "wbtzip",
    "xenoglobalembed",
    "none"
  ],
  "video_subtypes": [
    "youtube",
    "vimeo",
    "ted",
    "daumtvpot",
    "navertvcast"
  ]
}
;
 const allowed=d=>{try{const u=new URL(d.URL);return u.protocol==='https:'&&u.hostname==='canvas.bufs.ac.kr'&&(!u.port||u.port==='443');}catch(e){return false;}};
 const docs=[];const walk=(d,depth)=>{if(depth>6||!allowed(d))return;docs.push(d);for(const f of d.querySelectorAll('iframe')){try{if(f.contentDocument)walk(f.contentDocument,depth+1);}catch(e){}}};walk(document,0);
 for(const d of docs){
  const root=d.querySelector('#root[data-canvas_course_id]');if(!root)continue;
  const builder=root.querySelector('.xn-module-builder');if(!builder)continue;
  const folded=[...builder.querySelectorAll('.xnmb-module-left-wrapper[aria-expanded="false"]')];
  if(folded.length){for(const b of folded)b.click();return {state:'expanding'};}
  const weeks=[...builder.querySelectorAll('.xnmb-module-title')];
  const expected=builder.querySelectorAll('.xnmb-link-container .xnmb-link').length;
  if(!weeks.length||weeks.length<expected)return {state:'loading'};
  const text=(el,selector)=>{const n=el.querySelector(selector);return n?n.textContent.trim():'';};
  const rows=[];let unsupported=0;
  const observed=d.defaultView[Symbol.for('calix.campus.reader')]?.courses[root.getAttribute('data-canvas_course_id')]?.mediaByItem||{};
  for(const item of builder.querySelectorAll('.xnmb-module_item-wrapper')){
   const meta=item.querySelector('.xnmb-module_item-meta_data-wrapper')||item;
   const icon=item.querySelector('.xnmb-module_item-icon');
   const a=meta.querySelector('a.xnmb-module_item-left-title.link');
   const id=a?(a.getAttribute('href')||'').match(/\/modules\/items\/(\d+)(?:[?#]|$)/)?.[1]:null;
   const api=id?observed[id]:null;
   if(api?.video===false)continue;
   const kind=api?.video?api.kind:icon?rules.video.find(k=>icon.classList.contains(k)):null;
   if(!kind){if((a||icon)&&(!icon||!rules.non_video.some(k=>icon.classList.contains(k))))unsupported++;continue;}
   const done=item.querySelector('.xnmb-module_item-completed');
   const attendance=meta.querySelector('.xnmb-module_item-meta_data-attendance_status');
   rows.push({title:a?a.textContent.trim():'',url:a?a.getAttribute('href'):'',kind,
    start:text(meta,'.xnlal-attendance-list-item-meta_data-lecture_periods-unlock_at'),
    due:text(meta,'.xnlal-attendance-list-item-meta_data-lecture_periods-due_at'),
    lock:text(meta,'.xnlal-attendance-list-item-meta_data-lecture_periods-lock_at'),
    week:text(meta,'.xnmb-module_item-meta_data-lesson_periods-week'),
    completed:done?(done.classList.contains('completed')?true:done.classList.contains('incomplete')?false:null):null,
    attendance:attendance?['attendance','late','excused','absent','none'].find(k=>attendance.classList.contains(k))||'':''});
  }
  return {state:'ready',course_id:root.getAttribute('data-canvas_course_id'),owner:root.getAttribute('data-user_id')||'',name:root.getAttribute('data-course_name')||'',term:root.getAttribute('data-term')||'',weeks:weeks.length,expected,unsupported_items:unsupported,items:rows};
 }
 for(const d of docs){for(const a of d.querySelectorAll('a[href]')){if(/주차학습|학습콘텐츠|강의콘텐츠|LearningX/i.test(a.textContent)){const u=new URL(a.getAttribute('href'),d.URL);if(u.protocol==='https:'&&u.hostname==='canvas.bufs.ac.kr'&&(!u.port||u.port==='443')&&/\/external_tools\//.test(u.pathname))return {state:'navigate',url:u.href};}}}
 return {state:'loading'};
})())