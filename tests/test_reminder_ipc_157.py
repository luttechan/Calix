from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_popup_does_not_import_the_main_app_or_start_an_engine():
    for name in ('reminder-entry.tsx', 'ReminderWindow.tsx', 'reminderState.ts'):
        code=(ROOT/'desktop/src'/name).read_text(encoding='utf-8')
        assert 'from "./App"' not in code and "from './App'" not in code
        assert 'bridge' not in code and 'sidecar' not in code
    assert 'reminder-entry.tsx' in (ROOT/'desktop/reminder.html').read_text(encoding='utf-8')

def test_windows_reminder_commands_do_not_block_the_ipc_thread():
    code=(ROOT/'desktop/src-tauri/src/reminder.rs').read_text(encoding='utf-8')
    for command in ('reminder_show', 'reminder_close', 'reminder_open_event'):
        assert f'pub async fn {command}' in code
    assert 'spawn_blocking(move ||show(' in code
    assert 'state.gate.lock().await' in code
    assert 'WebviewUrl::App("reminder.html".into())' in code
    assert 'index.html?reminder' not in code

def test_native_check_uses_real_ipc_and_checks_backup_responsiveness():
    code=(ROOT/'desktop/src/reminder-probe.ts').read_text(encoding='utf-8')
    assert 'reminder_show' in code and 'backup_file' in code
    assert 'STALE_CLOSE_REMOVED_NEW_REMINDER' in code
    assert 'CLOSE_REOPEN_ORDER' in code
