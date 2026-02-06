# UI Design Features - Quick Reference

## Visual Appearance

### Color Scheme
The app now uses a sophisticated **liquid glass** aesthetic with:

```
Background:     Deep dark navy (#0f1419)
Cards:          Slightly lighter dark (#1a202d) with subtle borders
Glass Effects:  Medium gray backgrounds (#2a3549) for depth
Text (Primary): Bright white (#ffffff)
Text (Secondary): Soft gray (#b3b8c2)

Accent Colors:
  - Blue (Primary):      #6b9bef
  - Blue (Hover):        #8db3ff
  - Green (Success):     #34c759
  - Red (Error):         #ff3b30
  - Border Gray:         #3a4556
```

### Layout Structure

```
┌─────────────────────────────────────────┐
│  YouTube to File                        │  Header (28px title, 14px subtitle)
│  Download and convert videos instantly. │
├─────────────────────────────────────────┤
│                                         │
│  YouTube URL                            │  Input Card Section
│  [__________ Paste link here ___________│  - URL input (46px height)
│  ───────────────────────────────────────│  - Subtle divider
│  Format              │ Save to          │  - Two-column options
│  [MP4 Video|MP3...] │ /path/...Browse  │
│                                         │
│  [        Download         ]            │  Large primary button (48px)
│                                         │
├─────────────────────────────────────────┤
│  ▓▓▓▓▓▓▓░░░░░░░░░░░  45%               │  Progress Card
│  Downloading: 125MB / 280MB • ETA 3m   │
├─────────────────────────────────────────┤
│  Status Log                             │  Log Section (scrollable)
│  ⬇ Starting download...                │
│  Mode: Best Video (MP4)                 │
│  ✓ Download complete!                   │
│                                         │
│                                         │
└─────────────────────────────────────────┘
```

## Interactive Elements

### URL Input Field
- **Size**: 46px tall (larger touch target)
- **Placeholder**: "Paste your YouTube link here…"
- **Disabled During Download**: Yes
- **Visual Style**: Glass effect with subtle border
- **Focus**: Maintains design consistency

### Format Selector
- **Type**: Segmented button control
- **Options**:
  - "MP4 Video" - For best quality video
  - "MP3 Audio" - For audio extraction
- **Default**: MP4 Video
- **Visual Feedback**:
  - Selected: Bright blue (#6b9bef)
  - Hover: Light blue (#8db3ff)
  - Unselected: Border color (#3a4556)
- **Disabled During Download**: Yes

### Save Location
- **Format**: Shows truncated path (e.g., "...Downloads")
- **Button**: "Browse" button (100px width)
- **Visual Style**: Glass effect with border
- **Hover State**: Subtle color transition
- **Disabled During Download**: Yes

### Download Button
- **Size**: 48px tall (prominent, large)
- **Color**: Accent blue (#6b9bef)
- **Hover Color**: Light blue (#8db3ff)
- **Text**: "Download" or "Downloading…"
- **During Download**:
  - Text changes to "Downloading…"
  - Color stays accent blue (disabled state visual)
  - No longer clickable
- **Shape**: 12px rounded corners (modern appearance)

### Progress Bar
- **Height**: 6px (thin, refined)
- **Background**: Glass light color
- **Progress Color**: Accent blue
- **Position**: Above status line

### Status Line
- **Text Size**: 11px (smaller, supporting role)
- **Color Variations**:
  - Default: Secondary gray
  - During Download: Secondary gray
  - Success: Green (#34c759)
  - Error: Red (#ff3b30)
- **Examples**:
  - "Ready to download."
  - "Starting download…"
  - "✓ Download complete!"
  - "✗ Download failed. Check log."

### Status Log
- **Background**: Glass light color (#2a3549)
- **Text Color**: Secondary gray (#b3b8c2)
- **Font**: 10px monospace-like
- **Scrolling**: Auto-scrolls to latest messages
- **Read-Only**: Yes (prevents editing)
- **Visual Indicators**:
  - ✓ Success operations (green text)
  - ✗ Errors (red text)
  - ⬇ Download starting
  - Standard messages (gray text)

## Interaction Flows

### Idle State
- All inputs enabled
- Status: "Ready to download."
- Progress: 0%
- Button text: "Download"

### During Download
- URL input: Disabled
- Format selector: Disabled
- Browse button: Disabled
- Download button: Disabled (shows "Downloading…")
- Progress bar: Animates 0% → 100%
- Status line: Shows live metrics (speed, ETA)
- Log: Displays download progress

### Success State
- All inputs re-enabled
- Progress: 100% (filled)
- Status: "✓ Download complete!" (green)
- Log shows: "✓ Download complete!"

### Error State
- All inputs re-enabled
- Progress: Remains at fail point
- Status: "✗ Download failed. Check log." (red)
- Log shows error details

## Design Philosophy

### Liquid Glass (Glassmorphism)
- Layered depth with multiple background colors
- Subtle borders creating glass-like separation
- Consistent rounded corners (18px)
- Semi-transparent effect through color choices
- Clean, minimal visual clutter

### Apple Design Principles
- **Hierarchical Typography**: Clear visual hierarchy with 6 font sizes
- **Generous Spacing**: Ample padding and margins (24px-28px)
- **Subtle Colors**: Soft gradients through color palette rather than gradients
- **Rounded Corners**: Consistent 18px radius for cohesion
- **Dark Mode**: Premium dark background throughout
- **Feedback**: Clear status indicators with colors and symbols
- **Minimalism**: Only essential elements visible

### Typography
- **Title**: 28px, Bold (commands attention)
- **Subtitle**: 14px, Regular (supporting information)
- **Labels**: 12px, Semibold (section headers)
- **Input Text**: 13px, Regular (readable content)
- **Supporting Text**: 11px, Regular (secondary info)
- **Log Text**: 10px, Regular (detailed messages)

## Accessibility Features
- High contrast text on background (WCAG AA compliant)
- Sufficient touch target sizes (46px+ for inputs)
- Clear visual hierarchy
- Color + symbols for status (not color alone)
- Readable font sizes throughout

## Performance Considerations
- No animations to keep lightweight
- Native customtkinter components for efficiency
- Minimal custom drawing
- Color palette uses solid colors (no gradients/transparency overlays)
