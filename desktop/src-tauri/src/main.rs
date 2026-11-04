#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod reminder;
use tauri::{Emitter, Manager, WindowEvent};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState};
mod auth;
mod campus;

#[derive(Default)]
pub struct DeveloperState(pub std::sync::atomic::AtomicBool);

fn developer_settings_enabled(value: &serde_json::Value) -> bool {
    value["developer_mode"].as_bool() == Some(true) && value["developer_acknowledged"].as_bool() == Some(true)
}

pub(crate) fn require_developer() -> Result<(), String> {
    let enabled = std::env::var_os("APPDATA").map(std::path::PathBuf::from)
        .map(|path|path.join("LutteLaurent/Calix/settings.json"))
        .and_then(|path|std::fs::metadata(&path).ok().filter(|meta|meta.len() <= 5_000_000).and_then(|_|std::fs::read(path).ok()))
        .and_then(|data|serde_json::from_slice::<serde_json::Value>(&data).ok())
        .is_some_and(|value|developer_settings_enabled(&value));
    if enabled { Ok(()) } else { Err("Developer Mode is disabled.".into()) }
}

#[tauri::command]
fn developer_disable(app: tauri::AppHandle, webview: tauri::Webview) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    app.state::<DeveloperState>().0.store(false, std::sync::atomic::Ordering::SeqCst);
    if let Some(window) = app.get_webview_window("main") { window.close_devtools(); let _=window.set_always_on_top(false); }
    campus::campus_debug(app, webview, false)
}

pub fn focus_developer(app: &tauri::AppHandle) {
    if app.state::<DeveloperState>().0.load(std::sync::atomic::Ordering::SeqCst) {
        if let Some(window)=app.get_webview_window("main") { let _=window.set_always_on_top(true);let _=window.unminimize();let _=window.show();let _=window.set_focus(); }
    }
}
#[tauri::command]
fn developer_console(app: tauri::AppHandle, webview: tauri::Webview, open: bool) -> Result<(),String> {
    auth::trusted(&webview,&["main"])?;
    if open { require_developer()?; }
    app.state::<DeveloperState>().0.store(open,std::sync::atomic::Ordering::SeqCst);
    if let Some(window)=app.get_webview_window("main") { window.set_always_on_top(open).map_err(|_|"Unable to prioritize Live Console.")?; }
    if let Some(window)=app.get_webview_window("login") { let _=window.set_always_on_top(!open); }
    if let Some(window)=app.get_webview_window("reminder") { let _=window.set_always_on_top(!open); }
    focus_developer(&app);
    Ok(())
}

#[tauri::command]
async fn developer_devtools(app: tauri::AppHandle, webview: tauri::Webview) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    require_developer()?;
    let window = app.get_webview_window("main").ok_or("Main window unavailable.")?;
    window.open_devtools();
    Ok(())
}

#[tauri::command]
async fn developer_export(app: tauri::AppHandle, webview: tauri::Webview, report: serde_json::Value) -> Result<bool, String> {
    use tauri_plugin_dialog::DialogExt;
    auth::trusted(&webview, &["main"])?;
    require_developer()?;
    let content = serde_json::to_vec_pretty(&report).map_err(|_| "Invalid diagnostics report.")?;
    if content.len() > 4 * 1024 * 1024 { return Err("Diagnostics report exceeds the size limit.".into()); }
    let parent = app.get_webview_window("main").ok_or("Main window unavailable.")?;
    let selected = app.dialog().file().set_parent(&parent).add_filter("JSON report", &["json"])
        .set_file_name("Calix-diagnostics.json").blocking_save_file();
    let Some(selected) = selected else { return Ok(false); };
    let path = selected.into_path().map_err(|_| "Invalid destination.")?;
    std::fs::write(path, content).map_err(|_| "Unable to save diagnostics report.")?;
    Ok(true)
}

#[tauri::command]
fn quit_app(app: tauri::AppHandle, webview: tauri::Webview) -> Result<(), String> { auth::trusted(&webview, &["main"])?;app.exit(0);Ok(()) }
#[tauri::command]
fn restart_app(app: tauri::AppHandle, webview: tauri::Webview) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    app.restart();
}
#[tauri::command]
fn app_ready(app: tauri::AppHandle, webview: tauri::Webview) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    if let Some(window) = app.get_webview_window("main") { let _ = window.set_always_on_top(app.state::<DeveloperState>().0.load(std::sync::atomic::Ordering::SeqCst)); }
    Ok(())
}

fn show(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize(); let _ = window.show(); let _ = window.set_focus();
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let reminder_check=args.iter().any(|arg|arg=="--reminder-check");
    let check = args.iter().position(|arg| arg == "--campus-check" || arg == "--reminder-check").and_then(|index|args.get(index+1)).cloned();
    let mut context = tauri::generate_context!();
    let window_title = format!("Calix {}", env!("CARGO_PKG_VERSION"));
    for window in &mut context.config_mut().app.windows {
        if window.label == "main" {
            window.title = window_title.clone();
        }
    }
    if check.is_some() { context.config_mut().app.windows.clear(); }
    let check_mode = check.is_some();
    let builder = tauri::Builder::default()
        .manage(campus::CampusState::default())
        .manage(DeveloperState::default())
        .manage(reminder::ReminderState::default())
        .manage(auth::AuthGate(std::sync::Mutex::new(())))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![reminder::reminder_show, reminder::reminder_payload, reminder::reminder_close, reminder::reminder_open_event, developer_console, developer_disable, developer_devtools, developer_export, campus::campus_identity, campus::campus_collect, campus::campus_cancel, campus::campus_debug, quit_app, restart_app, app_ready, auth::auth_open, auth::auth_mount, auth::auth_complete, auth::auth_status, auth::auth_reload, auth::auth_logout, auth::backup_file])
        .setup(move |app| {
            if let Some(path) = check.clone() {
                let handle=app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    let result=if reminder_check {reminder::self_check(handle.clone()).await}else{campus::self_check(handle.clone()).await};
                    let passed=result.is_ok();
                    let mut report=result.unwrap_or_else(|error|serde_json::json!({"passed":false,"error":error}));
                    report["mainWindowTitle"] = serde_json::Value::String(window_title);
                    let _=std::fs::write(path,report.to_string());
                    handle.exit(if passed {0}else{1});
                });
                return Ok(());
            }
            let open = MenuItem::with_id(app, "open", "열기", true, None::<&str>)?;
            let exit = MenuItem::with_id(app, "exit", "종료", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &exit])?;
            let mut tray = TrayIconBuilder::new().tooltip("Calix").menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => show(app),
                    "exit" => { show(app); let _ = app.emit("app:exit-request", ()); },
                    _ => ()
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event { show(tray.app_handle()); }
                });
            if let Some(icon) = app.default_window_icon() { tray = tray.icon(icon.clone()); }
            tray.build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" { api.prevent_close();let _ = window.emit("app:hidden", ());let _ = window.hide(); }
                else if window.label() == "reminder" {
                    api.prevent_close();
                    let app=window.app_handle().clone();
                    tauri::async_runtime::spawn(async move {let _=reminder::dismiss_window(app).await;});
                }
                else if window.label() == "login" { let _ = window.app_handle().emit_to("main", "auth:dismissed", ()); }
            }
        })
        ;
    let builder = if check_mode { builder } else { builder.plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show(app))) };
    builder.run(context).expect("Calix failed to start");
}

#[cfg(test)]
mod developer_gate_tests {
    use super::*;
    #[test]
    fn developer_tools_require_explicit_boolean_consent() {
        assert!(developer_settings_enabled(&serde_json::json!({"developer_mode":true,"developer_acknowledged":true})));
        for value in [serde_json::json!({}),serde_json::json!({"developer_mode":true}),serde_json::json!({"developer_mode":"true","developer_acknowledged":true}),serde_json::json!({"developer_mode":true,"developer_acknowledged":false})] { assert!(!developer_settings_enabled(&value)); }
    }
}
