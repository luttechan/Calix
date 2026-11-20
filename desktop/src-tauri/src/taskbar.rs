use windows::core::{GUID, Result};
use windows::Win32::Foundation::{HWND, PROPERTYKEY};
use windows::Win32::System::Com::StructuredStorage::{
    PropVariantChangeType, PROPVARIANT, PROPVAR_CHANGE_FLAGS,
};
use windows::Win32::System::Variant::VT_LPWSTR;
use windows::Win32::UI::Shell::PropertiesSystem::{IPropertyStore, SHGetPropertyStoreForWindow};

const APP_MODEL_FMTID: GUID = GUID::from_u128(0x9f4c2855_9f79_4b39_a8d0_e1d42de1d5f3);
const RELAUNCH_COMMAND: PROPERTYKEY = PROPERTYKEY { fmtid: APP_MODEL_FMTID, pid: 2 };
const DISPLAY_NAME: PROPERTYKEY = PROPERTYKEY { fmtid: APP_MODEL_FMTID, pid: 4 };
const APP_ID: PROPERTYKEY = PROPERTYKEY { fmtid: APP_MODEL_FMTID, pid: 5 };

fn set_string(store: &IPropertyStore, key: &PROPERTYKEY, value: &str) -> Result<()> {
    let mut variant = PROPVARIANT::default();
    let string = PROPVARIANT::from(value);
    unsafe {
        PropVariantChangeType(&mut variant, &string, PROPVAR_CHANGE_FLAGS(0), VT_LPWSTR)?;
        store.SetValue(key, &variant)
    }
}

pub fn set_identity(hwnd: HWND, app_id: &str, title: &str) -> std::result::Result<(), String> {
    let executable = std::env::current_exe().map_err(|error| error.to_string())?;
    let command = format!("\"{}\"", executable.display());
    let store: IPropertyStore = unsafe { SHGetPropertyStoreForWindow(hwnd) }
        .map_err(|error| error.to_string())?;
    // Set the command and title first. Assigning the window ID refreshes the taskbar entry.
    let result = set_string(&store, &RELAUNCH_COMMAND, &command)
        .and_then(|_| set_string(&store, &DISPLAY_NAME, title))
        .and_then(|_| set_string(&store, &APP_ID, app_id))
        .map_err(|error| error.to_string());
    if result.is_err() {
        clear_identity(hwnd);
    }
    result
}

pub fn clear_identity(hwnd: HWND) {
    if let Ok(store) = unsafe { SHGetPropertyStoreForWindow::<IPropertyStore>(hwnd) } {
        let empty = PROPVARIANT::default();
        for key in [&APP_ID, &DISPLAY_NAME, &RELAUNCH_COMMAND] {
            let _ = unsafe { store.SetValue(key, &empty) };
        }
    }
}

pub fn verify_identity(hwnd: HWND, app_id: &str, title: &str) -> std::result::Result<String, String> {
    set_identity(hwnd, app_id, title)?;
    let result = (|| {
        let store: IPropertyStore = unsafe { SHGetPropertyStoreForWindow(hwnd) }
            .map_err(|error| error.to_string())?;
        let read = |key| unsafe { store.GetValue(key) }.map(|value| value.to_string()).map_err(|error| error.to_string());
        let name = read(&DISPLAY_NAME)?;
        let command = read(&RELAUNCH_COMMAND)?;
        if name != title || read(&APP_ID)? != app_id || !command.starts_with('"') || !command.ends_with('"') {
            return Err("Unexpected Windows taskbar identity.".into());
        }
        Ok(name)
    })();
    clear_identity(hwnd);
    result
}
