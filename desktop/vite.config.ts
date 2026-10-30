import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {readFileSync} from 'node:fs';
const startup={name:'calix-startup',transformIndexHtml:{order:'pre' as const,handler:(html:string)=>html.replace('<body>',`<body><style>${readFileSync(new URL('./src/startup.css',import.meta.url),'utf8')}</style>${readFileSync(new URL('./public-startup.html',import.meta.url),'utf8')}`)}};
export default defineConfig({plugins:[startup,react()],clearScreen:false,server:{host:'127.0.0.1',port:5173,strictPort:true,watch:{ignored:['**/.build/**','**/src-tauri/**']},proxy:{'/api':{target:'http://127.0.0.1:5174',headers:{'X-Calix-Token':process.env.CALIX_DEV_TOKEN||''}}}},build:{target:'es2022'},envPrefix:['VITE_','TAURI_ENV_']});
