#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use tauri::{Emitter, Manager, WindowEvent};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState};
mod auth;

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
    if let Some(window) = app.get_webview_window("main") { let _ = window.set_always_on_top(false); }
    Ok(())
}

fn show(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize(); let _ = window.show(); let _ = window.set_focus();
    }
}

fn main() {
    tauri::Builder::default()
        .manage(auth::AuthGate(std::sync::Mutex::new(())))
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show(app)))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![quit_app, restart_app, app_ready, auth::auth_open, auth::auth_mount, auth::auth_complete, auth::auth_status, auth::auth_reload, auth::auth_logout, auth::backup_file])
        .setup(|app| {
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
                else if window.label() == "login" { let _ = window.app_handle().emit_to("main", "auth:dismissed", ()); }
            }
        })
        .run(tauri::generate_context!())
        .expect("Calix failed to start");
}
