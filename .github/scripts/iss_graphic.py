import math
import datetime


def render_iss_svg(d, polygons, track):
    # ---- Defensive input sanitation ------------------------------------
    if not isinstance(d, dict):
        d = {}
    clean_polys = []
    for ring in (polygons or []):
        cr = []
        for p in (ring or []):
            try:
                cr.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError, IndexError):
                continue
        if len(cr) >= 3:
            clean_polys.append(cr)
    polygons = clean_polys

    # ---- Canvas / layout ------------------------------------------------
    W, H = 1000, 640
    MX, MY = 40, 96
    MW = 920
    MH = MW / 2  # equirectangular: height = width / 2  -> 460
    PANEL_Y = MY + MH + 18  # telemetry panel below map

    # ---- Palette (tokyonight) ------------------------------------------
    C_BG = "#0d1117"
    C_PANEL = "#11131c"
    C_MAP_BG = "#0b0e17"
    C_DOT = "#2b3a67"        # land dots (muted blue)
    C_GRID = "#1c2438"
    C_AXIS = "#27304a"
    C_NIGHT = "#060912"      # night overlay (dark)
    C_TRACK = "#7aa2f7"      # ground track
    C_ISS = "#7ee787"        # ISS accent (neon green)
    C_TEXT = "#c0caf5"
    C_TEXT_DIM = "#565f89"
    C_ACCENT = "#58a6ff"
    C_CYAN = "#38bdae"

    # ---- Safe telemetry extraction -------------------------------------
    def fnum(key, default=0.0):
        try:
            return float(d.get(key, default))
        except (TypeError, ValueError):
            return default

    lat = fnum("latitude", 0.0)
    lon = fnum("longitude", 0.0)
    alt = fnum("altitude", 0.0)
    vel = fnum("velocity", 0.0)
    foot = fnum("footprint", 0.0)
    vis = str(d.get("visibility", "unknown"))
    ts = d.get("timestamp", None)
    sol_lat = fnum("solar_lat", 0.0)
    sol_lon = fnum("solar_lon", 0.0)
    units = str(d.get("units", "kilometers"))

    def clamp(v, lo, hi):
        return lo if v < lo else (hi if v > hi else v)

    lat = clamp(lat, -89.999, 89.999)
    lon = ((lon + 180.0) % 360.0) - 180.0

    try:
        if ts is not None:
            dt = datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            time_str = "--:--:-- UTC"
    except (TypeError, ValueError, OSError, OverflowError):
        time_str = "--:--:-- UTC"

    # ---- Projection helpers --------------------------------------------
    def px(lo):
        return MX + (lo + 180.0) / 360.0 * MW

    def py(la):
        return MY + (90.0 - la) / 180.0 * MH

    def fmtf(v, nd=2):
        return ("%." + str(nd) + "f") % v

    parts = []
    parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="%d" height="%d" viewBox="0 0 %d %d" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">'
        % (W, H, W, H)
    )

    # ---- defs ----------------------------------------------------------
    parts.append("<defs>")
    parts.append(
        '<filter id="glow" x="-80%" y="-80%" width="260%" height="260%">'
        '<feGaussianBlur stdDeviation="3.2" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
    )
    parts.append(
        '<filter id="trackglow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="1.4"/></filter>'
    )
    parts.append(
        '<radialGradient id="mapgrad" cx="50%" cy="42%" r="75%">'
        '<stop offset="0%" stop-color="#101524"/>'
        '<stop offset="100%" stop-color="' + C_MAP_BG + '"/></radialGradient>'
    )
    parts.append(
        '<linearGradient id="bggrad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#0e1018"/>'
        '<stop offset="100%" stop-color="' + C_BG + '"/></linearGradient>'
    )
    parts.append("</defs>")

    # ---- Background ----------------------------------------------------
    parts.append('<rect x="0" y="0" width="%d" height="%d" fill="url(#bggrad)"/>' % (W, H))
    parts.append(
        '<rect x="0.5" y="0.5" width="%0.1f" height="%0.1f" fill="none" '
        'stroke="%s" stroke-width="1" rx="6"/>' % (W - 1, H - 1, C_AXIS)
    )

    # ---- Header --------------------------------------------------------
    parts.append(
        '<text x="40" y="42" fill="%s" font-size="22" font-weight="700" '
        'letter-spacing="3">ISS &#183; ORBITAL TELEMETRY</text>' % C_TEXT
    )
    parts.append(
        '<text x="40" y="64" fill="%s" font-size="11" letter-spacing="2">'
        'LIVE GROUND TRACK &#183; DOT-MATRIX WORLD &#183; EQUIRECTANGULAR</text>'
        % C_TEXT_DIM
    )
    sun = vis.lower().startswith("sun") or vis.lower() == "daylight"
    pill_col = "#f7c14d" if sun else C_ACCENT
    pill_txt = "SUNLIT" if sun else ("ECLIPSED" if vis.lower().startswith("ecl") else vis.upper())
    parts.append(
        '<rect x="%0.1f" y="26" width="150" height="26" rx="13" fill="none" '
        'stroke="%s" stroke-width="1.2"/>' % (W - 190, pill_col)
    )
    parts.append(
        '<circle cx="%0.1f" cy="39" r="4" fill="%s"><animate attributeName="opacity" '
        'values="1;0.3;1" dur="2.2s" repeatCount="indefinite"/></circle>'
        % (W - 174, pill_col)
    )
    parts.append(
        '<text x="%0.1f" y="43" fill="%s" font-size="12" font-weight="700" '
        'letter-spacing="2">%s</text>' % (W - 160, pill_col, pill_txt)
    )

    # ---- Map base ------------------------------------------------------
    parts.append(
        '<rect x="%0.1f" y="%0.1f" width="%0.1f" height="%0.1f" rx="4" '
        'fill="url(#mapgrad)" stroke="%s" stroke-width="1"/>'
        % (MX, MY, MW, MH, C_AXIS)
    )
    parts.append(
        '<clipPath id="mapclip"><rect x="%0.1f" y="%0.1f" width="%0.1f" '
        'height="%0.1f" rx="4"/></clipPath>' % (MX, MY, MW, MH)
    )
    parts.append('<g clip-path="url(#mapclip)">')

    # ---- Graticule -----------------------------------------------------
    grat = []
    for glon in range(-180, 181, 30):
        x = px(glon)
        grat.append('<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f"/>'
                    % (x, MY, x, MY + MH))
    for glat in range(-90, 91, 30):
        y = py(glat)
        grat.append('<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f"/>'
                    % (MX, y, MX + MW, y))
    parts.append('<g stroke="%s" stroke-width="0.6">%s</g>' % (C_GRID, "".join(grat)))
    parts.append('<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f" stroke="%s" '
                 'stroke-width="0.8" stroke-dasharray="2 4"/>'
                 % (MX, py(0), MX + MW, py(0), C_AXIS))
    parts.append('<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f" stroke="%s" '
                 'stroke-width="0.8" stroke-dasharray="2 4"/>'
                 % (px(0), MY, px(0), MY + MH, C_AXIS))

    # ---- Point in polygon (even-odd) -----------------------------------
    def point_in_ring(plon, plat, ring):
        inside = False
        n = len(ring)
        if n < 3:
            return False
        j = n - 1
        for i in range(n):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            if (yi > plat) != (yj > plat):
                denom = (yj - yi)
                if denom != 0.0:
                    xint = xi + (plat - yi) * (xj - xi) / denom
                    if plon < xint:
                        inside = not inside
            j = i
        return inside

    bboxes = []
    for ring in polygons:
        if not ring:
            bboxes.append(None)
            continue
        mnx = mny = 1e9
        mxx = mxy = -1e9
        for p in ring:
            lo, la = p[0], p[1]
            if lo < mnx: mnx = lo
            if lo > mxx: mxx = lo
            if la < mny: mny = la
            if la > mxy: mxy = la
        bboxes.append((mnx, mny, mxx, mxy))

    def is_land(plon, plat):
        for ring, bb in zip(polygons, bboxes):
            if bb is None:
                continue
            if plon < bb[0] or plon > bb[2] or plat < bb[1] or plat > bb[3]:
                continue
            if point_in_ring(plon, plat, ring):
                return True
        return False

    # ---- Dot-matrix continents -----------------------------------------
    STEP_LON = 2.0
    STEP_LAT = 2.0
    R_DOT = 1.5

    dots = []
    plat = 88.0
    while plat >= -88.0:
        rscale = max(0.55, math.cos(math.radians(plat)) ** 0.35)
        plon = -179.0
        while plon <= 179.0:
            if is_land(plon, plat):
                dots.append((px(plon), py(plat), R_DOT * rscale))
            plon += STEP_LON
        plat -= STEP_LAT

    dot_main = []
    for (x, y, r) in dots:
        dot_main.append('<circle cx="%0.1f" cy="%0.1f" r="%0.2f"/>' % (x, y, r))
    parts.append('<g fill="%s" opacity="0.9">%s</g>' % (C_DOT, "".join(dot_main)))

    # ---- Day / Night terminator overlay --------------------------------
    SL = math.radians(sol_lat)
    SLON = math.radians(sol_lon)

    def is_day(plat_d, plon_d):
        la = math.radians(plat_d)
        lo = math.radians(plon_d)
        return (math.sin(la) * math.sin(SL)
                + math.cos(la) * math.cos(SL) * math.cos(lo - SLON)) > 0

    def term_lat(plon_d):
        try:
            t = math.tan(SL)
            if abs(t) < 1e-9:
                return 0.0
            v = -math.cos(math.radians(plon_d) - SLON) / t
            return math.degrees(math.atan(v))
        except (ValueError, ZeroDivisionError):
            return 0.0

    term_pts = []
    for lo in range(-180, 181, 2):
        term_pts.append((px(lo), py(term_lat(lo))))

    north_is_night = not is_day(89.0, sol_lon)
    if north_is_night:
        pole_y = MY
        night_poly = [(px(180), pole_y), (px(-180), pole_y)] + term_pts
    else:
        pole_y = MY + MH
        night_poly = term_pts + [(px(180), pole_y), (px(-180), pole_y)]

    pts_str = " ".join("%0.1f,%0.1f" % (x, y) for (x, y) in night_poly)
    parts.append('<polygon points="%s" fill="%s" opacity="0.55"/>' % (pts_str, C_NIGHT))
    tline = " ".join("%0.1f,%0.1f" % (x, y) for (x, y) in term_pts)
    parts.append(
        '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.1" '
        'opacity="0.5" stroke-dasharray="4 3"/>' % (tline, "#3a4a7a")
    )

    sx, sy = px(((sol_lon + 180) % 360) - 180), py(clamp(sol_lat, -89, 89))
    parts.append(
        '<g opacity="0.85"><circle cx="%0.1f" cy="%0.1f" r="4.5" fill="#f7c14d"/>'
        '<circle cx="%0.1f" cy="%0.1f" r="9" fill="none" stroke="#f7c14d" '
        'stroke-width="0.8" opacity="0.5"/></g>' % (sx, sy, sx, sy)
    )

    # ---- Ground track (with antimeridian split) ------------------------
    segs = []
    cur = []
    prev_lon = None
    for pt in (track or []):
        try:
            tla = float(pt[0])
            tlo = float(pt[1])
        except (TypeError, ValueError, IndexError):
            continue
        if prev_lon is not None and abs(tlo - prev_lon) > 180.0:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
        cur.append((px(((tlo + 180) % 360) - 180), py(clamp(tla, -89.99, 89.99))))
        prev_lon = tlo
    if len(cur) > 1:
        segs.append(cur)

    track_paths = []
    for seg in segs:
        track_paths.append(" ".join("%0.1f,%0.1f" % (x, y) for (x, y) in seg))

    for tp in track_paths:
        parts.append(
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="3.2" '
            'opacity="0.25" filter="url(#trackglow)" stroke-linecap="round" '
            'stroke-linejoin="round"/>' % (tp, C_TRACK)
        )
    for tp in track_paths:
        parts.append(
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.4" '
            'opacity="0.95" stroke-linecap="round" stroke-linejoin="round"/>'
            % (tp, C_TRACK)
        )

    # ---- Footprint ellipse ---------------------------------------------
    if foot > 0:
        lat_r = (foot / 2.0) / 111.0
        lon_r = lat_r / max(math.cos(math.radians(lat)), 0.25)
        rx_px = lon_r / 360.0 * MW
        ry_px = lat_r / 180.0 * MH
        cx_p, cy_p = px(lon), py(lat)
        parts.append(
            '<ellipse cx="%0.1f" cy="%0.1f" rx="%0.1f" ry="%0.1f" fill="%s" '
            'opacity="0.07"/>' % (cx_p, cy_p, rx_px, ry_px, C_ISS)
        )
        parts.append(
            '<ellipse cx="%0.1f" cy="%0.1f" rx="%0.1f" ry="%0.1f" fill="none" '
            'stroke="%s" stroke-width="1" opacity="0.5" stroke-dasharray="3 4"/>'
            % (cx_p, cy_p, rx_px, ry_px, C_ISS)
        )

    # ---- ISS marker (neon + pulse) -------------------------------------
    mx, my = px(lon), py(lat)
    parts.append('<g filter="url(#glow)">')
    parts.append(
        '<circle cx="%0.1f" cy="%0.1f" r="6" fill="none" stroke="%s" '
        'stroke-width="1.4" opacity="0.9">'
        '<animate attributeName="r" values="6;22" dur="2.6s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="0.9;0" dur="2.6s" '
        'repeatCount="indefinite"/></circle>' % (mx, my, C_ISS)
    )
    parts.append(
        '<circle cx="%0.1f" cy="%0.1f" r="6" fill="none" stroke="%s" '
        'stroke-width="1.2" opacity="0.7">'
        '<animate attributeName="r" values="6;22" dur="2.6s" begin="1.3s" '
        'repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="0.7;0" dur="2.6s" begin="1.3s" '
        'repeatCount="indefinite"/></circle>' % (mx, my, C_ISS)
    )
    parts.append(
        '<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f" stroke="%s" '
        'stroke-width="1"/>' % (mx - 12, my, mx - 5, my, C_ISS)
    )
    parts.append(
        '<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f" stroke="%s" '
        'stroke-width="1"/>' % (mx + 5, my, mx + 12, my, C_ISS)
    )
    parts.append(
        '<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f" stroke="%s" '
        'stroke-width="1"/>' % (mx, my - 12, mx, my - 5, C_ISS)
    )
    parts.append(
        '<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f" stroke="%s" '
        'stroke-width="1"/>' % (mx, my + 5, mx, my + 12, C_ISS)
    )
    parts.append(
        '<circle cx="%0.1f" cy="%0.1f" r="4" fill="%s">'
        '<animate attributeName="r" values="4;5.2;4" dur="2.6s" '
        'repeatCount="indefinite"/></circle>' % (mx, my, C_ISS)
    )
    parts.append("</g>")

    lblx = mx + 14
    anchor = "start"
    if lblx > MX + MW - 90:
        lblx = mx - 14
        anchor = "end"
    parts.append(
        '<text x="%0.1f" y="%0.1f" fill="%s" font-size="10" font-weight="700" '
        'text-anchor="%s" letter-spacing="1">ISS</text>'
        % (lblx, my - 8, C_ISS, anchor)
    )

    parts.append("</g>")  # end mapclip group

    # ---- Map border re-stroke + corner ticks ---------------------------
    parts.append(
        '<rect x="%0.1f" y="%0.1f" width="%0.1f" height="%0.1f" rx="4" '
        'fill="none" stroke="%s" stroke-width="1"/>'
        % (MX, MY, MW, MH, C_AXIS)
    )
    for (cx, cy, dx, dy) in [
        (MX, MY, 1, 1), (MX + MW, MY, -1, 1),
        (MX, MY + MH, 1, -1), (MX + MW, MY + MH, -1, -1),
    ]:
        parts.append(
            '<path d="M%0.1f %0.1f L%0.1f %0.1f M%0.1f %0.1f L%0.1f %0.1f" '
            'stroke="%s" stroke-width="1.5" fill="none"/>'
            % (cx, cy + dy * 12, cx, cy, cx, cy, cx + dx * 12, cy, C_ACCENT)
        )

    for glon in range(-180, 181, 60):
        parts.append(
            '<text x="%0.1f" y="%0.1f" fill="%s" font-size="8.5" '
            'text-anchor="middle">%d&#176;</text>'
            % (px(glon), MY + MH + 12, C_TEXT_DIM, glon)
        )
    for glat in range(-60, 61, 30):
        parts.append(
            '<text x="%0.1f" y="%0.1f" fill="%s" font-size="8.5" '
            'text-anchor="end">%d&#176;</text>'
            % (MX - 6, py(glat) + 3, C_TEXT_DIM, glat)
        )

    # ---- Telemetry panel ----------------------------------------------
    u = "km" if units.lower().startswith("kilo") else units
    fields = [
        ("LATITUDE", fmtf(lat, 4) + "&#176;", C_TEXT),
        ("LONGITUDE", fmtf(lon, 4) + "&#176;", C_TEXT),
        ("ALTITUDE", fmtf(alt, 1) + " " + u, C_CYAN),
        ("VELOCITY", fmtf(vel, 0) + " " + u + "/h", C_ACCENT),
        ("FOOTPRINT", fmtf(foot, 0) + " " + u, C_TEXT),
        ("VISIBILITY", pill_txt, pill_col),
    ]

    n = len(fields)
    gap = 10
    cell_w = (MW - gap * (n - 1)) / n
    cy_top = PANEL_Y
    cell_h = 58
    for i, (label, val, col) in enumerate(fields):
        cx0 = MX + i * (cell_w + gap)
        parts.append(
            '<rect x="%0.1f" y="%0.1f" width="%0.1f" height="%0.1f" rx="5" '
            'fill="%s" stroke="%s" stroke-width="1"/>'
            % (cx0, cy_top, cell_w, cell_h, C_PANEL, C_AXIS)
        )
        parts.append(
            '<rect x="%0.1f" y="%0.1f" width="3" height="%0.1f" rx="1.5" fill="%s"/>'
            % (cx0, cy_top, cell_h, col)
        )
        parts.append(
            '<text x="%0.1f" y="%0.1f" fill="%s" font-size="9" letter-spacing="1.5">'
            '%s</text>' % (cx0 + 12, cy_top + 20, C_TEXT_DIM, label)
        )
        parts.append(
            '<text x="%0.1f" y="%0.1f" fill="%s" font-size="15" font-weight="700">'
            '%s</text>' % (cx0 + 12, cy_top + 43, col, val)
        )

    fy = cy_top + cell_h + 26
    parts.append(
        '<text x="%0.1f" y="%0.1f" fill="%s" font-size="11" letter-spacing="1">'
        'EPOCH &#183; <tspan fill="%s" font-weight="700">%s</tspan></text>'
        % (MX, fy, C_TEXT_DIM, C_TEXT, time_str)
    )
    lx = MX + MW
    parts.append(
        '<g font-size="9.5" fill="%s">'
        '<circle cx="%0.1f" cy="%0.1f" r="3.5" fill="%s"/>'
        '<text x="%0.1f" y="%0.1f" text-anchor="end">ISS</text>'
        '<line x1="%0.1f" y1="%0.1f" x2="%0.1f" y2="%0.1f" stroke="%s" '
        'stroke-width="1.6"/><text x="%0.1f" y="%0.1f" text-anchor="end">ORBIT</text>'
        '<rect x="%0.1f" y="%0.1f" width="10" height="8" fill="%s" opacity="0.6"/>'
        '<text x="%0.1f" y="%0.1f" text-anchor="end">NIGHT</text>'
        "</g>"
        % (
            C_TEXT_DIM,
            lx - 250, fy - 3.5, C_ISS,
            lx - 232, fy,
            lx - 210, fy - 3.5, lx - 190, fy - 3.5, C_TRACK,
            lx - 145, fy,
            lx - 120, fy - 7.5, C_NIGHT,
            lx, fy,
        )
    )

    parts.append("</svg>")
    return "".join(parts)