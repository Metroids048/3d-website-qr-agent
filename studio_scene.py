"""Build an interactive 3D composition from a reusable form and source palette."""
import math

import numpy as np

from brand_scene import Mesh, angles, sample_scene, signal_ribbon
from image_character import IMAGE_FORM, build_character
from studio_forms import blue_bob, horned, medallion, mix, plush, slab

LAYER_SLIDE = "image-layer-slide"
GRAPHIC_FORMS = {
    "image-logo": ("立体品牌标志", .84, [.23, .055, .012, 6.4]),
    "image-element": ("立体网页元素", .65, [.15, .09, .085, 5.4]),
    LAYER_SLIDE: ("圆边立体展件", 1.08, [-.58, .085, 0., 3.6]),
}

FORMS = {
    **{form: (entry[0], "gallery") for form, entry in GRAPHIC_FORMS.items()},
    IMAGE_FORM: ("全身角色", "gallery"),
    "botanical": ("温室种子", "canopy"),
    "signal": ("光带风洞", "canopy"),
    "console": ("悬浮操控台", "instrument"),
    "lens": ("光学剖面台", "instrument"),
    "antenna": ("讯号伙伴", "companion"),
    "ears": ("面罩伙伴", "companion"),
    "tentacles": ("星门信使", "companion"),
    "horned": ("风谷巡游", "sky"),
    "slab": ("光棚机身", "lightbox"),
    "medallion": ("日冕浮雕", "dawn"),
    "plush": ("圆身玩偶", "gallery"),
    "blue-bob": ("蓝发招手伙伴", "download"),
}
COMPOSITIONS = {
    "canopy": dict(environment="canopy", pose=[-.40, -.22], frame=[.86, -.052, .068],
                   camera=[.20, .065, .024, 7.4], light=[-.65, .39, -.66], hue=[120, 214, 155]),
    "instrument": dict(environment="scan", pose=[-.54, -.34], frame=[.91, .103, -.025],
                       camera=[.29, .095, .010, 6.2], light=[.64, .61, -.46], hue=[126, 183, 250]),
    "companion": dict(environment="portal", pose=[-.16, -.10], frame=[.94, -.010, -.020],
                      camera=[.41, .12, .070, 7.2], light=[-.38, .58, -.72], hue=[142, 122, 255]),
    "sky": dict(environment="sky", pose=[-.20, -.12], frame=[.79, -.033, .063],
                camera=[.35, .105, .135, 6.8], light=[-.49, .70, -.51], hue=[97, 200, 175]),
    "lightbox": dict(environment="lightbox", pose=[-.68, -.23], frame=[.91, .065, .053],
                     camera=[.55, .27, .034, 7.8], light=[-.44, .70, -.49], hue=[139, 176, 199]),
    "dawn": dict(environment="dawn", pose=[.22, -.09], frame=[.82, -.074, .017],
                 camera=[.56, .15, .034, 6.0], light=[.44, .61, -.65], hue=[191, 79, 220]),
    "gallery": dict(environment="gallery", pose=[-.17, -.015], frame=[.82, .005, -.023],
                    camera=[.46, .095, .027, 7.6], light=[-.56, .68, -.47], hue=[117, 217, 229]),
    "download": dict(environment="download", pose=[-.11, -.035], frame=[.93, -.022, .012],
                     camera=[.32, .095, .030, 5.9], light=[-.51, .68, -.60], hue=[246, 159, 191]),
}


def palette(subject, family):
    defaults = {
        "canopy": ([66, 182, 156], [243, 176, 108]),
        "instrument": ([190, 146, 85], [152, 118, 238]),
        "companion": ([160, 217, 119], [235, 157, 102]),
        "sky": ([150, 207, 94], [240, 163, 69]),
        "lightbox": ([212, 215, 215], [78, 91, 105]),
        "dawn": ([248, 79, 68], [96, 52, 231]),
        "gallery": ([91, 186, 216], [194, 142, 103]),
        "download": ([112, 194, 233], [233, 100, 143]),
    }
    primary, accent = defaults[family]
    thumb = subject.copy()
    thumb.thumbnail((120, 120))
    pixels = np.asarray(thumb).reshape(-1, 4)
    rgb = pixels[:, :3].astype(float)
    spread = np.ptp(rgb, axis=1)
    bright = rgb.max(axis=1)
    if family == "download":
        r, g, b = rgb.T
        visible = pixels[:, 3] > 180
        for selected, color in (
            (visible & (g > 120) & (b > g+14) & (b > r+38), primary),
            (visible & (r > 190) & (r > g+48) & (b > g+9), accent),
        ):
            if np.count_nonzero(selected) >= 12:
                color[:] = np.median(rgb[selected], axis=0).round().astype(int).tolist()
        return primary, accent
    if family == "lightbox":
        opaque = rgb[pixels[:, 3] > 180]
        if len(opaque) and np.median(np.ptp(opaque,axis=1)) < 27:
            light, dark = np.percentile(opaque,[64,20],axis=0).round().astype(int)
            return light.tolist(), mix(dark.tolist(), [68,81,92], .65)
    colors = rgb[(pixels[:, 3] > 180) & (spread > 26) & (bright > 94)]
    if len(colors) > 12:
        bins, indices, counts = np.unique((colors // 40).astype(int), axis=0, return_inverse=True, return_counts=True)
        primary_bin = counts.argmax()
        primary = np.rint(colors[indices == primary_bin].mean(axis=0)).astype(int).tolist()
        contrasting = (np.linalg.norm((bins - bins[primary_bin]) * 40, axis=1) > 125) & (counts > len(colors) * .035)
        if contrasting.any():
            accent_bin = np.where(contrasting, counts, 0).argmax()
            accent = np.rint(colors[indices == accent_bin].mean(axis=0)).astype(int).tolist()
    return primary, accent


def loop(mesh, root, radius, color, *, thickness=.009, tilt=0, steps=60, span=math.tau):
    x, y, z = root
    points = [(x + radius * math.cos(a), y + radius * math.sin(a),
               z + radius * tilt * math.sin(a)) for a in np.linspace(0, span, steps)]
    mesh.tube(points, thickness, color)


def moving(mesh, actions, movement, geometry):
    first = len(mesh.vertices)
    geometry()
    actions.append([first, len(mesh.vertices), *movement])


def canopy(mesh, actions, primary, accent, organic):
    deep = mix(primary, [9, 18, 29], .83)
    edge = mix(accent, [255, 241, 198], .48)
    mint = mix(primary, [173, 255, 233], .42)
    # Low, irregular terraces give the leaves a shoreline with a visible underside.
    contour = [(math.cos(a) * (.34 + .055 * math.sin(3*a)), math.sin(a) * (.24 + .04 * math.cos(5*a)))
               for a in angles(42)]
    for roof, floor, color, size in ((.292, .320, deep, 1), (.316, .350, edge, .92), (.348, .438, deep, .85)):
        mesh.surface([[(x*factor*size, y*factor*size, z) for x,y in contour]
                      for z,factor in ((floor, 0), (floor, .72), (roof+.015, 1), (roof, .87), (roof, 0))], color)
    for i, angle in enumerate(angles(8 if organic else 5)):
        tall = [.56, .53, .74, .82, .69][i % 5]
        color = mix(primary, accent, (i % 4) * .21)
        if organic:
            root = (.06 * math.cos(angle), .06 * math.sin(angle), .295)
            mesh.leaf(root, angle, tall, .25 + .026 * (i % 3), .126, color, twist=.7 + .35 * (i % 3))
            mesh.leaf(root, angle + .1, tall * .59, .18, .062, mint, twist=.76)
        else:
            signal_ribbon(mesh, root=angle, sweep=2.2, height=tall, radius=.29,
                          width=.068, color=color, edge=mint)
    for i, angle in enumerate(angles(12)):
        x, y = (.32 * math.cos(angle), .32 * math.sin(angle))
        mesh.oval((x, y, .277), (.024, .024, .023 + .016 * (i % 3)), edge, steps=10, bands=7)

    def seed():
        mesh.oval((-.17, .257, -.013), (.043, .042, .086), edge)
        loop(mesh, (-.17, .257, -.032), .066, mint, tilt=.41)
        mesh.oval((-.17, .257, -.033), (.027, .041, .053), accent)

    def bud():
        for angle in angles(5):
            mesh.leaf((.205, .287, .101), angle, .145, .063, .042, accent, twist=.76)
        mesh.oval((.205, .287, .038), (.043, .041, .057), edge)

    moving(mesh, actions, (.235, .034, -.155, 1.10), seed)
    moving(mesh, actions, (.038, .08, -.155, 1.35), bud)


def instrument(mesh, actions, primary, accent, console):
    shell = mix(primary, [249, 220, 135], .19)
    dark = mix(accent, [14, 20, 38], .82)
    silver = mix(accent, [223, 246, 255], .69)
    luminous = mix(accent, [215, 215, 255], .47)
    for y in (-.26, -.165, .07):
        mesh.shell((0, y, .223), (.70, .105, .089), .032, dark)
    mesh.shell((0, -.035, -.055), (.538, .262, .626), .062, shell)
    mesh.shell((0, -.18, -.055), (.442, .058, .543), .045, mix(shell, dark, .25))
    for i in range(7):
        mesh.shell((0, -.217, -.173+i*.038), (.255+abs(i-3)*.014, .023, .014), .006, dark)
    for x in (-.223, .223):
        for z in (-.274, .147):
            mesh.axial((x,-.234,z), (x,-.210,z), .017, silver)
    if console:
        mesh.shell((0, .113, -.155), (.421, .078, .264), .038, dark)
        mesh.shell((0, .158, -.155), (.351, .024, .195), .017, mix(dark, [70, 127, 130], .58))
        for i in range(8):
            mesh.shell((-.113+i*.032, .177, -.152 + ((i*5) % 7 - 3)*.013), (.019, .024, .029), .009,
                       mix(silver, [180, 255, 176], (i % 3) * .28))
        for x, z, w, h in ((-.11, .071, .124, .035), (-.11, .071, .035, .124)):
            mesh.shell((x, .113, z), (w, .045, h), .012, dark)
        for x, z in ((.101, .097), (.166, .055)):
            mesh.axial((x, .092, z), (x, .15, z), .026, dark, tip=.025)
    else:
        for radius, y, color in ((.168,.116,dark),(.142,.157,silver),(.118,.197,accent),(.096,.214,dark)):
            mesh.axial((0, y, -.133), (0, y+.04, -.133), radius, color, steps=34)
        mesh.oval((0, .242, -.133), (.074,.053,.074), luminous)
    mesh.tube([(-.22, -.195, .19), (-.22, -.22, .268), (.21, -.22, .268), (.25, -.195, .19)], .018, silver)
    mesh.axial((.234, .045, -.12), (.32, .045, -.12), .029, dark)

    def lever():
        mesh.axial((.297, .045, -.119), (.297, .172, -.058), .019, silver)
        mesh.axial((.297, .172, -.058), (.345, .196, -.058), .031, shell)
        mesh.oval((.365, .194, -.058), (.04,.039,.047), luminous)

    def scanner():
        mesh.shell((-.036, .21, .235), (.244,.087,.086), .036, dark)
        mesh.shell((-.036, .259, .221), (.155,.019,.028), .011, luminous)
        for x in (-.129,.062):
            mesh.oval((x,.256,.234), (.013,.012,.014), silver)

    moving(mesh, actions, (.075, .037, -.205, 1.10), lever)
    moving(mesh, actions, (-.056,.107,-.05, 1.35), scanner)


def companion(mesh, actions, primary, accent, antenna):
    pearl = mix(primary, [243, 253, 224], .21)
    paint = mix(primary, [54, 78, 87], .19)
    dark = mix(accent, [18, 20, 40], .79)
    warm = mix(accent, [255, 211, 167], .51)
    glass = [24, 47, 53]
    for x in (-.112, .112):
        mesh.oval((x,-.012,.253), (.077,.113,.067), dark)
        mesh.oval((x,.055,.266), (.074,.107,.054), paint)
    mesh.oval((0,0,.101), (.20,.146,.187), paint)
    mesh.oval((0,-.14,.099), (.121,.069,.102), dark)
    for x in (-.225,.225):
        mesh.oval((x,.002,.081), (.065,.081,.138), pearl)
        mesh.oval((x,.011,.174), (.049,.057,.039), warm)
    mesh.oval((-.012,.01,-.227), (.278,.212,.201), pearl, steps=38, bands=22)
    for sign in (-1,1):
        x = sign * .145
        if antenna:
            mesh.axial((x,.002,-.371),(x+sign*.065,.008,-.5), .024, paint, tip=.011)
            mesh.oval((x+sign*.066,.008,-.5), (.026,.028,.03), warm)
        else:
            mesh.oval((x+sign*.025,0,-.40), (.082,.069,.12), paint)
            mesh.oval((x+sign*.025,.052,-.424), (.041,.03,.067), warm)
        mesh.axial((sign*.233,.005,-.219),(sign*.298,.005,-.219),.077,dark)
        mesh.axial((sign*.294,.005,-.219),(sign*.307,.005,-.219),.05,warm)

    def visor():
        mesh.shell((-.013,.177,-.213), (.423,.116,.164), .066, glass)
        for x in (-.111,.084):
            mesh.oval((x,.236,-.214), (.031,.01,.028), [205,255,229])
        mesh.shell((-.013,.236,-.169), (.084,.013,.013), .006, warm)

    def core():
        mesh.oval((0,.144,.077), (.081,.046,.094), dark)
        mesh.axial((0,.153,.077), (0,.209,.077), .052, pearl, steps=6)
        mesh.axial((0,.204,.077), (0,.228,.077), .033, warm, steps=6)

    moving(mesh, actions, (.115,.122,.08, 1.10), core)
    moving(mesh, actions, (0,.055,-.111, 1.35), visor)


def tentacle_avatar(mesh, actions, primary, accent):
    shell = [39, 34, 59]
    edge = mix(accent, [123, 93, 235], .78)
    face = mix(primary, [255, 219, 195], .60)
    mesh.oval((0, -.032, .105), (.133, .135, .174), shell, steps=24)
    mesh.oval((0, 0, -.150), (.299, .225, .208), shell, steps=42, bands=24)
    for sign in (-1, 1):
        contour = ((sign*.073,-.290), (sign*.209,-.444), (sign*.243,-.428), (sign*.270,-.265))
        center = (sign*.18, -.338)
        mesh.surface([[(center[0]+(x-center[0])*f, y, center[1]+(z-center[1])*f) for x,z in contour]
                      for y, f in ((-.13,0),(-.105,.88),(-.045,1),(.102,.92),(.131,0))], shell)
        mesh.oval((sign*.202, .091, -.341), (.042, .037, .054), edge, steps=20)
    mesh.oval((.006, .172, -.101), (.239, .103, .140), face, steps=40, bands=17)
    for x in (-.090, .095):
        mesh.oval((x, .265, -.111), (.026, .015, .050), [38, 26, 45], steps=24)
        mesh.oval((x-.006, .278, -.126), (.007, .005, .015), [255, 246, 242], steps=12, bands=7)
    mesh.tube([(-.037+.074*t, .269+.003*math.sin(math.pi*t), -.041+.017*math.sin(math.pi*t))
               for t in np.linspace(0, 1, 16)], .006, [84, 47, 71])

    for i, heading in enumerate((-.16, 1.04, 2.20, 3.26, 4.48)):
        first = len(mesh.vertices)
        rings = []
        for t in np.linspace(0, 1, 27):
            angle = heading + .73*t*t
            reach = .063 + (.29 + .034*(i % 3))*math.sin(t*1.51)
            x, y = reach*math.cos(angle), reach*math.sin(angle)
            z = .14 + .265*t - (.11 if i % 2 else .23)*t**4
            radius = .064*(1-t)**.8
            rings.append([(x+radius*math.cos(a)*math.sin(angle), y-radius*math.cos(a)*math.cos(angle),
                           z+radius*math.sin(a)) for a in angles(16)])
        mesh.surface([np.repeat([rings[0][0]], 16, axis=0), *rings], mix(shell, edge, .13 + .08*(i % 3)))
        # Each ring follows the arm's rhythm, with the root fixed and the tip lifting.
        for rung in range(1, len(rings) + 1):
            t = (rung - 1) / (len(rings) - 1)
            reach = t**1.65
            wave = 1.05 + .115 * i
            start = first + 16 * rung
            actions.append([start, start + 16, .063*math.cos(heading)*reach,
                            .038*math.sin(heading)*reach, -.172*reach, wave])


def build_studio(subject, form, n, character=None):
    label, family = FORMS[form]
    primary, accent = palette(subject, family)
    mesh, actions = Mesh(), []
    relief_material = None
    forms = {"horned": horned, "slab": slab, "medallion": medallion, "plush": plush,
             "blue-bob": blue_bob}
    if form == IMAGE_FORM:
        build_character(mesh, actions, character, subject)
        family = character["stage"]
        primary, accent = ([round(channel) for channel in character[key]]
                           for key in ("mainColor", "accentColor"))
    elif form in GRAPHIC_FORMS:
        _, depth, _ = GRAPHIC_FORMS[form]
        relief_material = medallion(mesh, actions, primary, accent, subject, depth=depth,
                                   embers=False, require_alpha=form in ("image-logo", LAYER_SLIDE),
                                   tapered_wall=form == LAYER_SLIDE)
    elif form in forms:
        relief_material = forms[form](mesh, actions, primary, accent, subject)
    elif family == "canopy":
        canopy(mesh, actions, primary, accent, form == "botanical")
    elif family == "instrument":
        instrument(mesh, actions, primary, accent, form == "console")
    elif form == "tentacles":
        tentacle_avatar(mesh, actions, primary, accent)
    else:
        companion(mesh, actions, primary, accent, form == "antenna")
    model, pieces = sample_scene(mesh, n, [actions, None])
    if relief_material is not None:
        model.extend(relief_material)
    theme = mix(primary, [9, 15, 29], .92)
    highlight = mix(accent, [255, 241, 218], .54)
    behavior = {
        "form": form, "family": family,
        "background": [mix(mix(primary, accent, .31), theme, .54), theme], "spark": highlight,
    }
    composition = COMPOSITIONS[family]
    behavior["composition"] = {
        **composition, "hue": mix(composition["hue"], primary, .34 if family != "companion" else .14),
        "accent": mix(composition["hue"], accent, .47), "background": mix(theme, composition["hue"], .075),
    }
    if form in GRAPHIC_FORMS:
        _, _, camera = GRAPHIC_FORMS[form]
        theme = mix([244, 246, 250], primary, .075)
        behavior["composition"].update(environment="display", background=theme,
                                       pose=[0., 0.], frame=[.78, 0., -.040],
                                       camera=camera, grounding=[.45, .16])
        if form == LAYER_SLIDE:
            behavior["composition"].update(motion="layer-slide", pose=[.015, .025],
                                           frame=[.75, -.04, -.044])
    elif form == IMAGE_FORM and character.get("stance") == "grounded":
        theme = mix([244, 240, 234], primary, .07)
        behavior["composition"].update(environment="display", background=theme,
                                       camera=[.14, .035, 0., 7.6],
                                       grounding=[max(vertex[2] for vertex in model[0]), 0.])
    if family == "download" and behavior["composition"]["environment"] == "download":
        theme = [255, 237, 245]
        behavior["composition"]["background"] = theme
    pose = character.get("view", composition["pose"]) if form == IMAGE_FORM else behavior["composition"]["pose"]
    return model, pieces, behavior, label, theme, pose, highlight
