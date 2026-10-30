import {isTauri} from '@tauri-apps/api/core';
import {Command,type Child} from '@tauri-apps/plugin-shell';
let child:Child|null=null,starting:Promise<void>|null=null,sequence=0;
const pending=new Map<number,{resolve:(value:unknown)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
const listeners=new Set<(message:Record<string,unknown>)=>void>();
const stopped=new Set<()=>void>();
export function subscribe(listener:(message:Record<string,unknown>)=>void){listeners.add(listener);return()=>{listeners.delete(listener);};}
function failAll(message:string){for(const request of pending.values()){clearTimeout(request.timer);request.reject(new Error(message));}pending.clear();child=null;starting=null;for(const resolve of stopped)resolve();stopped.clear();}
async function start(){
  if(starting)return starting;
  starting=(async()=>{
    const command=Command.sidecar('binaries/calix-engine');
    command.stdout.on('data',(line:string)=>{
      let message;try{message=JSON.parse(line);}catch{return;}
      if(message.event){for(const listener of listeners)listener(message);return;}
      const request=pending.get(message.id);if(!request)return;
      pending.delete(message.id);clearTimeout(request.timer);
      if(message.error)request.reject(new Error(message.error));else request.resolve(message.result);
    });
    command.on('error',()=>failAll('일정 서비스 연결이 끊겼습니다.'));
    command.on('close',()=>failAll('일정 서비스가 종료되었습니다.'));
    child=await command.spawn();
  })().catch(error=>{starting=null;throw error;});return starting;
}
export async function rpc<T=unknown>(method:string,params:Record<string,unknown>={}):Promise<T>{
  const id=++sequence;
  if(!isTauri()){
    const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,method,params})});
    if(!response.ok)throw new Error('일정 서비스에 연결하지 못했습니다.');
    const payload=await response.json();if(payload.error)throw new Error(payload.error);return payload.result;
  }
  await start();if(!child)throw new Error('일정 서비스를 시작하지 못했습니다.');
  if(pending.size>=128)throw new Error('처리 중인 작업이 많습니다. 잠시 후 다시 시도하세요.');
  return new Promise<T>((resolve,reject)=>{
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error('처리 시간이 초과되었습니다.'));},120000);
    pending.set(id,{resolve:value=>resolve(value as T),reject,timer});
    child!.write(JSON.stringify({id,method,params})+'\n').catch(error=>{pending.delete(id);clearTimeout(timer);reject(error);});
  });
}
export async function stopEngine(install=false){
 if(!isTauri()){await rpc('quit',{install});return;}
 if(!child)return;
 let timer:ReturnType<typeof setTimeout>|undefined,done:()=>void=()=>{};
 const closed=new Promise<void>((resolve,reject)=>{done=()=>{clearTimeout(timer);resolve();};timer=setTimeout(()=>{stopped.delete(done);reject(new Error('동기화 종료를 기다리는 중입니다.'));},20000);stopped.add(done);});
 // Observe both promises immediately, including a quit response racing process exit.
 try{await Promise.all([rpc('quit',{install}).catch(error=>{if(child)throw error;}),closed]);}
 finally{clearTimeout(timer);stopped.delete(done);}
}
