---
name: mobile-flutter
description: Flutter + Riverpod: Dart mastery, widget architecture, Riverpod 2.x providers, platform channels, performance optimization, Flutter Web/Desktop, and testing hierarchy (unit/widget/integration)
license: MIT
compatibility: opencode
metadata:
  audience: mobile-developers
  domain: mobile
  paradigm: declarative-ui
  integrates_with: [frontend-animation, mobile-tauri, database-postgres, security-crypto, backend-python]
---

## Mobile Flutter & Dart Skill

### Dart Mastery
- **Null safety**: Always sound null safety; late for deferred init; ? nullable; ! assertion (avoid in prod)
- **Async**: Future/async/await; Stream for sequences; StreamBuilder for UI binding; isolates for background
- **Extension methods**: Add functionality to existing types without subclassing
- **Sealed classes**: Exhaustive pattern matching (Dart 3+); ideal for state/result types
- **Records & Patterns**: Destructuring, switch expressions, pattern matching (Dart 3+)
- **Freezed**: Code gen for immutable classes; union types, copyWith, JSON serialization

### Widget Architecture
- **Composition > Inheritance**: Compose small StatelessWidgets; StatefulWidget only when needed
- **Keys**: ValueKey for lists with stable IDs; GlobalKey rarely (access state from parent)
- **BuildContext**: Never access context before build completes; don't store in class fields
- **Layout builders**: LayoutBuilder for responsive; use constraints (BoxConstraints) for layout logic
- **Slivers**: CustomScrollView + SliverList/SliverGrid/SliverAppBar for complex scrolling

### Riverpod 2.x
- **Provider types**:
  - `Provider<T>`: Read-only, recomputed on dependency change
  - `StateProvider<T>`: Simple mutable state
  - `NotifierProvider<T>` / `AsyncNotifierProvider<T>`: Complex state with async support
  - `FutureProvider<T>`: Single async result; auto-refetch
  - `StreamProvider<T>`: Real-time data stream
- **Modifiers**: `.autoDispose` for automatic cleanup; `.family` for parameterized providers
- **Widgets**: Consumer/ConsumerWidget for rebuilder; ref.watch() for reactive; ref.read() for one-time

### Platform Channels
- **MethodChannel**: Call native methods from Dart; binary protocol; Pigeon for type-safe codegen
- **EventChannel**: Stream of events from native to Dart (sensors, location)
- **Platform views**: UiKitView (iOS), AndroidView (Android) for embedding native views
- **FFI (dart:ffi)**: Direct C interop for performance-critical code

### Performance
- **const constructors**: Use everywhere possible; compile-time instantiation
- **RepaintBoundary**: Wrap animated subtrees to isolate repaint
- **ListView.builder**: Lazy rendering for long lists; use itemExtent for fixed height
- **Image.asset/network**: Set cacheWidth/cacheHeight; avoid decoding full resolution
- **Shader warm-up**: Precompile shaders on splash screen to avoid jank
- **DevTools**: Flutter Inspector, Performance overlay, memory profiler

### Testing
- **Unit tests**: Pure Dart, no Flutter dependency; test data models, business logic
- **Widget tests**: pumpWidget() for rendering; Finder for locating widgets; simulate taps/scrolls
- **Integration tests**: integration_test package; run on device/emulator
- **Golden tests**: Pixel-perfect screenshot comparison; alchemist for CI

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Rebuilding entire widget tree on state change | Every `setState` in parent rebuilds all children; jank at 60fps | Use `const` constructors; extract widgets; use Riverpod `Consumer` for granular rebuilds |
| Using `setState` for complex state | Scattered state; hard to test; coupled to widget lifecycle | Use Riverpod `Notifier` for business logic; `StateProvider` for simple state |
| Blocking the main isolate | JSON parsing, image processing, or crypto on UI thread causes missed frames | Use `compute()` or `Isolate.run()` for CPU-heavy work |
| `BuildContext` misuse (storing, async gap) | Context stored in variables across async gaps may reference unmounted widgets | Never store BuildContext; use `ref.read()` in Riverpod callbacks |
| No `const` constructors | Every rebuild creates new widget instances; increased GC pressure | Add `const` to all possible constructors; use lints to enforce |
| `ListView` without builder | Renders all items upfront; OOM on large lists | Use `ListView.builder` with `itemCount`; prefer `itemExtent` for fixed-size items |
| Platform-agnostic design | iOS users get Material widgets; Android users get Cupertino; poor UX | Use `Platform.isIOS` / `Platform.isAndroid` for adaptive UI; or use `flutter_platform_widgets` |
| Deeply nested widget trees | Pyramid of doom; hard to read and maintain | Extract widgets into named classes/functions; use composition |
| Ignoring keyboard overflow | Keyboard covers input fields on small screens | Wrap with `SingleChildScrollView` or `Scaffold.resizeToAvoidBottomInset` |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| `setState called after dispose` | Async callback fired after widget unmounted | Check if `mounted` is true before `setState` | Use Riverpod; it handles lifecycle automatically |
| `RenderFlex overflow` | Column/Row children exceed available space | Check `Flex` error message; look for unbounded constraints | Use `Expanded`, `Flexible`; wrap with `SingleChildScrollView` |
| `A RenderFlex overflowed by X pixels` | Content too large for parent | Same as above; most common Flutter error | Add `flex` properties; break into scrollable sections |
| `Null check operator used on null` | Dart null safety violation | Check stack trace for the null value source | Use `?` and `??` operators; avoid `!` in production code |
| Slow first frame / jank on startup | Heavy work in `initState` or `build`; shader compilation | Profile with DevTools; check frame rendering times | Defer work with `WidgetsBinding.instance.addPostFrameCallback`; shader warm-up |
| `Could not resolve host` on API calls | No internet permission (Android); ATS blocking (iOS) | Check `AndroidManifest.xml` for INTERNET permission; check `Info.plist` for NSAppTransportSecurity | Add `<uses-permission android:name="android.permission.INTERNET"/>` |
| `StateError: Bad state: Stream has already been listened to` | Multiple listeners on single-subscription stream | Check for multiple `StreamBuilder` widgets on same stream | Use `StreamController.broadcast()` or `BehaviorSubject` (rxdart) |

### Implementation Checklist

- [ ] Dart analysis passes with zero errors and warnings
- [ ] All widgets use `const` constructors where possible
- [ ] Riverpod providers used for all non-trivial state
- [ ] `ListView.builder` used for all scrollable lists
- [ ] Platform-adaptive UI where appropriate (Material for Android, Cupertino for iOS)
- [ ] `RepaintBoundary` wrapping animated/complex subtrees
- [ ] Network calls use `dio` with interceptors for auth, logging, retry
- [ ] Error states, loading states, and empty states handled in all screens
- [ ] Local persistence configured (sqflite/Drift/Hive)
- [ ] Secure storage for tokens and sensitive data (flutter_secure_storage)
- [ ] Deep linking configured for both platforms
- [ ] `flutter build appbundle` (Android) and `flutter build ipa` (iOS) succeed
- [ ] App signing configured for release builds
- [ ] Performance tested on low-end devices (not just flagship)
- [ ] Unit tests for business logic; widget tests for critical UI; integration tests for flows
- [ ] `flutter test --coverage` passes with ≥ 70% coverage
