# 🌧️ Eesti Radar GIF Generator

A modern, highly polished, and fully-functional desktop application to generate pixel-perfect, highly optimized weather radar GIFs directly from the Estonian Environment Agency's WMS service.

Instead of generic screen recordings or video-to-GIF conversions that degrade quality and increase file size, this application queries the official Estonian Geoserver Web Map Service (WMS) endpoints for raw transparent overlays and composites them in parallel, yielding ultra-compact, crisp, and high-fidelity loops.

---

## ✨ Key Features & Technical Achievements

* **Zero-Quality-Loss WMS Compositing**: Downloads raw PNG frames directly from `ilmgs.envir.ee` in parallel (`ThreadPoolExecutor`) for both observations (`ilm:cmp_cap` history) and nowcasting (`ilm:nowcasting` forecast).
* **Grayscale Base Map Blend (Maa-amet)**: Converts Maa-amet's detailed colored aluskaart (`MA-ALUS` group layer) into a soft light-grayscale background (`85%` map, `15%` solid white) within Pillow. This neutral base guarantees that the lightest light-blue precipitation clouds are **100% visible and sharp** over both land and sea.
* **Pixel-for-Pixel Viewport Selection**: Calculates the exact coordinate-to-container boundary pixels directly from Leaflet, meaning the compiled GIF is cropped exactly 1:1 to your onscreen selection box.
* **Resolution Multipliers**: Choose from `0.5×` (highly compact/small file), `1.0×` (native pixel mapping), or `1.5×` (high-definition export).
* **High-Contrast City & Label Overlay**: Automatically composites a readable, transparent station labels map (`ilm:station_map`) directly *on top* of the radar data, so cities remain perfectly legible even through heavy storm fronts.
* **Mathematically Aligned Badge Overlay**: Draws a beautiful, glassmorphic overlay pill in the top-left corner tracking frame states. Includes a color-coded status indicator dot and timestamp text, perfectly centered vertically using font ascent calculations.
* **Color-Coded Bottom Progress Timeline**: Automatically draws a dynamic `6px` progress line at the very bottom of each GIF frame that advances chronologically:
  * 🔵 **Blue** for observation history frames.
  * 🟠 **Orange** for forecasted forecast frames.
* **Interactive Leaflet Dashboard**: A clean, responsive glassmorphic slate-dark control panel featuring custom range sliders, regional presets (Tallinn, Tartu, Islands, etc.), and a drag-and-resize bounding box selector that auto-scales itself to fit the map viewport perfectly on startup.

---

## 📂 Project Structure

```bash
radar_gif/
├── public/                 # Static front-end assets
│   ├── index.html          # Glassmorphic user interface
│   ├── design.css          # Dashboard styling and color variables
│   └── app.js              # Leaflet bindings & async API hooks
├── app.py                  # Single-file Python web server & GIF compositer
├── requirements.txt        # Python dependency list
├── .gitignore              # Git ignore rules for clean commits
└── README.md               # Project documentation (this file)
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
Ensure you have Python 3.x installed on your system. 

### 2. Install Dependencies
The backend requires the standard Python Image Library (`Pillow`) for canvas composition and GIF compiling. Install it using pip:
```bash
pip install -r requirements.txt
```

### 3. Run the Application
Start the lightweight local server:
```bash
python app.py
```
The server will initialize and begin listening on:
> **[http://localhost:8096](http://localhost:8096)**

### 4. Customizing Your GIF
1. **Define Selection**: Drag, resize, or use presets (e.g. *Tallinn & Põhja-Eesti*) to frame the bounding box on the dark Leaflet map.
2. **Configure Parameters**: Choose your desired number of History frames (up to 36, ~3 hours back) and Forecast frames (up to 18, ~1.5 hours ahead), loop delay (frame speed), and multiplier scale.
3. **Generate & Download**: Click **Genereeri GIF**. Once compiled, enjoy the in-browser preview and click **Laadi GIF alla** to save it locally.

---

## 🛠️ Technology Stack
* **Backend**: Pure Python (using built-in `http.server` for zero-configuration, `urllib` for parsing ilmateenistus radar times, and `Pillow` for image compositing).
* **Frontend**: HTML5, CSS3 (featuring glassmorphism layouts and custom slider overrides), Vanilla JavaScript (Leaflet map coordinates integration).
* **Map Providers**:
  * Dashboard Map: CartoDB Dark Matter (`dark_all` tiles).
  * GIF Background Map: Maa-amet Topographic Base Map (`MA-ALUS` layer in EPSG:3301 LEST97).
  * Overlays: Estonian Environment Agency Geoserver WMS (`ilmgs.envir.ee`).

---

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
