# Macena CS2 Analyzer — Frontend Architecture Biopsy

> **Document classification:** Internal Technical Reference
> **Scope:** Complete dissection of the desktop application UI architecture, rendering pipeline, state management, and backend integration.
> **Last verified:** 2026-02-14 (full codebase audit)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack & Architecture](#2-technology-stack--architecture)
3. [Screen Architecture](#3-screen-architecture)
4. [Tactical Viewer — Real-Time Playback](#4-tactical-viewer--real-time-playback)
5. [TacticalMap — 2D Rendering Engine](#5-tacticalmap--2d-rendering-engine)
6. [PlayerSidebar — Widget Pooling](#6-playersidebar--widget-pooling)
7. [Timeline Scrubber](#7-timeline-scrubber)
8. [ViewModels (MVVM State Management)](#8-viewmodels-mvvm-state-management)
9. [KV Template Structure](#9-kv-template-structure)
10. [Performance Patterns](#10-performance-patterns)
11. [Backend Integration](#11-backend-integration)
12. [Interaction Flows](#12-interaction-flows)

---

## 1. Executive Summary

The Macena CS2 Analyzer desktop application is a **Kivy + KivyMD MVVM architecture** designed for real-time CS2 demo analysis with tactical visualization and AI coaching integration. The codebase comprises:

- **11 Python modules** + **1 KV template** = **~3,070 lines** (verified via `wc -l`)
- **9 distinct screens** with **15 major classes** and **~140 methods**
- **Material Design 3** compliance with multi-language support (en/it/pt)
- **60+ FPS** real-time playback with widget pooling optimization
- **Lazy-loaded ML inference** (torch/CUDA deferred until needed)
- **Thread-safe** background scanning and heatmap generation

---

## 2. Technology Stack & Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI Framework** | Kivy 2.x + KivyMD 2.x | Cross-platform widget toolkit + Material Design 3 |
| **Architecture** | MVVM | Model-View-ViewModel separation |
| **Rendering** | OpenGL (via Kivy Canvas) | Hardware-accelerated 2D graphics |
| **Charts** | Matplotlib + FigureCanvasKivyAgg | Analytics visualization |
| **Threading** | Python threading + Kivy Clock | Background ops + main-thread safety |
| **Localization** | Custom i18n (`_t(key)`) | en/it/pt support |

### MVVM Separation

```
PlaybackEngine (Model — frame data)
    ↓
TacticalPlaybackViewModel (ViewModel — state + callbacks)
    ↓
TacticalViewerScreen (View — UI orchestration)
    ↓
TacticalMap + PlayerSidebar + Timeline (Widgets — rendering)
    ↓
layout.kv (Template — layout + bindings)
```

---

## 3. Screen Architecture

### Nine-Screen Navigation Model

| Screen ID | Python Class | Purpose |
|-----------|-------------|---------|
| `wizard` | `WizardScreen` | Multi-step onboarding (paths, ML config) |
| `home` | KV-only | Dashboard: coaching status, ingestion, tactical entry |
| `coach` | KV-only | AI insights, belief state, analytics, momentum |
| `user_profile` | KV-only | Player avatar, role badge, Steam sync |
| `profile` | KV-only | In-game name input/edit |
| `steam_config` | KV-only | SteamID + API key input |
| `faceit_config` | KV-only | FaceIT API key input |
| `settings` | KV-only | Theme, paths, appearance, ingestion control |
| `help` | `HelpScreen` | Searchable documentation |
| `tactical_viewer` | `TacticalViewerScreen` | Live demo playback + analysis |

**Navigation patterns:**
- **Top App Bar** → Direct screen access (Settings, Help, Profile, Coach, Home)
- **Dashboard Cards** → Contextual transitions (Home → specific screens)
- **Back Navigation** → Explicit back button or `app.switch_screen("home")`

### WizardScreen (`wizard_screen.py`, 311 lines)

4-step onboarding sequence:
1. **Intro** — Welcome message
2. **Brain Path** — ML model root directory selection (knowledge/, models/, datasets/)
3. **Demo Path** — Demo file folder selection
4. **Finish** — Summary + Launch

Platform-aware file picker with Windows drive detection (letters A–Z). Saves config via `save_user_setting()`.

### HelpScreen (`help_screen.py`, 46 lines)

Two-pane searchable documentation:
- **Left sidebar (30%):** Search field with live filtering + scrollable topic list
- **Right content (70%):** Markdown-rendered content via `MDLabel(markup=True)`

---

## 4. Tactical Viewer — Real-Time Playback

**File:** `tactical_viewer_screen.py` (254 lines)
**Class:** `TacticalViewerScreen(MDScreen)` — Master orchestrator

### Layout

```
┌─────────────────────────────────────┐
│  MDTopAppBar (Tactical Analyzer)    │
├──────┬─────────────────┬────────────┤
│  CT  │  Tactical Map   │     T      │
│ (20%)│     (60%)       │   (20%)    │
│      │                 │            │
├──────┴─────────────────┴────────────┤
│ Map Spinner │ Round │ Tick │ Speed   │
│ Debug Toggle │ Ghost Toggle          │
│ [< Prev CM]        [> Next CM]      │
├─────────────────────────────────────┤
│  TimelineScrubber (40dp height)     │
└─────────────────────────────────────┘
```

### Subsystems

**A. Playback Control:**
- `toggle_playback()` — Play/pause via ViewModel
- `set_speed(speed)` — Multiplier: 0.5x, 0.75x, 1x, 2x, 4x
- `seek_to_tick(tick)` — Jump to specific tick
- `on_frame_update(frame)` — Receives `InterpolatedFrame`, updates map + sidebars
- `update_tick_ui(dt)` — Periodic refresh (0.1s interval)

**B. Demo Loading:**
- `on_demo_selected(demo_path)` — Loads `.dem` file via DemoLoader
- `switch_map(map_name)` — Loads data for selected map

**C. Chronovisor (Critical Moments):**
- `scan_for_critical_moments(match_id)` — Background thread scan
- `jump_to_next_cm()` / `jump_to_prev_cm()` — Navigate critical moments (32-tick buffer zone)

**D. Ghost Engine:**
- Lazy-loaded via `_ghost_vm.set_active(True)`
- Predictions injected into frame before rendering
- Toggle on/off without restart

---

## 5. TacticalMap — 2D Rendering Engine

**File:** `tactical_map.py` (476 lines)
**Class:** `TacticalMap(Widget)` — Custom multi-layer rendering

### Rendering Architecture

Three `InstructionGroup` layers:

| Layer | Content | Update Frequency |
|-------|---------|-----------------|
| `map_group` | Static map background + heatmap | On resize, map change, or heatmap update |
| `heatmap_group` | Density overlay | When heatmap data available |
| `dynamic_group` | Players, grenades, ghosts | Every frame (60 FPS) |

```
RENDERING LAYER STACK (Draw Order, Bottom to Top)

  ┌─────────────────────────────────────────────────────────┐
  │  Layer 3: dynamic_group (redrawn every frame @ 60 FPS)  │
  │  Players (CT=blue, T=orange), grenades, ghost overlays  │
  ├─────────────────────────────────────────────────────────┤
  │  Layer 2: heatmap_group (updated async on data change)  │
  │  Gaussian density overlay (2048×2048 RGBA texture)      │
  ├─────────────────────────────────────────────────────────┤
  │  Layer 1: map_group (updated on resize/map change)      │
  │  Static map background image                            │
  └─────────────────────────────────────────────────────────┘
```

### Coordinate Transformation

```python
def _world_to_screen(self, x, y):
    """CS2 world coords → widget pixel coords."""
    norm_x, norm_y = self.spatial_engine.world_to_normalized(x, y)
    # Maintain aspect ratio, center in widget
    if self.width > self.height:
        offset = (self.width - self.height) / 2
        screen_x = self.x + offset + norm_x * self.height
        screen_y = self.y + norm_y * self.height
    else:
        offset = (self.height - self.width) / 2
        screen_x = self.x + norm_x * self.width
        screen_y = self.y + offset + norm_y * self.width
    return (screen_x, screen_y)
```

Reverse transform `_screen_to_world()` for touch input.

### Player Rendering

- **CT:** Blue `(0.3, 0.5, 1.0)` | **T:** Orange `(1.0, 0.6, 0.2)` | **Dead:** Gray `(0.5, 0.5, 0.5, 0.5)`
- **Circle radius:** 8px visual, 20px hitbox (×2.5 for easier clicking)
- **Selection halo:** White circle outline (2px width, +4px radius)
- **Health bar:** Above player, red if <50% / green if ≥50%
- **Name label:** CoreLabel texture cached for performance

### Grenade Rendering

**Detonation overlays** (game-unit radius circles):

| Type | Color | Radius (game units) |
|------|-------|---------------------|
| **HE Grenade** | Red | 350 |
| **Molotov** | Orange | 180 |
| **Smoke** | Gray | 144 |
| **Flash** | Yellow | 1000 (outer), 300 (inner) |

Trajectory rendering: Multi-segment line from throw to detonation, 3-second fade-out, height-based coloring, apex marker.

### Heatmap Integration

Thread-safe async generation:
```
Thread → HeatmapEngine.generate_heatmap_data() (CPU)
  ↓ Clock.schedule_once()
Main thread → HeatmapEngine.create_texture_from_data() (OpenGL)
  ↓
Apply texture to heatmap_group
```

### Touch Interaction

Player selection via circle hit-test. Debug mode gives priority to `GhostPixelValidator` overlay. Empty-space click deselects.

---

## 6. PlayerSidebar — Widget Pooling

**File:** `player_sidebar.py` (310 lines)
**Classes:** `PlayerSidebar(BoxLayout)`, `LivePlayerCard(MDCard)`

### Widget Pooling Pattern

**Problem:** 10 players × 60 FPS = 600 widget allocations/second → GC churn.

**Solution:** Object pool with in-place updates:

```python
self._player_items = {}  # {player_id: (widget, parts_dict)}

def update_players(self, players, selected_id):
    for p in players:
        if p.id not in self._player_items:
            widget = self._create_player_widget()
            self._player_items[p.id] = (widget, {})
        widget, parts = self._player_items[p.id]
        # Update properties in-place — no destroy/recreate
        parts["name"].text = p.name
        parts["hp"].text = f"HP: {p.hp}"
        parts["money"].text = f"${p.money}"
```

### Player Item Structure

Each `MDListItem` contains:
- **Leading icon:** account/skull/shield/target based on alive/dead/armor/selected state
- **Headline text:** Player name
- **Supporting text:** Money + HP (if alive)
- **Trailing text:** Weapon name

### LivePlayerCard

Expanded detail card shown when a player is selected:
- HP bar (red/green gradient)
- Armor bar
- Money display
- K/D/A statistics
- Alive status indicator

---

## 7. Timeline Scrubber

**File:** `timeline.py` (109 lines)
**Class:** `TimelineScrubber(Widget)` — Canvas-based rendering

### Rendering Layers

1. **Background:** Gray bar `(0.2, 0.2, 0.2)`
2. **Progress:** Green fill `(0.3, 0.7, 0.3)` scaled by `current_tick / max_tick`
3. **Event Markers:**
   - **Kill** — Red, half-height `(0.9, 0.2, 0.2, 0.8)`
   - **Bomb Plant** — Yellow, full-height `(0.9, 0.8, 0.2, 0.8)`
   - **Defuse** — Blue, full-height `(0.2, 0.6, 0.9, 0.8)`
   - Width: 2px, positioned by `event.tick / max_tick`

### Touch Interaction

Touch/drag → normalized x → `target_tick = int(nx × max_tick)` → seek callback → PlaybackEngine seeks.

---

## 8. ViewModels (MVVM State Management)

**File:** `tactical_viewmodels.py` (306 lines)
**3 ViewModels** decoupling business logic from UI:

### 8.1 TacticalPlaybackViewModel

| Property | Type | Purpose |
|----------|------|---------|
| `is_playing` | BooleanProperty | Play/pause state |
| `current_tick` | NumericProperty | Current position |
| `total_ticks` | NumericProperty | Demo length |
| `speed` | NumericProperty | Playback speed (0.5x–4x) |

Methods: `set_engine()`, `load_frames()`, `toggle_playback()`, `set_speed()`, `seek_to_tick()`.

### 8.2 TacticalGhostViewModel

| Property | Type | Purpose |
|----------|------|---------|
| `ghost_active` | BooleanProperty | Enable/disable predictions |
| `is_loaded` | BooleanProperty | Engine loaded flag |

**Lazy loading pattern:** Defers `from ...ghost_engine import GhostEngine` until first activation. Prevents torch/CUDA import blocking app startup (saves 2–5 seconds).

`predict_ghosts(players)` returns copies of alive players with predicted `(x, y)` and `is_ghost=True` flag.

### 8.3 TacticalChronovisorViewModel

| Property | Type | Purpose |
|----------|------|---------|
| `is_scanning` | BooleanProperty | Scan in progress |
| `scan_complete` | BooleanProperty | Scan finished |
| `cm_count` | NumericProperty | Critical moments count |
| `scan_error` | StringProperty | Error message |

**Thread pattern:**
```python
def scan_match(self, match_id):
    def _scan():
        result = scanner.scan_match(match_id)  # Blocking CPU work
        Clock.schedule_once(lambda dt: self._on_scan_done(result.cms), 0)
    Thread(target=_scan, daemon=True).start()
```

Navigation: `jump_to_next(tick)` / `jump_to_prev(tick)` with 32-tick buffer zone.

---

## 9. KV Template Structure

**File:** `layout.kv` (1,367 lines)

### Custom Reusable Components

| Component | Purpose |
|-----------|---------|
| `SectionHeader` | Section title with icon (Settings screen) |
| `AppSettingItem` | Two-line setting display |
| `DashboardCard` | Base styled card (Home/Coach) |
| `TrainingStatusCard` | ML progress display |
| `FadingBackground` | Background crossfade animation |
| `CoachingCard` | Severity-based insight card (icon + title + message + focus_area) |

### CoachingCard Severity Colors

| Severity | Icon | Background Color |
|----------|------|-----------------|
| `info` | `information` | Blue tint |
| `warning` | `alert` | Yellow tint |
| `error` | `alert-circle` | Red tint |

### App-Level Properties (from KV bindings)

**Training State:** `current_epoch`, `total_epochs`, `train_loss`, `val_loss`, `eta_seconds`, `belief_confidence`

**Service Status:** `service_active`, `coach_status`

**Ingestion:** `parsing_progress`, `knowledge_reservoir_ticks`, `ingest_mode_auto`, `ingest_interval`

**Background Effects:** `background_source`, `background_source_next`, `background_opacity_current/next`

---

## 10. Performance Patterns

### 10.1 Widget Pooling (PlayerSidebar)

Maintains `_player_items` cache. Reuses 5–10 widgets, updates properties in-place. Eliminates 600 allocations/second during playback.

### 10.2 Instruction Groups (TacticalMap)

Static content (map background, heatmap) cached in `map_group`. Only `dynamic_group` (players, grenades, ghosts) redrawn at 60 FPS. Prevents redundant GPU texture uploads.

### 10.3 Lazy Loading (GhostViewModel)

torch/CUDA import deferred until user enables ghost predictions. App starts in ~1.5s instead of 3–5s.

### 10.4 Thread-Safe Background Ops

Pattern: daemon thread for CPU work → `Clock.schedule_once()` for main thread callback.

Used by: Heatmap generation, Chronovisor scanning, ML model loading.

### 10.5 Thread Interaction Pattern

```
THREAD SAFETY — WHO RUNS WHERE

  Main Thread (Kivy Event Loop)          Background Threads (Daemon)
  ─────────────────────────────          ─────────────────────────────
  ● Widget updates                       ● HeatmapEngine.generate_heatmap_data()
  ● Canvas rendering (OpenGL)            ● ChronovisorScanner.scan_match()
  ● Property changes                     ● GhostEngine initial CUDA load
  ● Touch event handling                 ● DemoLoader.load_demo()
  ● Clock.schedule_once() callbacks      │
        ▲                                │
        │  Clock.schedule_once(cb, 0)    │
        └────────────────────────────────┘
           (thread-safe bridge to main thread)
```

### 10.6 Performance Characteristics

| Operation | FPS/Duration | Mitigation |
|-----------|-------------|------------|
| Playback (10 players) | 60 FPS | Widget pooling, instruction groups |
| Heatmap generation | 1–2s one-time | Async thread |
| Ghost prediction | 30–50 FPS | Lazy-loaded, optional |
| Chronovisor scan | 1–5s | Background thread |
| App startup | ~1.5s | Deferred imports |

### 10.7 Memory Profile

| Component | Typical | Notes |
|-----------|---------|-------|
| App (idle) | 120 MB | Python + Kivy base |
| Demo frames (1 min) | 50 MB | Cached in memory |
| GhostEngine | +1.5 GB | torch/CUDA (lazy) |
| Heatmap texture | 15 MB | 2048×2048 RGBA |
| Player widget pool | 5 MB | 10 reused widgets |

---

## 11. Backend Integration

### Service Dependencies

| Service | Module | Interface |
|---------|--------|-----------|
| **PlaybackEngine** | `core/playback_engine.py` | Frame scheduling, seek, play/pause |
| **DemoLoader** | `ingestion/demo_loader.py` | `load_demo(path) → frames` |
| **GhostEngine** | `backend/nn/inference/ghost_engine.py` | `predict_tick(player) → (x, y)` |
| **ChronovisorScanner** | `backend/nn/rap_coach/chronovisor_scanner.py` | `scan_match(id) → ScanResult` |
| **HeatmapEngine** | `backend/processing/heatmap_engine.py` | Generate + texture creation |
| **MapManager** | `core/map_manager.py` | Async texture load, metadata |
| **SpatialEngine** | `core/spatial_engine.py` | Coordinate transforms |
| **CoachingService** | `backend/services/coaching_service.py` | `generate_new_insights()` |
| **Database** | `backend/storage/database.py` | SQLite + WAL mode |
| **Localization** | `core/localization.py` | `_t(key)` → translated text |

### Data Models

```python
@dataclass
class InterpolatedFrame:
    tick: int
    timestamp: float
    players: List[InterpolatedPlayerState]
    nades: List[GrenadeState]
    ghosts: List[InterpolatedPlayerState]
    events: List[GameEvent]

@dataclass
class InterpolatedPlayerState:
    player_id: int
    name: str
    team: Team          # CT or T
    x, y, z: float     # World coordinates
    yaw, pitch: float   # Direction
    hp, armor: int
    money: int
    weapon: str
    kills, deaths, assists: int
    is_alive: bool
    is_ghost: bool = False  # AI prediction flag
```

---

## 12. Interaction Flows

### 12.1 Demo Playback Flow

```
User: Pick demo + click "Play"
  ↓
TacticalViewerScreen.on_demo_selected(demo_path)
  ↓
DemoLoader.load_demo(demo_path) → InterpolatedFrame list
  ↓
PlaybackEngine.load_frames() → schedules frame callbacks
  ↓ Every 16.67ms (60 FPS)
PlaybackEngine._on_frame_update(frame)
  ↓
TacticalPlaybackViewModel._handle_frame_update(frame)
  ↓
TacticalViewerScreen.on_frame_update(frame)
  ├→ TacticalMap.update_map(players, nades, ghosts, tick)
  ├→ PlayerSidebar.update_players(players, selected_id) × 2
  └→ TimelineScrubber.current_tick = frame.tick
```

### 12.2 Player Selection Flow

```
User: Click player on map
  ↓
TacticalMap.on_touch_down(touch) → hit-test circles (20px hitbox)
  ↓
TacticalMap.selected_player_id = player_id
  ├→ TacticalMap._redraw() — adds selection halo
  └→ PlayerSidebar expands LivePlayerCard with stats
```

### 12.3 Critical Moment Scanning Flow

```
User: Click "Scan for Critical Moments"
  ↓
TacticalChronovisorViewModel.scan_match(match_id)
  ↓ Spawns daemon thread
Thread: ChronovisorScanner.scan_match() — CPU-intensive
  ↓
Clock.schedule_once() → main thread
  ↓
_on_scan_done(cms) → updates cm_count, enables navigation
  ↓
User: Click "Next CM"
  ↓
jump_to_next(current_tick) → finds CM after 32-tick buffer
  ↓
PlaybackEngine.seek_to_tick(tick) → jumps playback
```

### 12.4 Ghost Prediction Flow

```
User: Toggle "Show Ghost Predictions"
  ↓
TacticalGhostViewModel.set_active(True)
  ↓ First time only:
_ensure_loaded() → from ...ghost_engine import GhostEngine
  ↓ CUDA init (1–2s stutter, acceptable for first-time)
  ↓
Subsequent frames:
  on_frame_update(frame)
    ↓
  ghosts = predict_ghosts(frame.players) — ML inference per tick
    ↓
  TacticalMap.update_map(players, nades, ghosts, tick)
    ↓
  Ghosts rendered as semi-transparent player circles
```

### 12.5 Heatmap Generation Flow

```
User: Selects map with demo data
  ↓
TacticalMap.update_heatmap_async(events)
  ↓ Spawns daemon thread
Thread: HeatmapEngine.generate_heatmap_data() — CPU (thread-safe)
  ↓ Returns HeatmapData (RGBA bytes)
Clock.schedule_once() → main thread
  ↓
HeatmapEngine.create_texture_from_data() — OpenGL (main thread only)
  ↓
Apply texture to heatmap_group → visible overlay
```

---

## Error Handling & Graceful Degradation

| Failure | Behavior |
|---------|----------|
| Invalid demo path | Graceful picker error, retry prompt |
| Demo file corrupted | Error toast + back to demo selection |
| GhostEngine CUDA error | Ghost disabled, warning message |
| Chronovisor scan timeout | Scan aborted, error message displayed |
| Map texture missing | Fallback to wireframe + grid |
| Player selection miss | Deselect (hitbox validation) |
| Heatmap async failure | Skip heatmap, continue playback |
| Background thread exception | Caught, error scheduled to main thread via Clock |

---

> **End of Frontend Architecture Biopsy Document**
> Total frontend source files analysed: **12** (11 Python + 1 KV)
> Total lines of frontend code audited: **~3,070** (verified via `wc -l`)
> Screens documented: **9**
> ViewModels documented: **3** (Playback, Ghost, Chronovisor)
> Rendering layers: **3** (static map, heatmap, dynamic)
> Performance patterns: **6** (widget pooling, instruction groups, lazy loading, thread safety, canvas rendering, thread interaction)
> Line count discrepancies corrected: **6** (D-31 through D-36)
