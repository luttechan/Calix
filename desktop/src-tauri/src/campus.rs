use serde_json::{json, Value};
use std::{collections::HashSet, sync::{Mutex, atomic::{AtomicBool, AtomicU64, Ordering}}, time::{Duration, Instant}};
use tauri::{AppHandle, Emitter, Manager, Webview, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

pub const ARGS: &str = "--disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --autoplay-policy=user-gesture-required";
const AGENT: &str = include_str!("../../scripts/campus-agent.js");
const SNAPSHOT: &str = include_str!("../../scripts/campus-snapshot.js");

#[derive(Default)]
pub struct CampusState {
    gate: tokio::sync::Mutex<()>,
    epoch: AtomicU64,
    debug: AtomicBool,
    sequence: AtomicU64,
}

struct HideOnDrop(WebviewWindow);
impl Drop for HideOnDrop { fn drop(&mut self) { let _ = self.0.hide(); } }

pub fn directory(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    app.path().app_local_data_dir().map(|p| p.join("campus-session")).map_err(|_| "학교 저장소를 준비하지 못했습니다.".into())
}

fn worker(app: &AppHandle) -> Result<WebviewWindow, String> {
    if let Some(view) = app.get_webview_window("campus-worker") { return Ok(view); }
    let gate = app.state::<crate::auth::AuthGate>();
    let _guard = gate.0.lock().map_err(|_| "수집 화면을 준비하지 못했습니다.")?;
    if let Some(view) = app.get_webview_window("campus-worker") { return Ok(view); }
    WebviewWindowBuilder::new(app, "campus-worker", WebviewUrl::External("https://canvas.bufs.ac.kr/".parse().unwrap()))
        .title("Calix 동기화").inner_size(1280.0, 900.0).visible(false).focused(false).skip_taskbar(true)
        .data_directory(directory(app)?).additional_browser_args(ARGS)
        .initialization_script_for_all_frames(AGENT)
        .on_navigation(crate::auth::campus)
        .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
        .build().map_err(|e| format!("수집 브라우저를 열지 못했습니다. ({e})"))
}

fn current(app: &AppHandle, epoch: u64) -> Result<(), String> {
    if app.state::<CampusState>().epoch.load(Ordering::SeqCst) != epoch { Err("CANCELLED".into()) } else { Ok(()) }
}

async fn evaluate(view: &WebviewWindow, script: String) -> Result<Value, String> {
    let (sender, receiver) = tokio::sync::oneshot::channel::<String>();
    let sender = Mutex::new(Some(sender));
    view.eval_with_callback(script, move |value| {
        if let Ok(mut sender) = sender.lock() { if let Some(sender) = sender.take() { let _ = sender.send(value); } }
    }).map_err(|_| "BROWSER_SCRIPT_FAILED")?;
    let text = tokio::time::timeout(Duration::from_secs(8), receiver).await.map_err(|_| "BROWSER_SCRIPT_TIMEOUT")?.map_err(|_| "BROWSER_CLOSED")?;
    if text.len() > 4 * 1024 * 1024 { return Err("BROWSER_RESPONSE_TOO_LARGE".into()); }
    let value: Value = serde_json::from_str(&text).map_err(|_| "INVALID_BROWSER_RESPONSE")?;
    if let Value::String(text) = value { serde_json::from_str(&text).map_err(|_| "INVALID_BROWSER_RESPONSE".into()) } else { Ok(value) }
}

async fn request(app: &AppHandle, view: &WebviewWindow, operation: &str, course: Option<u64>, epoch: u64) -> Result<Value, String> {
    let id = app.state::<CampusState>().sequence.fetch_add(1, Ordering::SeqCst).to_string();
    let deadline = Instant::now() + Duration::from_secs(65);
    let mut started = false;
    loop {
        current(app, epoch)?;
        if Instant::now() > deadline { return Err("BROWSER_REQUEST_TIMEOUT".into()); }
        let script = if !started {
            format!("(()=>{{if(location.origin!=='https://canvas.bufs.ac.kr')return {{status:'loading'}};const s=window[Symbol.for('calix.campus.reader')];if(!s)return {{status:'loading'}};s.debug={debug};s.start({},{},{});return {{status:'started'}};}})()", json!(id), json!(operation), json!(course), debug=app.state::<CampusState>().debug.load(Ordering::SeqCst))
        } else {
            format!("(()=>{{const s=window[Symbol.for('calix.campus.reader')];return s?.jobs[{}]?{{...s.jobs[{}],logs:s.logs.splice(0)}}:{{status:'lost'}};}})()", json!(id),json!(id))
        };
        let value = evaluate(view, script).await?;
        if app.state::<CampusState>().debug.load(Ordering::SeqCst) {
            if let Some(logs)=value["logs"].as_array() { for log in logs { if let Some(message)=log.as_str() { let _=app.emit_to("main","campus:diagnostic",json!({"message":message})); } } }
        }
        match value["status"].as_str() {
            Some("started") => started = true,
            Some("ready") => return Ok(value["value"].clone()),
            Some("error") => return Err(value["error"].as_str().unwrap_or("BROWSER_REQUEST_FAILED").to_string()),
            Some("lost") => return Err("BROWSER_NAVIGATED".into()),
            _ => (),
        }
        tokio::time::sleep(Duration::from_millis(150)).await;
    }
}

async fn identity(app: &AppHandle, view: &WebviewWindow, epoch: u64) -> Result<Value, String> {
    request(app, view, "identity", None, epoch).await
}

pub async fn identity_internal(app: &AppHandle) -> Result<Value, String> {
    let state = app.state::<CampusState>();
    let _guard = state.gate.lock().await;
    let epoch = state.epoch.load(Ordering::SeqCst);
    identity(app, &worker(app)?, epoch).await
}

#[tauri::command]
pub async fn campus_identity(app: AppHandle, webview: Webview) -> Result<Value, String> {
    crate::auth::trusted(&webview, &["main"])?;
    identity_internal(&app).await
}

#[tauri::command]
pub fn campus_debug(app: AppHandle, webview: Webview, enabled: bool) -> Result<(), String> {
    crate::auth::trusted(&webview, &["main"])?;
    app.state::<CampusState>().debug.store(enabled, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
pub fn campus_cancel(app: AppHandle, webview: Webview) -> Result<(), String> {
    crate::auth::trusted(&webview, &["main"])?;
    app.state::<CampusState>().epoch.fetch_add(1, Ordering::SeqCst);
    Ok(())
}

fn progress(app: &AppHandle, run_id: &str, message: String, log: bool) {
    if !log || app.state::<CampusState>().debug.load(Ordering::SeqCst) {
        let _ = app.emit_to("main", "campus:progress", json!({"runId":run_id,"message":message,"log":log}));
    }
}

async fn course_snapshot(app: &AppHandle, view: &WebviewWindow, owner: &str, course: u64, epoch: u64) -> Result<Value, String> {
    view.navigate(format!("https://canvas.bufs.ac.kr/courses/{course}").parse().unwrap()).map_err(|_| "COURSE_NAVIGATION_FAILED")?;
    let deadline = Instant::now() + Duration::from_secs(60);
    let mut routes = HashSet::new();
    let mut last = String::new();
    let mut since = Instant::now();
    let mut shown = false;
    let course_key = course.to_string();
    loop {
        current(app, epoch)?;
        if Instant::now() > deadline { return Err("COURSE_CONTENT_TIMEOUT".into()); }
        let script = format!(r#"(()=>{{try{{const snapshot=JSON.parse({SNAPSHOT});let network=null,viewport={{width:innerWidth,height:innerHeight}};const scan=(d,n=0)=>{{if(n>6)return;const root=d.querySelector('#root[data-canvas_course_id]');if(root&&root.getAttribute('data-canvas_course_id')==={course_id}){{const w=d.defaultView;if(w[Symbol.for('calix.campus.reader')])w[Symbol.for('calix.campus.reader')].debug={debug};network=w[Symbol.for('calix.campus.reader')]?.courses[{course_id}]||null;viewport={{width:w.innerWidth,height:w.innerHeight}};}}for(const f of d.querySelectorAll('iframe')){{try{{if(f.contentDocument)scan(f.contentDocument,n+1)}}catch{{}}}}}};scan(document);return {{snapshot,network,viewport}};}}catch{{return {{error:'SNAPSHOT_FAILED'}};}}}})()"#, course_id=json!(course.to_string()),debug=app.state::<CampusState>().debug.load(Ordering::SeqCst));
        let value = evaluate(view, script).await?;
        if value.get("error").is_some() { return Err("SNAPSHOT_FAILED".into()); }
        let snap = &value["snapshot"];
        if value["viewport"]["width"].as_u64().unwrap_or(0) == 0 || value["viewport"]["height"].as_u64().unwrap_or(0) == 0 {
            if !shown { view.show().map_err(|_| "COLLECTION_VIEWPORT_ZERO")?; shown = true; }
            tokio::time::sleep(Duration::from_millis(250)).await; continue;
        }
        if snap["state"] == "navigate" {
            if let Some(url) = snap["url"].as_str() {
                let parsed = url::Url::parse(url).map_err(|_| "UNSAFE_COURSE_URL")?;
                if parsed.scheme() != "https" || parsed.host_str() != Some("canvas.bufs.ac.kr") || parsed.port_or_known_default() != Some(443) || !parsed.username().is_empty() || parsed.password().is_some() || !parsed.path().starts_with(&format!("/courses/{course}/")) { return Err("UNSAFE_COURSE_URL".into()); }
                if routes.insert(url.to_string()) { view.navigate(parsed).map_err(|_| "COURSE_NAVIGATION_FAILED")?; }
            }
            last.clear();
        } else if snap["state"] == "ready" && snap["course_id"].as_str() == Some(course_key.as_str()) && snap["owner"].as_str() == Some(owner) {
            let network = &value["network"];
            let items = snap["items"].as_array().ok_or("INVALID_VIDEO_LIST")?;
            let loaded = network["modules"] == true && network["lessons"] == true && network["pending"].as_u64() == Some(0) && network["failed"] != true;
            let allowed_empty = !items.is_empty() || network["hasVideo"] == false;
            let complete_count = items.len() as u64 >= network["videoCount"].as_u64().unwrap_or(0);
            if loaded && allowed_empty && complete_count {
                let signature = serde_json::to_string(snap).map_err(|_| "INVALID_SNAPSHOT")?;
                if signature != last { last = signature; since = Instant::now(); }
                else if since.elapsed() >= Duration::from_secs(1) { let _ = view.hide(); return Ok(snap.clone()); }
            } else { last.clear(); }
        } else { last.clear(); }
        tokio::time::sleep(Duration::from_millis(200)).await;
    }
}

#[tauri::command]
pub async fn campus_collect(app: AppHandle, webview: Webview, run_id: String) -> Result<Value, String> {
    crate::auth::trusted(&webview, &["main"])?;
    if run_id.len() != 32 || !run_id.bytes().all(|b| b.is_ascii_hexdigit()) { return Err("INVALID_RUN".into()); }
    let state = app.state::<CampusState>();
    let _guard = state.gate.lock().await;
    let epoch = state.epoch.load(Ordering::SeqCst);
    let view = worker(&app)?;
    let _hide = HideOnDrop(view.clone());
    let who = identity(&app, &view, epoch).await?;
    let owner = who["owner"].as_str().ok_or("INVALID_OWNER")?;
    let courses = who["courses"].as_array().ok_or("INVALID_COURSES")?;
    let mut results = Vec::new();
    let mut responses = serde_json::Map::new();
    for course in courses {
        current(&app, epoch)?;
        let id = course["id"].as_u64().ok_or("INVALID_COURSE")?;
        progress(&app, &run_id, format!("{} / 주차학습 확인 중", course["name"].as_str().unwrap_or("수업")), false);
        match course_snapshot(&app, &view, owner, id, epoch).await {
            Ok(snapshot) => { progress(&app, &run_id, format!("과목 {id} 영상 {}건 확인", snapshot["items"].as_array().map_or(0, |v|v.len())), true); results.push(json!({"course_id":id,"verified":true,"empty_confirmed":snapshot["items"].as_array().is_some_and(|v|v.is_empty()),"snapshot":snapshot})); },
            Err(error) => { if error == "CANCELLED" { return Err(error); } progress(&app, &run_id, format!("과목 {id} 영상 확인 실패: {error}"), true); results.push(json!({"course_id":id,"error":error})); },
        }
        match request(&app, &view, "assignments", Some(id), epoch).await {
            Ok(Value::Object(values)) => responses.extend(values),
            Ok(_) => (),
            Err(error) => { responses.insert(format!("/api/v1/courses/{id}/assignments"), json!({"error":error})); },
        }
    }
    let final_identity = identity(&app, &view, epoch).await?;
    if final_identity["owner"] != who["owner"] { return Err("AUTH_REQUIRED".into()); }
    let _ = view.hide();
    let result = json!({"owner":owner,"courses":courses,"results":results,"responses":responses,"transport":"webview2"});
    if result.to_string().len() > 1500000 { return Err("COLLECTION_TOO_LARGE".into()); }
    Ok(result)
}

pub async fn self_check(app: AppHandle) -> Result<Value, String> {
    use std::{io::{Read, Write}, net::TcpListener, sync::Arc};
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e|e.to_string())?;
    listener.set_nonblocking(true).map_err(|e|e.to_string())?;
    let address = listener.local_addr().map_err(|e|e.to_string())?;
    let stop = Arc::new(AtomicBool::new(false));
    let signal = stop.clone();
    std::thread::spawn(move || {
        while !signal.load(Ordering::SeqCst) {
            match listener.accept() {
                Ok((mut stream, _)) => {
                    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
                    let mut bytes = [0;8192];
                    let count = stream.read(&mut bytes).unwrap_or(0);
                    let request = String::from_utf8_lossy(&bytes[..count]);
                    let setting = request.starts_with("GET /set ");
                    let shared = request.lines().any(|l|l.to_ascii_lowercase().starts_with("cookie:") && l.contains("calix_probe=shared"));
                    let body = format!("<!doctype html><div id='probe' data-shared='{shared}'>Calix offline check</div>");
                    let cookie = if setting { "Set-Cookie: calix_probe=shared; Path=/; HttpOnly; SameSite=Lax\r\n" } else { "" };
                    let response = format!("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\n{cookie}Connection: close\r\n\r\n{body}",body.len());
                    let _ = stream.write_all(response.as_bytes());
                },
                Err(_) => std::thread::sleep(Duration::from_millis(10)),
            }
        }
    });
    let folder = std::env::temp_dir().join(format!("calix-webview-check-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_millis()));
    let mut views = Vec::new();
    let mut readings = Vec::new();
    let result = async {
        for (label,path) in [("check-set","set"),("check-read","read")] {
            let view = WebviewWindowBuilder::new(&app,label,WebviewUrl::External(format!("http://{address}/{path}").parse().unwrap()))
                .inner_size(1280.0,900.0).visible(false).focused(false).skip_taskbar(true).data_directory(folder.clone()).additional_browser_args(ARGS)
                .build().map_err(|e|e.to_string())?;
            views.push(view.clone());
            let deadline = Instant::now()+Duration::from_secs(25);
            loop {
                if Instant::now()>deadline { return Err("WEBVIEW2_CHECK_TIMEOUT".to_string()); }
                let value=evaluate(&view,"({ready:!!document.getElementById('probe'),shared:document.getElementById('probe')?.dataset.shared,width:innerWidth,height:innerHeight,httpOnlyHidden:!document.cookie.includes('calix_probe')})".into()).await?;
                if value["ready"]==true {
                    if value["width"].as_u64().unwrap_or(0)==0 || value["height"].as_u64().unwrap_or(0)==0 { view.show().map_err(|e|e.to_string())?; }
                    else { readings.push(value); break; }
                }
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
        }
        if readings[1]["shared"]!="true" || readings[1]["httpOnlyHidden"]!=true { return Err("WEBVIEW2_PROFILE_NOT_SHARED".to_string()); }
        Ok(json!({"passed":true,"transport":"webview2","sameProfile":true,"httpOnlyProtected":true,"viewport":readings[1]}))
    }.await;
    for view in views { let _=view.destroy(); }
    stop.store(true,Ordering::SeqCst);
    result
}
