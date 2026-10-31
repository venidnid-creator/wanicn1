"""500 m test road: straight 150 m, curve R=200 m (L=200 m, 57.3 deg), straight 150 m.
Sections every 25 m (+ TC/CT), shots across +-20 m, codes CL / EP / SH / N / DT."""
import math, sys
E0, N0, AZ0 = 701250.000, 1612480.000, math.radians(60.0)   # UTM 47N, bearing 60 deg from north
L1, R, LC, L2 = 150.0, 200.0, 200.0, 150.0
def point(s):
    """(E, N, azimuth) at chainage s along tangent-curve-tangent."""
    if s <= L1:
        return E0 + s*math.sin(AZ0), N0 + s*math.cos(AZ0), AZ0
    e1, n1 = E0 + L1*math.sin(AZ0), N0 + L1*math.cos(AZ0)
    if s <= L1 + LC:                                   # right-hand curve
        d = (s - L1) / R
        ce, cn = e1 + R*math.sin(AZ0 + math.pi/2), n1 + R*math.cos(AZ0 + math.pi/2)
        a = AZ0 - math.pi/2 + d
        return ce + R*math.sin(a), cn + R*math.cos(a), AZ0 + d
    e2, n2, az = point(L1 + LC)
    t = s - L1 - LC
    return e2 + t*math.sin(az), n2 + t*math.cos(az), az
def ground(s, o):
    """Rolling ground: a hill near 0+200 (cut), a valley near 0+400 (fill),
    a cross fall to the right and a natural ditch 15 m left."""
    z = 92.0 + 0.004*s
    z += 4.2*math.exp(-((s - 200.0)/70.0)**2)          # hill  -> cut
    z -= 3.6*math.exp(-((s - 410.0)/55.0)**2)          # valley -> fill
    z -= 0.035*o                                        # falls to the right
    z -= 0.8*math.exp(-((o + 15.0)/2.0)**2)            # ditch left
    z += 0.15*math.sin(s/17.0 + o/5.0)                  # roughness
    return z
offs = [(-20,'N'),(-17,'N'),(-15,'DT'),(-13,'N'),(-10,'N'),(-7,'N'),(-4,'SH'),(-3,'EP'),
        (-1.5,'N'),(0,'CL'),(1.5,'N'),(3,'EP'),(4,'SH'),(7,'N'),(10,'N'),(13,'N'),(16,'N'),(20,'N')]
stations = sorted(set([i*25.0 for i in range(21)] + [L1, L1 + LC]))
rows = ["P,N,E,Z,D"]
num = 1
for s in stations:
    e, n, az = point(s)
    for o, code in offs:                                # +o = right of the direction of travel
        pe, pn = e + o*math.cos(az), n - o*math.sin(az)
        rows.append(f"{num},{pn:.3f},{pe:.3f},{ground(s, o):.3f},{code}")
        num += 1
open(sys.argv[1], "w", encoding="utf-8-sig").write("\n".join(rows) + "\n")
print(num - 1, "points,", len(stations), "sections")
