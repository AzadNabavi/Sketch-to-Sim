import cv2
import numpy as np
import json

def extract_geometries(image_path: str, colored_out_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read {image_path}")
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    k_merge = max(3, int(w * 8 / 2700))
    k_open = max(3, int(w * 15 / 2700))
    k_close_small = max(3, int(w * 15 / 2700))
    k_close_large = max(15, int(w * 150 / 2700))
    
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    kernel_merge = cv2.getStructuringElement(cv2.MORPH_RECT, (k_merge, k_merge))
    binary_merged = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_merge, iterations=2)

    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (k_open, k_open))
    pure_walls = cv2.morphologyEx(binary_merged, cv2.MORPH_OPEN, kernel_open)

    kernel_close1 = cv2.getStructuringElement(cv2.MORPH_RECT, (k_close_small, k_close_small))
    binary_closed1 = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close1, iterations=3)
    house_contours, _ = cv2.findContours(binary_closed1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    house_cnt = None
    if house_contours:
        house_cnt = max(house_contours, key=cv2.contourArea)
        # We don't want to distort the exterior, just use it
        exterior_shell = np.zeros_like(binary)
        cv2.drawContours(exterior_shell, [house_cnt], -1, 255, max(5, int(w * 20 / 2700)))
        pure_walls = cv2.bitwise_or(pure_walls, exterior_shell)

    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (k_close_large, k_close_large))
    closed_walls = cv2.morphologyEx(pure_walls, cv2.MORPH_CLOSE, kernel_close)

    rooms = cv2.bitwise_not(closed_walls)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(rooms, connectivity=4)
    
    markers = np.zeros_like(gray, dtype=np.int32)
    
    valid_idx = 1
    valid_labels = {}
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        area_min = (w * h) * 0.005
        area_max = (w * h) * 0.9
        if area < area_min or area > area_max: 
            continue
            
        mask = (labels == i).astype(np.uint8) * 255
        edge_thickness = max(2, int(w * 15 / 2700))
        if cv2.countNonZero(mask[0:edge_thickness, :]) > 0 or cv2.countNonZero(mask[h-edge_thickness:h, :]) > 0 or \
           cv2.countNonZero(mask[:, 0:edge_thickness]) > 0 or cv2.countNonZero(mask[:, w-edge_thickness:w]) > 0:
            continue
            
        markers[labels == i] = valid_idx
        valid_labels[valid_idx] = i
        valid_idx += 1

    exterior_mask = np.ones_like(gray, dtype=np.uint8) * 255
    if house_cnt is not None:
        cv2.drawContours(exterior_mask, [house_cnt], -1, 0, -1)
    markers[exterior_mask == 255] = valid_idx 
    
    # Use ORIGINAL GRAYSCALE for watershed so it perfectly follows the original wall lines!
    img_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    cv2.watershed(img_bgr, markers)
    
    zones = []
    out_img = img.copy()
    
    final_idx = 0
    for v_idx in valid_labels.keys():
        room_mask = (markers == v_idx).astype(np.uint8) * 255
        contours, _ = cv2.findContours(room_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        cnt = max(contours, key=cv2.contourArea)
        
        # DRASTICALLY INCREASE EPSILON so the AI boundaries become clean lines instead of jagged noise
        epsilon = max(3.0, w * 5.0 / 2700.0) 
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        
        color = np.random.randint(0, 255, (3,)).tolist()
        cv2.fillPoly(out_img, [approx], color)
        
        coords = approx.squeeze(1).tolist()
        if not isinstance(coords[0], list):
            coords = [coords]
            
        zones.append({
            "label": f"Zone_{final_idx}",
            "dl_name": "Room",
            "coordinates": coords,
            "area_px": round(float(cv2.contourArea(approx)), 1)
        })
        final_idx += 1
        
    cv2.imwrite(colored_out_path, out_img)
    return zones

def vectorize_floorplan(image_path: str, json_out: str = "output_zones.json", viz_out: str = "output_vectors.jpg"):
    zones = extract_geometries(image_path, viz_out)
    with open(json_out, "w") as f:
        json.dump(zones, f, indent=2)
    return zones
