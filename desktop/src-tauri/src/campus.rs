use serde_json::{json, Value};
use std::{collections::HashSet, sync::{Mutex, atomic::{AtomicBool, AtomicU64, Ordering}}, time::{Duration, Instant}};
use tauri::{AppHandle, Emitter, Manager, Webview, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

pub const ARGS: &str = "--disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --autoplay-policy=user-gesture-required";
const MEDIA_RULES: &str = include_str!("../../../learning_calendar/media_types.json");
const CANVAS_MODULES: &str = include_str!("../../scripts/canvas-modules.js");
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
        .initialization_script_for_all_frames(format!("{}\n{}",AGENT.replace("__CALIX_MEDIA_RULES__", MEDIA_RULES),CANVAS_MODULES))
        .on_navigation(crate::auth::campus)
        .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
        .build().map_err(|e| format!("수집 브라우저를 열지 못했습니다. ({e})"))
}

fn current(app: &AppHandle, epoch: u64) -> Result<(), String> {
    if app.state::<CampusState>().epoch.load(Ordering::SeqCst) != epoch { Err("CANCELLED".into()) } else { Ok(()) }
}

pub(crate) async fn evaluate(view: &WebviewWindow, script: String) -> Result<Value, String> {
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

async fn request(app: &AppHandle, view: &WebviewWindow, operation: &str, course: Value, epoch: u64) -> Result<Value, String> {
    let id = app.state::<CampusState>().sequence.fetch_add(1, Ordering::SeqCst).to_string();
    let deadline = Instant::now() + Duration::from_secs(65);
    let mut started = false;
    loop {
        current(app, epoch)?;
        if Instant::now() > deadline { return Err("BROWSER_REQUEST_TIMEOUT".into()); }
        if let Ok(url) = view.url() {
            if url.host_str().is_some_and(|host| host != "canvas.bufs.ac.kr") { return Err("AUTH_REQUIRED".into()); }
        }
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
    request(app, view, "identity", Value::Null, epoch).await
}

pub async fn identity_internal(app: &AppHandle) -> Result<Value, String> {
    let state = app.state::<CampusState>();
    let epoch = state.epoch.load(Ordering::SeqCst);
    let _guard = state.gate.lock().await;
    current(app, epoch)?;
    let view = worker(app)?;
    if view.url().ok().and_then(|u|u.host_str().map(str::to_owned)).as_deref() != Some("canvas.bufs.ac.kr") {
        view.navigate("https://canvas.bufs.ac.kr/".parse().unwrap()).map_err(|_|"BROWSER_NAVIGATION_FAILED")?;
        let deadline = Instant::now()+Duration::from_secs(20);
        loop {
            current(app,epoch)?;
            if Instant::now()>deadline { return Err("AUTH_REQUIRED".into()); }
            let ready=evaluate(&view,"(location.origin==='https://canvas.bufs.ac.kr'&&!!window[Symbol.for('calix.campus.reader')])".into()).await?;
            if ready==true { break; }
            tokio::time::sleep(Duration::from_millis(150)).await;
        }
    }
    identity(app, &view, epoch).await
}

#[tauri::command]
pub async fn campus_identity(app: AppHandle, webview: Webview) -> Result<Value, String> {
    crate::auth::trusted(&webview, &["main"])?;
    identity_internal(&app).await
}

#[tauri::command]
pub fn campus_debug(app: AppHandle, webview: Webview, enabled: bool) -> Result<(), String> {
    crate::auth::trusted(&webview, &["main"])?;
    if enabled { crate::require_developer()?; }
    app.state::<CampusState>().debug.store(enabled, Ordering::SeqCst);
    if let Some(view)=app.get_webview_window("campus-worker") {
        let script=format!("(()=>{{const walk=(w,n=0)=>{{if(n>6)return;try{{const s=w[Symbol.for('calix.campus.reader')];if(s){{s.debug={enabled};if(!s.debug)s.logs=[];}}for(const f of w.document.querySelectorAll('iframe'))if(f.contentWindow)walk(f.contentWindow,n+1);}}catch{{}}}};walk(window);}})()");
        let _=view.eval(script);
    }
    Ok(())
}

#[tauri::command]
pub fn campus_cancel(app: AppHandle, webview: Webview) -> Result<(), String> {
    crate::auth::trusted(&webview, &["main"])?;
    app.state::<CampusState>().epoch.fetch_add(1, Ordering::SeqCst);
    if let Some(view)=app.get_webview_window("campus-worker") {
        let _=view.eval("(()=>{const walk=(w,n=0)=>{if(n>6)return;try{w[Symbol.for('calix.campus.reader')]?.cancel();for(const f of w.document.querySelectorAll('iframe'))if(f.contentWindow)walk(f.contentWindow,n+1);}catch{}};walk(window);})()");
        let _=view.hide();
    }
    Ok(())
}

fn progress(app: &AppHandle, run_id: &str, message: String, log: bool) {
    if !log || app.state::<CampusState>().debug.load(Ordering::SeqCst) {
        let _ = app.emit_to("main", "campus:progress", json!({"runId":run_id,"message":message,"log":log}));
    }
}

async fn course_snapshot(app: &AppHandle, view: &WebviewWindow, owner: &str, course: u64, epoch: u64, entry:Option<&str>, known:bool) -> Result<Value, String> {
    let start_url=entry.and_then(|value|url::Url::parse(value).ok()).filter(|u|u.scheme()=="https" && u.host_str()==Some("canvas.bufs.ac.kr") && u.port_or_known_default()==Some(443) && u.username().is_empty() && u.password().is_none() && u.path().starts_with(&format!("/courses/{course}/external_tools/"))).unwrap_or_else(||format!("https://canvas.bufs.ac.kr/courses/{course}").parse().unwrap());
    view.navigate(start_url).map_err(|_| "COURSE_NAVIGATION_FAILED")?;
    let deadline = Instant::now() + Duration::from_secs(30);
    let mut routes = HashSet::new();
    let mut last = String::new();
    let mut since = Instant::now();
    let mut shown = false;
    let course_key = course.to_string();
    let started = Instant::now();
    loop {
        current(app, epoch)?;
        if Instant::now() > deadline { return Err("COURSE_CONTENT_TIMEOUT".into()); }
        if view.url().ok().and_then(|u|u.host_str().map(str::to_owned)).is_some_and(|host|host!="canvas.bufs.ac.kr") { return Err("AUTH_REQUIRED".into()); }
        let script = format!(r#"(()=>{{try{{const snapshot=JSON.parse({SNAPSHOT});let network=null,logs=[],viewport={{width:innerWidth,height:innerHeight,hidden:document.hidden}};const scan=(d,n=0)=>{{if(n>6)return;const root=d.querySelector('#root[data-canvas_course_id]');if(root&&root.getAttribute('data-canvas_course_id')==={course_id}){{const w=d.defaultView;if(w[Symbol.for('calix.campus.reader')])w[Symbol.for('calix.campus.reader')].debug={debug};network=w[Symbol.for('calix.campus.reader')]?.courses[{course_id}]||null;if({debug})logs.push(...(w[Symbol.for('calix.campus.reader')]?.logs.splice(0)||[]));viewport={{width:w.innerWidth,height:w.innerHeight,hidden:d.hidden}};}}for(const f of d.querySelectorAll('iframe')){{try{{if(f.contentDocument)scan(f.contentDocument,n+1)}}catch{{}}}}}};scan(document);return {{snapshot,network,viewport,logs}};}}catch{{return {{error:'SNAPSHOT_FAILED'}};}}}})()"#, course_id=json!(course.to_string()),debug=app.state::<CampusState>().debug.load(Ordering::SeqCst));
        let value = evaluate(view, script).await?;
        if value.get("error").is_some() { return Err("SNAPSHOT_FAILED".into()); }
        if app.state::<CampusState>().debug.load(Ordering::SeqCst) {
            if let Some(logs)=value["logs"].as_array() { for log in logs { if let Some(message)=log.as_str() { let _=app.emit_to("main","campus:diagnostic",json!({"message":message})); } } }
        }
        let snap = &value["snapshot"];
        if value["viewport"]["width"].as_u64().unwrap_or(0) == 0 || value["viewport"]["height"].as_u64().unwrap_or(0) == 0 || (!shown && value["viewport"]["hidden"]==true && started.elapsed()>=Duration::from_secs(3)) {
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
            if network["failed"] == true && network["pending"].as_u64() == Some(0) { return Err("COURSE_RESPONSE_FAILED".into()); }
            if loaded && (network["unsupported"] == true || snap["unsupported_items"].as_u64().unwrap_or(0) > 0) { return Err("UNSUPPORTED_LEARNING_CONTENT".into()); }
            let allowed_empty = !items.is_empty() || network["hasVideo"] == false;
            let complete_count = items.len() as u64 >= network["videoCount"].as_u64().unwrap_or(0);
            if loaded && allowed_empty && complete_count {
                let signature = serde_json::to_string(snap).map_err(|_| "INVALID_SNAPSHOT")?;
                if signature != last { last = signature; since = Instant::now(); }
                else if since.elapsed() >= Duration::from_secs(1) { let _ = view.hide(); return Ok(snap.clone()); }
            } else { last.clear(); }
        } else {
            last.clear();
            if !known && started.elapsed()>=Duration::from_secs(5) {return Err("LEARNINGX_NOT_FOUND".into());}
        }
        tokio::time::sleep(Duration::from_millis(200)).await;
    }
}

fn cancel_reads(view:&WebviewWindow) {
    let _=view.eval("(()=>{const walk=(w,n=0)=>{if(n>6)return;try{w[Symbol.for('calix.campus.reader')]?.cancel();for(const f of w.document.querySelectorAll('iframe'))if(f.contentWindow)walk(f.contentWindow,n+1);}catch{}};walk(window);})()");
}
async fn bounded_request(app:&AppHandle,view:&WebviewWindow,operation:&str,course:Option<u64>,epoch:u64,budget:Duration)->Result<Value,String> {
    if budget.is_zero(){return Err("COURSE_BUDGET_EXCEEDED".into());}
    match tokio::time::timeout(budget,request(app,view,operation,json!(course),epoch)).await {
        Ok(value)=>value,
        Err(_)=>{cancel_reads(view);Err("COURSE_BUDGET_EXCEEDED".into())}
    }
}
fn reuse_manifest(probe:&Value, previous:&str)->bool {
    probe["cacheable"]==true && probe["complete"]==true && previous.len()==64 && previous.bytes().all(|b|b.is_ascii_hexdigit()) && probe["digest"].as_str()==Some(previous)
}
fn manifest_matches_snapshot(snapshot:&Value,baseline:&Value)->bool {
    snapshot["items"].as_array().is_some_and(|rows|rows.iter().all(|item|item["url"].as_str().and_then(|url|url.split("/modules/items/").nth(1)).and_then(|tail|tail.split(['?','#','/']).next()).is_some_and(|id|item["completed"].is_boolean() && baseline["states"][id]==item["completed"])))
}
#[cfg(test)]
mod incremental_tests {
    use super::*;
    #[test]
    fn fresh_content_must_match_verified_hash() {
        let hash="a".repeat(64);
        assert!(reuse_manifest(&json!({"cacheable":true,"complete":true,"digest":hash}),&hash));
        assert!(!reuse_manifest(&json!({"cacheable":true,"complete":true,"digest":"b".repeat(64)}),&hash));
        assert!(!reuse_manifest(&json!({"cacheable":false,"complete":true,"digest":hash}),&hash));
        assert!(!reuse_manifest(&json!({"cacheable":true,"complete":false,"digest":hash}),&hash));
    }
    #[test]
    fn stale_dom_cannot_seed_a_newer_api_fingerprint() {
        let snapshot=json!({"items":[{"url":"/courses/1/modules/items/123","completed":false}]});
        assert!(manifest_matches_snapshot(&snapshot,&json!({"states":{"123":false}})));
        assert!(!manifest_matches_snapshot(&snapshot,&json!({"states":{"123":true}})));
        assert!(!manifest_matches_snapshot(&snapshot,&json!({"states":{}})));
        assert!(!manifest_matches_snapshot(&json!({"items":[{"url":"/courses/1/modules/items/123","completed":null}]}),&json!({"states":{"123":null}})));
    }
}

#[tauri::command]
pub async fn campus_collect(app: AppHandle, webview: Webview, run_id: String, cache: Option<Value>, attendance_sync: Option<bool>) -> Result<Value, String> {
    crate::auth::trusted(&webview, &["main"])?;
    if run_id.len() != 32 || !run_id.bytes().all(|b| b.is_ascii_hexdigit()) { return Err("INVALID_RUN".into()); }
    let state = app.state::<CampusState>();
    let epoch = state.epoch.load(Ordering::SeqCst);
    let _guard = state.gate.lock().await;
    current(&app, epoch)?;
    let view = worker(&app)?;
    let _hide = HideOnDrop(view.clone());
    let collection_deadline=Instant::now()+Duration::from_secs(180);
    let who = bounded_request(&app,&view,"identity",None,epoch,Duration::from_secs(12)).await?;
    let owner = who["owner"].as_str().ok_or("INVALID_OWNER")?;
    let courses = who["courses"].as_array().ok_or("INVALID_COURSES")?;
    let mut results = Vec::new();
    let mut responses = serde_json::Map::new();
    let known = cache.filter(|c|c["owner"].as_str()==Some(owner)).unwrap_or(Value::Null);
    let mut reused = 0;
    let courses_started = Instant::now();
    let attendance_enabled = attendance_sync.unwrap_or(false);
    for (index, course) in courses.iter().enumerate() {
        current(&app, epoch)?;
        let id = course["id"].as_u64().ok_or("INVALID_COURSE")?;
        progress(&app, &run_id, format!("{} / 주차학습 확인 중", course["name"].as_str().unwrap_or("수업")), false);
        let remaining=collection_deadline.saturating_duration_since(Instant::now());
        let remaining_seconds = if index == 0 {
            None
        } else {
            let average = courses_started.elapsed().as_secs_f64() / index as f64;
            let estimate = average * (courses.len() - index) as f64;
            Some(estimate.min(remaining.as_secs_f64()).ceil() as u64 + 1)
        };
        let _=app.emit_to("main","campus:progress",json!({"runId":run_id,"message":format!("{} 확인 중",course["name"].as_str().unwrap_or("수업")),"current":index,"total":courses.len(),"remainingSeconds":remaining_seconds}));
        if remaining.is_zero(){
            results.push(json!({"course_id":id,"error":"COLLECTION_BUDGET_EXCEEDED"}));
            responses.insert(format!("/api/v1/courses/{id}/assignments"),json!({"error":"COLLECTION_BUDGET_EXCEEDED"}));continue;
        }
        let course_deadline=Instant::now()+remaining.min(Duration::from_secs(45));
        let canvas=match bounded_request(&app,&view,"canvas-modules",Some(id),epoch,course_deadline.saturating_duration_since(Instant::now()).min(Duration::from_secs(13))).await {
            Ok(value)=>value,
            Err(error)=>{if error=="CANCELLED"||error=="AUTH_REQUIRED"{return Err(error);}json!({"status":"unavailable","complete":false,"items":[],"learningx":{"present":null},"warnings":["모듈 응답 시간 초과"]})}
        };
        match bounded_request(&app,&view,"assignments",Some(id),epoch,course_deadline.saturating_duration_since(Instant::now()).min(Duration::from_secs(8))).await {
            Ok(Value::Object(values))=>responses.extend(values),
            Ok(_)=>(),
            Err(error)=>{responses.insert(format!("/api/v1/courses/{id}/assignments"),json!({"error":error}));}
        }
        let need_lx=canvas["learningx"]["present"]!=false;
        let canvas_clear=canvas["complete"]==true && canvas["items"].as_array().is_some_and(|rows|rows.is_empty());
        let previous=known["videos"][id.to_string()].as_str().filter(|v|v.len()==64);
        let unchanged=if need_lx && canvas_clear { if let Some(digest)=previous {
            match bounded_request(&app,&view,"video-probe",Some(id),epoch,course_deadline.saturating_duration_since(Instant::now()).min(Duration::from_secs(8))).await {
                Ok(probe)=>reuse_manifest(&probe,digest),
                Err(error)=>{if error=="CANCELLED"{return Err(error);}false}
            }
        } else {false} } else {false};
        if unchanged {
            reused+=1;results.push(json!({"course_id":id,"unchanged":true,"fingerprint":previous}));
            progress(&app,&run_id,format!("과목 {id} 변경 없음: 저장된 영상 유지"),true);
        } else if !need_lx {
            results.push(json!({"course_id":id,"canvas":canvas,"sources_complete":canvas["complete"]==true,"verified":true}));
        } else {
            let budget=course_deadline.saturating_duration_since(Instant::now()).min(Duration::from_secs(30));
            let collected=tokio::time::timeout(budget,course_snapshot(&app,&view,owner,id,epoch,canvas["learningx"]["url"].as_str(),canvas["learningx"]["present"]==true)).await;
            match collected {
                Ok(Ok(snapshot))=>{
                    let baseline=bounded_request(&app,&view,"video-baseline",Some(id),epoch,course_deadline.saturating_duration_since(Instant::now()).min(Duration::from_secs(2))).await.unwrap_or(Value::Null);
                    let fingerprint=if canvas_clear && manifest_matches_snapshot(&snapshot,&baseline) && baseline["cacheable"]==true && baseline["complete"]==true {baseline["digest"].clone()}else{Value::Null};
                    results.push(json!({"course_id":id,"verified":true,"empty_confirmed":snapshot["items"].as_array().is_some_and(|v|v.is_empty()),"snapshot":snapshot,"fingerprint":fingerprint,"canvas":canvas,"sources_complete":canvas["complete"]==true}));
                }
                value=>{
                    let error=match value {Ok(Err(error))=>error,_=>"COURSE_CONTENT_TIMEOUT".into()};
                    if error=="CANCELLED"||error=="AUTH_REQUIRED"{return Err(error);}
                    cancel_reads(&view);
                    results.push(json!({"course_id":id,"canvas":canvas,"sources_complete":false,"error":error}));
                    progress(&app,&run_id,format!("과목 {id} 영상 확인 보류: {error}"),true);
                }
            }
        }

    }
    if attendance_enabled {
        let course_ids: Vec<u64> = courses.iter().filter_map(|course| course["id"].as_u64()).collect();
        let attendance_started = Instant::now();
        let attendance_deadline = attendance_started + Duration::from_secs(20);
        let batches = course_ids.chunks(3);
        let total_batches = batches.len();
        for (index, batch) in batches.enumerate() {
            current(&app, epoch)?;
            let remaining = attendance_deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() { break; }
            let seconds_per_batch = if index == 0 { 4.5 } else {
                attendance_started.elapsed().as_secs_f64() / index as f64
            };
            let estimate = (seconds_per_batch * (total_batches - index) as f64)
                .min(remaining.as_secs_f64()).ceil() as u64 + 1;
            let _ = app.emit_to("main", "campus:progress", json!({
                "runId": run_id, "message": "출결 확인 중", "current": courses.len(),
                "total": courses.len(), "remainingSeconds": estimate
            }));
            let budget = remaining.min(Duration::from_secs(6));
            match tokio::time::timeout(budget, request(&app, &view, "attendance-batch", json!(batch), epoch)).await {
                Ok(Ok(Value::Object(values))) => responses.extend(values),
                Ok(Err(error)) if error == "CANCELLED" => return Err(error),
                Err(_) => cancel_reads(&view),
                _ => (),
            }
        }
    }
    let _=app.emit_to("main","campus:progress",json!({"runId":run_id,"message":"변경 사항 저장 중","current":courses.len(),"total":courses.len()}));
    let final_identity = bounded_request(&app,&view,"owner",None,epoch,Duration::from_secs(8)).await?;
    if final_identity["owner"] != who["owner"] { return Err("AUTH_REQUIRED".into()); }
    let _ = view.hide();
    let result = json!({"owner":owner,"courses":courses,"results":results,"responses":responses,"transport":"webview2","reused_courses":reused,"attendance_sync":attendance_enabled});
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
                    let body = if setting { "<!doctype html><div id='probe'>Calix offline check</div>".to_string() } else { format!("<!doctype html><script>function ready(){{if(!document.hidden&&!document.getElementById('probe'))document.body.innerHTML=\"<div id='probe' data-shared='{shared}'>Calix offline check</div>\";}}document.addEventListener('visibilitychange',ready);document.addEventListener('DOMContentLoaded',ready);</script>") };
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
            let started=Instant::now();
            loop {
                if Instant::now()>deadline { return Err("WEBVIEW2_CHECK_TIMEOUT".to_string()); }
                let value=evaluate(&view,"({ready:!!document.getElementById('probe'),shared:document.getElementById('probe')?.dataset.shared,width:innerWidth,height:innerHeight,hidden:document.hidden,httpOnlyHidden:!document.cookie.includes('calix_probe')})".into()).await?;
                if started.elapsed()>=Duration::from_secs(3) && value["hidden"]==true { view.show().map_err(|e|e.to_string())?; }
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
