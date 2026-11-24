"""Art-directed, offline geometry for the first three conversation scenes."""
import math

import numpy as np

SCENES = {
    "service-guide": ("信号潮汐", [8, 18, 35], [-.29, -.43], [109, 243, 233]),
    "reception-desk": ("企点接待台", [10, 29, 40], [-.43, -.30], [109, 243, 233]),
    "living-garden": ("共生岛 · 种子回流", [10, 32, 33], [-.43, -.36], [247, 219, 147]),
    "handheld-display": ("掌机街机台 · 关卡越屏", [33, 26, 26], [-.43, -.27], [255, 215, 104]),
}


class Mesh:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.palette = []

    def surface(self, rings, color):
        if color not in self.palette:
            self.palette.append(color)
        material = self.palette.index(color)
        start = len(self.vertices)
        width = len(rings[0])
        self.vertices.extend([tuple(round(float(v), 5) for v in vertex) for ring in rings for vertex in ring])
        faces = []
        for row in range(len(rings) - 1):
            for column in range(width):
                a = start + row * width + column
                b = start + row * width + (column + 1) % width
                faces.extend(((a, b, b + width), (a, b + width, a + width)))
        triangles = np.asarray(self.vertices[start:])[np.asarray(faces) - start]
        u, v, w = triangles.transpose(1, 0, 2)
        outward = np.sum(u * np.cross(v, w)) > 0
        valid = np.linalg.norm(np.cross(v - u, w - u), axis=1) > 1e-9
        self.faces.extend((a, b, c, material) if outward else (a, c, b, material)
                          for (a, b, c), area in zip(faces, valid) if area)

    def oval(self, center, radius, color, *, steps=24, bands=14):
        x, y, z = center
        sx, sy, sz = radius
        self.surface([
            [(x + sx * math.sin(t) * math.cos(a), y + sy * math.sin(t) * math.sin(a), z + sz * math.cos(t))
             for a in angles(steps)] for t in np.linspace(0, math.pi, bands + 1)], color)

    def axial(self, start, end, radius, color, *, tip=None, steps=18):
        a, b = np.array(start), np.array(end)
        axis = (b - a) / np.linalg.norm(b - a)
        reference = [0, 0, 1] if abs(axis[2]) < .9 else [1, 0, 0]
        u = np.cross(axis, reference)
        u /= np.linalg.norm(u)
        v = np.cross(axis, u)
        if tip is None:
            tip = radius
        self.surface([[p + r * (math.cos(theta) * u + math.sin(theta) * v) for theta in angles(steps)]
                      for p, r in ((a, 0), (a, radius), (b, tip), (b, 0))], color)

    def tube(self, points, radius, color):
        points = np.asarray(points)
        tangents = np.gradient(points, axis=0)
        rings = []
        for point, tangent in zip(points, tangents):
            tangent /= np.linalg.norm(tangent)
            reference = (0, 1, 0) if abs(tangent[1]) < .92 else (0, 0, 1)
            u = np.cross(tangent, reference)
            u /= np.linalg.norm(u)
            v = np.cross(tangent, u)
            rings.append([point + radius * (math.cos(t) * u + math.sin(t) * v) for t in angles(8)])
        self.surface([np.repeat([points[0]], 8, axis=0), *rings,
                      np.repeat([points[-1]], 8, axis=0)], color)

    def shell(self, center, size, corner, color, *, power=None):
        """Rounded enclosure at fixed depths, including the closed back and front."""
        x, y, z = center
        w, d, h = (v / 2 for v in size)
        edge = min(d * .8, corner * .75)
        contour = []
        for sx, sz, angle in ((1, 1, 0), (-1, 1, math.pi / 2), (-1, -1, math.pi), (1, -1, 3 * math.pi / 2)):
            for a in np.linspace(angle, angle + math.pi / 2, 5):
                if power is None:
                    contour.append((sx * (w - corner) + math.cos(a) * corner,
                                    sz * (h - corner) + math.sin(a) * corner))
                else:
                    c, s = math.cos(a), math.sin(a)
                    contour.append((w * math.copysign(abs(c) ** power, c),
                                    h * math.copysign(abs(s) ** power, s)))
        self.surface([[(x + px * scale, y + depth, z + pz * scale) for px, pz in contour]
                      for depth, scale in ((-d, 0), (-d, .90), (-d + edge, 1),
                                           (d - edge, 1), (d, .90), (d, 0))], color)

    def leaf(self, root, direction, height, reach, width, color, *, twist=0.):
        x, y, z = root
        u = np.array([math.cos(direction), math.sin(direction)])
        v = np.array([-u[1], u[0]])
        rings = []
        for t in np.linspace(0, 1, 14):
            shape = math.sin(math.pi * t) ** .88
            center = np.array([x, y]) + reach * t ** 1.6 * u + width * .3 * t * v
            ring = []
            for a in angles(20):
                spread = math.cos(a) * shape
                cross = width * (spread * math.cos(twist * t) - math.sin(a) * .34 * shape * math.sin(twist * t))
                curl = width * (.42 * math.sin(a) * shape + .27 * spread ** 2)
                pos = center + cross * v + curl * u
                ring.append((*pos, z - height * t + spread * .08 * t))
            rings.append(ring)
        self.surface(rings, color)

    def pack(self):
        return [self.vertices, self.faces, self.palette]


def angles(steps):
    return (step * math.tau / steps for step in range(steps))


def pedestal(mesh, radius, top, rim, flank, z):
    mesh.axial((0, 0, z + .065), (0, 0, z + .029), radius * .91, flank, tip=radius, steps=48)
    mesh.axial((0, 0, z + .030), (0, 0, z + .016), radius, rim, steps=48)
    mesh.axial((0, 0, z + .017), (0, 0, z), radius, top, tip=radius * .95, steps=48)


def signal_ribbon(mesh, *, root, sweep, height, radius, width, color, edge):
    rings, filament = [], []
    for t in np.linspace(0, 1, 76):
        angle = root - sweep * t
        rise = t ** 1.22
        distance = radius * (1 + .23 * math.sin(math.pi * t) - .63 * t ** 4)
        x = -.06 + distance * math.cos(angle)
        y = .016 + distance * .84 * math.sin(angle)
        z = .324 - height * rise + .028 * math.sin(2 * math.pi * t)
        flare = width * math.sin(math.pi * t) ** .72
        roll = .87 + .47 * math.sin(math.pi * t * 1.4)
        ring = []
        for a in angles(16):
            spread = math.cos(a) * flare
            bevel = math.sin(a) * flare * .20
            r = spread * math.cos(roll) + bevel * math.sin(roll)
            ring.append((x + r * math.cos(angle), y + r * math.sin(angle),
                         z - spread * math.sin(roll) + bevel * math.cos(roll)))
        rings.append(ring)
        if .08 < t < .96:
            # The fillet catches light along the upper edge of each sculpted ribbon.
            filament.append(ring[0])
    mesh.surface(rings, color)
    mesh.tube(filament, .0035, edge)


def service_guide(m):
    basalt, sea = (34, 52, 76), (32, 99, 121)
    gold, copper, porcelain = (255, 197, 102), (158, 86, 52), (218, 242, 248)
    # An eroded, asymmetric plinth, with a low seawall and narrow gold signal channels.
    contour = np.array([(.55, .035), (.49, .255), (.27, .438), (-.07, .493), (-.41, .384),
                        (-.552, .15), (-.53, -.145), (-.328, -.365), (-.026, -.397),
                        (.264, -.343), (.484, -.195)])
    corners = np.asarray([a * ratio + b * (1-ratio) for a, b in zip(contour, np.roll(contour, -1, axis=0))
                          for ratio in (.84, .16)])
    def terrace(outline, floor, roof, material):
        m.surface([[(x * factor, y * factor, z) for x, y in outline]
                   for z, factor in ((floor, 0), (floor, .95), (floor-.015, 1),
                                     (roof+.012, 1), (roof, .96), (roof, 0))], material)

    terrace(corners, .462, .408, (37, 55, 78))
    terrace(corners * .976, .409, .398, copper)
    terrace(corners * .971, .398, .329, basalt)
    terrace(corners * .84 + [-.04, -.037], .330, .290, (38, 77, 102))
    for i in range(4):
        for r, shade in ((.009, (22, 47, 70)), (.0036, (212, 145, 82) if i == 0 else sea)):
            m.tube([(x, .366+i*.021 - .75*(x+.1)**2 + .045*math.sin(6*x+i*.38), .326-r*.25)
                    for x in np.linspace(-.315, .375-i*.025, 32)], r, shade)
    for i, (x, y, rise) in enumerate(((-.42,-.02,.092),(-.33,-.235,.075),(-.212,-.31,.049),
                                       (.24,.305,.048),(.38,.19,.071),(.43,.07,.048),(.32,-.188,.049))):
        m.axial((x,y,.332), (x+.012,y+.007,.321-rise), .022, (66, 104, 129), tip=.014, steps=6)
        m.oval((x+.012,y+.007,.318-rise), (.010,.010,.010), gold if i % 3 == 0 else (68, 166, 190),
               steps=10, bands=6)

    # Inlaid stone steps lead from the foreground seawall to the reception point.
    for i in range(16):
        t = i / 15
        x, y = -.33 + .34*t, .25 - .092*t + .063 * math.sin(math.pi * t)
        m.shell((x, y, .288), (.019, .061 - .019*t, .008), .003,
                ((60, 107, 130), (84, 130, 146), (48, 89, 114))[i % 3])
        if i % 3 == 1:
            m.shell((x, y+.033-.008*t, .285), (.013, .010, .008), .003, gold)

    # The coming and going signals wrap in opposite visual layers around the light well.
    for root, sweep, height, radius, width, stone, edge in (
        (.22, 3.53, .884, .393, .151, (38, 104, 195), (113, 223, 255)),
        (-.19, 3.93, .823, .439, .105, (102, 223, 214), (172, 255, 236)),
        (.95, 2.80, .696, .372, .086, (34, 151, 189), (155, 230, 248)),
        (.86, 3.75, .78, .445, .036, (171, 103, 58), (255, 205, 132)),
    ):
        signal_ribbon(m, root=root, sweep=sweep, height=height, radius=radius,
                      width=width, color=stone, edge=edge)

    # A small reception guide puts the public sculpture in scale. The amber sphere
    # and wet-blue stone are separately modeled, so the view holds while orbiting.
    m.axial((.094, .110, .291), (.094, .110, .252), .158, sea, tip=.143, steps=44)
    m.axial((.094, .110, .253), (.094, .110, .245), .144, copper, tip=.143, steps=44)
    m.axial((.094, .110, .246), (.094, .110, .238), .142, (33, 65, 90), tip=.137, steps=44)
    for r in (.109, .129):
        m.tube([(.094 + r * math.cos(t), .110 + r * math.sin(t), .235)
                for t in np.linspace(.25, 5.99, 65)], .0029, (117, 221, 214))
    m.oval((.094, .109, .161), (.075, .056, .090), (28, 79, 173))
    m.oval((.094, .149, .170), (.056, .028, .064), porcelain, bands=10)
    m.shell((.094,.111,.063), (.206,.149,.135), .041, porcelain, power=.69)
    m.shell((.094,.168,.062), (.172,.045,.096), .029, (15, 32, 63), power=.64)
    m.shell((.094,.036,.066), (.111,.020,.064), .022, (35, 73, 114))
    for x in (.070, .094, .118):
        m.shell((x,.024,.066), (.011,.005,.025), .004, (93, 205, 211))
    for side in (-1, 1):
        x = .094 + side * .044
        m.shell((x,.193,.060), (.018,.008,.027), .006, (131, 255, 232))
        m.axial((.094+side*.051,.113,.152), (.094+side*.099,.146,.192), .020, (77, 143, 218), tip=.012)
    m.oval((.028,-.082,-.391), (.060,.060,.060), gold, steps=36, bands=24)
    for i, (x, y, z, roughness) in enumerate(((-.095,-.112,-.488, .012), (.141,-.057,-.318,.011),
                                               (-.071,-.050,-.348,.008), (.027,-.072,-.514,.006),
                                               (.116,-.133,-.419,.008), (-.183,-.100,-.447,.006))):
        m.oval((x, y, z), (roughness, roughness, roughness*1.36), gold if i % 2 == 0 else (119, 204, 222),
               steps=12, bands=7)


def living_garden(m):
    water, bank, gold = (26, 107, 104), (70, 92, 51), (255, 200, 119)
    pedestal(m, .423, water, (86, 200, 163), (27, 69, 66), .329)
    m.oval((-.035, .02, .297), (.314, .237, .061), bank, steps=36)
    m.oval((.102, -.047, .294), (.206, .206, .062), (59, 106, 72), steps=32)
    for direction, height, reach, width, color in (
        (1.66, .577, .224, .124, (89, 218, 156)),
        (3.65, .676, .309, .139, (87, 166, 235)),
        (5.67, .536, .326, .131, (240, 120, 108)),
    ):
        root = (0, 0, .268)
        m.leaf(root, direction, height, reach, width, color, twist=1.10)
        u = math.cos(direction), math.sin(direction)
        m.axial(root, (u[0] * .16, u[1] * .16, .077), .020, (196, 168, 103), tip=.009)
        tip = u[0] * reach, u[1] * reach, .268 - height - .035
        m.oval(tip, (.025, .025, .025), (253, 219, 153), steps=14, bands=8)
    for x, y, tilt, height in ((-.22, .095, 2.6, .212), (.19, .126, .53, .162), (.13, -.197, 4.8, .233),
                               (-.124, -.174, 2.8, .133), (.045, .19, 1.52, .146)):
        m.leaf((x, y, .263), tilt, height, .071, .044, (158, 200, 101), twist=.67)
        m.leaf((x, y, .263), tilt + 1.6, height * .72, .067, .030, (70, 159, 123), twist=.8)
    for i in range(12):
        a = i * 2.39996
        r = .25 + .082 * (i % 3) / 2
        x, y = r * math.cos(a), r * math.sin(a)
        m.oval((x, y, .275 - .018 * (i % 4)), (.020, .019, .028), gold, steps=10, bands=6)
    # A crescent of little islands and water contours gives the leaves a landscape.
    for i, t in enumerate(np.linspace(-1.2, 2.5, 13)):
        x, y = .35 * math.cos(t), .295 * math.sin(t)
        m.oval((x, y, .298), (.056, .046, .045 + .008 * (i % 3)),
               ((75, 135, 97), (101, 160, 94), (44, 105, 91))[i % 3], steps=13, bands=6)
        if i % 3 != 1:
            for blade in range(3):
                m.leaf((x, y, .270), t + blade * 1.87, .075 + .013 * blade, .042, .017,
                       (114 + blade * 33, 192, 111), twist=.68)
    for i in range(3):
        size=.43 - i*.018
        m.tube([(size * math.cos(t), size * math.sin(t), .318 + .005 * i)
                for t in np.linspace(1.72 + i * .18, 5.15 - i * .12, 42)],
               .0032, (102, 211, 186))
    for i, t in enumerate(np.linspace(-.35, 5.45, 10)):
        r = .30 + .07 * math.sin(3 * t)
        x, y, z = r * math.cos(t), r * math.sin(t), -.02 - .17 * math.sin(t)**2
        size = .013 + .003 * (i % 3)
        m.oval((x, y, z), (size, size, size), (255, 221, 148), steps=10, bands=7)


def handheld(m):
    case, cap, edge = (247, 181, 35), (255, 209, 64), (210, 133, 24)
    screen, tint, ink = (45, 55, 35), (162, 181, 101), (55, 75, 51)
    pedestal(m, .381, (65, 83, 73), (195, 180, 104), (43, 61, 52), .304)
    m.shell((0, -.028, -.025), (.571, .235, .654), .056, edge)
    m.shell((0, .044, -.035), (.567, .168, .649), .054, case)
    m.shell((0, .098, -.043), (.552, .068, .632), .047, cap)
    m.shell((0, -.147, -.028), (.498, .024, .556), .036, case)
    m.shell((0, .139, -.163), (.455, .024, .264), .019, screen)
    m.shell((0, .153, -.166), (.410, .010, .217), .007, tint)
    # A small original landscape echoes the monochrome screen in the product reference.
    for row, widths in enumerate(((7, 8), (6, 9), (2, 4, 13, 16), (1, 5, 12, 17),
                                  (0, 6, 11, 18), (0, 1, 6, 7, 10, 18), tuple(range(19)))):
        for col in widths:
            px, pz = (col - 9) * .0187, -.232 + row * .022
            m.shell((px, .160, pz), (.0185, .003, .0217), .002, ink)
    for s in (-1, 1):
        for z in (-.244, .196):
            m.axial((s * .205, -.162, z), (s * .205, -.171, z), .015, edge, steps=14)
    for z in (.028, .054, .080, .106):
        m.shell((.0, -.165, z), (.131, .009, .008), .003, edge)
    m.shell((-.129, .149, .132), (.152, .039, .048), .009, screen)
    m.shell((-.129, .151, .132), (.048, .044, .152), .009, screen)
    for x, z in ((.087, .145), (.170, .103)):
        m.axial((x, .135, z), (x, .171, z), .037, (169, 101, 24), steps=20)
        m.axial((x, .171, z), (x, .178, z), .033, (255, 228, 124), tip=.028, steps=20)
    m.axial((.273, -.004, .057), (.317, -.004, .057), .043, screen)
    m.axial((.311, -.004, .057), (.342, -.004, .057), .031, (226, 238, 221))
    m.axial((.339, -.004, .057), (.354, .006, .165), .014, (212, 230, 212))
    m.axial((.354, .006, .165), (.421, .006, .165), .017, (221, 234, 218))
    m.axial((.403, .006, .165), (.462, .006, .165), .032, cap, tip=.027)
    # The screen landscape continues as a miniature level around the enclosure.
    for i, (x, y, h) in enumerate(((-.34, .08, .10),(-.25, .21, .073),(-.15,.297,.056),
                                   (.01,.329,.033),(.16,.305,.063),(.285,.236,.090),
                                   (.34,-.195,.125),(.20,-.295,.065),(-.21,-.287,.076))):
        m.shell((x,y,.303-h/2),(.116,.12,h),.009, (91,111,75))
        m.shell((x,y,.301-h),(.107,.114,.024),.006, ((174,190,104),(222,207,125))[i%2])
        if i in (0, 3, 5, 6):
            m.shell((x,y,.260-h),(.040,.046,.040),.004, cap)
    for i, (x,y,z) in enumerate(((-.357,-.137,-.165),(-.337,-.196,-.245),(-.27,-.26,-.32),
                                (.29,.045,-.330),(.351,.069,-.298),(.392,.097,-.236))):
        size = .030 + (i % 3) * .018
        m.shell((x,y,z),(size,size,size),.004, (255,220,114))


def reception_desk(m):
    ink, slate, nickel = (12, 35, 47), (33, 69, 80), (129, 165, 165)
    porcelain, enamel, glass = (224, 232, 219), (29, 105, 111), (75, 179, 173)
    brass, amber = (196, 133, 77), (251, 190, 111)
    actions = []

    def mark(start, *, shift=(0, 0, 0), light=0):
        actions.append((start, len(m.vertices), *shift, light))

    # Laminated base, with a shadow gap between the upper deck and the plinth.
    def deck(layers, color):
        m.surface([[(a * math.copysign(abs(math.cos(t)) ** .66, math.cos(t)),
                     b * math.copysign(abs(math.sin(t)) ** .66, math.sin(t)), z)
                    for t in angles(64)] for a, b, z in layers], color)

    deck([(0, 0, .380), (.49, .297, .380), (.52, .32, .354), (.52, .32, .322),
          (.50, .30, .304), (0, 0, .304)], ink)
    deck([(0, 0, .322), (.501, .303, .322), (.508, .311, .313), (.501, .306, .306),
          (0, 0, .306)], nickel)
    deck([(0, 0, .305), (.48, .288, .305), (.50, .311, .287), (.50, .311, .257),
          (.469, .281, .237), (0, 0, .237)], slate)

    # A pale cantilever and rounded fins frame the dark interior without hiding the side.
    m.shell((-.025, -.037, -.294), (.90, .447, .118), .050, porcelain)
    m.shell((-.025, -.021, -.234), (.851, .409, .041), .020, enamel)
    m.shell((-.025, -.033, -.205), (.739, .350, .027), .013, ink)
    # The two colored faces of the reference mark are inlaid into the porcelain fascia.
    for outline, color in (
        ([(-.306,-.270),(-.272,-.322),(-.255,-.322),(-.283,-.273)], (60,81,199)),
        ([(-.279,-.280),(-.253,-.310),(-.224,-.270),(-.247,-.270),(-.257,-.281)], (33,150,117)),
    ):
        cx = sum(x for x, _ in outline) / len(outline)
        cz = sum(z for _, z in outline) / len(outline)
        m.surface([[(cx+(x-cx)*k, y, cz+(z-cz)*k) for x,z in outline]
                   for y,k in ((.184,0),(.184,1),(.190,1),(.190,0))], color)
    for z, length in ((-.306, .096), (-.287, .072)):
        m.axial((.17,.187,z), (.17+length,.187,z), .003, nickel, steps=10)
    m.shell((-.035, -.205, -.004), (.725, .084, .454), .038, ink)
    m.shell((-.320, .000, .012), (.118, .438, .448), .046, enamel)
    for x in (-.391, -.376, -.361):
        m.axial((x, .095, -.172), (x, .095, .213), .006, glass, steps=8)
    m.shell((.310, -.118, .046), (.185, .183, .370), .055, enamel)
    m.shell((.312, .125, .120), (.148, .091, .231), .038, porcelain)
    for i in range(3):
        m.shell((.315+i*.014, .172, .126), (.008, .006, .063-i*.012), .003, enamel)
    m.shell((-.018, -.004, .168), (.542, .280, .109), .045, nickel)
    m.shell((-.018, .019, .217), (.690, .363, .046), .020, ink)

    # Inside the booth, a curved porcelain console sits under a fan of warm louvers.
    m.shell((-.025, -.116, .068), (.328, .109, .222), .047, porcelain)
    m.shell((-.014, -.053, -.013), (.354, .127, .060), .026, nickel)
    m.shell((-.061, -.101, -.098), (.140, .033, .102), .013, slate)
    for i in range(9):
        x = -.201 + .044 * i
        z = -.160 + .039 * ((i - 4) / 4) ** 2
        start = len(m.vertices)
        m.axial((x, -.154, z), (x, -.154, -.024), .008, amber, steps=10)
        mark(start, light=.72)

    # Exposed side tracks bend down into the foundation and terminate in brass ferrules.
    for i in range(3):
        y = -.112 + i * .078
        path = [(.390, y, -.196), (.429, y, -.186), (.457, y, -.155), (.467, y, -.117),
                (.467, y, .098), (.458, y, .146), (.435, y, .176), (.408, y, .199)]
        m.tube(path, .021, ink)
        start = len(m.vertices)
        m.tube([(x+.013, t, z) for x, t, z in path], .010, glass)
        mark(start, light=1)
        m.axial((.473, y, .139), (.473, y, .166), .015, brass, steps=12)
    for i in range(5):
        m.shell((-.175 + i*.075, -.249, .090), (.048, .012, .021), .005, nickel)

    # Each fluted leaf slides into its own side pocket; the button moves with its cap.
    for side in (-1, 1):
        x = -.023 + side*.108
        start = len(m.vertices)
        m.shell((x, .124, -.016), (.205, .043, .352), .020, enamel)
        for i in range(7):
            rib = x-.077+i*.026
            m.axial((rib, .145, -.154), (rib, .145, .116), .006, glass, steps=8)
        m.axial((x - side*.079, .156, -.051), (x - side*.079, .156, .005), .011, brass, steps=12)
        mark(start, shift=(side * .193, -.052, 0))

    for y in (.060, .160, .235):
        start = len(m.vertices)
        m.tube([(-.335,y,.233),(-.270,y,.233),(-.201,y,.233)], .005, glass)
        mark(start, light=1)
    button = (.207, .238, .155)
    x, y, z = button
    m.axial((x,y,.233),(x,y,.199),.073,ink,tip=.063,steps=32)
    m.axial((x,y,.201),(x,y,.188),.058,brass,steps=32)
    start = len(m.vertices)
    m.axial((x,y,.187),(x,y,z),.051,amber,tip=.041,steps=32)
    mark(start, shift=(0, 0, .027), light=.45)
    return [actions, button]


AUTHORS = {"service-guide": service_guide, "reception-desk": reception_desk,
           "living-garden": living_garden, "handheld-display": handheld}


def authored_scene(name, n):
    mesh = Mesh()
    return sample_scene(mesh, n, AUTHORS[name](mesh))


def sample_scene(mesh, n, interaction):
    vertices, faces, palette = mesh.pack()
    triangles = np.asarray(faces, dtype=np.intp)
    points = np.asarray(vertices)[triangles[:, :3]]
    areas = np.linalg.norm(np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0]), axis=1)
    cumulative = areas.cumsum()
    # Sample the surfaces themselves so the first separation follows the actual objects.
    sample = np.arange(n * n)
    indices = np.searchsorted(cumulative, (sample + .5) / len(sample) * cumulative[-1])
    a = np.sqrt((sample * .6180339887) % 1)[:, None]
    b = ((sample * .4142135624) % 1)[:, None]
    u, v, w = points[indices].transpose((1, 0, 2))
    positions = (1 - a) * u + a * (1 - b) * v + a * b * w
    centers = points.mean(axis=1)
    materials = triangles[indices, 3]
    # Match each face to the nearby surface sample that owns its moving QR cell.
    fragments = []
    for start in range(0, len(centers), 256):
        batch = slice(start, start + 256)
        distances = ((centers[batch, None, :] - positions) ** 2).sum(axis=2)
        distances += (triangles[batch, 3, None] != materials) * .013
        fragments.extend(distances.argmin(axis=1).tolist())
    pieces = [dict(id=i, x=float(x), h=float(y), z=float(z), w=.78 / n, d=.84 / n,
                   color=palette[triangles[face, 3]], group=f"{int((x+.5)*8)}:{int((z+.5)*8)}")
              for i, ((x, y, z), face) in enumerate(zip(positions, indices))]
    if interaction:
        for piece, face in zip(pieces, indices):
            vertex = triangles[face, 0]
            for start, end, *action in interaction[0]:
                if start <= vertex < end:
                    piece["action"] = action
                    break
        return [vertices, faces, palette, fragments, interaction], pieces
    return [vertices, faces, palette, fragments], pieces
