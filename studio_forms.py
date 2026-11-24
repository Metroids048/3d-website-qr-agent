"""Geometry for mascots, slim devices and layered marks."""
import base64
import math
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps

from brand_scene import angles


def mix(a, b, weight):
    return [round(x * (1 - weight) + y * weight) for x, y in zip(a, b)]


def emblem_panel(mesh, contour, depths, color):
    x0, z0 = np.mean(contour, axis=0)
    mesh.surface([[(x0 + (x - x0) * scale, depth, z0 + (z - z0) * scale)
                   for x, z in contour] for depth, scale in depths], color)


def dragon_face(mesh, skin, green, cream):
    width, depth, height, center = .239, .177, .203, -.205

    def muzzle(z):
        return .108 * math.exp(-((z + .154) / .083) ** 2)

    def surface(x, z):
        extent = math.sqrt(max(0, 1 - (x / width) ** 2 - ((z - center) / height) ** 2))
        return .019 + (depth + muzzle(z)) * extent

    mesh.surface([
        [(width * math.sin(t) * math.cos(a),
          .019 + depth * math.sin(t) * math.sin(a) + muzzle(z) * max(0, math.sin(t) * math.sin(a)), z)
         for a in angles(56)]
        for t in np.linspace(0, math.pi, 35)
        for z in [center + height * math.cos(t)]
    ], skin)

    def inlay(contour, color, offset, dome=0):
        x0, z0 = np.mean(contour, axis=0)
        mesh.surface([
            [(x0 + (x - x0) * scale, surface(x0 + (x - x0) * scale, z0 + (z - z0) * scale)
              + offset + dome * (1 - scale ** 2), z0 + (z - z0) * scale)
             for x, z in contour]
            for scale in (1, .82, .60, .34, 0)
        ], color)

    def ellipse(x, z, rx, rz, tilt=0):
        return [(x + rx * math.cos(a) + tilt * rz * math.sin(a), z + rz * math.sin(a))
                for a in angles(36)]

    for side in (-1, 1):
        x, z = side * .133, -.267
        inlay(ellipse(x, z, .051, .074, -.17 * side), [71, 81, 61], .004, .012)
        inlay(ellipse(x, z + .002, .045, .066, -.17 * side), cream, .008, .012)
        iris_x = x - side * .004
        inlay(ellipse(iris_x, z + .010, .034, .055, -.17 * side), [34, 44, 39], .013, .014)
        inlay(ellipse(iris_x - .009, z - .019, .010, .012), [251, 248, 222], .024, .013)
        inlay(ellipse(side * .050, -.157, .013, .009, .26 * side), green, .004)

    def smile(x):
        return -.118 + .021 * (1 - (x / .137) ** 2)

    def mouth_line(x):
        return max(0, 1 - (x / .137) ** 2) ** .85

    xs = np.linspace(-.137, .137, 41)
    inlay([(x, smile(x)) for x in xs] +
          [(x, smile(x) + .054 * mouth_line(x)) for x in xs[-2:0:-1]], [161, 43, 36], .004)
    tongue_xs = np.linspace(-.074, .077, 30)
    inlay([(x, smile(x) + (.046 - .021 * math.sin(math.pi * i / 29)) * mouth_line(x))
           for i, x in enumerate(tongue_xs)] +
          [(x, smile(x) + .051 * mouth_line(x)) for x in tongue_xs[::-1]], [232, 94, 39], .008)
    inlay([(.070, smile(.070) + .001), (.100, smile(.100) + .001),
           (.092, smile(.092) + .012), (.085, smile(.085) + .015)], cream, .010)


def horned(mesh, actions, primary, accent, source):
    skin = mix(primary, [139, 195, 70], .53)
    green = mix(skin, [46, 109, 46], .36)
    belly = mix(skin, [242, 249, 197], .75)
    cream = [247, 243, 214]
    horn = [230, 163, 61]
    scarf = [181, 51, 41]

    # A larger head and short feet keep the mascot silhouette at mobile size.
    mesh.oval((.013, -.013, .092), (.182, .159, .227), green, steps=34, bands=20)
    mesh.oval((.005, .112, .118), (.144, .072, .194), belly, steps=30)
    for x in (-.108, .149):
        mesh.oval((x, .058, .270), (.095, .126, .065), skin)
        for toe in range(3):
            mesh.oval((x-.045+toe*.043, .154, .274), (.022,.023,.025), belly, steps=12, bands=8)
    dragon_face(mesh, skin, green, cream)
    mesh.oval((0,.067,-.023), (.174,.113,.042), scarf, steps=36)
    emblem_panel(mesh, [(-.135,-.039),(-.085,-.023),(.064,-.023),(.151,-.057),
                         (.121,-.012),(.012,.092),(-.050,.067),(-.105,.017)],
                [(.102,0),(.128,.90),(.161,1),(.196,.78),(.207,0)], scarf)
    emblem_panel(mesh, [(-.078,-.016),(-.049,-.019),(-.034,.007),(.059,-.034),(.085,-.044),
                         (.038,.004),(-.002,.034),(.009,.059),(-.017,.067),
                         (-.037,.037),(-.063,.059),(-.081,.050),(-.052,.021)],
                [(.183,0),(.198, .88),(.203,1),(.207,.95),(.210,0)], cream)

    for sign in (-1,1):
        root = sign*.146
        points = [(root,-.378),(sign*.185,-.483),(sign*.221,-.437),(sign*.294,-.510),
                  (sign*.263,-.362),(sign*.217,-.382),(sign*.188,-.325)]
        emblem_panel(mesh,points,[(-.085,0),(-.087,.87),(-.040,1),(.006,.84),(.012,0)],horn)

    tail = [(.09,-.091,.173),(.235,-.117,.224),(.362,-.110,.205),
            (.435,-.090,.125),(.459,-.071,.065)]
    first = len(mesh.vertices)
    radii = (.091,.083,.063,.039,.006)
    rings = [[(x,y+r*math.cos(a),z+r*math.sin(a)) for a in angles(18)]
             for (x,y,z),r in zip(tail,radii)]
    mesh.surface(rings,skin)
    for row in range(len(tail)):
        x_move, z_move = .019 * row, -.019 * row
        actions.append([first+row*18,first+(row+1)*18,x_move,0,z_move,1.19])
    for row,(x,y,z) in enumerate(tail[1:4],1):
        first = len(mesh.vertices)
        mesh.axial((x,y,z-radii[row]*.65),(x+.015,y,z-radii[row]-.05),
                   .041*(1-.14*row),horn,tip=.002,steps=5)
        actions.append([first,len(mesh.vertices),.019*row,0,-.019*row,1.19])

    mesh.oval((.189,.085,.075),(.055,.063,.114),green)
    first = len(mesh.vertices)
    mesh.oval((-.189,.087,.067),(.059,.065,.116),skin,steps=26)
    mesh.oval((-.227,.101,.008),(.055,.055,.061),skin,steps=24)
    for i in range(3):
        mesh.oval((-.264+.024*i,.115,-.015-.005*i),(.015,.022,.030),skin,steps=16)
    actions.append([first,len(mesh.vertices),-.037,.024,-.025,1.52])
    first = len(mesh.vertices)
    emblem_panel(mesh,[(.105,-.037),(.274,-.066),(.404,-.027),(.293,.005),(.17,.044)],
                [(-.090,0),(-.072,.8),(-.053,1),(-.050,0)],scarf)
    actions.append([first,len(mesh.vertices),.045,-.025,-.056,1.42])


def slab(mesh, actions, primary, accent, source):
    pearl = mix(primary,[255,255,255],.43)
    silver = mix(pearl,[86,100,114],.30)
    highlight = mix(pearl,[255,255,255],.71)
    dark = [27,34,43]
    mesh.shell((0,0,-.055),(.408,.105,.811),.054,silver)
    mesh.shell((0,-.049,-.055),(.385,.032,.785),.047,dark)
    mesh.shell((0,-.062,-.057),(.357,.018,.748),.048,[51,72,95])
    mesh.shell((0,.045,-.055),(.390,.031,.787),.048,pearl)
    mesh.shell((0,.063,.133),(.348,.017,.327),.040,mix(pearl,silver,.23))
    mesh.shell((0,.068,.124),(.317,.010,.310),.040,mix(pearl,silver,.11))
    mesh.axial((0,.065,-.247),(0,.079,-.247),.126,pearl,steps=50)
    mesh.shell((0,.079,-.249),(.206,.030,.103),.045,silver)
    for x in (-.055,.055):
        for y,r,color in ((.095,.048,dark),(.106,.034,[61,74,91]),(.108,.026,[21,33,52])):
            mesh.axial((x,y,-.247),(x,y+.006,-.247),r,color,steps=28)
        mesh.oval((x-.008,.115,-.255),(.013,.009,.013),[124,160,189],steps=16)
        mesh.oval((x-.011,.123,-.258),(.005,.002,.005),[226,244,255],steps=12)
    for x,z in ((-.141,-.348),(.139,-.347),(-.141,.261),(.151,.280)):
        mesh.axial((x,.061,z),(x,.071,z),.010,silver,steps=14)
        mesh.shell((x,.073,z),(.013,.006,.0025),.001,mix(silver,dark,.47))
    mesh.shell((.131,.061,-.102),(.035,.015,.035),.003,[156,71,65])
    mesh.shell((.202,.002,-.195),(.018,.041,.081),.006,highlight)
    mesh.shell((-.202,.002,-.120),(.018,.031,.127),.006,mix(pearl,silver,.45))
    curve = [(x,.082,z) for x,z in ((-.146,-.040),(.088,-.040),(.145,-.008),(.146,.034),
             (.117,.062),(-.102,.062),(-.137,.088),(-.134,.135),(-.100,.159),
             (.062,.159),(.116,.182),(.131,.215),(.118,.267),(.075,.291),(.022,.291))]
    mesh.tube(curve,.017,mix(pearl,silver,.37))
    mesh.tube([(x,y+.004,z) for x,y,z in curve],.010,highlight)
    # An optical highlight travels in staggered segments without moving the housing.
    for i,(x,y,z) in enumerate(curve[2:-2]):
        first = len(mesh.vertices)
        mesh.oval((x,y+.007,z),(.015,.003,.014),highlight,steps=12,bands=7)
        actions.append([first,len(mesh.vertices),0,.008,0,1.05+.07*i])


def plush(mesh, actions, primary, accent, source):
    """Sculpt the paired facial features and rounded body of a reference mascot."""
    skin = mix(primary, [228, 240, 244], .09)
    paw_ink = mix(accent, [201, 153, 113], .57)
    inner = mix(skin, [11, 35, 49], .59)
    pupil, nose_ink = [21, 32, 38], [27, 40, 47]
    white, ivory = [247, 249, 241], [255, 245, 223]
    detail = dict(steps=38, bands=22)
    mesh.surface([
        [(.258 * math.sin(t) ** .78 * math.cos(a),
          .170 * math.sin(t) ** .78 * math.sin(a),
          .003 + .379 * math.cos(t)) for a in angles(64)]
        for t in np.linspace(0, math.pi, 48)
    ], skin)
    for side in (-1, 1):
        mesh.oval((side*.193, .017, -.300), (.077, .050, .084), skin, **detail)
        mesh.oval((side*.206, .057, -.307), (.040, .021, .049), inner, **detail)
        mesh.oval((side*.105, .114, -.181), (.106, .058, .095), white, **detail)
        mesh.oval((side*.095, .161, -.175), (.045, .025, .056), pupil, **detail)
        mesh.oval((side*.095-.010, .185, -.194), (.013, .007, .012), white)
        mesh.oval((side*.131, .046, .346), (.090, .083, .049), paw_ink, **detail)

        start = len(mesh.vertices)
        wrist = (side*.246, .047, .107)
        hand = (side*.268, .086, .145)
        mesh.tube([(side*.218, .009, .042), (side*.240, .023, .075), wrist, hand], .040, skin)
        mesh.oval(hand, (.047, .039, .050), paw_ink, **detail)
        actions.append([start, len(mesh.vertices), side*.017, .018, -.048, .53 if side > 0 else .13])

    mesh.oval((0, .166, -.057), (.086, .042, .057), paw_ink, **detail)
    mesh.oval((0, .198, -.024), (.054, .012, .024), nose_ink, **detail)
    for side in (-1, 1):
        mesh.shell((side*.021, .207, -.013), (.036, .036, .051), .010, ivory)
    mesh.oval((0, .201, -.093), (.044, .024, .027), nose_ink, **detail)
    mesh.oval((-.012, .223, -.101), (.014, .004, .006), [92, 114, 119])


def star_points(x, z, radius):
    return [(x + math.cos(a) * r, z + math.sin(a) * r)
            for i, a in enumerate(angles(10))
            for r in [radius * (1 if i % 2 else .46)]]


def blue_bob(mesh, actions, primary, accent, source):
    """Sculpt the download-page character as volumes with an articulated waving arm."""
    sky = mix([112, 194, 233], primary, .25)
    frost, shadow = mix(sky, [241, 250, 255], .66), mix(sky, [38, 88, 158], .47)
    skin, cheek = [255, 221, 210], [246, 149, 154]
    navy, white, rose = [27, 52, 92], [246, 251, 255], mix([233, 100, 143], accent, .25)
    detail = dict(steps=38, bands=24)
    mesh.oval((0, 0, -.238), (.198, .155, .175), skin, **detail)
    for side in (-1, 1):
        mesh.oval((side*.186, .017, -.200), (.041, .036, .043), skin)
        mesh.oval((side*.202, .042, -.198), (.020, .009, .023), cheek)
    # The scalp wraps behind the face and ends in several unequal points at the nape.
    hair_rings = []
    for t in np.linspace(0, 1, 39):
        ring = []
        for a in angles(76):
            front = max(0, math.sin(a))**1.45
            cut = 2.85 - 1.76*front + .11*math.cos(7*a)*(1-front)
            lat = t*cut
            ring.append((.233*math.sin(lat)*math.cos(a), -.037+.199*math.sin(lat)*math.sin(a),
                         -.228-.229*math.cos(lat)))
        hair_rings.append(ring)
    hair_rings.append([(x*.83, y*.78-.010, z-.013) for x, y, z in hair_rings[-1]])
    hair_rings.append([(0, -.040, -.233)] * 76)
    mesh.surface(hair_rings, sky)
    fringe = [
        ([(-.217,-.254),(-.201,-.324),(-.152,-.387),(-.099,-.397),(-.114,-.345),(-.145,-.281),(-.181,-.246),(-.207,-.172)], .113, sky),
        ([(-.138,-.343),(-.109,-.404),(-.050,-.426),(-.008,-.395),(-.029,-.350),(-.078,-.293),(-.109,-.308)], .153, frost),
        ([(-.076,-.345),(-.035,-.407),(.021,-.412),(.086,-.365),(.054,-.328),(.001,-.291),(-.041,-.309)], .158, sky),
        ([(.040,-.397),(.093,-.414),(.160,-.367),(.176,-.289),(.136,-.304),(.101,-.345)], .131, frost),
        ([(.145,-.362),(.197,-.335),(.228,-.276),(.216,-.195),(.178,-.116),(.106,-.096),(.137,-.152),(.144,-.205),(.155,-.271)], .127, sky),
        ([(.177,-.270),(.202,-.264),(.184,-.198),(.154,-.148),(.112,-.121),(.148,-.174)], .158, shadow),
    ]
    for outline, depth, color in fringe:
        emblem_panel(mesh, outline, [(depth-.074, .52), (depth-.041, .98),
                                     (depth+.008, 1), (depth+.028, .62), (depth+.033, 0)], color)
    mesh.tube([(0,-.010,-.429),(.036,-.013,-.468),(.074,.001,-.478),
               (.108,.020,-.471),(.123,.029,-.459)], .012, frost)

    for x in (-.080, .074):
        mesh.oval((x,.139,-.230),(.043,.017,.052),[255,246,240], **detail)
        mesh.oval((x+.004,.151,-.224),(.028,.012,.042),rose, **detail)
        mesh.oval((x+.005,.160,-.236),(.018,.005,.029),[126,41,78], **detail)
        mesh.oval((x-.007,.165,-.251),(.009,.003,.011),white,steps=22,bands=12)
        mesh.oval((x+.013,.165,-.214),(.005,.003,.007),[255,204,193],steps=20,bands=10)
        mesh.tube([(x-.031,.144,-.273),(x-.013,.155,-.283),
                   (x+.014,.154,-.282),(x+.034,.144,-.272)], .006, navy)
        mesh.oval((x*1.49,.126,-.179),(.033,.012,.011),cheek)
    mesh.oval((-.007,.151,-.170),(.012,.014,.011),skin)
    mesh.oval((-.014,.148,-.148),(.019,.008,.024),[174,63,97])
    mesh.oval((-.014,.155,-.138),(.012,.003,.010),rose,steps=20,bands=10)
    # One visible headset with a white earpiece and dark triangular insert.
    mesh.tube([(.150,-.029,-.412),(.210,-.025,-.383),(.232,-.003,-.326)], .027, navy)
    mesh.oval((.210,.003,-.286),(.067,.054,.059),shadow, **detail)
    mesh.oval((.226,.035,-.291),(.057,.046,.052),white, **detail)
    emblem_panel(mesh, [(.221,-.317),(.197,-.276),(.248,-.282)],
                [(.071,.7),(.079,1),(.084,.84),(.085,0)], navy)

    mesh.oval((0, -.009, -.075), (.049,.045,.064), skin)
    dress = [(-.085,.064,.038),(-.061,.098,.067),(-.018,.127,.073),
             (.070,.103,.075),(.129,.112,.084),(.225,.156,.090),(.246,.155,.085)]
    mesh.surface([[(rx*math.cos(a),ry*math.sin(a),z) for a in angles(40)]
                  for z,rx,ry in [(-.092,0,0),*dress,(.249,0,0)]], white)
    mesh.oval((0, .001, .239), (.153,.086,.021), sky, **detail)
    emblem_panel(mesh, [(-.094,-.044),(-.058,-.075),(.054,-.075),(.101,-.045),(.014,.033),(-.012,.024)],
                [(.047,.84),(.069,1),(.079,.87),(.083,0)], navy)
    mesh.shell((-.009,.082,.026),(.049,.016,.095),.012,navy)
    mesh.oval((-.009,.092,.038),(.012,.005,.017),[103,203,234])
    mesh.tube([(-.113,.057,.205),(-.063,.082,.213),(-.023,.090,.174),
               (-.006,.088,.049)], .004, sky)
    mesh.tube([(-.023,.090,.174),(.008,.091,.217),(.070,.078,.218),(.118,.055,.196)], .004, sky)

    # Movement is weighted from shoulder to fingers to keep the joint attached.
    start = len(mesh.vertices)
    mesh.tube([(-.102,.009,-.011),(-.152,.021,.021),(-.203,.039,-.020),
               (-.235,.059,-.072),(-.258,.072,-.112)], .025, skin)
    mesh.oval((-.265,.069,-.124),(.030,.022,.025),skin)
    for x,y,z in [(-.285,.070,-.139),(-.274,.069,-.151),(-.260,.069,-.152),(-.247,.069,-.143)]:
        mesh.oval((x,y,z),(.009,.012,.022),skin,steps=18,bands=9)
    for i,(x,y,z) in enumerate(mesh.vertices[start:], start):
        reach = min(1., max(0., (-x-.124)/.151))
        actions.append([i,i+1,.024*reach,.020*reach,-.090*reach,1.54])

    start = len(mesh.vertices)
    mesh.tube([(.104,.014,-.019),(.149,.014,.041),(.183,.045,.088),(.200,.052,.129)],.023,skin)
    mesh.oval((.204,.051,.131),(.034,.027,.032),white)
    board = [(.184,.175),(.296,.077),(.378,.175),(.264,.278)]
    emblem_panel(mesh, board, [(.010,0),(.010,.97),(.018,1),(.042,1),(.049,.94),(.049,0)], navy)
    emblem_panel(mesh, board, [(.048,.86),(.059,.87),(.066,.77),(.067,0)], rose)
    emblem_panel(mesh, star_points(.294,.173,.055), [(.062,1),(.070,1),(.072,0)], white)
    for i,(x,y,z) in enumerate(mesh.vertices[start:], start):
        reach = min(1., max(0., (x-.125)/.064))
        actions.append([i,i+1,.022*reach,.019*reach,.034*reach,1.20])

    for side in (-1, 1):
        x = side*.072
        start = len(mesh.vertices)
        mesh.tube([(x,-.002,.213),(x*1.11,.002,.282),(x*1.46,.006,.355)], .041, navy)
        mesh.oval((x*1.49,.029,.374),(.047,.059,.043),navy, **detail)
        mesh.oval((x*1.50,.039,.397),(.045,.053,.018),[41,70,108])
        for i,(vx,vy,z) in enumerate(mesh.vertices[start:], start):
            reach = min(1., max(0., (z-.233)/.14))
            actions.append([i,i+1,side*.009*reach,side*.035*reach,side*.019*reach,1.06])


def medallion(mesh, actions, primary, accent, source, *, depth=1., embers=True, require_alpha=True, tapered_wall=False):
    """Trace the half-alpha contour and round a welded, continuously colored relief."""
    content = source.getchannel("A").point(lambda a: 255 if a > 35 else 0).getbbox()
    mark = source.crop(content) if content else source
    mark.thumbnail((640, 640), Image.Resampling.LANCZOS)
    if not content or (require_alpha and not np.any(np.asarray(source.getchannel("A")) < 100)):
        raise ValueError("制作贴合轮廓的浮雕需要透明背景的主体图，请上传去底的 PNG 或静态 SVG。")
    geometry = ImageOps.contain(mark, (82, 82), Image.Resampling.LANCZOS)
    rgba = np.asarray(ImageOps.expand(geometry, border=4), dtype=np.float64)
    alpha = cv2.GaussianBlur(rgba[:, :, 3], (7, 7), .85)
    solid = alpha >= 127.5
    height, width = alpha.shape
    scale = .90 / max(geometry.size)
    materials, points, border = {}, {}, {}
    vertex_colors = []

    def vertex(point, cut):
        x, z = point
        a, b = cut
        key = (a, b)
        if key in points:
            return points[key]
        if a == b:
            ix, iz = a
            ink = rgba[iz, ix, :3]
        else:
            (ix, iz), (jx, jz) = a, b
            ink = rgba[iz, ix, :3] if solid[iz, ix] else rgba[jz, jx, :3]
        front, back = len(mesh.vertices), len(mesh.vertices) + 1
        mesh.vertices.extend(((x, 0, z), (x, 0, z)))
        vertex_colors.extend((ink.round().astype(int).tolist(), mix(ink, [81, 45, 76], .18) if embers else ink.round().astype(int).tolist()))
        points[key] = front, back
        return front, back

    def face(a, b, c):
        ink = tuple(min(255, 6 * round((vertex_colors[a][i] + vertex_colors[b][i] + vertex_colors[c][i]) / 18))
                    for i in range(3))
        if ink not in materials:
            materials[ink] = len(mesh.palette)
            mesh.palette.append(list(ink))
        mesh.faces.append((a, b, c, materials[ink]))

    def trace(corners):
        ring = []
        for a, b in zip(corners, corners[1:] + corners[:1]):
            ax, az = a
            bx, bz = b
            inside_a, inside_b = solid[az, ax], solid[bz, bx]
            if inside_a:
                ring.append((vertex(a, (a, a)), False))
            if inside_a != inside_b:
                aa, ab = alpha[az, ax], alpha[bz, bx]
                t = (127.5 - aa) / (ab - aa)
                edge = (ax + (bx - ax) * t, az + (bz - az) * t)
                ring.append((vertex(edge, tuple(sorted((a, b)))), True))
        if len(ring) < 3:
            return
        (f0, b0), _ = ring[0]
        for ((f1, b1), _), ((f2, b2), _) in zip(ring[1:], ring[2:]):
            face(f0, f1, f2)
            face(b0, b2, b1)
        for (a, edge_a), (b, edge_b) in zip(ring, ring[1:] + ring[:1]):
            if edge_a and edge_b:
                border[a[0], b[0]] = (a[1], b[1])

    intersects = solid[:-1, :-1] | solid[1:, :-1] | solid[:-1, 1:] | solid[1:, 1:]
    for z, x in zip(*np.nonzero(intersects)):
        tl, bl, br, tr = (x, z), (x, z + 1), (x + 1, z + 1), (x + 1, z)
        trace((tl, bl, br))
        trace((tl, br, tr))
    for (a, b), (rear_a, rear_b) in border.items():
        face(b, a, rear_a)
        face(b, rear_a, rear_b)

    if not border:
        raise ValueError("标志图需要有可见的主体轮廓。")
    # Measure from the traced contour, including holes, instead of the thresholded
    # pixel grid so oblique highlights follow the same curves as the silhouette.
    edge_indices = np.asarray(list(border), dtype=int)
    raw = np.asarray(mesh.vertices)[:, [0, 2]]
    edges = raw[edge_indices]
    starts = edges[:, 0]
    segments = edges[:, 1] - starts
    lengths = (segments ** 2).sum(axis=1)
    gz, gx = np.gradient(cv2.GaussianBlur(alpha, (15, 15), 2.4))
    map_x, map_z = (raw[::2, i].astype(np.float32).reshape(-1, 1) for i in (0, 1))
    slopes = np.column_stack((cv2.remap(gx, map_x, map_z, cv2.INTER_LINEAR).ravel(),
                              cv2.remap(gz, map_x, map_z, cv2.INTER_LINEAR).ravel()))
    slopes /= np.maximum(1e-6, np.linalg.norm(slopes, axis=1, keepdims=True))
    thickness = np.ones(len(map_x))
    if tapered_wall:
        # Sample the width of the nearby material on each side of the contour.
        # A narrow tip stays thin even while a wider body opens up.
        radius = cv2.distanceTransform(solid.astype(np.uint8), cv2.DIST_L2, 5)
        neighborhood = cv2.dilate(radius, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
        width_map = cv2.GaussianBlur(neighborhood, (0, 0), 1.35)
        local_radius = cv2.remap(width_map, map_x, map_z, cv2.INTER_LINEAR).ravel()
        thickness = .34 + .66 * np.clip((local_radius - 1.5) / 5.5, 0, 1)
    relief_normals = []
    for start in range(0, len(raw) // 2, 160):
        end = min(start + 160, len(raw) // 2)
        coords = raw[2*start:2*end:2]
        relative = coords[:, None, :] - starts
        nearest = np.clip((relative * segments).sum(axis=2) / lengths, 0, 1)
        distance = np.sqrt(((relative - nearest[:, :, None] * segments) ** 2).sum(axis=2).min(axis=1))
        slope = np.minimum(1, distance / 4.6)
        bevel = slope * (2 - slope)
        crown = -.017 * np.expm1(-distance / 12)
        coords = (coords - ((width - 1) / 2, (height - 1) / 2)) * scale
        for i, ((x, z), curve, dome) in enumerate(zip(coords, bevel, crown), start):
            back_depth = depth * thickness[i]
            mesh.vertices[2*i] = (round(x, 6), round(depth * (.037 + .034*curve + dome), 6), round(z, 6))
            mesh.vertices[2*i+1] = (round(x, 6), round(back_depth * (-.039 - .027*curve), 6), round(z, 6))
        # The same contour gradient lights the bevel and the tangent of the side wall.
        for (x, z), d in zip(slopes[start:end], distance):
            angle = math.pi / 2 * math.exp(-d / 2.45)
            nx, ny, nz = -x * math.sin(angle), math.cos(angle), -z * math.sin(angle)
            relief_normals.extend(((round(nx, 4), round(ny, 4), round(nz, 4)),
                                   (round(nx, 4), round(-ny, 4), round(nz, 4))))

    # A short arc of solid embers traces the upper shoulder of the relief.
    for i in range(6 if embers else 0):
        a = -.92+i*.22
        x,z = .51*math.cos(a), .42*math.sin(a)-.11
        y = -.17 + .078*i
        first=len(mesh.vertices)
        mesh.oval((x,y,z),(.013+.002*i,.019,.012+.002*i),mix(accent,[255,234,144],.28),
                  steps=14,bands=10)
        actions.append([first,len(mesh.vertices),.082,.061,-.115,1.08+i*.085])
    buf = BytesIO()
    mark.save(buf, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    return vertex_colors, [data_url, geometry.width * scale, geometry.height * scale], relief_normals
