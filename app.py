import json
import os
import re
import urllib.request
import urllib.parse
import datetime
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

PORT = 8096
PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "public")

def get_tallinn_time(utc_dt):
    # Estonia is UTC+2 in winter, UTC+3 in summer (DST).
    # DST starts: last Sunday of March at 01:00 UTC
    # DST ends: last Sunday of October at 01:00 UTC
    year = utc_dt.year
    
    # Last Sunday of March
    march_31 = datetime.datetime(year, 3, 31, 1, 0, tzinfo=datetime.timezone.utc)
    dst_start = march_31 - datetime.timedelta(days=(march_31.weekday() + 1) % 7)
    
    # Last Sunday of October
    october_31 = datetime.datetime(year, 10, 31, 1, 0, tzinfo=datetime.timezone.utc)
    dst_end = october_31 - datetime.timedelta(days=(october_31.weekday() + 1) % 7)
    
    if dst_start <= utc_dt < dst_end:
        offset_hours = 3
    else:
        offset_hours = 2
        
    return utc_dt + datetime.timedelta(hours=offset_hours)

def wgs84_to_lest97(lat, lon):
    # WGS84 ellipsoid
    a = 6378137.0
    f = 1.0 / 298.257222101
    e2 = 2 * f - f * f
    e = math.sqrt(e2)

    # LEST97 projection parameters
    lat1 = math.radians(58.0)
    lat2 = math.radians(59.3333333333)
    lat0 = math.radians(57.5175538889)
    lon0 = math.radians(24.0)
    X0 = 500000.0
    Y0 = 6375000.0

    phi = math.radians(lat)
    lam = math.radians(lon)

    m1 = math.cos(lat1) / math.sqrt(1 - e2 * math.sin(lat1)**2)
    m2 = math.cos(lat2) / math.sqrt(1 - e2 * math.sin(lat2)**2)
    t1 = math.tan(math.pi/4 - lat1/2) / ((1 - e * math.sin(lat1)) / (1 + e * math.sin(lat1)))**(e/2)
    t2 = math.tan(math.pi/4 - lat2/2) / ((1 - e * math.sin(lat2)) / (1 + e * math.sin(lat2)))**(e/2)
    t0 = math.tan(math.pi/4 - lat0/2) / ((1 - e * math.sin(lat0)) / (1 + e * math.sin(lat0)))**(e/2)
    t = math.tan(math.pi/4 - phi/2) / ((1 - e * math.sin(phi)) / (1 + e * math.sin(phi)))**(e/2)

    n = math.log(m1 / m2) / math.log(t1 / t2)
    F = m1 / (n * t1**n)
    
    rho0 = a * F * t0**n
    rho = a * F * t**n
    theta = n * (lam - lon0)

    x = X0 + rho * math.sin(theta)
    y = Y0 + rho0 - rho * math.cos(theta)
    return x, y

def wgs84_bbox_to_lest97(bbox_str):
    lon_min, lat_min, lon_max, lat_max = map(float, bbox_str.split(","))
    x_min, y_min = wgs84_to_lest97(lat_min, lon_min)
    x_max, y_max = wgs84_to_lest97(lat_max, lon_max)
    return f"{min(x_min, x_max):.2f},{min(y_min, y_max):.2f},{max(x_min, x_max):.2f},{max(y_min, y_max):.2f}"

class RadarHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/radar-times":
            self.handle_radar_times()
        else:
            self.handle_static_file()

    def do_POST(self):
        if self.path == "/api/generate":
            self.handle_generate_gif()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_static_file(self):
        # Serve files from public folder
        path = self.path.split("?")[0]
        if path == "/":
            path = "/index.html"
            
        file_path = os.path.join(PUBLIC_DIR, path.lstrip("/"))
        
        # Security check to prevent directory traversal
        real_public_dir = os.path.realpath(PUBLIC_DIR)
        real_file_path = os.path.realpath(file_path)
        if not real_file_path.startswith(real_public_dir):
            self.send_error(403, "Access Denied")
            return

        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            # Send content type
            if file_path.endswith(".html"):
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif file_path.endswith(".css"):
                self.send_header("Content-Type", "text/css")
            elif file_path.endswith(".js"):
                self.send_header("Content-Type", "application/javascript")
            elif file_path.endswith(".png"):
                self.send_header("Content-Type", "image/png")
            elif file_path.endswith(".gif"):
                self.send_header("Content-Type", "image/gif")
            elif file_path.endswith(".json"):
                self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "File Not Found")

    def handle_radar_times(self):
        try:
            url = "https://www.ilmateenistus.ee/ilm/ilmavaatlused/radar/"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')

            # Parse ExistsTimes and sliderConf
            exists_times_match = re.search(r'_var\["ExistsTimes"\]\s*=\s*(.*?);', html)
            slider_conf_match = re.search(r'_var\["sliderConf"\]\s*=\s*(.*?);', html)

            if not exists_times_match or not slider_conf_match:
                self.send_error_json(500, "Could not parse radar times from the official website.")
                return

            exists_times = json.loads(exists_times_match.group(1))
            slider_conf = json.loads(slider_conf_match.group(1))

            response_data = {
                "existsTimes": exists_times,
                "sliderConf": slider_conf
            }

            self.send_json_response(200, response_data)
        except Exception as e:
            self.send_error_json(500, f"Error fetching radar times: {str(e)}")

    def handle_generate_gif(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            params = json.loads(post_data.decode('utf-8'))
        except Exception as e:
            self.send_error_json(400, f"Invalid JSON parameters: {str(e)}")
            return

        history_count = int(params.get("history_count", 12))
        forecast_count = int(params.get("forecast_count", 12))
        srs = params.get("srs", "EPSG:4326")
        bbox = params.get("bbox", "21.5,57.5,28.5,60.5") # Estonia Lat/Lon default
        width = int(params.get("width", 800))
        height = int(params.get("height", 600))
        delay = int(params.get("delay", 200)) # in ms
        include_timestamp = bool(params.get("include_timestamp", True))
        theme = params.get("theme", "dark") # "dark" or "light" or "transparent"

        try:
            # 1. Fetch current available times from the radar page
            url = "https://www.ilmateenistus.ee/ilm/ilmavaatlused/radar/"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')

            exists_times_match = re.search(r'_var\["ExistsTimes"\]\s*=\s*(.*?);', html)
            if not exists_times_match:
                self.send_error_json(500, "Failed to retrieve current radar timestamps.")
                return
            exists_times = json.loads(exists_times_match.group(1))

            # Restrict history frames
            history_count = min(max(1, history_count), len(exists_times))
            history_times = exists_times[-history_count:]
            latest_history_time = history_times[-1]

            # Parse the zero-point time to datetime (we assume UTC format "YYYY-MM-DDTHH:MM:SS.SSSZ")
            # Usually like "2026-05-29T15:25:00.000Z"
            dt_format = "%Y-%m-%dT%H:%M:%S.%fZ"
            try:
                zero_point_dt = datetime.datetime.strptime(latest_history_time, dt_format)
            except ValueError:
                # Fallback to without milliseconds if needed
                zero_point_dt = datetime.datetime.strptime(latest_history_time.split(".")[0] + "Z", "%Y-%m-%dT%H:%M:%SZ")

            # 2. Compute forecast times (5-minute intervals starting after zero-point)
            forecast_times = []
            for i in range(1, forecast_count + 1):
                f_dt = zero_point_dt + datetime.timedelta(minutes=5 * i)
                # Format to standard ISO string
                forecast_times.append(f_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"))

            # Convert incoming EPSG:4326 Lat/Lon BBOX to EPSG:3301 LEST97
            lest97_bbox = wgs84_bbox_to_lest97(bbox)
            
            # We always use the high-quality Maa-amet topographic base map on a solid white background
            base_wms_url = "http://kaart.maaamet.ee/wms/alus"
            base_layers = "MA-ALUS"
            bg_color = (255, 255, 255, 255)

            print(f"Generating GIF: History={len(history_times)}, Forecast={len(forecast_times)}, ZeroPoint={latest_history_time}")
            print(f"LEST97 BBOX: {lest97_bbox}")

            # 3. Create parallel download jobs
            # Fetch the base map and station labels map in parallel!
            base_map_params = {
                "SERVICE": "WMS",
                "VERSION": "1.1.1",
                "REQUEST": "GetMap",
                "LAYERS": base_layers,
                "FORMAT": "image/png",
                "TRANSPARENT": "true",
                "WIDTH": str(width),
                "HEIGHT": str(height),
                "SRS": "EPSG:3301",
                "BBOX": lest97_bbox
            }
            station_map_params = {
                "SERVICE": "WMS",
                "VERSION": "1.1.1",
                "REQUEST": "GetMap",
                "LAYERS": "ilm:station_map",
                "FORMAT": "image/png",
                "TRANSPARENT": "true",
                "WIDTH": str(width),
                "HEIGHT": str(height),
                "SRS": "EPSG:3301",
                "BBOX": lest97_bbox
            }
            
            static_maps = [None, None]
            def fetch_static_map(idx_and_params):
                idx, (url_val, params_val) = idx_and_params
                img = self.fetch_wms_layer(url_val, params_val)
                static_maps[idx] = img
                
            with ThreadPoolExecutor(max_workers=2) as exec_static:
                exec_static.map(fetch_static_map, [
                    (0, (base_wms_url, base_map_params)),
                    (1, ("https://ilmgs.envir.ee/geoserver/ilm/wms", station_map_params))
                ])
                
            base_map_image, station_map_image = static_maps
            
            if not base_map_image:
                self.send_error_json(500, "Failed to download the base map from the WMS server.")
                return

            # Combine tasks: (index, is_forecast, timestamp)
            tasks = []
            for idx, t_str in enumerate(history_times):
                tasks.append((idx, False, t_str))
            for idx, t_str in enumerate(forecast_times):
                tasks.append((len(history_times) + idx, True, t_str))

            # Fetch overlays in parallel!
            radar_frames = [None] * len(tasks)

            def fetch_frame_worker(task):
                task_idx, is_forecast, t_str = task
                if is_forecast:
                    layer_url = "https://ilmgs.envir.ee/geoserver/ilm/wms"
                    layer_params = {
                        "SERVICE": "WMS",
                        "VERSION": "1.1.1",
                        "REQUEST": "GetMap",
                        "LAYERS": "ilm:nowcasting",
                        "STYLES": "ilm:opera_radar",
                        "FORMAT": "image/png",
                        "TRANSPARENT": "true",
                        "WIDTH": str(width),
                        "HEIGHT": str(height),
                        "SRS": "EPSG:3301",
                        "BBOX": lest97_bbox,
                        "TIME": t_str
                    }
                else:
                    layer_url = "https://ilmgs.envir.ee/geoserver/ilm/wms"
                    layer_params = {
                        "SERVICE": "WMS",
                        "VERSION": "1.1.1",
                        "REQUEST": "GetMap",
                        "LAYERS": "ilm:cmp_cap",
                        "STYLES": "ilm:opera_radar_talv",
                        "FORMAT": "image/png",
                        "TRANSPARENT": "true",
                        "WIDTH": str(width),
                        "HEIGHT": str(height),
                        "SRS": "EPSG:3301",
                        "BBOX": lest97_bbox,
                        "TIME": t_str
                    }
                
                img = self.fetch_wms_layer(layer_url, layer_params)
                radar_frames[task_idx] = (is_forecast, t_str, img)

            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(fetch_frame_worker, tasks)

            # 4. Composite the frames
            compiled_frames = []
            
            # Setup background canvas: solid white for our grayscale theme
            bg_color = (255, 255, 255, 255)

            total_frames = len(radar_frames)
            for frame_idx, (is_forecast, t_str, radar_img) in enumerate(radar_frames):
                # Create background canvas
                frame_canvas = Image.new("RGBA", (width, height), bg_color)
                
                # Blend base map (convert to a beautiful, soft light grayscale)
                if base_map_image:
                    gray = base_map_image.convert("L")
                    gray_rgba = Image.merge("RGBA", (gray, gray, gray, Image.new("L", base_map_image.size, 255)))
                    # Blend with solid white to construct a premium soft light grayscale background
                    white_img = Image.new("RGBA", base_map_image.size, (255, 255, 255, 255))
                    soft_gray = Image.blend(white_img, gray_rgba, 0.85)
                    frame_canvas.alpha_composite(soft_gray)
                
                # Blend radar data if available
                if radar_img:
                    frame_canvas.alpha_composite(radar_img)
                
                # Overlay station map (city names and labels) on top of the radar!
                if station_map_image:
                    frame_canvas.alpha_composite(station_map_image)
                
                # Render timestamp and indicators if active
                if include_timestamp:
                    self.draw_overlay_ui(frame_canvas, is_forecast, t_str, zero_point_dt, width, height)
                
                # Draw the timeline progress bar at the very bottom (6px height)
                progress_x = int((frame_idx + 1) / total_frames * width)
                draw = ImageDraw.Draw(frame_canvas)
                
                # Draw background light gray line
                draw.rectangle([0, height - 6, width, height], fill=(226, 232, 240, 255))
                
                # Determine state and color matching
                if is_forecast:
                    # Forecast (Orange)
                    color = (249, 115, 22, 255)
                else:
                    # History (Blue)
                    color = (59, 130, 246, 255)
                
                # Draw active progress segment
                draw.rectangle([0, height - 6, progress_x, height], fill=color)
                
                # Convert frame to P mode with adaptive palette to ensure compact & beautiful GIF representation
                p_frame = frame_canvas.convert("RGB").quantize(colors=256, method=Image.Quantize.MAXCOVERAGE)
                compiled_frames.append(p_frame)

            # 5. Output the GIF as raw bytes
            temp_gif_path = os.path.join(PUBLIC_DIR, "radar_temp.gif")
            compiled_frames[0].save(
                temp_gif_path,
                save_all=True,
                append_images=compiled_frames[1:],
                duration=delay,
                loop=0,
                optimize=True
            )

            # Read the temporary GIF and return it
            with open(temp_gif_path, "rb") as f:
                gif_data = f.read()

            # Clean up temp file
            try:
                os.remove(temp_gif_path)
            except:
                pass

            # Return the file directly
            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.send_header("Content-Length", str(len(gif_data)))
            # Content-Disposition to name it nicely if downloaded directly
            filename = f"radar_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.gif"
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(gif_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error_json(500, f"Failed to generate radar GIF: {str(e)}")

    def fetch_wms_layer(self, base_url, params):
        query = urllib.parse.urlencode(params)
        url = f"{base_url}?{query}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
                if data[:4] == b'\x89PNG':
                    # Load as PIL Image
                    from io import BytesIO
                    return Image.open(BytesIO(data)).convert("RGBA")
                else:
                    # Not a PNG, probably WMS exception xml
                    print(f"WMS error for layer {params.get('LAYERS')}: {data[:300].decode('utf-8', errors='ignore')}")
                    return None
        except Exception as e:
            print(f"Error fetching WMS layer: {e}")
            return None

    def draw_overlay_ui(self, image, is_forecast, t_str, zero_point_dt, width, height):
        draw = ImageDraw.Draw(image)
        
        # Parse timestamp into Tallinn local time
        # WMS times are in UTC, e.g. "2026-05-29T12:30:00.000Z"
        try:
            utc_dt = datetime.datetime.strptime(t_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            utc_dt = datetime.datetime.strptime(t_str.split(".")[0] + "Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
            
        tallinn_dt = get_tallinn_time(utc_dt)
        time_str = tallinn_dt.strftime("%H:%M")
        
        # Label text (pure Blue for History, Orange for Forecast)
        label_text = f"FORECAST {time_str}" if is_forecast else f"HISTORY {time_str}"
        dot_color = (249, 115, 22, 255) if is_forecast else (59, 130, 246, 255)

        # Try to load a clean default font
        font = None
        try:
            # Try loading a standard font from Windows directory
            font_paths = [
                "C:\\Windows\\Fonts\\segoeuib.ttf",  # Segoe UI Bold
                "C:\\Windows\\Fonts\\arialbd.ttf",   # Arial Bold
                "C:\\Windows\\Fonts\\tahoma.ttf",    # Tahoma
            ]
            for path in font_paths:
                if os.path.exists(path):
                    font = ImageFont.truetype(path, 12)
                    break
        except:
            pass
            
        if not font:
            font = ImageFont.load_default()

        # Measure text size
        # draw.textbbox is available in newer Pillow versions
        try:
            text_bbox = draw.textbbox((0, 0), label_text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
        except:
            # Fallback
            text_w, text_h = draw.textsize(label_text, font=font) if hasattr(draw, "textsize") else (120, 16)
            text_bbox = (0, 0, text_w, text_h)

        # Draw a beautiful background pill for the label (Top Left)
        padding_x = 12
        padding_y = 6
        badge_w = text_w + padding_x * 2 + 16 # Extra room for the status dot
        badge_h = text_h + padding_y * 2
        
        # Position: Top Left
        pos_x = 15
        pos_y = 15
        
        # Background: Glassmorphic dark badge with border
        draw.rounded_rectangle(
            [pos_x, pos_y, pos_x + badge_w, pos_y + badge_h],
            radius=8,
            fill=(15, 23, 42, 220), # Slate-900 high opacity
            outline=(51, 65, 85, 255), # Slate-700 border
            width=1
        )
        
        # Draw indicator dot (perfectly centered vertically inside the badge)
        dot_radius = 4
        dot_x = pos_x + padding_x + dot_radius
        dot_y = pos_y + (badge_h // 2)
        draw.ellipse(
            [dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius],
            fill=dot_color
        )
        
        # Draw Text (perfectly centered vertically inside the badge)
        text_draw_y = pos_y + (badge_h // 2) - ((text_bbox[3] + text_bbox[1]) // 2)
        draw.text(
            (pos_x + padding_x + 14, text_draw_y),
            label_text,
            fill=(248, 250, 252, 255), # Slate-50 near white
            font=font
        )

    def send_json_response(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_json(self, status, message):
        self.send_json_response(status, {"error": message})

def run():
    # Make sure public folder exists
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, RadarHTTPHandler)
    print(f"Starting Eesti Radar GIF Generator server on http://localhost:{PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == '__main__':
    run()
