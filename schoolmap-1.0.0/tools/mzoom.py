"""Dev helper: crop rectified floor image by building-metre box and overlay a metre grid."""
import sys, cv2
PPM, M = 25, 2.0
def main(src, x0, y0, x1, y1, out, scale=None):
    img = cv2.imread(src)
    X0, Y0, X1, Y1 = [int(round((v + M) * PPM)) for v in (x0, y0, x1, y1)]
    X0, Y0 = max(X0, 0), max(Y0, 0)
    crop = img[Y0:Y1, X0:X1].copy()
    s = scale or min(1500 / crop.shape[1], 1500 / crop.shape[0])
    crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    import math
    for gx in range(math.ceil(x0), int(x1) + 1):
        X = int(((gx + M) * PPM - X0) * s)
        even = gx % 2 == 0
        cv2.line(crop, (X, 0), (X, crop.shape[0]), (0, 0, 255) if even else (255, 170, 0), 1)
        if even: cv2.putText(crop, str(gx), (X + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 220), 1)
    for gy in range(math.ceil(y0), int(y1) + 1):
        Y = int(((gy + M) * PPM - Y0) * s)
        even = gy % 2 == 0
        cv2.line(crop, (0, Y), (crop.shape[1], Y), (0, 0, 255) if even else (255, 170, 0), 1)
        if even: cv2.putText(crop, str(gy), (2, Y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 220), 1)
    cv2.imwrite(out, crop)
if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], *map(float, a[1:5]), a[5], *(float(v) for v in a[6:]))
