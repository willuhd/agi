"""Dev helper: crop a region of an image, upscale, and overlay a labelled pixel grid."""
import sys, cv2
def main(src, x0, y0, x1, y1, out, step=None, scale=None):
    img = cv2.imread(src)
    x0, y0, x1, y1 = map(int, (x0, y0, x1, y1))
    crop = img[y0:y1, x0:x1].copy()
    w, h = x1 - x0, y1 - y0
    scale = scale or max(1.0, min(1400 / w, 1400 / h))
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    step = int(step) if step else None
    step = step or (10 if max(w, h) <= 200 else 25 if max(w, h) <= 500 else 50)
    for gx in range((x0 // step + 1) * step, x1, step):
        X = int((gx - x0) * scale)
        major = gx % (step * 2) == 0
        cv2.line(crop, (X, 0), (X, crop.shape[0]), (0, 0, 255) if major else (255, 160, 0), 1)
        if major: cv2.putText(crop, str(gx), (X + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    for gy in range((y0 // step + 1) * step, y1, step):
        Y = int((gy - y0) * scale)
        major = gy % (step * 2) == 0
        cv2.line(crop, (0, Y), (crop.shape[1], Y), (0, 0, 255) if major else (255, 160, 0), 1)
        if major: cv2.putText(crop, str(gy), (2, Y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    cv2.imwrite(out, crop)
if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], *a[1:5], a[5], *(float(v) for v in a[6:]))
