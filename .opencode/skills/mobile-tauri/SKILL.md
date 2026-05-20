---
name: mobile-tauri
description: Tauri 2.x + SvelteKit: Rust backend integration (Serde, Tokio, SQLx), IPC commands, event system, desktop features (tray, menu, notifications), cross-platform builds, and secure patterns
license: MIT
compatibility: opencode
metadata:
  audience: mobile-developers
  domain: mobile
  paradigm: native-webview
  integrates_with: [frontend-svelte, mobile-flutter, security-crypto, backend-go, database-postgres]
---

## Mobile Tauri + SvelteKit Skill

### Tauri 2.x Architecture
```
Frontend (WebView) ←--- IPC (invoke/emit) ---→ Rust Backend
  SvelteKit/Svelte 5                            └─ Commands (tauri::command)
  Web API access                                └─ Events (emit/listen)
                                                └─ Plugin system
                                                └─ File system (safe paths)
```

### Rust Backend
- **Commands (#[tauri::command])**: async or sync; AppHandle/Window for state access; serde for args/return
- **State management**: tauri::State<T> for shared app state; Mutex/RwLock for thread safety
- **Plugin system**: tauri::plugin::Builder; register JS API + Rust commands; scoped permissions
- **File system**: std::fs operations; resolve paths relative to app dir; NEVER full filesystem access
- **Database**: SQLx (async PostgreSQL/SQLite); SeaORM for ORM; migrations embedded

### IPC (Inter-Process Communication)
- **invoke('command_name', { args })**: Frontend → Backend; typed with serde; error via Result
- **listen('event', callback)**: Backend → Frontend; windows.emit for broadcast; app_handle.emit for global
- **Channel**: For streaming data (file progress, logs); JS channel with onmessage
- **Security**: CSP headers enforced; danger_disable_asset_csp only when absolutely necessary

### Desktop Features
- **System tray**: TrayIconBuilder; menu items, tooltip, events; conditional compilation per platform
- **Window management**: WindowBuilder (size, position, decorations); multiple windows; drag regions
- **Menu**: Custom menu bar (macOS global); Menu::with_items; accelerators
- **Notifications**: tauri-plugin-notification; native OS notifications
- **Auto-updater**: tauri-plugin-updater; check on startup; download and install

### SvelteKit Frontend
- **Static adapter**: @sveltejs/adapter-static; fallback: 'index.html' for SPA mode
- **Tauri integration**: @tauri-apps/api (invoke, event, window, path, fs)
- **State**: Svelte 5 runes ($state, $derived) for reactive state; stores for IPC-cached data
- **Routing**: Client-side routing; no server-side rendering in Tauri

### Build Configuration (tauri.conf.json)
- **Identifier**: Reverse domain (com.example.app); unique per app
- **Bundle**: Resources to include; icons per platform; file associations
- **Security capabilities**: Whitelist only needed APIs; deny all by default
- **Platform-specific**: Target macOS 10.15+, Windows 10+, Ubuntu 20.04+

### Security Rules for Tauri
- **Disable eval**: CSP: script-src 'self'; no unsafe-eval
- **IPC validation**: Validate all invoke arguments in Rust; never trust frontend
- **Scope filesystem**: Only access app-specific directories; path traversal prevention
- **No remote content**: Don't load external scripts; bundle everything

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Full filesystem access | Malicious web content could read/write any file | Scope file access to app-specific directories; use Tauri path plugin with base dirs |
| Enabling `danger_disable_asset_csp` | CSP disabled opens XSS attack surface in WebView | Never disable CSP in production; define explicit `script-src 'self'` |
| Calling heavy Rust functions from UI thread | Blocks IPC; UI freezes | Use `tauri::async_runtime::spawn` for async; `tokio::task::spawn_blocking` for CPU-bound work |
| Exposing Tauri commands without auth | Any frontend code can call any `#[tauri::command]` | Validate all command arguments in Rust; never trust frontend input |
| Not handling IPC errors | invoke().then() without .catch() silently fails | Always add `.catch()` to `invoke()` calls; return `Result` from Rust commands |
| Storing secrets in frontend JS | Any secret in SvelteKit frontend is trivially extractable | Keep secrets only in Rust backend; use OS keychain via Tauri plugin |
| Mixing Tauri and browser APIs for filesystem | `window.__TAURI__` env vs browser `File` API; inconsistent behavior | Always check for Tauri environment; use `@tauri-apps/api` exclusively for native features |
| Not bundling resources correctly | Images, fonts, config files missing in production build | Use `tauri.conf.json > bundle > resources`; test `tauri build` output |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| `invoke` returns `Unhandled Promise Rejection` | Rust command panicked or returned `Err` | Check Rust backend logs; add `.catch(console.error)` | Use `Result` types; implement proper error handling in commands |
| `command not found` | Command name mismatch between Rust and frontend | Verify `#[tauri::command] fn my_command()` matches `invoke('my_command')` | Use snake_case consistently; register command in `tauri::Builder` |
| WebView shows blank screen | SvelteKit build output not found; path mismatch in `tauri.conf.json` | Check `frontendDist` path; verify build output directory | Set `frontendDist: "../build"` matching SvelteKit adapter-static output |
| `Permission denied` on file ops | Tauri scope doesn't include requested path | Check `tauri.conf.json > allowlist > fs > scope` | Add allowed paths; use `appDir`, `dataDir`, etc. |
| App crashes on launch (Windows) | Missing WebView2 runtime | Check event viewer for WebView2 errors | Bundle WebView2 installer or detect and prompt installation |
| Slow IPC response (>100ms) | Blocking computation in Rust command; data serialization overhead | Profile with `console.time` around `invoke()` | Move heavy work to background thread; use channels for progress |
| Build fails with linking errors | Missing system dependencies (libwebkit2gtk, libappindicator on Linux) | Check build output for missing `-dev` packages | Install dependencies: `sudo apt install libwebkit2gtk-4.1-dev ...` |

### Implementation Checklist

- [ ] `tauri.conf.json` configured with correct identifier, bundle, and security settings
- [ ] CSP headers: `script-src 'self'` — no `unsafe-eval` in production
- [ ] Filesystem access scoped to app directories only
- [ ] All Tauri commands validate input in Rust (never trust frontend)
- [ ] IPC error handling on both frontend (`.catch()`) and backend (`Result`)
- [ ] Secrets stored in OS keychain, never in frontend code
- [ ] Rust backend uses `tokio::spawn_blocking` for CPU-bound work
- [ ] SvelteKit adapter-static configured for SPA mode
- [ ] Cross-platform build tested (Windows, macOS, Linux)
- [ ] App signing: `codesign` (macOS), code signing certificate (Windows)
- [ ] Auto-updater plugin configured with update server endpoint
- [ ] File associations configured in `tauri.conf.json` if needed
- [ ] System tray, menu, and notifications tested
- [ ] `.gitignore` includes `src-tauri/target/` and build artifacts
- [ ] CI/CD pipeline configured for all target platforms
- [ ] App tested on minimum supported OS versions (macOS 10.15+, Windows 10+)
