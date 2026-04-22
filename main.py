from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random

# ═══════════════════════════════════════════════════════════════════════════════
#  URBAN DRIVE SIMULATION  –  Main Scaffold
#  Members:
#    Member 1 : Dania Siddique  – 24241088  (Car Movement, Speed, Crash/Health)
#    Member 2 : Sadman Rahman   – 24101331  (Traffic, Road, Rule System)
#    Member 3 : Sanzida Hasan   – 22201321  (Police, Camera, Scoring)
# ═══════════════════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────────────────────────
#  WINDOW / VIEWPORT
# ───────────────────────────────────────────────────────────────────────────────
WIN_W               = 1200
WIN_H               = 800
fov_angle           = 75          # perspective field of view (degrees)

# ───────────────────────────────────────────────────────────────────────────────
#  CAMERA  (Member 3 – Sanzida)
# ───────────────────────────────────────────────────────────────────────────────
# Two modes: 0 = top-down orthographic-style, 1 = third-person follow
cam_view_mode       = 1           # 0 → top-view  |  1 → third-person
cam_orbit_yaw       = 0.0         # horizontal rotation around scene (degrees)
cam_orbit_pitch     = 400.0       # vertical height of camera
cam_orbit_dist      = 900.0       # radial distance from player
cam_shake_intensity = 0.0         # camera shake magnitude (collision feedback)
cam_shake_decay     = 0.92        # multiplier applied each frame to decay shake
cam_tilt_offset     = 0.0         # tilt feedback on hard turns
cam_zoom_factor     = 1.0         # zoom-in/out multiplier

# ───────────────────────────────────────────────────────────────────────────────
#  ROAD / WORLD GEOMETRY
# ───────────────────────────────────────────────────────────────────────────────
WORLD_HALF          = 800         # half-size of square world boundary
ROAD_LANE_WIDTH     = 80          # width of one traffic lane
ROAD_BLOCK_SIZE     = 160         # city block size (space between parallel roads)
ROAD_SEGMENT_COUNT  = 5           # number of road segments per axis

# Speed limits keyed by road type: 'main', 'side'
SPEED_LIMIT_TABLE   = {
    "main": 80.0,
    "side": 40.0,
}

# ───────────────────────────────────────────────────────────────────────────────
#  PLAYER CAR  (Member 1 – Dania)
# ───────────────────────────────────────────────────────────────────────────────
plyr_pos_x          = 0.0         # world X position
plyr_pos_y          = 0.0         # world Y position
plyr_heading        = 90.0        # direction the car faces (degrees, 0 = +X axis)
plyr_velocity       = 0.0         # current speed (units/frame, signed: + forward)
plyr_steer_angle    = 0.0         # current steering wheel angle (visual only)

PLYR_ACCEL_RATE     = 0.6         # acceleration per key-held frame
PLYR_BRAKE_RATE     = 1.2         # deceleration per key-held frame
PLYR_FRICTION       = 0.94        # natural speed decay multiplier per frame
PLYR_MAX_SPEED      = 12.0        # forward speed cap (normal)
PLYR_REVERSE_CAP    = 4.0         # reverse speed cap
PLYR_STEER_STEP     = 3.5         # degrees turned per frame at full speed
PLYR_CAR_HALF_LEN   = 55         # half car length (collision box)
PLYR_CAR_HALF_WID   = 28         # half car width  (collision box)

plyr_health         = 100         # 0..100; collision reduces it
plyr_health_max     = 100
PLYR_COLLISION_DMG  = 20          # health lost per collision event
plyr_collision_cd   = 0           # cooldown frames after a collision
PLYR_COLLISION_CD_MAX = 90        # immunity frames

# keys held down (set in keyboard callbacks)
key_accel_held      = False
key_brake_held      = False
key_left_held       = False
key_right_held      = False

# ───────────────────────────────────────────────────────────────────────────────
#  TRAFFIC VEHICLES  (Member 2 – Sadman)
# ───────────────────────────────────────────────────────────────────────────────
TRAFFIC_CAR_COUNT   = 2           # non-player traffic cars visible at once
TRAFFIC_CAR_SPEED   = 3.0         # base speed of NPC traffic
TRAFFIC_MIN_GAP     = 120         # minimum following distance between traffic cars

def _build_traffic_car(tx, ty, heading_deg, lane_tag):
    """Return a dict representing one NPC traffic vehicle."""
    return {
        "x"       : float(tx),
        "y"       : float(ty),
        "heading" : float(heading_deg),
        "speed"   : TRAFFIC_CAR_SPEED,
        "lane"    : lane_tag,       # string label e.g. "main_north"
        "stopped" : False,          # True when obeying red light
    }

# Spawn two traffic cars on opposite sides of origin
traffic_vehicles    = [
    _build_traffic_car(-200, 40, 0,   "main_east"),
    _build_traffic_car( 200, 40, 180, "main_west"),
]

# ───────────────────────────────────────────────────────────────────────────────
#  TRAFFIC SIGNALS  (Member 2 – Sadman)
# ───────────────────────────────────────────────────────────────────────────────
SIGNAL_GREEN_DUR    = 300         # frames signal stays green
SIGNAL_RED_DUR      = 200         # frames signal stays red
signal_phase_timer  = 0           # counts up each frame
signal_is_green     = True        # current phase for the main intersection

# Intersection positions (world coords) – signals placed at road junctions
INTERSECTION_NODES  = [
    {"x":  0.0, "y":  0.0},      # centre
    {"x":  320.0, "y":  0.0},
    {"x": -320.0, "y":  0.0},
    {"x":  0.0, "y":  320.0},
    {"x":  0.0, "y": -320.0},
]

# ───────────────────────────────────────────────────────────────────────────────
#  VIOLATION DETECTION  (Member 2 – Sadman)
# ───────────────────────────────────────────────────────────────────────────────
violation_overspeed_active  = False   # True while player exceeds limit
violation_redlight_active   = False   # True on the frame player crosses on red
# These flags are read by the police system each frame

# ───────────────────────────────────────────────────────────────────────────────
#  CRIME & REWARD  (Member 3 – Sanzida)
# ───────────────────────────────────────────────────────────────────────────────
crime_points        = 0           # increases on violations
reward_points       = 0           # increases for safe driving
CRIME_THRESHOLD     = 5           # crime_points > this → Game Over
CRIME_PER_OVERSPEED = 1
CRIME_PER_REDLIGHT  = 2
REWARD_PER_SAFE_SEC = 1           # reward increment interval (frames)
safe_drive_timer    = 0           # counts frames without violation

# ───────────────────────────────────────────────────────────────────────────────
#  POLICE  (Member 3 – Sanzida)
# ───────────────────────────────────────────────────────────────────────────────
# Police states: "patrol" → "chase" → "attack"
POLICE_STATE_PATROL = "patrol"
POLICE_STATE_CHASE  = "chase"
POLICE_STATE_ATTACK = "attack"

POLICE_PATROL_SPEED = 2.5
POLICE_CHASE_SPEED  = 8.0
POLICE_ATTACK_DIST  = 80.0        # distance at which police "attacks" (game over)
POLICE_SIGHT_RANGE  = 500.0       # range within which police detects player

def _build_police_car(px, py, heading_deg):
    return {
        "x"          : float(px),
        "y"          : float(py),
        "heading"    : float(heading_deg),
        "state"      : POLICE_STATE_PATROL,
        "patrol_waypoint_idx": 0,   # index into patrol route
        "siren_on"   : False,
    }

# Patrol waypoints (looped)
POLICE_PATROL_ROUTE = [
    ( 300,  300),
    (-300,  300),
    (-300, -300),
    ( 300, -300),
]

police_units        = [
    _build_police_car(300, 300, 270),
]

# ───────────────────────────────────────────────────────────────────────────────
#  GAME STATE
# ───────────────────────────────────────────────────────────────────────────────
game_over_flag      = False
game_over_reason    = ""          # "crime" | "health" | ""
frame_counter       = 0           # incremented every idle() call

# ───────────────────────────────────────────────────────────────────────────────
#  HUD BAR GEOMETRY  (rendered in 2-D overlay)
# ───────────────────────────────────────────────────────────────────────────────
HUD_BAR_X           = 20          # left edge of all bars
HUD_HEALTH_Y        = 50          # bottom of health bar
HUD_PENALTY_Y       = 80          # bottom of penalty bar
HUD_REWARD_Y        = 110         # bottom of reward bar
HUD_BAR_W           = 200         # full bar width in screen pixels
HUD_BAR_H           = 18          # bar height in screen pixels


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def deg_to_rad(degrees):
    return degrees * math.pi / 180.0

def angular_diff(alpha, beta):
    """Smallest unsigned difference between two angles (0..180)."""
    raw = abs(alpha - beta) % 360.0
    return raw if raw <= 180.0 else 360.0 - raw

def euclidean_dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)

def clamp_value(val, lo, hi):
    return max(lo, min(hi, val))

def random_world_point(margin=120):
    rx = random.uniform(-WORLD_HALF + margin, WORLD_HALF - margin)
    ry = random.uniform(-WORLD_HALF + margin, WORLD_HALF - margin)
    return rx, ry

def draw_hud_text(scr_x, scr_y, text_string, font=GLUT_BITMAP_HELVETICA_18):
    """Render a string at 2-D screen position using an orthographic overlay."""
    glColor3f(1.0, 1.0, 1.0)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(scr_x, scr_y)
    for ch in text_string:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


# ═══════════════════════════════════════════════════════════════════════════════
#  CAMERA SETUP  (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def setup_camera():
    """
    Configure projection and place the camera.
    cam_view_mode 0 → top-down  |  1 → third-person follow
    Camera shake is added as a random offset when cam_shake_intensity > 0.
    """
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fov_angle * cam_zoom_factor,
                   WIN_W / WIN_H, 1.0, 5000.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    # optional shake offset
    shk_x = random.uniform(-cam_shake_intensity, cam_shake_intensity)
    shk_y = random.uniform(-cam_shake_intensity, cam_shake_intensity)

    if cam_view_mode == 0:
        # ── Top-down view ──
        # Camera directly above origin looking straight down
        gluLookAt(plyr_pos_x + shk_x,
                  plyr_pos_y + shk_y,
                  cam_orbit_dist,            # high above
                  plyr_pos_x, plyr_pos_y, 0,
                  0, 1, 0)                   # north is "up" on screen
    else:
        # ── Third-person follow ──
        rad      = deg_to_rad(cam_orbit_yaw)
        cam_ex   = plyr_pos_x + cam_orbit_dist * math.cos(rad) + shk_x
        cam_ey   = plyr_pos_y + cam_orbit_dist * math.sin(rad) + shk_y
        cam_ez   = cam_orbit_pitch
        gluLookAt(cam_ex, cam_ey, cam_ez,
                  plyr_pos_x, plyr_pos_y, 30.0,
                  0, 0, 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: WORLD GEOMETRY  (shared)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_road_grid():
    """
    Dynamically draw a tiled city floor with road segments.
    Floor tiles are grey; road strips are darker. 
    Do NOT hardcode individual quads – generate via loops.
    (Member 2 completes road markings / lane dividers here)
    """
    TILE_SIZE       = ROAD_LANE_WIDTH
    num_tiles_axis  = int(2 * WORLD_HALF / TILE_SIZE)

    glBegin(GL_QUADS)
    for row in range(num_tiles_axis):
        for col in range(num_tiles_axis):
            x0 = -WORLD_HALF + col * TILE_SIZE
            y0 = -WORLD_HALF + row * TILE_SIZE
            x1 = x0 + TILE_SIZE
            y1 = y0 + TILE_SIZE

            # Road strips run along fixed column/row indices
            on_road = (col % 4 == 0) or (row % 4 == 0)
            if on_road:
                glColor3f(0.22, 0.22, 0.22)   # asphalt
            elif (row + col) % 2 == 0:
                glColor3f(0.55, 0.70, 0.45)   # grassy block A
            else:
                glColor3f(0.50, 0.65, 0.40)   # grassy block B

            glVertex3f(x0, y0, 0.0)
            glVertex3f(x1, y0, 0.0)
            glVertex3f(x1, y1, 0.0)
            glVertex3f(x0, y1, 0.0)
    glEnd()

    # World boundary walls
    H = WORLD_HALF
    WALL_H = 120
    glBegin(GL_QUADS)
    glColor3f(0.6, 0.3, 0.1)   # north
    glVertex3f(-H,  H, 0);  glVertex3f( H,  H, 0)
    glVertex3f( H,  H, WALL_H); glVertex3f(-H,  H, WALL_H)

    glColor3f(0.6, 0.3, 0.1)   # south
    glVertex3f(-H, -H, 0);  glVertex3f( H, -H, 0)
    glVertex3f( H, -H, WALL_H); glVertex3f(-H, -H, WALL_H)

    glColor3f(0.5, 0.25, 0.08)  # west
    glVertex3f(-H, -H, 0);  glVertex3f(-H,  H, 0)
    glVertex3f(-H,  H, WALL_H); glVertex3f(-H, -H, WALL_H)

    glColor3f(0.5, 0.25, 0.08)  # east
    glVertex3f( H, -H, 0);  glVertex3f( H,  H, 0)
    glVertex3f( H,  H, WALL_H); glVertex3f( H, -H, WALL_H)
    glEnd()


def draw_traffic_signal(ix, iy, is_green):
    """
    Draw a simple traffic signal pole at intersection (ix, iy).
    Green/red light shown as a sphere on top of a cylinder.
    (Member 2 – Sadman)
    """
    glPushMatrix()
    glTranslatef(ix, iy, 0)

    # pole
    glColor3f(0.35, 0.35, 0.35)
    gluCylinder(gluNewQuadric(), 4, 4, 80, 6, 2)

    # light sphere
    glTranslatef(0, 0, 80)
    if is_green:
        glColor3f(0.0, 0.95, 0.2)
    else:
        glColor3f(0.95, 0.05, 0.05)
    gluSphere(gluNewQuadric(), 10, 10, 10)

    glPopMatrix()


def draw_all_signals():
    for node in INTERSECTION_NODES:
        draw_traffic_signal(node["x"], node["y"], signal_is_green)


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: PLAYER CAR  (Member 1 – Dania)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_player_car():
    """
    Draw the player-controlled car at (plyr_pos_x, plyr_pos_y) facing plyr_heading.
    Use cylinders for wheels, cuboids for body/roof/hood, spheres for headlights.
    Colour scheme: bright red body.
    Member 1 fills in the detailed shape assembly.
    """
    glPushMatrix()
    glTranslatef(plyr_pos_x, plyr_pos_y, 0)
    glRotatef(plyr_heading, 0, 0, 1)

    # ── car body (cuboid) ──
    glColor3f(0.85, 0.08, 0.08)          # red
    glPushMatrix()
    glTranslatef(0, 0, 22)
    glScalef(PLYR_CAR_HALF_LEN * 2,
             PLYR_CAR_HALF_WID * 2,
             24)
    glutSolidCube(1)
    glPopMatrix()

    # ── roof (cuboid, narrower) ──
    glColor3f(0.70, 0.06, 0.06)
    glPushMatrix()
    glTranslatef(0, 0, 42)
    glScalef(PLYR_CAR_HALF_LEN * 1.1,
             PLYR_CAR_HALF_WID * 1.5,
             18)
    glutSolidCube(1)
    glPopMatrix()

    # ── wheels (4 cylinders) ──
    glColor3f(0.12, 0.12, 0.12)
    wheel_positions = [
        ( PLYR_CAR_HALF_LEN * 0.6,  PLYR_CAR_HALF_WID + 6),
        ( PLYR_CAR_HALF_LEN * 0.6, -PLYR_CAR_HALF_WID - 6),
        (-PLYR_CAR_HALF_LEN * 0.6,  PLYR_CAR_HALF_WID + 6),
        (-PLYR_CAR_HALF_LEN * 0.6, -PLYR_CAR_HALF_WID - 6),
    ]
    for (wx, wy) in wheel_positions:
        glPushMatrix()
        glTranslatef(wx, wy, 12)
        glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 12, 12, 12, 10, 2)
        glPopMatrix()

    # ── headlights (spheres) ──
    glColor3f(1.0, 1.0, 0.7)
    for side in [1, -1]:
        glPushMatrix()
        glTranslatef(PLYR_CAR_HALF_LEN + 2,
                     side * PLYR_CAR_HALF_WID * 0.6,
                     24)
        gluSphere(gluNewQuadric(), 6, 8, 8)
        glPopMatrix()

    glPopMatrix()


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: TRAFFIC CARS  (Member 2 – Sadman)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_single_traffic_car(tc):
    """
    Draw one NPC traffic car (dict from traffic_vehicles).
    Yellow body to distinguish from player.
    Member 2 may extend with lane arrows, indicators, etc.
    """
    glPushMatrix()
    glTranslatef(tc["x"], tc["y"], 0)
    glRotatef(tc["heading"], 0, 0, 1)

    # body
    glColor3f(0.95, 0.80, 0.10)
    glPushMatrix()
    glTranslatef(0, 0, 20)
    glScalef(90, 44, 22)
    glutSolidCube(1)
    glPopMatrix()

    # roof
    glColor3f(0.80, 0.68, 0.08)
    glPushMatrix()
    glTranslatef(0, 0, 38)
    glScalef(55, 36, 16)
    glutSolidCube(1)
    glPopMatrix()

    # wheels
    glColor3f(0.10, 0.10, 0.10)
    for (wx, wy) in [(34, 26), (34, -26), (-34, 26), (-34, -26)]:
        glPushMatrix()
        glTranslatef(wx, wy, 11)
        glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 11, 11, 11, 10, 2)
        glPopMatrix()

    glPopMatrix()


def draw_all_traffic_cars():
    for tc in traffic_vehicles:
        draw_single_traffic_car(tc)


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: POLICE CAR  (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_single_police_car(pc):
    """
    Draw a police car: black-and-white body with 'POLICE' label on the side,
    a blue/red siren dome on the roof.
    Member 3 adds siren flashing animation via frame_counter.
    """
    glPushMatrix()
    glTranslatef(pc["x"], pc["y"], 0)
    glRotatef(pc["heading"], 0, 0, 1)

    # ── main body: white front half ──
    glColor3f(0.95, 0.95, 0.95)
    glPushMatrix()
    glTranslatef(18, 0, 20)
    glScalef(54, 44, 22)
    glutSolidCube(1)
    glPopMatrix()

    # ── main body: black rear half ──
    glColor3f(0.08, 0.08, 0.08)
    glPushMatrix()
    glTranslatef(-18, 0, 20)
    glScalef(54, 44, 22)
    glutSolidCube(1)
    glPopMatrix()

    # ── black roof ──
    glColor3f(0.08, 0.08, 0.08)
    glPushMatrix()
    glTranslatef(0, 0, 38)
    glScalef(55, 36, 16)
    glutSolidCube(1)
    glPopMatrix()

    # ── siren dome (alternates red/blue each 20 frames) ──
    siren_blue_phase = (frame_counter // 20) % 2 == 0
    if siren_blue_phase:
        glColor3f(0.05, 0.2, 0.95)
    else:
        glColor3f(0.95, 0.05, 0.05)
    glPushMatrix()
    glTranslatef(0, 0, 54)
    gluSphere(gluNewQuadric(), 9, 8, 8)
    glPopMatrix()

    # ── wheels ──
    glColor3f(0.10, 0.10, 0.10)
    for (wx, wy) in [(34, 26), (34, -26), (-34, 26), (-34, -26)]:
        glPushMatrix()
        glTranslatef(wx, wy, 11)
        glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 11, 11, 11, 10, 2)
        glPopMatrix()

    # ── "POLICE" text on side (bitmap characters, projected in 3-D) ──
    # NOTE: glutBitmapCharacter is 2-D; text is drawn via HUD overlay
    # in draw_hud() when a police car is near. 3-D label done here with
    # a flat coloured strip that Member 3 can extend.
    glColor3f(0.05, 0.05, 0.60)
    glPushMatrix()
    glTranslatef(0, 23, 22)
    glScalef(55, 4, 10)
    glutSolidCube(1)
    glPopMatrix()

    glPopMatrix()


def draw_all_police_cars():
    for pc in police_units:
        draw_single_police_car(pc)


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: HUD BARS & TEXT  (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_hud_bar(bar_x, bar_y, bar_w, bar_h,
                 fill_ratio,
                 fill_r, fill_g, fill_b,
                 label_str):
    """
    Draw a labelled horizontal progress bar at 2-D screen coords.
    fill_ratio in [0.0, 1.0].
    Uses gluOrtho2D overlay (same technique as draw_hud_text).
    """
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # background track
    glColor3f(0.25, 0.25, 0.25)
    glBegin(GL_QUADS)
    glVertex3f(bar_x,           bar_y,          0)
    glVertex3f(bar_x + bar_w,   bar_y,          0)
    glVertex3f(bar_x + bar_w,   bar_y + bar_h,  0)
    glVertex3f(bar_x,           bar_y + bar_h,  0)
    glEnd()

    # filled portion
    filled_w = bar_w * clamp_value(fill_ratio, 0.0, 1.0)
    glColor3f(fill_r, fill_g, fill_b)
    glBegin(GL_QUADS)
    glVertex3f(bar_x,            bar_y,          0)
    glVertex3f(bar_x + filled_w, bar_y,          0)
    glVertex3f(bar_x + filled_w, bar_y + bar_h,  0)
    glVertex3f(bar_x,            bar_y + bar_h,  0)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    # label
    draw_hud_text(bar_x + bar_w + 8, bar_y, label_str, GLUT_BITMAP_HELVETICA_12)


def draw_hud():
    """Render all HUD elements: bars + text overlays."""
    # ── Health bar ──
    draw_hud_bar(HUD_BAR_X, HUD_HEALTH_Y,
                 HUD_BAR_W, HUD_BAR_H,
                 plyr_health / plyr_health_max,
                 0.15, 0.85, 0.20,
                 f"Health  {plyr_health}/{plyr_health_max}")

    # ── Penalty bar (crime) ──
    draw_hud_bar(HUD_BAR_X, HUD_PENALTY_Y,
                 HUD_BAR_W, HUD_BAR_H,
                 crime_points / CRIME_THRESHOLD,
                 0.88, 0.12, 0.12,
                 f"Penalty  {crime_points}/{CRIME_THRESHOLD}")

    # ── Reward bar ──
    reward_display_max = 20
    draw_hud_bar(HUD_BAR_X, HUD_REWARD_Y,
                 HUD_BAR_W, HUD_BAR_H,
                 reward_points / reward_display_max,
                 0.10, 0.55, 0.95,
                 f"Reward  {reward_points}")

    # ── Speed readout ──
    speed_kmh = abs(plyr_velocity) * 10          # rough conversion
    limit_now = SPEED_LIMIT_TABLE["main"]
    speed_col_flag = speed_kmh > limit_now
    if speed_col_flag:
        glColor3f(1.0, 0.2, 0.2)
    else:
        glColor3f(1.0, 1.0, 1.0)
    draw_hud_text(WIN_W - 260, WIN_H - 36,
                  f"Speed: {speed_kmh:.0f} km/h  Limit: {limit_now:.0f}",
                  GLUT_BITMAP_HELVETICA_18)

    # ── Signal indicator ──
    sig_str = "Signal: GREEN  GO" if signal_is_green else "Signal: RED  STOP"
    draw_hud_text(WIN_W - 260, WIN_H - 62, sig_str, GLUT_BITMAP_HELVETICA_18)

    # ── Police state ──
    if police_units:
        draw_hud_text(WIN_W - 260, WIN_H - 88,
                      f"Police: {police_units[0]['state'].upper()}",
                      GLUT_BITMAP_HELVETICA_18)

    # ── Camera mode indicator ──
    cam_label = "CAM: TOP" if cam_view_mode == 0 else "CAM: 3RD"
    draw_hud_text(10, WIN_H - 36, cam_label, GLUT_BITMAP_HELVETICA_12)

    # ── Game Over overlay ──
    if game_over_flag:
        draw_hud_text(WIN_W // 2 - 220, WIN_H // 2,
                      f"GAME OVER – {game_over_reason.upper()}  |  Press R to Restart",
                      GLUT_BITMAP_TIMES_ROMAN_24)


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: PLAYER MOVEMENT  (Member 1 – Dania)
# ═══════════════════════════════════════════════════════════════════════════════

def update_player_movement():
    """
    Apply acceleration/braking/steering each frame.
    Clamps position to world boundary.
    Member 1 fills in detailed physics and steering curve.
    """
    global plyr_velocity, plyr_heading, plyr_pos_x, plyr_pos_y

    if game_over_flag:
        return

    # accelerate / brake
    if key_accel_held:
        plyr_velocity = clamp_value(plyr_velocity + PLYR_ACCEL_RATE,
                                    -PLYR_REVERSE_CAP, PLYR_MAX_SPEED)
    elif key_brake_held:
        plyr_velocity = clamp_value(plyr_velocity - PLYR_BRAKE_RATE,
                                    -PLYR_REVERSE_CAP, PLYR_MAX_SPEED)
    else:
        plyr_velocity *= PLYR_FRICTION      # coast to stop

    # steering (only effective while moving)
    if abs(plyr_velocity) > 0.3:
        steer_dir = 0
        if key_left_held:
            steer_dir = 1
        elif key_right_held:
            steer_dir = -1
        # scale steering by speed so it's tighter at high speed
        effective_steer = PLYR_STEER_STEP * steer_dir * (
            1.0 - abs(plyr_velocity) / (PLYR_MAX_SPEED * 2.5))
        plyr_heading = (plyr_heading + effective_steer) % 360.0

    # move along heading
    rad           = deg_to_rad(plyr_heading)
    nx            = plyr_pos_x + math.cos(rad) * plyr_velocity
    ny            = plyr_pos_y + math.sin(rad) * plyr_velocity
    plyr_pos_x    = clamp_value(nx, -WORLD_HALF + 60, WORLD_HALF - 60)
    plyr_pos_y    = clamp_value(ny, -WORLD_HALF + 60, WORLD_HALF - 60)


def update_player_health(dmg):
    """Reduce health and trigger camera shake. Member 1 owns this."""
    global plyr_health, plyr_collision_cd, cam_shake_intensity, game_over_flag, game_over_reason
    if plyr_collision_cd > 0:
        return
    plyr_health        -= dmg
    plyr_collision_cd   = PLYR_COLLISION_CD_MAX
    cam_shake_intensity = 18.0
    if plyr_health <= 0 and not game_over_flag:
        plyr_health        = 0
        game_over_flag     = True
        game_over_reason   = "health"


def update_speed_system():
    """
    Compute real-time speed and check against limit.
    Member 1 sets violation_overspeed_active here.
    """
    global violation_overspeed_active
    speed_kmh = abs(plyr_velocity) * 10
    violation_overspeed_active = speed_kmh > SPEED_LIMIT_TABLE["main"]


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: TRAFFIC SYSTEM  (Member 2 – Sadman)
# ═══════════════════════════════════════════════════════════════════════════════

def update_traffic_signals():
    """Advance signal phase timer and flip green/red. Member 2 owns this."""
    global signal_phase_timer, signal_is_green
    signal_phase_timer += 1
    phase_dur = SIGNAL_GREEN_DUR if signal_is_green else SIGNAL_RED_DUR
    if signal_phase_timer >= phase_dur:
        signal_is_green    = not signal_is_green
        signal_phase_timer = 0


def update_traffic_movement():
    """
    Move NPC traffic cars along their lanes.
    Maintain safe gap between consecutive vehicles.
    Stop at red lights near intersections.
    Member 2 completes lane logic and spacing checks here.
    """
    for tc in traffic_vehicles:
        # simple placeholder: move forward in heading direction
        rad    = deg_to_rad(tc["heading"])
        near_red = False

        # check if near an intersection on red
        for node in INTERSECTION_NODES:
            if euclidean_dist(tc["x"], tc["y"],
                              node["x"], node["y"]) < 90 and not signal_is_green:
                near_red = True
                break

        tc["stopped"] = near_red
        if not near_red:
            tc["x"] += math.cos(rad) * tc["speed"]
            tc["y"] += math.sin(rad) * tc["speed"]

            # wrap around world edges (loop along lane)
            if abs(tc["x"]) > WORLD_HALF - 40:
                tc["x"] *= -0.9
            if abs(tc["y"]) > WORLD_HALF - 40:
                tc["y"] *= -0.9


def update_violation_detection():
    """
    Detect red-light crossing by player.
    Sends flags read by crime/police systems.
    Member 2 completes crossing detection geometry here.
    """
    global violation_redlight_active
    violation_redlight_active = False
    if signal_is_green:
        return
    # Check if player is moving through any intersection on red
    for node in INTERSECTION_NODES:
        if (euclidean_dist(plyr_pos_x, plyr_pos_y,
                           node["x"], node["y"]) < 70
                and abs(plyr_velocity) > 1.0):
            violation_redlight_active = True
            break


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: CRIME & REWARD  (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def update_crime_reward():
    """
    Increment crime on violations, reward on clean driving.
    Trigger game over if crime exceeds threshold.
    Member 3 owns this.
    """
    global crime_points, reward_points
    global safe_drive_timer, game_over_flag, game_over_reason

    if game_over_flag:
        return

    # violations increment crime
    if violation_overspeed_active:
        crime_points = min(crime_points + CRIME_PER_OVERSPEED, CRIME_THRESHOLD + 1)
    if violation_redlight_active:
        crime_points = min(crime_points + CRIME_PER_REDLIGHT, CRIME_THRESHOLD + 1)

    # game over on crime threshold
    if crime_points > CRIME_THRESHOLD and not game_over_flag:
        game_over_flag   = True
        game_over_reason = "crime"
        return

    # safe driving rewards
    if not violation_overspeed_active and not violation_redlight_active:
        safe_drive_timer += 1
        if safe_drive_timer >= REWARD_PER_SAFE_SEC * 60:
            reward_points   += 1
            safe_drive_timer = 0
    else:
        safe_drive_timer = 0


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: POLICE SYSTEM  (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def update_police_system():
    """
    State machine: patrol → chase → attack.
    Triggered by violation flags from Member 2.
    Member 3 fills in patrol waypoint cycling and chase steering.
    """
    global game_over_flag, game_over_reason

    violation_detected = violation_overspeed_active or violation_redlight_active

    for pc in police_units:
        dist_to_player = euclidean_dist(pc["x"], pc["y"],
                                         plyr_pos_x, plyr_pos_y)

        # ── state transitions ──
        if pc["state"] == POLICE_STATE_PATROL:
            if violation_detected and dist_to_player < POLICE_SIGHT_RANGE:
                pc["state"]   = POLICE_STATE_CHASE
                pc["siren_on"] = True

        elif pc["state"] == POLICE_STATE_CHASE:
            if not violation_detected and dist_to_player > POLICE_SIGHT_RANGE * 1.3:
                pc["state"]    = POLICE_STATE_PATROL
                pc["siren_on"] = False
            elif dist_to_player < POLICE_ATTACK_DIST:
                pc["state"] = POLICE_STATE_ATTACK

        elif pc["state"] == POLICE_STATE_ATTACK:
            if dist_to_player > POLICE_ATTACK_DIST * 1.5:
                pc["state"] = POLICE_STATE_CHASE

        # ── movement per state ──
        if pc["state"] == POLICE_STATE_PATROL:
            # move toward next waypoint
            wp   = POLICE_PATROL_ROUTE[pc["patrol_waypoint_idx"]]
            ddx  = wp[0] - pc["x"]
            ddy  = wp[1] - pc["y"]
            dist_wp = math.hypot(ddx, ddy)
            if dist_wp < 30:
                pc["patrol_waypoint_idx"] = (
                    pc["patrol_waypoint_idx"] + 1) % len(POLICE_PATROL_ROUTE)
            else:
                pc["x"] += (ddx / dist_wp) * POLICE_PATROL_SPEED
                pc["y"] += (ddy / dist_wp) * POLICE_PATROL_SPEED
                pc["heading"] = math.degrees(math.atan2(ddy, ddx))

        elif pc["state"] in (POLICE_STATE_CHASE, POLICE_STATE_ATTACK):
            # chase player
            ddx  = plyr_pos_x - pc["x"]
            ddy  = plyr_pos_y - pc["y"]
            dist_p = math.hypot(ddx, ddy)
            if dist_p > 1:
                spd = POLICE_CHASE_SPEED
                pc["x"]       += (ddx / dist_p) * spd
                pc["y"]       += (ddy / dist_p) * spd
                pc["heading"]  = math.degrees(math.atan2(ddy, ddx))

        # ── attack damages player ──
        if pc["state"] == POLICE_STATE_ATTACK:
            update_player_health(PLYR_COLLISION_DMG // 2)


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: CAMERA FEEDBACK  (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def update_camera_feedback():
    """Decay shake; compute tilt from steering; adjust zoom during chase."""
    global cam_shake_intensity, cam_tilt_offset, cam_zoom_factor

    # decay shake
    cam_shake_intensity *= cam_shake_decay
    if cam_shake_intensity < 0.5:
        cam_shake_intensity = 0.0

    # tilt follows steering
    if key_left_held:
        cam_tilt_offset = clamp_value(cam_tilt_offset + 0.8, -12, 12)
    elif key_right_held:
        cam_tilt_offset = clamp_value(cam_tilt_offset - 0.8, -12, 12)
    else:
        cam_tilt_offset *= 0.85

    # zoom in slightly during police chase
    chasing = any(pc["state"] == POLICE_STATE_CHASE for pc in police_units)
    target_zoom = 0.85 if chasing else 1.0
    cam_zoom_factor += (target_zoom - cam_zoom_factor) * 0.04


# ═══════════════════════════════════════════════════════════════════════════════
#  MASTER UPDATE  (called every idle frame)
# ═══════════════════════════════════════════════════════════════════════════════

def update_all_systems():
    global frame_counter, plyr_collision_cd
    frame_counter      += 1

    if plyr_collision_cd > 0:
        plyr_collision_cd -= 1

    update_player_movement()
    update_speed_system()
    update_traffic_signals()
    update_traffic_movement()
    update_violation_detection()
    update_crime_reward()
    update_police_system()
    update_camera_feedback()


# ═══════════════════════════════════════════════════════════════════════════════
#  RESET
# ═══════════════════════════════════════════════════════════════════════════════

def reset_simulation():
    global plyr_pos_x, plyr_pos_y, plyr_heading, plyr_velocity
    global plyr_health, plyr_collision_cd
    global crime_points, reward_points, safe_drive_timer
    global signal_phase_timer, signal_is_green
    global violation_overspeed_active, violation_redlight_active
    global game_over_flag, game_over_reason, frame_counter
    global cam_shake_intensity, cam_tilt_offset, cam_zoom_factor
    global cam_orbit_yaw, cam_orbit_pitch
    global key_accel_held, key_brake_held, key_left_held, key_right_held

    plyr_pos_x = plyr_pos_y  = 0.0
    plyr_heading             = 90.0
    plyr_velocity            = 0.0
    plyr_health              = plyr_health_max
    plyr_collision_cd        = 0
    crime_points             = 0
    reward_points            = 0
    safe_drive_timer         = 0
    signal_phase_timer       = 0
    signal_is_green          = True
    violation_overspeed_active = False
    violation_redlight_active  = False
    game_over_flag           = False
    game_over_reason         = ""
    frame_counter            = 0
    cam_shake_intensity      = 0.0
    cam_tilt_offset          = 0.0
    cam_zoom_factor          = 1.0
    cam_orbit_yaw            = 0.0
    cam_orbit_pitch          = 400.0
    key_accel_held = key_brake_held = key_left_held = key_right_held = False

    # reset traffic
    traffic_vehicles[0].update({"x": -200, "y": 40, "heading": 0,   "stopped": False})
    traffic_vehicles[1].update({"x":  200, "y": 40, "heading": 180, "stopped": False})

    # reset police
    for pc in police_units:
        pc.update({"x": 300, "y": 300, "heading": 270,
                   "state": POLICE_STATE_PATROL,
                   "patrol_waypoint_idx": 0, "siren_on": False})


# ═══════════════════════════════════════════════════════════════════════════════
#  INPUT CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

def keyboard_down(key, x, y):
    """GLUT keyboardFunc – key pressed."""
    global key_accel_held, key_brake_held, key_left_held, key_right_held
    global cam_view_mode

    if key == b'r':
        reset_simulation()
        return

    if game_over_flag:
        return

    if key == b'w':
        key_accel_held  = True
    if key == b's':
        key_brake_held  = True
    if key == b'a':
        key_left_held   = True
    if key == b'd':
        key_right_held  = True

    # toggle camera view
    if key == b'c':
        cam_view_mode   = 1 - cam_view_mode


def keyboard_up(key, x, y):
    """GLUT keyboardUpFunc – key released."""
    global key_accel_held, key_brake_held, key_left_held, key_right_held

    if key == b'w':
        key_accel_held  = False
    if key == b's':
        key_brake_held  = False
    if key == b'a':
        key_left_held   = False
    if key == b'd':
        key_right_held  = False


def special_key_down(key, x, y):
    """Arrow keys: orbit camera around scene."""
    global cam_orbit_yaw, cam_orbit_pitch

    if key == GLUT_KEY_LEFT:
        cam_orbit_yaw   = (cam_orbit_yaw  + 4) % 360
    if key == GLUT_KEY_RIGHT:
        cam_orbit_yaw   = (cam_orbit_yaw  - 4) % 360
    if key == GLUT_KEY_UP:
        cam_orbit_pitch = clamp_value(cam_orbit_pitch + 20, 80, 1800)
    if key == GLUT_KEY_DOWN:
        cam_orbit_pitch = clamp_value(cam_orbit_pitch - 20, 80, 1800)


def mouse_click(button, state, mx, my):
    """Mouse: reserved for future use (e.g. horn, indicator)."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
#  GLUT CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

def idle_callback():
    update_all_systems()
    glutPostRedisplay()


def display_callback():
    glClearColor(0.53, 0.81, 0.98, 1.0)    # sky blue background
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WIN_W, WIN_H)

    setup_camera()

    # ── 3-D scene ──
    draw_road_grid()
    draw_all_signals()
    draw_player_car()
    draw_all_traffic_cars()
    draw_all_police_cars()

    # ── 2-D HUD overlay ──
    draw_hud()

    glutSwapBuffers()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WIN_W, WIN_H)
    glutInitWindowPosition(100, 50)
    glutCreateWindow(b"Urban Drive Simulation")

    glutDisplayFunc(display_callback)
    glutKeyboardFunc(keyboard_down)
    glutKeyboardUpFunc(keyboard_up)
    glutSpecialFunc(special_key_down)
    glutMouseFunc(mouse_click)
    glutIdleFunc(idle_callback)

    glutMainLoop()


if __name__ == "__main__":
    main()