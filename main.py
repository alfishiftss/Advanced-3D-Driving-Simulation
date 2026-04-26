from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random

# ═══════════════════════════════════════════════════════════════════════════════
#  URBAN DRIVE SIMULATION  –  Complete Implementation
#  Member 1 : Dania Siddique  – 24241088  (Car Movement, Speed, Crash/Health)
#  Member 2 : Sadman Rahman   – 24101331  (Traffic, Road, Rule System)
#  Member 3 : Sanzida Hasan   – 22201321  (Police, Camera, Scoring)
# ═══════════════════════════════════════════════════════════════════════════════

WIN_W  = 1200
WIN_H  = 800

# ───────────────────────────────────────────────────────────────────────────────
#  ROAD / WORLD GEOMETRY   ── Member 2 : Sadman ──
# ───────────────────────────────────────────────────────────────────────────────
# World is now much larger so the player has plenty of road to drive on
WORLD_HALF      = 6000            # was 2000 – 3x bigger road

# Three parallel lanes running along the X-axis.  Lane 0 = northernmost.
LANE_WIDTH      = 120
LANE_CENTRES    = [LANE_WIDTH, 0.0, -LANE_WIDTH]
ROAD_HALF_W     = LANE_WIDTH * 1.5   # 180

DASH_LEN        = 80
DASH_GAP        = 60
DASH_Z          = 1.2

# Traffic light sits further ahead so the player has time to react
SIGNAL_X        = 1200.0
SIGNAL_DETECT_R = 110.0
# Green 10 s, Red 4 s at ~60 fps
GREEN_FRAMES    = 600             # 600 frames ≈ 10 s
RED_FRAMES      = 240             # 240 frames ≈ 4 s
signal_phase_timer = 0
signal_is_green    = True

# ── Member 2 : speed limit raised to 120 km/h ──
SPEED_LIMIT_KMH = 120.0
# Display formula: kmh_display = abs(plyr_vel) * KMH_SCALE
# MAX_VEL = 20 units/frame → 20 * 6 = 120 km/h at full throttle
KMH_SCALE       = 6.0

# ───────────────────────────────────────────────────────────────────────────────
#  PLAYER CAR   ── Member 1 : Dania ──
# ───────────────────────────────────────────────────────────────────────────────
plyr_x          = -4000.0         # spawn near west end of expanded world
plyr_y          = LANE_CENTRES[2]
plyr_heading    = 0.0
plyr_vel        = 0.0             # starts at exactly 0 km/h
plyr_target_lane= 2
PLYR_HALF_LEN   = 55
PLYR_HALF_WID   = 28

# ── Member 1 : very gradual acceleration ──
# ACCEL_RATE is tiny: reaching 120 km/h (vel=20) takes ~250 frames ≈ 4 s of
# held W key, which feels realistic and not instant.
ACCEL_RATE      = 0.05            # units/frame per frame  (was 0.55 – way too fast)
BRAKE_RATE      = 0.15            # deceleration when S held
FRICTION        = 0.985           # coast-down multiplier each frame
MAX_VEL         = 20.0            # 20 * 6 = 120 km/h display cap
REVERSE_CAP     = 2.0
LANE_SNAP_SPEED = 3.5

# ── Member 1 : health / collision system ──
plyr_health     = 100
plyr_health_max = 100
COLLISION_DMG   = 34              # ~3 hits to destroy the car
plyr_hit_cd     = 0
HIT_CD_MAX      = 90

# ── Member 1 : collision flash ──
boom_flash_timer = 0
BOOM_FLASH_DUR   = 50

# ── Member 1 : held-key states ──
k_up    = False
k_down  = False
k_left  = False
k_right = False

lane_change_active   = False
lane_change_target_y = LANE_CENTRES[2]

# ───────────────────────────────────────────────────────────────────────────────
#  NPC TRAFFIC CARS   ── Member 2 : Sadman ──
# ───────────────────────────────────────────────────────────────────────────────
NPC_MIN_GAP    = 180
# NPC cars are slow city traffic – about 25-30 km/h display
NPC_BASE_SPEED = 0.55             # units/frame  (0.55 * 6 ≈ 33 km/h)

def _mk_npc(start_x, lane_idx):
    return {
        "x"      : float(start_x),
        "y"      : float(LANE_CENTRES[lane_idx]),
        "lane"   : lane_idx,
        "speed"  : NPC_BASE_SPEED + random.uniform(-0.05, 0.10),
        "stopped": False,
    }

npc_cars = [
    _mk_npc(-1000, 0),
    _mk_npc(  500, 1),
]

# ───────────────────────────────────────────────────────────────────────────────
#  VIOLATION / FINE   ── Member 2 : Sadman ──
# ───────────────────────────────────────────────────────────────────────────────
wallet         = 15
FINE_AMOUNT    = 5
fine_cooldown  = 0
FINE_CD_MAX    = 240

overspeed_flag = False
redlight_flag  = False

# ───────────────────────────────────────────────────────────────────────────────
#  CRIME   ── Member 3 : Sanzida ──
#  (Reward feature removed as requested)
# ───────────────────────────────────────────────────────────────────────────────
crime_pts      = 0
CRIME_MAX      = 10
CRIME_PER_VIO  = 2

# ───────────────────────────────────────────────────────────────────────────────
#  POLICE CAR   ── Member 3 : Sanzida ──
# ───────────────────────────────────────────────────────────────────────────────
POLICE_PATROL  = "patrol"
POLICE_CHASE   = "chase"
POLICE_PULLOVER= "pullover"       # replaces ATTACK – police stops beside player

police = {
    "x"         : 800.0,
    "y"         : LANE_CENTRES[0],
    "heading"   : 180.0,
    "state"     : POLICE_PATROL,
    "patrol_dir": -1,
    "pullover_timer": 0,          # counts down after reaching player
}

# Police speeds – both deliberately slow so player can outrun them
POLICE_PATROL_SPD  = 0.40         # units/frame  (0.4 * 6 ≈ 24 km/h – slow cruise)
POLICE_CHASE_SPD   = 1.20         # units/frame  (1.2 * 6 ≈ 72 km/h – catchable but beatable)
POLICE_SIGHT       = 900.0        # range within which police starts chasing
POLICE_PULLOVER_DIST = 110.0      # distance at which police "pulls over" the player
PULLOVER_HOLD_FRAMES = 180        # frames the police car holds beside player → game over

# ───────────────────────────────────────────────────────────────────────────────
#  CAMERA   ── Member 3 : Sanzida ──
# ───────────────────────────────────────────────────────────────────────────────
cam_mode   = 1               # 0 = top-down,  1 = third-person
cam_yaw    = 180.0           # orbit angle around player (degrees)
cam_pitch  = 350.0           # camera height
cam_dist   = 700.0           # radial distance from player
cam_fov    = 70.0
cam_shake  = 0.0
SHAKE_DECAY= 0.90
cam_zoom   = 1.0

# ── Member 3 : camera orbit step per arrow key press ──
CAM_YAW_STEP   = 5.0         # degrees rotated per key press (360° fully reachable)
CAM_PITCH_STEP = 20.0

# ───────────────────────────────────────────────────────────────────────────────
#  OBSTACLES
# ───────────────────────────────────────────────────────────────────────────────
obstacles = [
    {"x":   500.0, "y": LANE_CENTRES[1]},
    {"x":  2000.0, "y": LANE_CENTRES[0]},
]
OBSTACLE_HALF = 22

# ───────────────────────────────────────────────────────────────────────────────
#  GAME STATE
# ───────────────────────────────────────────────────────────────────────────────
game_over        = False
game_over_reason = ""
frame_tick       = 0


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════════════════════════════════════════

def d2r(deg):
    return deg * math.pi / 180.0

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def dist2d(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)

def draw_text_2d(sx, sy, txt, font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(1, 1, 1)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glRasterPos2f(sx, sy)
    for ch in txt:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text_col(sx, sy, txt, r, g, b, font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(r, g, b)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glRasterPos2f(sx, sy)
    for ch in txt:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


# ═══════════════════════════════════════════════════════════════════════════════
#  CAMERA SETUP   (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def setup_camera():
    # ── Member 3 : Sanzida – camera setup ──
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(cam_fov * cam_zoom, WIN_W / WIN_H, 1.0, 20000.0)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()

    shk_x = random.uniform(-cam_shake, cam_shake)
    shk_y = random.uniform(-cam_shake, cam_shake)

    if cam_mode == 0:
        # top-down view: camera high above player
        gluLookAt(plyr_x + shk_x, plyr_y + shk_y, 1800,
                  plyr_x, plyr_y, 0,
                  1, 0, 0)
    else:
        # third-person orbit: cam_yaw can be changed with arrow keys for 360° view
        rad = d2r(cam_yaw)
        ex  = plyr_x + cam_dist * math.cos(rad) + shk_x
        ey  = plyr_y + cam_dist * math.sin(rad) + shk_y
        gluLookAt(ex, ey, cam_pitch, plyr_x, plyr_y, 28, 0, 0, 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: ROAD   (Member 2 – Sadman)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_road():
    H   = WORLD_HALF
    RW  = ROAD_HALF_W

    # grass shoulders (looped, no hardcoding)
    SEG   = 40
    seg_w = (2 * H) / SEG
    glBegin(GL_QUADS)
    for i in range(SEG):
        x0  = -H + i * seg_w
        x1  = x0 + seg_w
        shd = 0.28 + 0.04 * (i % 2)
        glColor3f(shd * 0.9, shd * 1.55, shd * 0.7)
        glVertex3f(x0,  RW, 0); glVertex3f(x1,  RW, 0)
        glVertex3f(x1,  H,  0); glVertex3f(x0,  H,  0)
        glVertex3f(x0, -H,  0); glVertex3f(x1, -H,  0)
        glVertex3f(x1, -RW, 0); glVertex3f(x0, -RW, 0)
    glEnd()

    # asphalt base
    glColor3f(0.18, 0.18, 0.18)
    glBegin(GL_QUADS)
    glVertex3f(-H, -RW, 0); glVertex3f(H, -RW, 0)
    glVertex3f( H,  RW, 0); glVertex3f(-H, RW, 0)
    glEnd()

    # white kerb lines
    KW = 7.0
    glColor3f(0.95, 0.95, 0.95)
    glBegin(GL_QUADS)
    glVertex3f(-H,  RW-KW, DASH_Z); glVertex3f(H,  RW-KW, DASH_Z)
    glVertex3f( H,  RW,    DASH_Z); glVertex3f(-H, RW,    DASH_Z)
    glVertex3f(-H, -RW,    DASH_Z); glVertex3f(H, -RW,    DASH_Z)
    glVertex3f( H, -RW+KW, DASH_Z); glVertex3f(-H,-RW+KW, DASH_Z)
    glEnd()

    # dashed lane dividers (loop-generated)
    div_ys = [
        (LANE_CENTRES[0] + LANE_CENTRES[1]) / 2.0,
        (LANE_CENTRES[1] + LANE_CENTRES[2]) / 2.0,
    ]
    DW     = 5.0
    period = DASH_LEN + DASH_GAP
    glColor3f(0.95, 0.95, 0.95)
    glBegin(GL_QUADS)
    for dy in div_ys:
        cx = -H
        while cx < H:
            x0 = cx
            x1 = min(cx + DASH_LEN, H)
            glVertex3f(x0, dy-DW, DASH_Z); glVertex3f(x1, dy-DW, DASH_Z)
            glVertex3f(x1, dy+DW, DASH_Z); glVertex3f(x0, dy+DW, DASH_Z)
            cx += period
    glEnd()

    # boundary walls
    WH = 140
    glBegin(GL_QUADS)
    glColor3f(0.52, 0.28, 0.08)
    glVertex3f(-H,  H, 0); glVertex3f( H,  H, 0)
    glVertex3f( H,  H, WH); glVertex3f(-H,  H, WH)
    glVertex3f(-H, -H, 0); glVertex3f( H, -H, 0)
    glVertex3f( H, -H, WH); glVertex3f(-H, -H, WH)
    glColor3f(0.40, 0.22, 0.06)
    glVertex3f(-H, -H, 0); glVertex3f(-H,  H, 0)
    glVertex3f(-H,  H, WH); glVertex3f(-H, -H, WH)
    glVertex3f( H, -H, 0); glVertex3f( H,  H, 0)
    glVertex3f( H,  H, WH); glVertex3f( H, -H, WH)
    glEnd()


# ─────────────────────────────────────────────────────────────────────────────
#  TRAFFIC LIGHTS   (Member 2 – Sadman)
# ─────────────────────────────────────────────────────────────────────────────

def draw_traffic_light(sx, sy, is_grn):
    glPushMatrix()
    glTranslatef(sx, sy, 0)
    glColor3f(0.25, 0.25, 0.25)
    gluCylinder(gluNewQuadric(), 5, 5, 110, 8, 2)
    glTranslatef(0, 0, 110)
    glColor3f(0.08, 0.08, 0.08)
    glPushMatrix(); glTranslatef(0, 0, 22); glScalef(20, 20, 44)
    glutSolidCube(1); glPopMatrix()
    # red light
    if is_grn:
        glColor3f(0.28, 0.03, 0.03)
    else:
        glColor3f(0.95, 0.06, 0.06)
    glPushMatrix(); glTranslatef(0, 0, 38)
    gluSphere(gluNewQuadric(), 9, 12, 12); glPopMatrix()
    # green light
    if is_grn:
        glColor3f(0.05, 0.90, 0.16)
    else:
        glColor3f(0.03, 0.18, 0.03)
    glPushMatrix(); glTranslatef(0, 0, 10)
    gluSphere(gluNewQuadric(), 9, 12, 12); glPopMatrix()
    glPopMatrix()

def draw_all_signals():
    draw_traffic_light(SIGNAL_X,  ROAD_HALF_W + 25, signal_is_green)
    draw_traffic_light(SIGNAL_X, -ROAD_HALF_W - 25, signal_is_green)


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: PLAYER CAR   ── Member 1 : Dania ──
# ═══════════════════════════════════════════════════════════════════════════════

def draw_player_car():
    """
    Member 1 – Dania: player-controlled red sports car.
    Composed of: body cuboid, roof cuboid, hood wedge, windshield strip,
    4 rubber-tyre cylinders with grey rim discs, 2 headlight spheres,
    2 taillight spheres, and a side exhaust cylinder.
    Falls on its side (90° rotation) when health reaches 0.
    """
    glPushMatrix()
    glTranslatef(plyr_x, plyr_y, 0)
    glRotatef(plyr_heading, 0, 0, 1)

    # No tipping/falling – car stays upright even on game over.
    # Game-over state is communicated via the HUD overlay only.

    # ── main body – vivid cherry red ──
    glColor3f(0.92, 0.08, 0.08)
    glPushMatrix(); glTranslatef(0, 0, 20)
    glScalef(PLYR_HALF_LEN * 2, PLYR_HALF_WID * 2, 28)
    glutSolidCube(1); glPopMatrix()

    # ── roof – slightly darker red, narrower and shorter ──
    glColor3f(0.70, 0.04, 0.04)
    glPushMatrix(); glTranslatef(-4, 0, 40)
    glScalef(PLYR_HALF_LEN * 0.95, PLYR_HALF_WID * 1.45, 20)
    glutSolidCube(1); glPopMatrix()

    # ── front hood – lighter red, lower profile ──
    glColor3f(0.88, 0.10, 0.10)
    glPushMatrix(); glTranslatef(PLYR_HALF_LEN * 0.72, 0, 32)
    glScalef(PLYR_HALF_LEN * 0.55, PLYR_HALF_WID * 1.75, 8)
    glutSolidCube(1); glPopMatrix()

    # ── windshield – steel-blue tinted glass strip ──
    glColor3f(0.25, 0.42, 0.72)
    glPushMatrix(); glTranslatef(PLYR_HALF_LEN * 0.38, 0, 38)
    glScalef(10, PLYR_HALF_WID * 2.7, 17)
    glutSolidCube(1); glPopMatrix()

    # ── rear window – same tint ──
    glColor3f(0.25, 0.42, 0.72)
    glPushMatrix(); glTranslatef(-PLYR_HALF_LEN * 0.42, 0, 38)
    glScalef(9, PLYR_HALF_WID * 2.5, 15)
    glutSolidCube(1); glPopMatrix()

    # ── silver bumper strip (front) ──
    glColor3f(0.75, 0.75, 0.78)
    glPushMatrix(); glTranslatef(PLYR_HALF_LEN + 1, 0, 14)
    glScalef(5, PLYR_HALF_WID * 2.2, 8)
    glutSolidCube(1); glPopMatrix()

    # ── silver bumper strip (rear) ──
    glColor3f(0.75, 0.75, 0.78)
    glPushMatrix(); glTranslatef(-PLYR_HALF_LEN - 1, 0, 14)
    glScalef(5, PLYR_HALF_WID * 2.2, 8)
    glutSolidCube(1); glPopMatrix()

    # ── 4 rubber tyres (dark cylinders) + grey rims ──
    wheel_pos = [
        ( PLYR_HALF_LEN * 0.58,  PLYR_HALF_WID + 6),
        ( PLYR_HALF_LEN * 0.58, -PLYR_HALF_WID - 6),
        (-PLYR_HALF_LEN * 0.58,  PLYR_HALF_WID + 6),
        (-PLYR_HALF_LEN * 0.58, -PLYR_HALF_WID - 6),
    ]
    for wx, wy in wheel_pos:
        # tyre
        glColor3f(0.10, 0.10, 0.10)
        glPushMatrix(); glTranslatef(wx, wy, 13); glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 13, 13, 15, 14, 2); glPopMatrix()
        # rim disc (inner side)
        glColor3f(0.62, 0.64, 0.68)
        glPushMatrix(); glTranslatef(wx, wy + (8 if wy > 0 else -8), 13)
        glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 7, 7, 1, 10, 1); glPopMatrix()

    # ── headlights – warm yellow spheres ──
    glColor3f(1.0, 0.96, 0.55)
    for sy in [1, -1]:
        glPushMatrix(); glTranslatef(PLYR_HALF_LEN + 3, sy * PLYR_HALF_WID * 0.58, 22)
        gluSphere(gluNewQuadric(), 8, 10, 10); glPopMatrix()

    # ── taillights – bright red spheres ──
    glColor3f(0.96, 0.06, 0.06)
    for sy in [1, -1]:
        glPushMatrix(); glTranslatef(-PLYR_HALF_LEN - 3, sy * PLYR_HALF_WID * 0.58, 22)
        gluSphere(gluNewQuadric(), 7, 10, 10); glPopMatrix()

    # ── exhaust pipe – small dark cylinder on right rear ──
    glColor3f(0.35, 0.35, 0.35)
    glPushMatrix(); glTranslatef(-PLYR_HALF_LEN - 2, -PLYR_HALF_WID * 0.5, 10)
    glRotatef(90, 0, 1, 0)
    gluCylinder(gluNewQuadric(), 3, 3, 10, 8, 1); glPopMatrix()

    glPopMatrix()


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: NPC CARS   (Member 2 – Sadman)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_one_npc(tc):
    glPushMatrix()
    glTranslatef(tc["x"], tc["y"], 0)

    glColor3f(0.95, 0.72, 0.10)
    glPushMatrix(); glTranslatef(0, 0, 20); glScalef(90, 46, 24)
    glutSolidCube(1); glPopMatrix()

    glColor3f(0.76, 0.58, 0.07)
    glPushMatrix(); glTranslatef(0, 0, 38); glScalef(56, 34, 17)
    glutSolidCube(1); glPopMatrix()

    glColor3f(0.14, 0.22, 0.45)
    glPushMatrix(); glTranslatef(24, 0, 36); glScalef(7, 28, 12)
    glutSolidCube(1); glPopMatrix()

    glColor3f(0.10, 0.10, 0.10)
    for wx, wy in [(30, 26), (30, -26), (-30, 26), (-30, -26)]:
        glPushMatrix(); glTranslatef(wx, wy, 11); glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 11, 11, 13, 10, 2); glPopMatrix()

    br, bg, bb = (0.98, 0.06, 0.06) if tc["stopped"] else (0.45, 0.03, 0.03)
    glColor3f(br, bg, bb)
    for sy in [1, -1]:
        glPushMatrix(); glTranslatef(-47, sy*14, 22)
        gluSphere(gluNewQuadric(), 5, 8, 8); glPopMatrix()

    glPopMatrix()

def draw_all_npcs():
    for tc in npc_cars:
        draw_one_npc(tc)


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: POLICE CAR   (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_police_car():
    pc = police
    glPushMatrix()
    glTranslatef(pc["x"], pc["y"], 0)
    glRotatef(pc["heading"], 0, 0, 1)

    glColor3f(0.95, 0.95, 0.95)
    glPushMatrix(); glTranslatef(22, 0, 20); glScalef(56, 46, 24)
    glutSolidCube(1); glPopMatrix()

    glColor3f(0.07, 0.07, 0.07)
    glPushMatrix(); glTranslatef(-22, 0, 20); glScalef(56, 46, 24)
    glutSolidCube(1); glPopMatrix()

    glColor3f(0.07, 0.07, 0.07)
    glPushMatrix(); glTranslatef(0, 0, 38); glScalef(60, 36, 17)
    glutSolidCube(1); glPopMatrix()

    # blue stripe = POLICE marking
    glColor3f(0.06, 0.12, 0.70)
    glPushMatrix(); glTranslatef(0, 26, 23); glScalef(72, 5, 12)
    glutSolidCube(1); glPopMatrix()
    glPushMatrix(); glTranslatef(0, -26, 23); glScalef(72, 5, 12)
    glutSolidCube(1); glPopMatrix()

    # siren
    siren_blue = (frame_tick // 18) % 2 == 0
    if siren_blue:
        glColor3f(0.05, 0.18, 0.95)
    else:
        glColor3f(0.95, 0.05, 0.05)
    glPushMatrix(); glTranslatef(0, 0, 54)
    gluSphere(gluNewQuadric(), 10, 10, 10); glPopMatrix()

    glColor3f(0.10, 0.10, 0.10)
    for wx, wy in [(34, 26), (34, -26), (-34, 26), (-34, -26)]:
        glPushMatrix(); glTranslatef(wx, wy, 11); glRotatef(90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 11, 11, 13, 10, 2); glPopMatrix()

    glColor3f(1.0, 1.0, 0.65)
    for sy in [1, -1]:
        glPushMatrix(); glTranslatef(51, sy*14, 22)
        gluSphere(gluNewQuadric(), 6, 8, 8); glPopMatrix()

    glPopMatrix()


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: OBSTACLES
# ═══════════════════════════════════════════════════════════════════════════════

def draw_obstacles():
    for obs in obstacles:
        glPushMatrix()
        glTranslatef(obs["x"], obs["y"], 0)

        glColor3f(0.92, 0.45, 0.05)
        glPushMatrix(); glTranslatef(0, 0, OBSTACLE_HALF)
        glScalef(OBSTACLE_HALF*2, OBSTACLE_HALF*2, OBSTACLE_HALF*2)
        glutSolidCube(1); glPopMatrix()

        glColor3f(0.95, 0.95, 0.95)
        glPushMatrix(); glTranslatef(0, OBSTACLE_HALF+1, OBSTACLE_HALF)
        glScalef(OBSTACLE_HALF*2, 5, OBSTACLE_HALF*0.6)
        glutSolidCube(1); glPopMatrix()

        glColor3f(0.95, 0.08, 0.08)
        glPushMatrix(); glTranslatef(0, 0, OBSTACLE_HALF*2+12)
        gluSphere(gluNewQuadric(), 9, 8, 8); glPopMatrix()

        glPopMatrix()


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: BOOM FLASH   (Member 1 – Dania)
# ═══════════════════════════════════════════════════════════════════════════════

def draw_boom_flash():
    if boom_flash_timer <= 0:
        return
    alpha = boom_flash_timer / BOOM_FLASH_DUR
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    top_h = WIN_H * alpha * 0.38
    bot_h = WIN_H * (1 - alpha * 0.38)

    glColor3f(1.0, 0.92, 0.30)
    glBegin(GL_QUADS)
    glVertex3f(0,     0,     0); glVertex3f(WIN_W, 0,     0)
    glVertex3f(WIN_W, top_h, 0); glVertex3f(0,     top_h, 0)
    glEnd()

    glColor3f(1.0, 0.80, 0.10)
    glBegin(GL_QUADS)
    glVertex3f(0,     WIN_H,  0); glVertex3f(WIN_W, WIN_H,  0)
    glVertex3f(WIN_W, bot_h,  0); glVertex3f(0,     bot_h,  0)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING: HUD
# ═══════════════════════════════════════════════════════════════════════════════

def draw_hud_bar(bx, by, bw, bh, ratio, cr, cg, cb, label):
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    glColor3f(0.22, 0.22, 0.22)
    glBegin(GL_QUADS)
    glVertex3f(bx,    by,    0); glVertex3f(bx+bw, by,    0)
    glVertex3f(bx+bw, by+bh, 0); glVertex3f(bx,    by+bh, 0)
    glEnd()

    fw = bw * clamp(ratio, 0, 1)
    glColor3f(cr, cg, cb)
    glBegin(GL_QUADS)
    glVertex3f(bx,    by,    0); glVertex3f(bx+fw, by,    0)
    glVertex3f(bx+fw, by+bh, 0); glVertex3f(bx,    by+bh, 0)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    draw_text_2d(bx+bw+10, by, label, GLUT_BITMAP_HELVETICA_12)


def draw_hud():
    BX = 20; BW = 210; BH = 20

    # ── Member 1 : Dania – Health bar ──
    hr = plyr_health / plyr_health_max
    if hr > 0.55:    rc, gc, bc = 0.12, 0.82, 0.18
    elif hr > 0.25:  rc, gc, bc = 0.90, 0.62, 0.06
    else:            rc, gc, bc = 0.88, 0.08, 0.08
    draw_hud_bar(BX, WIN_H-40, BW, BH, hr, rc, gc, bc,
                 f"Health  {plyr_health}/{plyr_health_max}")

    # ── Member 3 : Sanzida – Crime bar (reward removed) ──
    draw_hud_bar(BX, WIN_H-68, BW, BH, crime_pts / CRIME_MAX,
                 0.90, 0.10, 0.10, f"Crime  {crime_pts}/{CRIME_MAX}")

    # ── Member 2 : Sadman – Wallet bar ──
    wr2 = clamp(wallet / 15, 0, 1)
    if wallet > 5:    wc = (0.18, 0.78, 0.18)
    elif wallet > 0:  wc = (0.90, 0.60, 0.08)
    else:             wc = (0.88, 0.10, 0.10)
    draw_hud_bar(BX, WIN_H-96, BW, BH, wr2, wc[0], wc[1], wc[2],
                 f"Wallet  ${wallet}")

    # ── Member 1 : Dania – Speed readout (uses KMH_SCALE) ──
    spd = abs(plyr_vel) * KMH_SCALE
    if spd > SPEED_LIMIT_KMH:
        draw_text_col(WIN_W-360, WIN_H-36,
                      f"Speed: {spd:.0f} km/h  |  Limit: {SPEED_LIMIT_KMH:.0f} km/h",
                      1.0, 0.18, 0.18)
    else:
        draw_text_2d(WIN_W-360, WIN_H-36,
                     f"Speed: {spd:.0f} km/h  |  Limit: {SPEED_LIMIT_KMH:.0f} km/h")

    # ── Member 2 : Sadman – Signal countdown ──
    fl  = max(0, (GREEN_FRAMES if signal_is_green else RED_FRAMES) - signal_phase_timer)
    sl  = fl // 60
    sig = f"Signal: {'GREEN  GO' if signal_is_green else 'RED  STOP'}  ({sl}s)"
    if signal_is_green:
        draw_text_col(WIN_W-360, WIN_H-62, sig, 0.10, 0.90, 0.20)
    else:
        draw_text_col(WIN_W-360, WIN_H-62, sig, 0.95, 0.12, 0.12)

    # ── Member 3 : Sanzida – Police state ──
    pc_state = police["state"].upper()
    if pc_state == "PATROL":
        draw_text_2d(WIN_W-360, WIN_H-88, f"Police: {pc_state}")
    else:
        draw_text_col(WIN_W-360, WIN_H-88, f"Police: {pc_state}", 1.0, 0.18, 0.18)

    # ── Camera mode ──
    draw_text_2d(BX, WIN_H-124,
                 f"CAM: {'TOP-DOWN' if cam_mode == 0 else '3RD-PERSON'}  (C to toggle)",
                 GLUT_BITMAP_HELVETICA_12)

    # ── Controls ──
    draw_text_2d(BX, 28,
                 "W/S: drive    A/D: change lane    Arrows: rotate camera    C: top/3rd    R: restart",
                 GLUT_BITMAP_HELVETICA_12)

    # ── Member 2 : Sadman – Violation flash notices ──
    flash = (frame_tick // 15) % 2 == 0
    if flash:
        if overspeed_flag:
            draw_text_col(WIN_W//2-190, WIN_H-50,
                          "  OVERSPEED!  -$5 FINE",
                          1.0, 0.14, 0.14, GLUT_BITMAP_TIMES_ROMAN_24)
        if redlight_flag:
            draw_text_col(WIN_W//2-230, WIN_H-84,
                          "RED LIGHT VIOLATION!  -$5 FINE",
                          1.0, 0.14, 0.14, GLUT_BITMAP_TIMES_ROMAN_24)

    # ── Game Over overlay ──
    if game_over:
        draw_text_col(WIN_W//2-270, WIN_H//2+20,
                      f"GAME OVER  -  {game_over_reason.upper()}",
                      1.0, 0.14, 0.14, GLUT_BITMAP_TIMES_ROMAN_24)
        draw_text_2d(WIN_W//2-170, WIN_H//2-20,
                     "Press  R  to Restart", GLUT_BITMAP_TIMES_ROMAN_24)


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: SIGNALS   (Member 2 – Sadman)
# ═══════════════════════════════════════════════════════════════════════════════

def logic_signals():
    global signal_phase_timer, signal_is_green
    signal_phase_timer += 1
    dur = GREEN_FRAMES if signal_is_green else RED_FRAMES
    if signal_phase_timer >= dur:
        signal_is_green    = not signal_is_green
        signal_phase_timer = 0


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: NPC TRAFFIC   (Member 2 – Sadman)
# ═══════════════════════════════════════════════════════════════════════════════

def logic_npc_traffic():
    for i, tc in enumerate(npc_cars):
        dist_sig = abs(tc["x"] - SIGNAL_X)
        at_red   = (not signal_is_green
                    and tc["x"] < SIGNAL_X
                    and dist_sig < SIGNAL_DETECT_R + 30)

        gap_block = False
        for j, other in enumerate(npc_cars):
            if j == i or other["lane"] != tc["lane"]:
                continue
            if 0 < (other["x"] - tc["x"]) < NPC_MIN_GAP:
                gap_block = True; break

        if abs(plyr_y - tc["y"]) < LANE_WIDTH * 0.5:
            if 0 < (plyr_x - tc["x"]) < NPC_MIN_GAP:
                gap_block = True

        tc["stopped"] = at_red or gap_block
        if not tc["stopped"]:
            tc["x"] += tc["speed"]

        if tc["x"] > WORLD_HALF - 80:
            tc["x"] = -WORLD_HALF + 80


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: PLAYER MOVEMENT   (Member 1 – Dania)
# ═══════════════════════════════════════════════════════════════════════════════

def logic_player():
    # ── Member 1 : Dania – forward/brake/lane-change ──
    global plyr_vel, plyr_x, plyr_y
    global plyr_target_lane, lane_change_active, lane_change_target_y

    if game_over:
        return

    # Gradual acceleration: ACCEL_RATE=0.05, so reaching MAX_VEL=20 takes
    # 20/0.05 = 400 frames ≈ 6-7 seconds of held W. Speed climbs slowly.
    if k_up:
        plyr_vel = clamp(plyr_vel + ACCEL_RATE, -REVERSE_CAP, MAX_VEL)
    elif k_down:
        plyr_vel = clamp(plyr_vel - BRAKE_RATE, -REVERSE_CAP, MAX_VEL)
    else:
        plyr_vel *= FRICTION
        if abs(plyr_vel) < 0.01:
            plyr_vel = 0.0

    # lane change (A/D or LEFT/RIGHT): one press = move one lane
    if k_left and not lane_change_active:
        nl = clamp(plyr_target_lane - 1, 0, len(LANE_CENTRES) - 1)
        if nl != plyr_target_lane:
            plyr_target_lane     = nl
            lane_change_target_y = LANE_CENTRES[nl]
            lane_change_active   = True
    if k_right and not lane_change_active:
        nl = clamp(plyr_target_lane + 1, 0, len(LANE_CENTRES) - 1)
        if nl != plyr_target_lane:
            plyr_target_lane     = nl
            lane_change_target_y = LANE_CENTRES[nl]
            lane_change_active   = True

    # smooth lateral drift toward target lane centre
    if lane_change_active:
        diff = lane_change_target_y - plyr_y
        if abs(diff) < 1.5:
            plyr_y             = lane_change_target_y
            lane_change_active = False
        else:
            plyr_y += clamp(diff, -LANE_SNAP_SPEED, LANE_SNAP_SPEED)

    plyr_x = clamp(plyr_x + plyr_vel, -WORLD_HALF + 70, WORLD_HALF - 70)


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: VIOLATIONS / FINES   (Member 2 – Sadman)
# ═══════════════════════════════════════════════════════════════════════════════

def logic_violations():
    # ── Member 2 : Sadman – overspeed and red-light detection ──
    global overspeed_flag, redlight_flag, wallet, fine_cooldown

    spd = abs(plyr_vel) * KMH_SCALE    # convert internal velocity to km/h
    overspeed_flag = spd > SPEED_LIMIT_KMH

    near  = abs(plyr_x - SIGNAL_X) < SIGNAL_DETECT_R
    moves = abs(plyr_vel) > 0.3
    redlight_flag = (not signal_is_green) and near and moves

    if fine_cooldown > 0:
        fine_cooldown -= 1

    if fine_cooldown == 0:
        charged = False
        if overspeed_flag:
            wallet = max(0, wallet - FINE_AMOUNT); charged = True
        if redlight_flag:
            wallet = max(0, wallet - FINE_AMOUNT); charged = True
        if charged:
            fine_cooldown = FINE_CD_MAX


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: COLLISIONS   (Member 1 – Dania)
# ═══════════════════════════════════════════════════════════════════════════════

def logic_collisions():
    global plyr_health, plyr_hit_cd, plyr_vel
    global boom_flash_timer, game_over, game_over_reason

    if plyr_hit_cd > 0:
        plyr_hit_cd -= 1
        return

    hit = False
    for tc in npc_cars:
        if (abs(plyr_x-tc["x"]) < PLYR_HALF_LEN+45 and
                abs(plyr_y-tc["y"]) < PLYR_HALF_WID+23):
            hit = True; break

    if not hit:
        for obs in obstacles:
            if (abs(plyr_x-obs["x"]) < PLYR_HALF_LEN+OBSTACLE_HALF and
                    abs(plyr_y-obs["y"]) < PLYR_HALF_WID+OBSTACLE_HALF):
                hit = True; break

    if not hit:
        pc = police
        if (abs(plyr_x-pc["x"]) < PLYR_HALF_LEN+45 and
                abs(plyr_y-pc["y"]) < PLYR_HALF_WID+23):
            hit = True

    if hit:
        plyr_health     -= COLLISION_DMG
        plyr_hit_cd      = HIT_CD_MAX
        plyr_vel        *= -0.3
        boom_flash_timer = BOOM_FLASH_DUR
        if plyr_health <= 0:
            plyr_health      = 0
            game_over        = True
            game_over_reason = "collision – car destroyed"


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: CRIME & REWARD   (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def logic_crime_reward():
    # ── Member 3 : Sanzida – crime points only (reward feature removed) ──
    global crime_pts, game_over, game_over_reason

    if game_over:
        return

    violated = overspeed_flag or redlight_flag
    if violated:
        crime_pts = min(crime_pts + CRIME_PER_VIO, CRIME_MAX + 1)

    if crime_pts > CRIME_MAX and not game_over:
        game_over        = True
        game_over_reason = "too many violations"


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: POLICE   (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def logic_police():
    # ── Member 3 : Sanzida – police state machine ──
    # PATROL: slow east-west cruise.
    # CHASE:  steers toward player at POLICE_CHASE_SPD (beatable by player).
    # PULLOVER: police parks beside player and counts down → game over.
    #           Police never collides – it stops next to the car and "pulls it over".
    global game_over, game_over_reason
    pc = police

    violated    = overspeed_flag or redlight_flag
    d_to_player = dist2d(pc["x"], pc["y"], plyr_x, plyr_y)

    # ── state transitions ──
    if pc["state"] == POLICE_PATROL:
        if violated and d_to_player < POLICE_SIGHT:
            pc["state"] = POLICE_CHASE

    elif pc["state"] == POLICE_CHASE:
        # give up chase if player drives away and stops violating
        if not violated and d_to_player > POLICE_SIGHT * 1.5:
            pc["state"] = POLICE_PATROL
        # close enough to pull over
        elif d_to_player < POLICE_PULLOVER_DIST:
            pc["state"]            = POLICE_PULLOVER
            pc["pullover_timer"]   = PULLOVER_HOLD_FRAMES

    elif pc["state"] == POLICE_PULLOVER:
        # count down; if player drives far away, abandon pullover
        if d_to_player > POLICE_PULLOVER_DIST * 2.5:
            pc["state"] = POLICE_CHASE
        else:
            pc["pullover_timer"] -= 1
            if pc["pullover_timer"] <= 0 and not game_over:
                game_over        = True
                game_over_reason = "pulled over by police"

    # ── movement per state ──
    if pc["state"] == POLICE_PATROL:
        # slow cruise east-west in its lane.
        # Gap check: if an NPC car is ahead in the same lane within safe distance,
        # the police car slows to a stop (just like NPC-to-NPC spacing logic).
        POLICE_GAP = 160        # minimum following distance behind an NPC
        lane_blocked = False
        for tc in npc_cars:
            if abs(tc["y"] - pc["y"]) < LANE_WIDTH * 0.5:   # same lane
                gap = (tc["x"] - pc["x"]) * pc["patrol_dir"]  # positive = ahead
                if 0 < gap < POLICE_GAP:
                    lane_blocked = True
                    break

        if not lane_blocked:
            pc["x"] += POLICE_PATROL_SPD * pc["patrol_dir"]
        if pc["x"] > WORLD_HALF - 200:
            pc["patrol_dir"] = -1; pc["heading"] = 180.0
        elif pc["x"] < -WORLD_HALF + 200:
            pc["patrol_dir"] =  1; pc["heading"] =   0.0

    elif pc["state"] == POLICE_CHASE:
        # steer toward player smoothly; stop short of collision distance
        dx = plyr_x - pc["x"]; dy = plyr_y - pc["y"]
        d  = math.hypot(dx, dy)
        if d > POLICE_PULLOVER_DIST:          # never drives INTO the player
            pc["x"]       += (dx / d) * POLICE_CHASE_SPD
            pc["y"]       += (dy / d) * POLICE_CHASE_SPD
            pc["heading"]  = math.degrees(math.atan2(dy, dx))

    elif pc["state"] == POLICE_PULLOVER:
        # hold position slightly beside the player (offset in Y to avoid overlap)
        target_x = plyr_x - 80
        target_y = plyr_y + (LANE_WIDTH * 0.9)   # park in adjacent lane
        dx = target_x - pc["x"]; dy = target_y - pc["y"]
        d  = math.hypot(dx, dy)
        if d > 5:
            spd = min(POLICE_CHASE_SPD, d * 0.15)
            pc["x"]      += (dx / d) * spd
            pc["y"]      += (dy / d) * spd
            pc["heading"] = math.degrees(math.atan2(dy, dx))


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGIC: CAMERA   (Member 3 – Sanzida)
# ═══════════════════════════════════════════════════════════════════════════════

def logic_camera():
    global cam_shake, cam_zoom

    cam_shake *= SHAKE_DECAY
    if cam_shake < 0.3:
        cam_shake = 0.0

    target_zoom = 0.82 if police["state"] == POLICE_CHASE else 1.0
    cam_zoom   += (target_zoom - cam_zoom) * 0.035

def trigger_shake(mag=20.0):
    global cam_shake
    cam_shake = mag


# ═══════════════════════════════════════════════════════════════════════════════
#  MASTER UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

def update_all():
    global frame_tick, boom_flash_timer

    frame_tick += 1
    if boom_flash_timer > 0:
        boom_flash_timer -= 1

    logic_signals()
    logic_player()
    logic_npc_traffic()
    logic_violations()
    logic_collisions()
    logic_crime_reward()
    logic_police()
    logic_camera()

    if boom_flash_timer == BOOM_FLASH_DUR - 1:
        trigger_shake(22.0)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESET
# ═══════════════════════════════════════════════════════════════════════════════

def reset_game():
    global plyr_x, plyr_y, plyr_heading, plyr_vel
    global plyr_health, plyr_hit_cd, boom_flash_timer
    global crime_pts
    global signal_phase_timer, signal_is_green
    global overspeed_flag, redlight_flag
    global wallet, fine_cooldown
    global game_over, game_over_reason, frame_tick
    global cam_shake, cam_zoom, cam_yaw, cam_pitch
    global k_up, k_down, k_left, k_right
    global lane_change_active, lane_change_target_y, plyr_target_lane

    plyr_x = -4000.0; plyr_y = LANE_CENTRES[2]
    plyr_heading = 0.0; plyr_vel = 0.0
    plyr_health  = plyr_health_max; plyr_hit_cd = 0
    boom_flash_timer = 0
    crime_pts = 0
    signal_phase_timer = 0; signal_is_green = True
    overspeed_flag = False; redlight_flag = False
    wallet = 15; fine_cooldown = 0
    game_over = False; game_over_reason = ""; frame_tick = 0
    cam_shake = 0.0; cam_zoom = 1.0
    cam_yaw = 180.0; cam_pitch = 350.0
    k_up = k_down = k_left = k_right = False
    lane_change_active   = False
    plyr_target_lane     = 2
    lane_change_target_y = LANE_CENTRES[2]

    npc_cars[0].update({"x": -1000.0, "y": LANE_CENTRES[0], "lane": 0,
                        "speed": NPC_BASE_SPEED, "stopped": False})
    npc_cars[1].update({"x":   500.0, "y": LANE_CENTRES[1], "lane": 1,
                        "speed": NPC_BASE_SPEED + 0.05, "stopped": False})
    police.update({"x": 800.0, "y": LANE_CENTRES[0], "heading": 180.0,
                   "state": POLICE_PATROL, "patrol_dir": -1, "pullover_timer": 0})


# ═══════════════════════════════════════════════════════════════════════════════
#  INPUT
# ═══════════════════════════════════════════════════════════════════════════════

def kb_down(key, x, y):
    # ── Member 1 : Dania – driving keys (W/S/A/D) ──
    global k_up, k_down, k_left, k_right, cam_mode
    if key == b'r': reset_game(); return
    if game_over: return
    if key == b'w': k_up    = True
    if key == b's': k_down  = True
    if key == b'a': k_left  = True
    if key == b'd': k_right = True
    if key == b'c': cam_mode = 1 - cam_mode

def kb_up(key, x, y):
    # ── Member 1 : Dania – key release ──
    global k_up, k_down, k_left, k_right
    if key == b'w': k_up    = False
    if key == b's': k_down  = False
    if key == b'a': k_left  = False
    if key == b'd': k_right = False

def special_down(key, x, y):
    # ── Member 3 : Sanzida – arrow keys rotate camera 360° around player ──
    # LEFT/RIGHT orbit the camera horizontally (cam_yaw)
    # UP/DOWN raise or lower the camera (cam_pitch)
    global cam_yaw, cam_pitch
    if key == GLUT_KEY_LEFT:
        cam_yaw = (cam_yaw + CAM_YAW_STEP) % 360.0
    if key == GLUT_KEY_RIGHT:
        cam_yaw = (cam_yaw - CAM_YAW_STEP) % 360.0
    if key == GLUT_KEY_UP:
        cam_pitch = clamp(cam_pitch + CAM_PITCH_STEP, 80, 2000)
    if key == GLUT_KEY_DOWN:
        cam_pitch = clamp(cam_pitch - CAM_PITCH_STEP, 80, 2000)

def special_up(key, x, y):
    pass   # arrow keys are discrete steps, no held-key state needed

def mouse_click(button, state, mx, my):
    pass


# ═══════════════════════════════════════════════════════════════════════════════
#  GLUT CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

def idle_cb():
    update_all()
    glutPostRedisplay()

def display_cb():
    glClearColor(0.50, 0.78, 0.95, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WIN_W, WIN_H)

    setup_camera()

    draw_road()
    draw_all_signals()
    draw_obstacles()
    draw_all_npcs()
    draw_police_car()
    draw_player_car()

    draw_boom_flash()
    draw_hud()

    glutSwapBuffers()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WIN_W, WIN_H)
    glutInitWindowPosition(80, 40)
    glutCreateWindow(b"Urban Drive  -  Dania | Sadman | Sanzida")

    glutDisplayFunc(display_cb)
    glutIdleFunc(idle_cb)
    glutKeyboardFunc(kb_down)
    glutKeyboardUpFunc(kb_up)
    glutSpecialFunc(special_down)
    glutSpecialUpFunc(special_up)
    glutMouseFunc(mouse_click)

    glutMainLoop()

if __name__ == "__main__":
    main()