use serde_json::{json, Value};
use std::{sync::Mutex, time::{Duration, Instant}};
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, Webview, WebviewUrl, WebviewWindowBuilder};

pub const UI_ARGS: &str = "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection --autoplay-policy=no-user-gesture-required --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows";
#[derive(Default)]
pub struct ReminderState(pub Mutex<Value>);

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

fn show(app:&AppHandle,payload:Value,visible:bool)->Result<(),String>{
    validate(&payload)?;
    *app.state::<ReminderState>().0.lock().map_err(|_|"알림을 준비하지 못했습니다.")?=payload.clone();
    if let Some(window)=app.get_webview_window("reminder") {
        window.emit("reminder:updated",payload).map_err(|_|"알림을 갱신하지 못했습니다.")?;
        if visible { let _=window.show(); }
        crate::focus_developer(app);
        return Ok(());
    }
    let developer=app.state::<crate::DeveloperState>().0.load(std::sync::atomic::Ordering::SeqCst);
    let monitor=app.primary_monitor().ok().flatten();
    let height=monitor.as_ref().map(|m|(m.size().height as f64/m.scale_factor()-100.0).clamp(360.0,580.0)).unwrap_or(580.0);
    let window=WebviewWindowBuilder::new(app,"reminder",WebviewUrl::App("index.html?reminder".into()))
        .title("Calix 알림").inner_size(440.0,height).decorations(false).resizable(false)
        .visible(visible).focused(false).skip_taskbar(true).always_on_top(!developer)
        .additional_browser_args(UI_ARGS).build().map_err(|e|format!("알림 창을 열지 못했습니다. ({e})"))?;
    if let Some(m)=monitor {
        let scale=m.scale_factor();let p=m.position();
        let x=p.x+(m.size().width as i32-(464.0*scale) as i32).max(0);
        let y=p.y+(m.size().height as i32-((height+80.0)*scale) as i32).max(0);
        let _=window.set_position(PhysicalPosition::new(x,y));
    }
    crate::focus_developer(app);
    Ok(())
}

#[tauri::command]
pub fn reminder_show(app:AppHandle,webview:Webview,payload:Value)->Result<(),String>{
    crate::auth::trusted(&webview,&["main"])?;show(&app,payload,true)
}
#[tauri::command]
pub fn reminder_payload(app:AppHandle,webview:Webview)->Result<Value,String>{
    crate::auth::trusted(&webview,&["reminder"])?;
    Ok(app.state::<ReminderState>().0.lock().map_err(|_|"알림을 읽지 못했습니다.")?.clone())
}
#[tauri::command]
pub fn reminder_close(app:AppHandle,webview:Webview)->Result<(),String>{
    crate::auth::trusted(&webview,&["main","reminder"])?;
    if let Some(window)=app.get_webview_window("reminder") { let _=window.destroy(); }
    *app.state::<ReminderState>().0.lock().map_err(|_|"알림을 닫지 못했습니다.")?=Value::Null;
    Ok(())
}
#[tauri::command]
pub fn reminder_open_event(app:AppHandle,webview:Webview,key:String)->Result<(),String>{
    crate::auth::trusted(&webview,&["reminder"])?;
    let value=app.state::<ReminderState>().0.lock().map_err(|_|"일정을 열지 못했습니다.")?.clone();
    if key!="" && !value["events"].as_array().is_some_and(|rows|rows.iter().any(|row|row["key"]==key)) { return Err("일정을 확인하세요.".into()); }
    if let Some(window)=app.get_webview_window("main") {
        let _=window.unminimize();let _=window.show();let _=window.set_focus();
        window.emit("reminder:open",json!({"key":key})).map_err(|_|"일정을 열지 못했습니다.")?;
    }
    if let Some(window)=app.get_webview_window("reminder") { let _=window.destroy(); }
    Ok(())
}

pub async fn self_check(app:AppHandle)->Result<Value,String>{
    let payload=json!({"title":"알림 실행 검사","message":"로컬 미디어 검사","urgent":true,"theme":"pink","glass":true,"sound":"crit","volume":0.0,"total":0,"events":[]});
    show(&app,payload,false)?;
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
            if !value.is_null() { if value["passed"]!=true{return Err(value.to_string());}return Ok(value); }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
    }.await;
    let _=window.destroy();result
}
