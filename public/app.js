// Eesti Radar GIF Generator - Frontend Logic
document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const historySlider = document.getElementById("history-slider");
    const historyVal = document.getElementById("history-val");
    const historyHint = document.getElementById("history-hint");
    
    const forecastSlider = document.getElementById("forecast-slider");
    const forecastVal = document.getElementById("forecast-val");
    const forecastHint = document.getElementById("forecast-hint");
    
    const speedSlider = document.getElementById("speed-slider");
    const speedVal = document.getElementById("speed-val");
    
    const resSelect = document.getElementById("res-select");
    const timestampToggle = document.getElementById("timestamp-toggle");
    
    const generateBtn = document.getElementById("generate-btn");
    const statusDot = document.getElementById("status-indicator");
    const statusText = document.getElementById("status-text");
    
    const previewPlaceholder = document.getElementById("preview-placeholder");
    const previewLoading = document.getElementById("preview-loading");
    const previewResult = document.getElementById("preview-result");
    const resultImg = document.getElementById("result-img");
    const downloadLink = document.getElementById("download-link");
    const progressBar = document.getElementById("progress-bar");
    const presetButtons = document.querySelectorAll(".btn-preset");

    // Bounding box selection variables
    let bboxCoords = {
        minLon: 21.5,
        minLat: 57.5,
        maxLon: 28.5,
        maxLat: 60.5
    };

    // Regional Presets
    const presets = {
        estonia: { minLon: 21.5, minLat: 57.5, maxLon: 28.5, maxLat: 60.5 },
        tallinn: { minLon: 24.1, minLat: 59.2, maxLon: 25.4, maxLat: 59.6 },
        tartu:   { minLon: 26.3, minLat: 58.1, maxLon: 27.2, maxLat: 58.6 },
        west:    { minLon: 21.7, minLat: 57.9, maxLon: 24.3, maxLat: 59.2 },
        east:    { minLon: 25.5, minLat: 58.8, maxLon: 28.2, maxLat: 59.5 }
    };

    // 1. Initialize Map (Leaflet)
    const map = L.map("selection-map", {
        center: [58.6, 25.0], // Center of Estonia
        zoom: 7,
        minZoom: 6,
        maxZoom: 11
    });

    // Elegant Dark Base Map
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    // Bounding Box Rectangle & Handles
    let boundsRect = null;
    let markerTL = null;
    let markerBR = null;

    function initBoundingBox() {
        const bounds = [
            [bboxCoords.minLat, bboxCoords.minLon],
            [bboxCoords.maxLat, bboxCoords.maxLon]
        ];

        // Draw Bounding Box Rectangle with Glowing Accent Border
        boundsRect = L.rectangle(bounds, {
            color: "#3b82f6",
            weight: 2,
            fillColor: "#3b82f6",
            fillOpacity: 0.1,
            className: "glowing-rect"
        }).addTo(map);

        // Custom styled draggable markers for resizing
        const handleIcon = L.divIcon({
            className: "map-resize-handle",
            html: '<div style="width: 12px; height: 12px; background: #3b82f6; border: 2px solid #fff; border-radius: 50%; box-shadow: 0 0 6px rgba(0,0,0,0.5)"></div>',
            iconSize: [12, 12],
            iconAnchor: [6, 6]
        });

        // Top-Left Handle
        markerTL = L.marker([bboxCoords.maxLat, bboxCoords.minLon], {
            draggable: true,
            icon: handleIcon
        }).addTo(map);

        // Bottom-Right Handle
        markerBR = L.marker([bboxCoords.minLat, bboxCoords.maxLon], {
            draggable: true,
            icon: handleIcon
        }).addTo(map);

        // Setup Drag Event Listeners
        markerTL.on("drag", updateRectangleFromHandles);
        markerBR.on("drag", updateRectangleFromHandles);
        
        markerTL.on("dragend", () => removePresetHighlight());
        markerBR.on("dragend", () => removePresetHighlight());
    }

    function updateRectangleFromHandles() {
        const posTL = markerTL.getLatLng();
        const posBR = markerBR.getLatLng();

        // Constrain and define bounds
        bboxCoords.minLon = Math.min(posTL.lng, posBR.lng);
        bboxCoords.maxLon = Math.max(posTL.lng, posBR.lng);
        bboxCoords.minLat = Math.min(posTL.lat, posBR.lat);
        bboxCoords.maxLat = Math.max(posTL.lat, posBR.lat);

        // Make sure it doesn't cross or invert
        boundsRect.setBounds([
            [bboxCoords.minLat, bboxCoords.minLon],
            [bboxCoords.maxLat, bboxCoords.maxLon]
        ]);
        
        // Lock other handles to corners
        markerTL.setLatLng([bboxCoords.maxLat, bboxCoords.minLon]);
        markerBR.setLatLng([bboxCoords.minLat, bboxCoords.maxLon]);
    }

    function setBBoxFromPreset(presetKey) {
        const coords = presets[presetKey];
        if (!coords) return;

        bboxCoords = { ...coords };

        // Animate Map Pan/Zoom to fit the new selection with padding
        const bounds = [
            [bboxCoords.minLat, bboxCoords.minLon],
            [bboxCoords.maxLat, bboxCoords.maxLon]
        ];
        map.flyToBounds(bounds, { padding: [20, 20], duration: 0.8 });

        // Update Rectangle
        boundsRect.setBounds(bounds);

        // Update Draggable Handles
        markerTL.setLatLng([bboxCoords.maxLat, bboxCoords.minLon]);
        markerBR.setLatLng([bboxCoords.minLat, bboxCoords.maxLon]);
    }

    function removePresetHighlight() {
        presetButtons.forEach(btn => btn.classList.remove("active"));
    }

    // 2. Preset Buttons Events
    presetButtons.forEach(button => {
        button.addEventListener("click", () => {
            removePresetHighlight();
            button.classList.add("active");
            setBBoxFromPreset(button.dataset.preset);
        });
    });

    // 3. Slider Binding Logic
    function updateHistorySliderHint() {
        const frames = parseInt(historySlider.value);
        historyVal.textContent = `${frames} kaadrit`;
        
        const minutes = frames * 5;
        const hours = (minutes / 60).toFixed(1);
        if (hours >= 1) {
            historyHint.textContent = `Umbes ${hours} tundi ajalugu (5 min/kaader)`;
        } else {
            historyHint.textContent = `Umbes ${minutes} minutit ajalugu (5 min/kaader)`;
        }
    }

    function updateForecastSliderHint() {
        const frames = parseInt(forecastSlider.value);
        forecastVal.textContent = `${frames} kaadrit`;
        
        const minutes = frames * 5;
        const hours = (minutes / 60).toFixed(1);
        if (frames === 0) {
            forecastHint.textContent = "Prognoos puudub (näita ainult ajalugu)";
        } else if (hours >= 1) {
            forecastHint.textContent = `Umbes ${hours} tundi prognoosi (5 min/kaader)`;
        } else {
            forecastHint.textContent = `Umbes ${minutes} minutit prognoosi (5 min/kaader)`;
        }
    }

    historySlider.addEventListener("input", updateHistorySliderHint);
    forecastSlider.addEventListener("input", updateForecastSliderHint);
    speedSlider.addEventListener("input", () => {
        speedVal.textContent = `${speedSlider.value} ms`;
    });

    // Initialize hints
    updateHistorySliderHint();
    updateForecastSliderHint();

    // 4. Fetch Radar Times and Initialize Dashboard
    let totalHistoryFrames = 36;
    let totalForecastFrames = 18;

    async function checkServerConnection() {
        statusDot.className = "status-dot loading";
        statusText.textContent = "Päritakse radaripilte...";

        try {
            const res = await fetch("api/radar-times");
            if (!res.ok) throw new Error("API base returned an error");
            const data = await res.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            // Successfully loaded times
            totalHistoryFrames = data.existsTimes.length;
            totalForecastFrames = data.sliderConf.nowcastImagesCount || 18;

            // Configure sliders
            historySlider.max = totalHistoryFrames;
            if (parseInt(historySlider.value) > totalHistoryFrames) {
                historySlider.value = totalHistoryFrames;
            }
            forecastSlider.max = totalForecastFrames;
            if (parseInt(forecastSlider.value) > totalForecastFrames) {
                forecastSlider.value = totalForecastFrames;
            }

            updateHistorySliderHint();
            updateForecastSliderHint();

            // Set UI Status to ONLINE
            statusDot.className = "status-dot online";
            statusText.textContent = `Server valmis. Radari ajalugu: ${totalHistoryFrames} kaadrit, prognoos: ${totalForecastFrames} kaadrit.`;
            generateBtn.disabled = false;

        } catch (err) {
            console.error("Connection failed:", err);
            statusDot.className = "status-dot offline";
            statusText.textContent = `Serveri tõrge: ${err.message}. Proovin uuesti...`;
            // Retry in 5 seconds
            setTimeout(checkServerConnection, 5000);
        }
    }

    // Initialize map shapes and fetch WMS times
    initBoundingBox();
    
    // Auto-fit initial bounding box on startup to fit the map viewport perfectly
    // Wait for the container to finish rendering in the DOM, then invalidate size and fit bounds
    setTimeout(() => {
        map.invalidateSize();
        const initialBounds = [
            [bboxCoords.minLat, bboxCoords.minLon],
            [bboxCoords.maxLat, bboxCoords.maxLon]
        ];
        map.fitBounds(initialBounds, { padding: [20, 20] });
    }, 200);
    
    checkServerConnection();

    // 5. Generate weather radar GIF
    let progressTimer = null;
    generateBtn.addEventListener("click", async () => {
        // Disable controls during build
        generateBtn.disabled = true;
        historySlider.disabled = true;
        forecastSlider.disabled = true;
        speedSlider.disabled = true;
        resSelect.disabled = true;
        timestampToggle.disabled = true;
        presetButtons.forEach(btn => btn.disabled = true);

        // Hide previews and show progress loader
        previewPlaceholder.classList.add("hidden");
        previewResult.classList.add("hidden");
        previewLoading.classList.remove("hidden");
        
        // Reset progress bar
        progressBar.style.width = "0%";
        let progress = 0;
        
        // Animate progress bar incrementally to feel premium
        progressTimer = setInterval(() => {
            if (progress < 90) {
                progress += Math.floor(Math.random() * 8) + 2;
                if (progress > 90) progress = 90;
                progressBar.style.width = `${progress}%`;
            }
        }, 300);

        // Calculate exact pixel dimensions of the selected bounding box on the Leaflet map container (pixel-for-pixel!)
        const bounds = boundsRect.getBounds();
        const northEast = bounds.getNorthEast();
        const southWest = bounds.getSouthWest();
        
        // Convert geographic coordinates to Leaflet map container pixel coords
        const pointNE = map.latLngToContainerPoint(northEast);
        const pointSW = map.latLngToContainerPoint(southWest);
        
        const screenWidth = Math.round(Math.abs(pointNE.x - pointSW.x));
        const screenHeight = Math.round(Math.abs(pointNE.y - pointSW.y));
        
        // Apply multiplier (0.5, 1.0, 1.5)
        const multiplier = parseFloat(resSelect.value);
        let finalWidth = Math.round(screenWidth * multiplier);
        let finalHeight = Math.round(screenHeight * multiplier);
        
        // Safety bounds check to prevent API or canvas failures
        finalWidth = Math.max(64, Math.min(finalWidth, 3000));
        finalHeight = Math.max(64, Math.min(finalHeight, 3000));
        
        // Assemble BBox coordinate string (min_lon,min_lat,max_lon,max_lat)
        const bboxString = `${bboxCoords.minLon.toFixed(6)},${bboxCoords.minLat.toFixed(6)},${bboxCoords.maxLon.toFixed(6)},${bboxCoords.maxLat.toFixed(6)}`;

        const requestBody = {
            history_count: parseInt(historySlider.value),
            forecast_count: parseInt(forecastSlider.value),
            srs: "EPSG:4326",
            bbox: bboxString,
            width: finalWidth,
            height: finalHeight,
            delay: parseInt(speedSlider.value),
            include_timestamp: timestampToggle.checked,
            theme: "light"
        };

        try {
            const response = await fetch("api/generate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `Server returnis staatuse ${response.status}`);
            }

            // Finish Progress Bar
            clearInterval(progressTimer);
            progressBar.style.width = "100%";

            // Get response as binary Blob
            const blob = await response.blob();
            const objectURL = URL.createObjectURL(blob);

            // Display result
            resultImg.src = objectURL;
            downloadLink.href = objectURL;
            
            // Format dynamic filename
            const dateStr = new Date().toISOString().replace(/T/, '_').replace(/\..+/, '').replace(/:/g, '-');
            downloadLink.download = `radar_eesti_${dateStr}.gif`;

            // Display preview section
            setTimeout(() => {
                previewLoading.classList.add("hidden");
                previewResult.classList.remove("hidden");
            }, 300);

        } catch (err) {
            clearInterval(progressTimer);
            alert(`GIF-i genereerimine ebaõnnestus: ${err.message}`);
            
            // Reset to placeholder
            previewLoading.classList.add("hidden");
            previewPlaceholder.classList.remove("hidden");
        } finally {
            // Re-enable all controls
            generateBtn.disabled = false;
            historySlider.disabled = false;
            forecastSlider.disabled = false;
            speedSlider.disabled = false;
            resSelect.disabled = false;
            timestampToggle.disabled = false;
            presetButtons.forEach(btn => btn.disabled = false);
        }
    });
});
