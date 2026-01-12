# Web OS Simulator - Documentation & Skeleton Map

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [File Structure](#file-structure)
4. [Code Skeleton Map](#code-skeleton-map)
5. [Core Systems](#core-systems)
6. [Applications](#applications)
7. [Theming](#theming)
8. [API Reference](#api-reference)
9. [Extending the OS](#extending-the-os)

---

## Overview

Web OS is a fully-featured operating system simulation running entirely in a single HTML file. It provides a Windows-like desktop experience with draggable windows, a start menu, taskbar, file system, and multiple applications.

**Key Features:**
- Boot sequence & login screen
- Virtual file system with localStorage persistence
- Multiple themes (Windows 95, XP, Dark)
- 12 built-in applications
- Window management (drag, resize, minimize, maximize, snap)
- Sound effects & notifications
- Right-click context menus

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WEB OS ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Boot Layer  │→ │ Login Layer  │→ │    Desktop Layer     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                               │                  │
│                    ┌──────────────────────────┼───────────────┐ │
│                    │                          ▼               │ │
│  ┌─────────────────┴───────────────────────────────────────┐ │ │
│  │                      OS CORE                             │ │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐│ │ │
│  │  │  Window     │ │   File      │ │    Theme            ││ │ │
│  │  │  Manager    │ │   System    │ │    Engine           ││ │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘│ │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐│ │ │
│  │  │  Sound      │ │  Notifi-    │ │    Context          ││ │ │
│  │  │  System     │ │  cations    │ │    Menus            ││ │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘│ │ │
│  └─────────────────────────────────────────────────────────┘ │ │
│                    │                                          │ │
│                    └──────────────────────────────────────────┘ │
│                                               │                  │
│                    ┌──────────────────────────┼───────────────┐ │
│                    │          APPLICATIONS    ▼               │ │
│  ┌─────────────────┴───────────────────────────────────────┐ │ │
│  │ File Explorer │ Notepad │ Calculator │ Terminal │ Paint │ │ │
│  │ Browser │ Music Player │ Minesweeper │ Solitaire │ etc. │ │ │
│  └─────────────────────────────────────────────────────────┘ │ │
│                    └──────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    UI COMPONENTS                           │  │
│  │  Desktop │ Taskbar │ Start Menu │ Windows │ Icons         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    STORAGE LAYER                           │  │
│  │                    localStorage                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
web-os-simulator.html (Single file - ~3400 lines)
│
├── <head>
│   ├── Meta tags
│   └── <style> (Lines 7-1368)
│       ├── CSS Variables / Themes
│       ├── Boot Screen Styles
│       ├── Login Screen Styles
│       ├── Desktop & Icons
│       ├── Taskbar & Start Menu
│       ├── Window Styles
│       ├── App-Specific Styles
│       └── Animations
│
├── <body>
│   ├── Boot Screen (#boot-screen)
│   ├── Login Screen (#login-screen)
│   ├── Desktop (#desktop)
│   ├── Taskbar (#taskbar)
│   ├── Start Menu (#start-menu)
│   ├── Context Menu (#context-menu)
│   ├── Snap Indicator (#snap-indicator)
│   └── Notifications (#notification-container)
│
└── <script> (Lines 1463-3439)
    ├── OS Core Object
    ├── FileSystem Class
    ├── System Functions
    ├── Window Management
    ├── Drag & Resize
    └── Application Functions
```

---

## Code Skeleton Map

### LINE NUMBERS REFERENCE

```
╔═══════════════════════════════════════════════════════════════════╗
║                        CSS SECTION (7-1368)                        ║
╠═══════════════════════════════════════════════════════════════════╣
║ 8-67      │ CSS Variables & Themes (:root, .theme-xp, .theme-dark)║
║ 69-81     │ Global Styles (*, body)                               ║
║ 83-137    │ Boot Screen Styles                                    ║
║ 139-213   │ Login Screen Styles                                   ║
║ 215-254   │ Desktop Icons                                         ║
║ 256-287   │ Context Menu                                          ║
║ 289-366   │ Taskbar                                               ║
║ 368-425   │ Start Menu                                            ║
║ 427-545   │ Window Styles                                         ║
║ 547-620   │ File Explorer                                         ║
║ 622-640   │ Notepad                                               ║
║ 642-694   │ Calculator                                            ║
║ 696-731   │ Terminal                                              ║
║ 733-796   │ Paint                                                 ║
║ 798-890   │ Settings                                              ║
║ 892-972   │ Minesweeper                                           ║
║ 974-1058  │ Solitaire                                             ║
║ 1060-1095 │ Notifications                                         ║
║ 1097-1146 │ Task Manager                                          ║
║ 1148-1249 │ Music Player                                          ║
║ 1251-1290 │ Image Viewer                                          ║
║ 1292-1319 │ Animations                                            ║
║ 1321-1367 │ Browser                                               ║
╠═══════════════════════════════════════════════════════════════════╣
║                       HTML SECTION (1370-1461)                     ║
╠═══════════════════════════════════════════════════════════════════╣
║ 1371-1380 │ Boot Screen HTML                                      ║
║ 1382-1391 │ Login Screen HTML                                     ║
║ 1393-1394 │ Desktop Container                                     ║
║ 1396-1408 │ Taskbar HTML                                          ║
║ 1410-1452 │ Start Menu HTML                                       ║
║ 1454-1461 │ Utility Elements (context menu, snap, notifications)  ║
╠═══════════════════════════════════════════════════════════════════╣
║                    JAVASCRIPT SECTION (1463-3439)                  ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                    ║
║ ┌── CORE OS ──────────────────────────────────────────────────┐   ║
║ │ 1464-1476  │ OS Global State Object                         │   ║
║ │ 1478-1598  │ FileSystem Class                               │   ║
║ │ 1600-1617  │ showNotification()                             │   ║
║ │ 1619-1660  │ playSound()                                    │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ ┌── BOOT & LOGIN ─────────────────────────────────────────────┐   ║
║ │ 1662-1703  │ bootSequence()                                 │   ║
║ │ 1705-1714  │ showLoginScreen()                              │   ║
║ │ 1716-1721  │ doLogin()                                      │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ ┌── DESKTOP INITIALIZATION ───────────────────────────────────┐   ║
║ │ 1723-1742  │ initDesktop()                                  │   ║
║ │ 1744-1750  │ applyTheme()                                   │   ║
║ │ 1752-1792  │ setupDesktopIcons()                            │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ ┌── CONTEXT MENU ─────────────────────────────────────────────┐   ║
║ │ 1794-1847  │ showContextMenu()                              │   ║
║ │ 1849-1855  │ createNewFolder()                              │   ║
║ │ 1857-1863  │ createNewFile()                                │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ ┌── EVENT LISTENERS ──────────────────────────────────────────┐   ║
║ │ 1865-1901  │ setupEventListeners()                          │   ║
║ │ 1903-1915  │ handleKeyboardShortcuts()                      │   ║
║ │ 1917-1919  │ updateSoundIcon()                              │   ║
║ │ 1921-1927  │ updateClock()                                  │   ║
║ │ 1929-1933  │ toggleStartMenu()                              │   ║
║ │ 1935-1944  │ shutDown()                                     │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ ┌── WINDOW MANAGEMENT ────────────────────────────────────────┐   ║
║ │ 1946-1957  │ launchApp()                                    │   ║
║ │ 1959-2063  │ getAppConfig()                                 │   ║
║ │ 2065-2152  │ createWindow()                                 │   ║
║ │ 2154-2169  │ addToTaskbar()                                 │   ║
║ │ 2171-2187  │ focusWindow()                                  │   ║
║ │ 2189-2197  │ minimizeWindow()                               │   ║
║ │ 2199-2207  │ restoreWindow()                                │   ║
║ │ 2209-2235  │ maximizeWindow()                               │   ║
║ │ 2237-2246  │ closeWindow()                                  │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ ┌── DRAGGING & RESIZING ──────────────────────────────────────┐   ║
║ │ 2248-2324  │ makeDraggable()                                │   ║
║ │ 2326-2357  │ makeResizable()                                │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ ┌── APPLICATIONS ─────────────────────────────────────────────┐   ║
║ │ 2359-2436  │ createFileExplorer()                           │   ║
║ │ 2438-2447  │ openFileInNotepad()                            │   ║
║ │ 2449-2466  │ createNotepad()                                │   ║
║ │ 2468-2550  │ createCalculator()                             │   ║
║ │ 2552-2700  │ createTerminal()                               │   ║
║ │ 2702-2767  │ createBrowser()                                │   ║
║ │ 2769-2887  │ createPaint()                                  │   ║
║ │ 2889-2928  │ createMusicPlayer()                            │   ║
║ │ 2930-3113  │ createMinesweeper()                            │   ║
║ │ 3115-3223  │ createSolitaire()                              │   ║
║ │ 3225-3374  │ createSettings()                               │   ║
║ │ 3376-3416  │ createTaskManager()                            │   ║
║ │ 3418-3436  │ createImageViewer()                            │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ 3438-3439   │ DOMContentLoaded → bootSequence()                   ║
║                                                                    ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## Core Systems

### 1. OS Global State Object

```javascript
const OS = {
    windows: [],          // Array of open window objects
    nextZIndex: 10,       // Z-index counter for window stacking
    nextWindowId: 1,      // Window ID counter
    activeWindow: null,   // Currently focused window ID
    soundEnabled: true,   // Sound effects toggle
    theme: 'default',     // Current theme name
    wallpaper: '',        // Custom wallpaper URL
    fileSystem: null,     // FileSystem instance
    clipboard: null,      // Clipboard data
    desktopIcons: []      // Desktop icon positions
};
```

### 2. FileSystem Class

```javascript
class FileSystem {
    constructor()           // Load from localStorage or create default
    getDefaultFS()          // Returns default folder structure
    load()                  // Load from localStorage
    save()                  // Save to localStorage
    getFolder(path)         // Get folder contents by path
    getFile(path)           // Get file by full path
    createFile(path, name, content)  // Create new file
    createFolder(path, name)         // Create new folder
    deleteItem(path, name)           // Delete file/folder
    renameItem(path, old, new)       // Rename file/folder
    updateFile(path, content)        // Update file content
}
```

### 3. Window Object Structure

```javascript
{
    id: 'window-1',        // Unique window ID
    appId: 'notepad',      // Application identifier
    title: 'Untitled - Notepad',  // Window title
    minimized: false,      // Minimize state
    maximized: false,      // Maximize state
    prevState: {           // Pre-maximize dimensions
        top, left, width, height
    }
}
```

### 4. App Config Structure

```javascript
{
    id: 'app-id',          // Unique app identifier
    title: 'App Title',    // Window title
    icon: '📁',            // Emoji icon
    width: 600,            // Default width
    height: 400,           // Default height
    menubar: ['File'],     // Optional menu items
    resizable: true,       // Allow resize (default: true)
    statusbar: true,       // Show status bar (default: true)
    content: function()    // Returns DOM element for window content
}
```

---

## Applications

### Application Registry

| App ID | Name | Icon | Description |
|--------|------|------|-------------|
| `file-explorer` | File Explorer | 📁 | Browse virtual file system |
| `notepad` | Notepad | 📝 | Text editor |
| `calculator` | Calculator | 🔢 | Basic calculator |
| `terminal` | Terminal | 💻 | Command line interface |
| `browser` | Browser | 🌐 | Simulated web browser |
| `paint` | Paint | 🎨 | Drawing application |
| `music` | Music Player | 🎵 | Audio player UI |
| `minesweeper` | Minesweeper | 💣 | Classic game |
| `solitaire` | Solitaire | 🃏 | Card game |
| `settings` | Settings | ⚙️ | System settings |
| `task-manager` | Task Manager | 📊 | Running apps & stats |
| `image-viewer` | Image Viewer | 🖼️ | View images |

### Terminal Commands

| Command | Description | Example |
|---------|-------------|---------|
| `help` | Show available commands | `help` |
| `ls` / `dir` | List files in current directory | `ls` |
| `cd <dir>` | Change directory | `cd Documents` |
| `cd ..` | Go up one directory | `cd ..` |
| `pwd` | Print working directory | `pwd` |
| `cat <file>` | Display file contents | `cat Notes.txt` |
| `mkdir <name>` | Create directory | `mkdir NewFolder` |
| `touch <name>` | Create empty file | `touch file.txt` |
| `rm <name>` | Remove file/folder | `rm oldfile.txt` |
| `clear` | Clear terminal | `clear` |
| `echo <text>` | Print text | `echo Hello World` |
| `whoami` | Display current user | `whoami` |
| `date` | Display current date/time | `date` |
| `matrix` | Easter egg | `matrix` |

---

## Theming

### Available Themes

1. **Windows 95** (default) - Classic teal desktop, gray windows
2. **Windows XP** - Blue Luna theme with gradients
3. **Dark Mode** - Modern dark theme with accent colors

### CSS Variables

```css
:root {
    --desktop-bg         /* Desktop background color */
    --taskbar-bg         /* Taskbar background */
    --taskbar-border     /* Taskbar top border */
    --window-bg          /* Window chrome background */
    --window-border      /* Window border color */
    --titlebar-bg        /* Active window titlebar */
    --titlebar-text      /* Titlebar text color */
    --titlebar-inactive  /* Inactive window titlebar */
    --button-bg          /* Button background */
    --button-border      /* Button border */
    --button-highlight   /* Button highlight/hover */
    --content-bg         /* Window content background */
    --text-color         /* Default text color */
    --menu-hover         /* Menu item hover background */
    --menu-hover-text    /* Menu item hover text */
    --start-button-bg    /* Start button background */
    --accent-color       /* Accent/selection color */
}
```

### Applying Themes

```javascript
// Apply theme programmatically
applyTheme('default');  // Windows 95
applyTheme('xp');       // Windows XP
applyTheme('dark');     // Dark Mode
```

---

## API Reference

### Window Management

```javascript
// Launch an application
launchApp('notepad');

// Create custom window
createWindow({
    id: 'my-app',
    title: 'My Application',
    icon: '🚀',
    width: 400,
    height: 300,
    content: function() {
        const div = document.createElement('div');
        div.textContent = 'Hello World!';
        return div;
    }
});

// Window operations
focusWindow('window-1');
minimizeWindow('window-1');
restoreWindow('window-1');
maximizeWindow('window-1');
closeWindow('window-1');
```

### Notifications

```javascript
// Show notification
showNotification('Title', 'Message body', 4000);  // 4 second duration
```

### Sound Effects

```javascript
// Play sounds
playSound('click');        // Button click
playSound('notification'); // Notification chime
playSound('error');        // Error sound
playSound('startup');      // Startup sound
```

### File System

```javascript
// Access file system
OS.fileSystem.createFile('Documents', 'test.txt', 'Hello');
OS.fileSystem.createFolder('Documents', 'NewFolder');
OS.fileSystem.deleteItem('Documents', 'test.txt');
OS.fileSystem.getFolder('Documents');  // Returns folder contents
OS.fileSystem.getFile('Documents/test.txt');  // Returns file object
```

### Context Menus

```javascript
// Show context menu
showContextMenu(event, 'desktop');  // Desktop context menu
showContextMenu(event, 'icon', 'notepad');  // Icon context menu
showContextMenu(event, 'file', {
    path: 'Documents',
    name: 'test.txt',
    onOpen: () => {},
    onRename: () => {},
    onDelete: () => {}
});
```

---

## Extending the OS

### Adding a New Application

1. **Add to getAppConfig()** (line ~1959):

```javascript
'my-app': {
    id: 'my-app',
    title: 'My Application',
    icon: '🚀',
    width: 400,
    height: 300,
    content: createMyApp
}
```

2. **Create the app function**:

```javascript
function createMyApp() {
    const container = document.createElement('div');
    container.style.padding = '20px';
    container.innerHTML = `
        <h1>My Application</h1>
        <p>Application content here</p>
    `;
    return container;
}
```

3. **Add to Start Menu** (HTML, line ~1410):

```html
<div class="start-menu-item" data-app="my-app">
    <span class="icon">🚀</span> My Application
</div>
```

4. **Add desktop icon** (in setupDesktopIcons, line ~1756):

```javascript
{ id: 'my-app', name: 'My App', icon: '🚀', top: 420, left: 110 }
```

5. **Add CSS if needed** (in <style> section).

### Adding a New Theme

1. **Add CSS class** (after line 67):

```css
.theme-custom {
    --desktop-bg: #your-color;
    --taskbar-bg: #your-color;
    /* ... all variables ... */
}
```

2. **Add to Settings** (in createSettings, line ~3252):

```html
<div class="theme-card" data-theme="custom">
    <div class="theme-card-preview" style="background: #your-color;"></div>
    <div class="theme-card-label">Custom Theme</div>
</div>
```

3. **Update applyTheme()** (line ~1744):

```javascript
else if (theme === 'custom') document.body.classList.add('theme-custom');
```

### Adding Terminal Commands

In `processCommand()` function (line ~2567):

```javascript
case 'mycommand':
    addLine('Output of my command');
    break;
```

---

## localStorage Keys

| Key | Description |
|-----|-------------|
| `webos-filesystem` | Virtual file system JSON |
| `webos-theme` | Current theme name |
| `webos-wallpaper` | Custom wallpaper URL |
| `webos-sound` | Sound enabled ('true'/'false') |
| `webos-username` | Display username |

---

## Event Flow

```
Page Load
    │
    ▼
bootSequence()
    │
    ├── Display BIOS text
    ├── Show loading bar
    ├── Play startup sound
    │
    ▼
showLoginScreen()
    │
    ▼
doLogin() ─────────────────┐
    │                       │
    ▼                       │
initDesktop()               │
    │                       │
    ├── Initialize FileSystem
    ├── Load saved settings
    ├── Apply theme
    ├── Setup desktop icons
    ├── Setup event listeners
    ├── Start clock
    │                       │
    ▼                       │
Desktop Ready ◄─────────────┘
    │
    ├── User clicks icon/menu
    │       │
    │       ▼
    │   launchApp(appId)
    │       │
    │       ▼
    │   getAppConfig(appId)
    │       │
    │       ▼
    │   createWindow(config)
    │       │
    │       ▼
    │   Window Displayed
    │
    └── User interacts with apps...
```

---

## Browser Compatibility

- **Recommended**: Chrome, Firefox, Edge (latest)
- **Supported**: Safari, Opera
- **Required Features**:
  - localStorage
  - Web Audio API (for sounds)
  - CSS Variables
  - ES6+ JavaScript

---

## Credits

Web OS Simulator v1.0
Single-file browser-based operating system simulation.
