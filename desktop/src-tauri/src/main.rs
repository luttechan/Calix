#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod reminder;
use tauri::{Emitter, Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState};
mod auth;
mod campus;
#[cfg(windows)]
mod taskbar;

#[derive(Default)]
pub struct DeveloperState(pub std::sync::atomic::AtomicBool);

const CONSOLE_WINDOW: &str = "developer-console";
const DEFAULT_THEME: &str = "aurora";
const THEMES: &[&str] = &[
    DEFAULT_THEME, "aurora-dawn", "aurora-dusk", "pink", "sky", "mint", "purple", "dark",
    "peach", "amber", "olive", "lavender",
];

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
    close_developer_console(&app);
    if let Some(window) = app.get_webview_window("main") { window.close_devtools(); let _=window.set_always_on_top(false); }
    campus::campus_debug(app, webview, false)
}

pub fn focus_developer(app: &tauri::AppHandle) {
    if app.state::<DeveloperState>().0.load(std::sync::atomic::Ordering::SeqCst) {
        if let Some(window) = app.get_webview_window(CONSOLE_WINDOW) {
            let _ = window.unminimize();
            let _ = window.show();
            let _ = window.set_focus();
        }
    }
}

fn restore_developer_priority(app: &tauri::AppHandle) {
    use std::sync::atomic::Ordering;
    if app.state::<DeveloperState>().0.swap(false, Ordering::SeqCst) {
        for label in ["login", "reminder"] {
            if let Some(window) = app.get_webview_window(label) {
                let _ = window.set_always_on_top(true);
            }
        }
        let _ = app.emit_to("main", "developer-console:closed", ());
    }
}

fn close_developer_console(app: &tauri::AppHandle) {
    restore_developer_priority(app);
    if let Some(window) = app.get_webview_window(CONSOLE_WINDOW) {
        let _ = window.destroy();
    }
}

pub(crate) fn create_developer_console_window(
    app: &tauri::AppHandle,
    test_profile: Option<&std::path::Path>,
) -> Result<tauri::WebviewWindow, String> {
    let mut builder = WebviewWindowBuilder::new(app, CONSOLE_WINDOW, WebviewUrl::App("developer-console.html".into()))
        .title("Calix Console")
        .inner_size(900.0, 620.0)
        .min_inner_size(580.0, 420.0)
        .additional_browser_args(reminder::UI_ARGS)
        .always_on_top(true);
    if let Some(profile) = test_profile {
        builder = builder.visible(false).data_directory(profile.to_path_buf());
    }
    builder.build().map_err(|error| error.to_string())
}

#[tauri::command]
async fn developer_console(app: tauri::AppHandle, webview: tauri::Webview, open: bool) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    if !open {
        close_developer_console(&app);
        return Ok(());
    }
    require_developer()?;
    if app.get_webview_window(CONSOLE_WINDOW).is_none() {
        create_developer_console_window(&app, None)?;
    }
    app.state::<DeveloperState>().0.store(true, std::sync::atomic::Ordering::SeqCst);
    for label in ["main", "login", "reminder"] {
        if let Some(window) = app.get_webview_window(label) {
            let _ = window.set_always_on_top(false);
        }
    }
    focus_developer(&app);
    Ok(())
}

#[tauri::command]
fn developer_console_publish(app: tauri::AppHandle, webview: tauri::Webview, state: serde_json::Value) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    require_developer()?;
    if app.get_webview_window(CONSOLE_WINDOW).is_none() { return Ok(()); }
    app.emit_to(CONSOLE_WINDOW, "developer-console:update", state).map_err(|error| error.to_string())
}

#[tauri::command]
fn developer_console_action(app: tauri::AppHandle, webview: tauri::Webview, action: String) -> Result<(), String> {
    auth::trusted(&webview, &[CONSOLE_WINDOW])?;
    require_developer()?;
    if !matches!(action.as_str(), "ready" | "sync" | "force" | "dismiss" | "cancel" | "capture" | "pause") {
        return Err("Unknown console action.".into());
    }
    app.emit_to("main", "developer-console:action", action).map_err(|error| error.to_string())
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
fn quit_app(app: tauri::AppHandle, webview: tauri::Webview) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    #[cfg(windows)]
    clear_taskbar_identity(&app);
    app.exit(0);
    Ok(())
}
#[tauri::command]
fn restart_app(app: tauri::AppHandle, webview: tauri::Webview) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    #[cfg(windows)]
    clear_taskbar_identity(&app);
    app.restart();
}
#[tauri::command]
fn app_ready(app: tauri::AppHandle, webview: tauri::Webview) -> Result<(), String> {
    auth::trusted(&webview, &["main"])?;
    if let Some(window) = app.get_webview_window("main") { let _ = window.set_always_on_top(false); }
    Ok(())
}

fn show(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize(); let _ = window.show(); let _ = window.set_focus();
    }
}

fn position_main_window(window: &tauri::WebviewWindow) -> tauri::Result<()> {
    let monitor = window.current_monitor()?.or(window.primary_monitor()?);
    let Some(monitor) = monitor else { return window.center(); };
    let area = monitor.work_area();
    let original = window.outer_size()?;
    let width = original.width.min(area.size.width);
    let height = original.height.min(area.size.height);
    let x = area.position.x + ((area.size.width - width) / 2) as i32;
    let y = area.position.y + ((area.size.height - height) / 2) as i32;
    #[cfg(windows)]
    {
        use windows::Win32::UI::WindowsAndMessaging::{SetWindowPos, SWP_NOACTIVATE, SWP_NOZORDER};
        let hwnd = windows::Win32::Foundation::HWND(window.hwnd()?.0);
        // Set the outer bounds together. Tauri's set_size sets the client area
        // and can add the Windows shadow frame back to the requested size.
        return unsafe { SetWindowPos(hwnd, None, x, y, width as i32, height as i32, SWP_NOACTIVATE | SWP_NOZORDER) }
            .map_err(|error| std::io::Error::other(error).into());
    }
    #[cfg(not(windows))]
    {
        if width != original.width || height != original.height {
            let client = window.inner_size()?;
            let frame_width = original.width.saturating_sub(client.width);
            let frame_height = original.height.saturating_sub(client.height);
            window.set_size(tauri::PhysicalSize::new(
                width.saturating_sub(frame_width),
                height.saturating_sub(frame_height),
            ))?;
        }
        window.set_position(tauri::PhysicalPosition::new(x, y))
    }
}

#[cfg(windows)]
fn register_taskbar_identity(identifier: &str) {
    #[link(name = "shell32")]
    extern "system" {
        fn SetCurrentProcessExplicitAppUserModelID(app_id: *const u16) -> i32;
    }
    let identifier: Vec<u16> = identifier.encode_utf16().chain(std::iter::once(0)).collect();
    // Windows reads this null-terminated string before any window is created.
    unsafe { SetCurrentProcessExplicitAppUserModelID(identifier.as_ptr()) };
}

#[cfg(windows)]
fn clear_taskbar_identity(app: &tauri::AppHandle) {
    if let Some(hwnd) = app.get_webview_window("main").and_then(|window| window.hwnd().ok()) {
        taskbar::clear_identity(windows::Win32::Foundation::HWND(hwnd.0));
    }
}

#[cfg(windows)]
fn verify_taskbar_identity(app: &tauri::App, title: &str) -> Result<String, String> {
    let probe = tauri::window::WindowBuilder::new(app, "taskbar-probe")
        .visible(false)
        .skip_taskbar(true)
        .build()
        .map_err(|error| error.to_string())?;
    // The hidden probe stays open until the self-check exits the application.
    // Destroying the only window here could end the event loop before the WebView check starts.
    probe.hwnd().map_err(|error| error.to_string()).and_then(|hwnd| {
        taskbar::verify_identity(windows::Win32::Foundation::HWND(hwnd.0), &app.config().identifier, title)
    })
}

#[tauri::command]
async fn privacy_lock(app: tauri::AppHandle) {
    close_developer_console(&app);
    if let Some(window) = app.get_webview_window("main") { window.close_devtools(); }
    if let Some(window) = app.get_webview_window("login") { let _ = window.hide(); }
    let _ = reminder::dismiss_window(app).await;
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let reminder_check=args.iter().any(|arg|arg=="--reminder-check");
    let check = args.iter().position(|arg| arg == "--campus-check" || arg == "--reminder-check").and_then(|index|args.get(index+1)).cloned();
    let mut context = tauri::generate_context!();
    #[cfg(windows)]
    if check.is_none() {
        register_taskbar_identity(&context.config().identifier);
    }
    let window_title = format!("Calix ({})", env!("CARGO_PKG_VERSION"));
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
        .invoke_handler(tauri::generate_handler![privacy_lock, reminder::reminder_show, reminder::reminder_payload, reminder::reminder_ready, reminder::reminder_close, reminder::reminder_open_event, developer_console, developer_console_publish, developer_console_action, developer_disable, developer_devtools, developer_export, campus::campus_identity, campus::campus_collect, campus::campus_cancel, campus::campus_debug, quit_app, restart_app, app_ready, auth::auth_open, auth::auth_mount, auth::auth_complete, auth::auth_status, auth::auth_reload, auth::auth_logout, auth::backup_file])
        .setup(move |app| {
            if let Some(path) = check.clone() {
                #[cfg(windows)]
                let taskbar_check = (!reminder_check).then(|| verify_taskbar_identity(app, &window_title));
                let handle=app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    let result=if reminder_check {reminder::self_check(handle.clone()).await}else{campus::self_check(handle.clone()).await};
                    let mut report=result.unwrap_or_else(|error|serde_json::json!({"passed":false,"error":error}));
                    report["mainWindowTitle"] = serde_json::Value::String(window_title);
                    #[cfg(windows)]
                    if let Some(check) = taskbar_check {
                        match check {
                            Ok(name) => report["taskbarDisplayName"] = serde_json::Value::String(name),
                            Err(error) => {
                                report["taskbarError"] = serde_json::Value::String(error);
                                report["passed"] = serde_json::Value::Bool(false);
                            }
                        }
                    }
                    let passed = report["passed"].as_bool() == Some(true);
                    let _=std::fs::write(path,report.to_string());
                    handle.exit(if passed {0}else{1});
                });
                return Ok(());
            }
            #[cfg(windows)]
            if let Some(hwnd) = app.get_webview_window("main").and_then(|window| window.hwnd().ok()) {
                if let Err(error) = taskbar::set_identity(windows::Win32::Foundation::HWND(hwnd.0), &app.config().identifier, &window_title) {
                    eprintln!("Could not set the Windows taskbar title: {error}");
                }
            }
            let open = MenuItem::with_id(app, "open", "열기", true, None::<&str>)?;
            let exit = MenuItem::with_id(app, "exit", "종료", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &exit])?;
            let mut tray = TrayIconBuilder::new().tooltip(window_title.clone()).menu(&menu)
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
            if let Some(window) = app.get_webview_window("main") {
                let _ = position_main_window(&window);
                window.show()?;
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() == CONSOLE_WINDOW && matches!(event, WindowEvent::Destroyed) {
                restore_developer_priority(window.app_handle());
            }
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
    let builder = if check_mode { builder } else { builder.plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
        show(app);
        let _ = app.emit_to("main", "app:launch", ());
    })) };
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
