use serde_json::{json, Value};
use std::{sync::Mutex, time::{Duration, Instant}};
use tauri::{AppHandle, Emitter, LogicalSize, Manager, PhysicalPosition, Webview, WebviewUrl, WebviewWindowBuilder};

const REMINDER_WIDTH: f64 = 444.0;

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
    if !crate::THEMES.contains(&value["theme"].as_str().unwrap_or("")) || value["urgent"].as_bool().is_none() || value["glass"].as_bool().is_none() { return Err("알림 설정을 확인하세요.".into()); }
    if let Some(language) = value.get("language") {
        if !matches!(language.as_str(), Some("ko" | "en" | "ja")) { return Err("알림 설정을 확인하세요.".into()); }
    }
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
        if event.get("urgent").is_some_and(|value| !value.is_boolean()) { return Err("알림 일정을 확인하세요.".into()); }
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

fn prepare(app:&AppHandle,payload:Value)->Result<u64,String>{
    let checking=app.state::<ReminderState>().checking.load(std::sync::atomic::Ordering::SeqCst);
    let monitor = app.get_webview_window("main")
        .and_then(|window| window.current_monitor().ok().flatten())
        .or_else(|| app.primary_monitor().ok().flatten());
    let rows = payload["events"].as_array().map_or(0, Vec::len);
    let available = monitor.as_ref()
        .map_or(528.0, |m| (m.work_area().size.height as f64 / m.scale_factor() - 40.0).clamp(220.0, 528.0));
    let countdown = if payload["urgent"] == true { 46.0 } else { 0.0 };
    let height = (174.0 + countdown + 63.0 * rows.clamp(1, 6) as f64).min(available);
    let position = monitor.as_ref().map(|m| {
        let scale = m.scale_factor();
        let area = m.work_area();
        PhysicalPosition::new(
            area.position.x + (area.size.width as i32 - ((REMINDER_WIDTH + 16.0) * scale) as i32).max(0),
            area.position.y + (area.size.height as i32 - ((height + 16.0) * scale) as i32).max(0),
        )
    });
    let window = if let Some(window) = app.get_webview_window("reminder") {
        window
    } else {
        let developer = app.state::<crate::DeveloperState>().0.load(std::sync::atomic::Ordering::SeqCst);
        let mut builder = WebviewWindowBuilder::new(app, "reminder", WebviewUrl::App("reminder.html".into()))
            .title("Calix").inner_size(REMINDER_WIDTH, height).decorations(false).resizable(false)
            .visible(false).focused(false).skip_taskbar(true).always_on_top(!developer)
            .transparent(true).background_color(tauri::window::Color(0, 0, 0, 0))
            .additional_browser_args(UI_ARGS);
        if checking {
            builder = builder.data_directory(std::env::temp_dir().join(format!("calix-media-check-{}", std::process::id())));
        }
        builder.build().map_err(|e| format!("알림 창을 열지 못했습니다. ({e})"))?
    };
    if let Some(position) = position {
        window.set_position(position).map_err(|_| "알림 창 위치를 조정하지 못했습니다.")?;
    }
    window.set_size(LogicalSize::new(REMINDER_WIDTH, height)).map_err(|_| "알림 창 크기를 조정하지 못했습니다.")?;
    publish(app, payload)
}

// WebView2 construction must never run inside a synchronous Windows IPC handler.
#[tauri::command]
pub async fn reminder_show(app:AppHandle,webview:Webview,payload:Value)->Result<u64,String>{
    crate::auth::trusted(&webview,&["main"])?;
    validate(&payload)?;
    let state=app.state::<ReminderState>();
    let _guard=state.gate.lock().await;
    let handle=app.clone();
    tauri::async_runtime::spawn_blocking(move ||prepare(&handle,payload)).await.map_err(|_|"알림을 준비하지 못했습니다.")?
}
#[tauri::command]
pub fn reminder_payload(app:AppHandle,webview:Webview)->Result<Value,String>{
    crate::auth::trusted(&webview,&["reminder"])?;
    snapshot(&app)
}

#[tauri::command]
pub async fn reminder_ready(app: AppHandle, webview: Webview, revision: u64) -> Result<bool, String> {
    crate::auth::trusted(&webview, &["reminder"])?;
    let state = app.state::<ReminderState>();
    let _guard = state.gate.lock().await;
    let value = snapshot(&app)?;
    if value["revision"].as_u64() != Some(revision) || value["payload"].is_null() { return Ok(false); }
    if state.checking.load(std::sync::atomic::Ordering::SeqCst) { return Ok(true); }
    let window = app.get_webview_window("reminder").ok_or("알림 창이 없습니다.")?;
    if !window.is_visible().map_err(|_| "알림 창 상태를 확인하지 못했습니다.")? {
        window.show().map_err(|_| "알림을 표시하지 못했습니다.")?;
        crate::focus_developer(&app);
    }
    Ok(true)
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
    let profile=std::env::temp_dir().join(format!("calix-media-check-{}",std::process::id()));
    let probe=WebviewWindowBuilder::new(&app,"main",WebviewUrl::App("reminder-probe.html".into()))
        .visible(false).additional_browser_args(UI_ARGS)
        .data_directory(profile.clone())
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
            let ready=crate::campus::evaluate(&window,"!!document.querySelector('.reminder-card[data-shown]')".into()).await?;
            if ready==true { break; }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        window.eval(r#"(async()=>{try{
            const image=new Image();const blob=await (await fetch('/assets/profile-avatar.png')).blob();
            const url=URL.createObjectURL(blob);let decoded=false;
            try{image.src=url;await image.decode();decoded=image.naturalWidth>0;}finally{URL.revokeObjectURL(url);}
            async function duration(path) {
                const audio=new Audio(path);audio.preload='metadata';
                await new Promise((resolve,reject)=>{audio.onloadedmetadata=resolve;audio.onerror=()=>reject(Error('AUDIO_DECODE_'+path));});
                const seconds=audio.duration;audio.src='';audio.load();return seconds;
            }
            const sounds=[];
            for(const name of ['1','2','3','4','5','6','7','8','9','10','crit']) {
                sounds.push({name,duration:await duration('/assets/alarm/'+name+'.mp3')});
            }
            const logonDecoded=await duration('/assets/sound/logon.mp3')>0;
            window.__mediaCheck={passed:decoded&&sounds.length===11&&logonDecoded,imageDecoded:decoded,sounds,logonDecoded};
        }catch(e){window.__mediaCheck={passed:false,error:String(e)};}})()"#).map_err(|_|"MEDIA_PROBE_FAILED")?;
        loop {
            if Instant::now()>deadline { return Err("MEDIA_PROBE_TIMEOUT".into()); }
            let value=crate::campus::evaluate(&window,"window.__mediaCheck||null".into()).await?;
            if !value.is_null() {
                if value["passed"]!=true {return Err(value.to_string());}
                let window_count=app.webview_windows().len();
                check_developer_console(&app,&profile).await?;
                return Ok(json!({"passed":true,"imageDecoded":value["imageDecoded"],"sounds":value["sounds"],"logonDecoded":value["logonDecoded"],"consoleWindow":true,"ipc":ipc,"windowCount":window_count}));
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
    }.await;
    let _=window.destroy();let _=probe.destroy();result
}

async fn check_developer_console(app: &AppHandle, profile: &std::path::Path) -> Result<(), String> {
    let console = crate::create_developer_console_window(app, Some(profile))?;
    let update = json!({
        "enabled":true,"busy":false,"requesting":false,"force":false,"error":"",
        "rows":[{"id":1,"time":"2026-11-21T00:00:00","source":"engine","level":"error","message":"Calix console probe"}],
    });
    let test = async {
        let deadline = Instant::now() + Duration::from_secs(15);
        while Instant::now() < deadline {
            app.emit_to("developer-console", "developer-console:update", &update)
                .map_err(|error| error.to_string())?;
            let shown = crate::campus::evaluate(&console,
                "document.querySelector('.console-logs')?.textContent.includes('Calix console probe') ?? false".into()
            ).await?;
            if shown == true { return Ok(()); }
            tokio::time::sleep(Duration::from_millis(150)).await;
        }
        Err("CONSOLE_IPC_TIMEOUT".into())
    }.await;
    let _ = console.destroy();
    test
}
