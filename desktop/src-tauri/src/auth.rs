use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, LogicalPosition, LogicalSize, Manager, Rect, Webview, WebviewUrl, WebviewWindowBuilder};
use tauri::webview::{NewWindowResponse, PageLoadEvent, WebviewBuilder};

pub struct AuthGate(pub Mutex<()>);

pub(crate) fn trusted(view: &Webview, labels: &[&str]) -> Result<(), String> {
    let url = view.url().map_err(|_| "창 주소를 확인하지 못했습니다.")?;
    let local = url.scheme() == "tauri" || url.host_str() == Some("tauri.localhost")
        || (cfg!(debug_assertions) && url.host_str() == Some("127.0.0.1") && url.port() == Some(5173));
    if !local || !labels.contains(&view.label()) { return Err("허용되지 않는 창입니다.".into()); }
    Ok(())
}

pub(crate) fn campus(url: &url::Url) -> bool {
    url.scheme() == "https" && url.port_or_known_default() == Some(443)
        && url.username().is_empty() && url.password().is_none()
        && url.host_str().is_some_and(|host| host == "bufs.ac.kr" || host.ends_with(".bufs.ac.kr"))
}

#[tauri::command]
pub async fn auth_open(app: AppHandle, webview: Webview, theme: Option<String>, font: Option<String>) -> Result<(), String> {
    trusted(&webview, &["main"])?;
    let gate = app.state::<AuthGate>();
    let _guard = gate.0.lock().map_err(|_| "로그인 창을 준비하지 못했습니다.")?;
    if let Some(window) = app.get_window("login") {
        window.unminimize().map_err(|_| "로그인 창을 복원하지 못했습니다.")?;
        window.show().map_err(|_| "로그인 창을 표시하지 못했습니다.")?;
        window.set_focus().map_err(|_| "로그인 창을 표시하지 못했습니다.")?;
        let _ = app.emit_to("login", "auth:theme", json!({"theme":theme,"font":font}));
        return Ok(());
    }
    let theme = theme.filter(|t| ["pink","sky","mint","purple","dark"].contains(&t.as_str())).unwrap_or("pink".into());
    let font = if font.as_deref() == Some("windows") { "windows" } else { "pretendard" };
    let page = format!("login.html?theme={theme}&font={font}");
    WebviewWindowBuilder::new(&app, "login", WebviewUrl::App(page.into()))
        .title("Calix 로그인").inner_size(1040.0, 780.0).min_inner_size(820.0, 600.0)
        .decorations(false).always_on_top(true).center().build()
        .map_err(|error| format!("로그인 창을 열지 못했습니다. ({error})"))?;
    Ok(())
}

#[derive(Deserialize)]
pub struct Bounds { x: f64, y: f64, width: f64, height: f64 }

#[tauri::command]
pub async fn auth_mount(app: AppHandle, webview: Webview, bounds: Bounds) -> Result<(), String> {
    trusted(&webview, &["login"])?;
    if [bounds.x,bounds.y,bounds.width,bounds.height].iter().any(|n| !n.is_finite() || *n < 0.0 || *n > 10000.0)
        || bounds.width < 100.0 || bounds.height < 100.0 { return Err("로그인 화면 크기를 확인하세요.".into()); }
    let gate = app.state::<AuthGate>();
    let _guard = gate.0.lock().map_err(|_| "로그인 창을 준비하지 못했습니다.")?;
    let rect = Rect { position: LogicalPosition::new(bounds.x,bounds.y).into(), size: LogicalSize::new(bounds.width,bounds.height).into() };
    if let Some(child) = app.get_webview("school-login") {
        child.set_bounds(rect).map_err(|_| "로그인 화면 크기를 적용하지 못했습니다.")?;
        child.show().map_err(|_| "로그인 화면을 표시하지 못했습니다.")?;
        return Ok(());
    }
    let window = app.get_window("login").ok_or("로그인 창이 닫혔습니다.")?;
    let directory = app.path().app_local_data_dir().map_err(|_| "로그인 저장소를 찾지 못했습니다.")?.join("campus-session");
    let page_app = app.clone();
    let popup_app = app.clone();
    let builder = WebviewBuilder::new("school-login", WebviewUrl::External("https://canvas.bufs.ac.kr/login".parse().unwrap()))
        .data_directory(directory).additional_browser_args(crate::campus::ARGS).incognito(false).general_autofill_enabled(false)
        .on_navigation(campus)
        .on_page_load(move |_view, payload| {
            let _ = page_app.emit_to("login", "auth:page", json!({"loaded":matches!(payload.event(),PageLoadEvent::Finished)}));
        })
        .on_new_window(move |url, _features| {
            if campus(&url) {
                let handle = popup_app.clone();
                tauri::async_runtime::spawn(async move {
                    if let Some(child) = handle.get_webview("school-login") { let _ = child.navigate(url); }
                });
            }
            NewWindowResponse::Deny
        });
    window.add_child(builder, LogicalPosition::new(bounds.x,bounds.y), LogicalSize::new(bounds.width,bounds.height))
        .map_err(|error| format!("학교 로그인 화면을 열지 못했습니다. ({error})"))?;
    Ok(())
}

#[tauri::command]
pub async fn auth_complete(app: AppHandle, webview: Webview) -> Result<(), String> {
    trusted(&webview, &["login"])?;
    let identity = crate::campus::identity_internal(&app).await.map_err(|error| {
        if error.contains("AUTH_REQUIRED") { "학교 로그인 후 완료를 누르세요.".to_string() }
        else if error.contains("INVALID_JSON") { "학교 응답을 읽지 못했습니다. 잠시 후 다시 시도하세요.".to_string() }
        else { format!("학교 로그인 상태를 확인하지 못했습니다. ({error})") }
    })?;
    app.emit_to("main", "auth:identity", identity).map_err(|_| "로그인 정보를 전달하지 못했습니다.".into())
}

#[tauri::command]
pub async fn auth_status(app: AppHandle, webview: Webview, success: bool, message: String) -> Result<(), String> {
    trusted(&webview, &["main"])?;
    let _ = app.emit_to("login", "auth:status", json!({"success":success,"message":message}));
    if success {
        if let Some(window) = app.get_window("login") {
            let visible = window.is_visible().unwrap_or(false);
            let _ = window.destroy();
            if visible { if let Some(main) = app.get_webview_window("main") { let _ = main.show();let _ = main.set_focus(); } }
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn auth_reload(app: AppHandle, webview: Webview) -> Result<(), String> {
    trusted(&webview, &["login"])?;
    if let Some(child) = app.get_webview("school-login") { child.reload().map_err(|_| "학교 화면을 새로고침하지 못했습니다.")?; }
    Ok(())
}

#[tauri::command]
pub async fn auth_logout(app: AppHandle, webview: Webview) -> Result<(), String> {
    trusted(&webview, &["main"])?;
    if let Some(child) = app.get_webview("school-login") {
        tauri::async_runtime::spawn_blocking(move || child.clear_all_browsing_data()).await
            .map_err(|_| "로그아웃하지 못했습니다.")?.map_err(|_| "로그아웃하지 못했습니다.")?;
    } else {
        let directory = app.path().app_local_data_dir().map_err(|_| "로그인 저장소를 찾지 못했습니다.")?.join("campus-session");
        if directory.exists() {
            let cleanup = WebviewWindowBuilder::new(&app, "session-clear", WebviewUrl::External("about:blank".parse().unwrap()))
                .data_directory(directory).additional_browser_args(crate::campus::ARGS).visible(false).skip_taskbar(true).build().map_err(|_| "로그아웃을 준비하지 못했습니다.")?;
            let view = cleanup.clone();
            let result = tauri::async_runtime::spawn_blocking(move || view.clear_all_browsing_data()).await
                .map_err(|_| "로그아웃하지 못했습니다.")?;
            let _ = cleanup.destroy();
            result.map_err(|_| "로그아웃하지 못했습니다.")?;
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn backup_file(app: AppHandle, webview: Webview, mode: String) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    trusted(&webview, &["main"])?;
    if mode != "backup" && mode != "restore" { return Err("작업을 확인하세요.".into()); }
    let parent = app.get_webview_window("main").ok_or("메인 창을 찾지 못했습니다.")?;
    let dialog = app.dialog().file().set_parent(&parent).add_filter("Calix backup", &["calix"]);
    let result = if mode == "backup" { dialog.set_file_name("Calix-backup.calix").blocking_save_file() } else { dialog.blocking_pick_file() };
    result.map(|path| path.into_path().map(|path| path.to_string_lossy().into_owned()).map_err(|_| "파일 경로를 확인하지 못했습니다.".into())).transpose()
}
