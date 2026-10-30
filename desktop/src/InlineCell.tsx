import {useRef,useState} from 'react';
import {flushSync} from 'react-dom';
type Props={value:string|number|null;label:string;display?:string;type?:'text'|'datetime-local';list?:string;maxLength?:number;options?:{value:number;label:string}[];color?:string;onCommit:(value:string|number|null)=>void};
export function InlineCell({value,label,display,type='text',list,maxLength=200,options,color,onCommit}:Props){
 const [editing,setEditing]=useState(false),[draft,setDraft]=useState('');const input=useRef<HTMLInputElement|HTMLSelectElement|null>(null),cancelled=useRef(false);
 const commit=()=>{if(cancelled.current){cancelled.current=false;return;}setEditing(false);onCommit(options?Number(draft):draft||null);};
 const begin=()=>{cancelled.current=false;flushSync(()=>{setDraft(String(value??''));setEditing(true);});input.current?.focus();if(type!=='text'||options){try{input.current?.showPicker();}catch{/* Keyboard focus remains available when native picker is unsupported. */}}};
 if(!editing)return <button type="button" className={`cell-value ${value?'':'cell-empty'}`} aria-label={label} title={display||String(value??'')} style={{color}} onClick={begin}>{display||String(value??'')||'—'}</button>;
 const keys=(event:React.KeyboardEvent)=>{if(event.key==='Escape'){cancelled.current=true;setEditing(false);}else if(event.key==='Enter'&&!options){event.preventDefault();input.current?.blur();}};
 return options?<select ref={element=>{input.current=element;}} aria-label={label} value={draft} onKeyDown={keys} onBlur={commit} onChange={event=>{cancelled.current=true;setEditing(false);onCommit(Number(event.target.value));}}>{options.map(option=><option value={option.value} key={option.value}>{option.label}</option>)}</select>:<input ref={element=>{input.current=element;}} aria-label={label} type={type} value={draft} maxLength={maxLength} list={list} onChange={event=>setDraft(event.target.value)} onKeyDown={keys} onBlur={commit}/>;
}
