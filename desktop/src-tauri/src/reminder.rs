use serde_json::{json, Value};
use std::{sync::Mutex, time::{Duration, Instant}};
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, Webview, WebviewUrl, WebviewWindowBuilder};

pub const UI_ARGS: &str = "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection --autoplay-policy=no-user-gesture-required --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows";
#[derive(Default)]
pub struct ReminderState {
    payload: Mutex<Value>,
    gate: tokio::sync::Mutex<()>,
    checking: std::sync::atomic::AtomicBool,
}

fn validate(value: &Value) -> Result<(),String> {
    if value.to_string().len()>180000 { return Err("알림 내용이 너무 큽니다.".into()); }
    for (key,limit) in [("title",160),("message",300)] {
        if value[key].as_str().is_none_or(|text| text.is_empty() || text.len()>limit) { return Err("알림 내용을 확인하세요.".into()); }
    }
    if !["pink","sky","mint","purple","dark"].contains(&value["theme"].as_str().unwrap_or("")) || value["urgent"].as_bool().is_none() || value["glass"].as_bool().is_none() { return Err("알림 설정을 확인하세요.".into()); }
    let sound=value["sound"].as_str().ok_or("음원을 확인하세요.")?;
    if sound!="" && sound!="crit" && !(1..=10).any(|n|sound==n.to_string()) { return Err("음원을 확인하세요.".into()); }
    if value["volume"].as_f64().is_none_or(|n| !(0.0..=1.0).contains(&n)) { return Err("음량을 확인하세요.".into()); }
    let events=value["events"].as_array().ok_or("알림 일정을 확인하세요.")?;
    if events.len()>50 || value["total"].as_u64().is_none_or(|n| n<events.len() as u64 || n>100000) { return Err("알림 일정을 확인하세요.".into()); }
    for event in events {
        for (key,limit) in [("key",400),("title",4000),("course_name",2000),("due_at",100)] {
            if event[key].as_str().is_none_or(|s| s.len()>limit) { return Err("알림 일정을 확인하세요.".into()); }
        }
        if !["assignment","movie"].contains(&event["kind"].as_str().unwrap_or("")) { return Err("일정 유형을 확인하세요.".into()); }
    }
    Ok(())
}

fn snapshot(app: &AppHandle) -> Result<Value, String> {
    Ok(app.state::<ReminderState>().payload.lock().map_err(|_| "알림을 읽지 못했습니다.")?.clone())
}

fn publish(app: &AppHandle, payload: Value) -> Result<u64, String> {
    let revision;
    let envelope;
    {
        let state=app.state::<ReminderState>();
        let mut current=state.payload.lock().map_err(|_|"알림을 준비하지 못했습니다.")?;
        revision=current["revision"].as_u64().unwrap_or(0)+1;
        envelope=json!({"revision":revision,"payload":payload});
        *current=envelope.clone();
    }
    if let Some(window)=app.get_webview_window("reminder") {
        window.emit("reminder:state",envelope).map_err(|_|"알림을 갱신하지 못했습니다.")?;
    }
    Ok(revision)
}

fn show(app:&AppHandle,payload:Value)->Result<u64,String>{
    validate(&payload)?;
    let visible=!app.state::<ReminderState>().checking.load(std::sync::atomic::Ordering::SeqCst);
    let revision=publish(app,payload)?;
    if let Some(window)=app.get_webview_window("reminder") {
        if visible { window.show().map_err(|_|"알림을 표시하지 못했습니다.")?; }
        crate::focus_developer(app);
        return Ok(revision);
    }
    let developer=app.state::<crate::DeveloperState>().0.load(std::sync::atomic::Ordering::SeqCst);
    let monitor=app.primary_monitor().ok().flatten();
    let height=monitor.as_ref().map(|m|(m.size().height as f64/m.scale_factor()-100.0).clamp(360.0,580.0)).unwrap_or(580.0);
    let mut builder=WebviewWindowBuilder::new(app,"reminder",WebviewUrl::App("reminder.html".into()))
        .title("Calix 알림").inner_size(440.0,height).decorations(false).resizable(false)
        .visible(visible).focused(false).skip_taskbar(true).always_on_top(!developer)
        .additional_browser_args(UI_ARGS);
    if !visible {
        builder=builder.data_directory(std::env::temp_dir().join(format!("calix-media-check-{}",std::process::id())));
    }
    let window=builder.build().map_err(|e|format!("알림 창을 열지 못했습니다. ({e})"))?;
    if let Some(m)=monitor {
        let scale=m.scale_factor();let p=m.position();
        let x=p.x+(m.size().width as i32-(464.0*scale) as i32).max(0);
        let y=p.y+(m.size().height as i32-((height+80.0)*scale) as i32).max(0);
        let _=window.set_position(PhysicalPosition::new(x,y));
    }
    crate::focus_developer(app);
    Ok(revision)
}

// WebView2 construction must never run inside a synchronous Windows IPC handler.
#[tauri::command]
pub async fn reminder_show(app:AppHandle,webview:Webview,payload:Value)->Result<u64,String>{
    crate::auth::trusted(&webview,&["main"])?;
    validate(&payload)?;
    let state=app.state::<ReminderState>();
    let _guard=state.gate.lock().await;
    let handle=app.clone();
    tauri::async_runtime::spawn_blocking(move ||show(&handle,payload)).await.map_err(|_|"알림을 준비하지 못했습니다.")?
}
#[tauri::command]
pub fn reminder_payload(app:AppHandle,webview:Webview)->Result<Value,String>{
    crate::auth::trusted(&webview,&["reminder"])?;
    snapshot(&app)
}
fn dismiss(app:&AppHandle,revision:Option<u64>)->Result<(),String>{
    let value=snapshot(app)?;
    if revision.is_some_and(|r|value["revision"].as_u64()!=Some(r)) {return Ok(());}
    if let Some(window)=app.get_webview_window("reminder") {
        window.hide().map_err(|_|"알림을 닫지 못했습니다.")?;
    }
    publish(app,Value::Null)?;
    Ok(())
}
pub async fn dismiss_window(app:AppHandle)->Result<(),String>{
    let state=app.state::<ReminderState>();
    let _guard=state.gate.lock().await;
    let handle=app.clone();
    tauri::async_runtime::spawn_blocking(move ||dismiss(&handle,None)).await.map_err(|_|"알림을 닫지 못했습니다.")?
}
#[tauri::command]
pub async fn reminder_close(app:AppHandle,webview:Webview,revision:Option<u64>)->Result<(),String>{
    crate::auth::trusted(&webview,&["main","reminder"])?;
    if webview.label()=="reminder" && revision.is_none() {return Err("알림을 확인하세요.".into());}
    let state=app.state::<ReminderState>();
    let _guard=state.gate.lock().await;
    let handle=app.clone();
    tauri::async_runtime::spawn_blocking(move ||dismiss(&handle,revision)).await.map_err(|_|"알림을 닫지 못했습니다.")?
}
#[tauri::command]
pub async fn reminder_open_event(app:AppHandle,webview:Webview,key:String,revision:u64)->Result<(),String>{
    crate::auth::trusted(&webview,&["reminder"])?;
    let state=app.state::<ReminderState>();
    let _guard=state.gate.lock().await;
    let handle=app.clone();
    tauri::async_runtime::spawn_blocking(move ||{
        let value=snapshot(&handle)?;
        if value["revision"].as_u64()!=Some(revision) || value["payload"].is_null() {return Ok(());}
        if !key.is_empty() && !value["payload"]["events"].as_array().is_some_and(|rows|rows.iter().any(|row|row["key"]==key)) {return Err("일정을 확인하세요.".into());}
        if let Some(window)=handle.get_webview_window("main") {
            let _=window.unminimize();let _=window.show();let _=window.set_focus();
            window.emit("reminder:open",json!({"key":key})).map_err(|_|"일정을 열지 못했습니다.")?;
        }
        dismiss(&handle,Some(revision))
    }).await.map_err(|_|"일정을 열지 못했습니다.")?
}

pub async fn self_check(app:AppHandle)->Result<Value,String>{
    app.state::<ReminderState>().checking.store(true,std::sync::atomic::Ordering::SeqCst);
    let probe=WebviewWindowBuilder::new(&app,"main",WebviewUrl::App("reminder-probe.html".into()))
        .visible(false).additional_browser_args(UI_ARGS)
        .data_directory(std::env::temp_dir().join(format!("calix-media-check-{}",std::process::id())))
        .build().map_err(|e|format!("PROBE_WINDOW_FAILED: {e}"))?;
    let deadline=Instant::now()+Duration::from_secs(45);
    let ipc=loop {
        if Instant::now()>deadline {return Err("REMINDER_IPC_TIMEOUT".into());}
        let value=crate::campus::evaluate(&probe,"window.__reminderProbe||null".into()).await?;
        if !value.is_null() {
            if value["passed"]!=true {return Err(value.to_string());}
            break value;
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    };
    if snapshot(&app)?["revision"]!=ipc["revision"] || app.webview_windows().len()!=2 {return Err("REMINDER_LIFECYCLE_MISMATCH".into());}
    let window=app.get_webview_window("reminder").ok_or("알림 창이 없습니다.")?;
    let result=async {
        let deadline=Instant::now()+Duration::from_secs(45);
        loop {
            if Instant::now()>deadline { return Err("REMINDER_UI_TIMEOUT".to_string()); }
            let ready=crate::campus::evaluate(&window,"!!document.querySelector('.reminder-card')".into()).await?;
            if ready==true { break; }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        window.eval(r#"(async()=>{try{const image=new Image();const blob=await (await fetch('/assets/profile-avatar.png')).blob();const url=URL.createObjectURL(blob);let decoded=false;try{image.src=url;await image.decode();decoded=image.naturalWidth>0;}finally{URL.revokeObjectURL(url);}const sounds=[];for(const name of ['1','2','3','4','5','6','7','8','9','10','crit']){const audio=new Audio('/assets/alarm/'+name+'.mp3');audio.preload='metadata';await new Promise((resolve,reject)=>{audio.onloadedmetadata=resolve;audio.onerror=()=>reject(Error('AUDIO_DECODE_'+name));});sounds.push({name,duration:audio.duration});audio.src='';audio.load();}window.__mediaCheck={passed:decoded&&sounds.length===11,imageDecoded:decoded,sounds};}catch(e){window.__mediaCheck={passed:false,error:String(e)};}})()"#).map_err(|_|"MEDIA_PROBE_FAILED")?;
        loop {
            if Instant::now()>deadline { return Err("MEDIA_PROBE_TIMEOUT".into()); }
            let value=crate::campus::evaluate(&window,"window.__mediaCheck||null".into()).await?;
            if !value.is_null() { if value["passed"]!=true{return Err(value.to_string());}return Ok(json!({"passed":true,"imageDecoded":value["imageDecoded"],"sounds":value["sounds"],"ipc":ipc,"windowCount":app.webview_windows().len()})); }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
    }.await;
    let _=window.destroy();let _=probe.destroy();result
}
