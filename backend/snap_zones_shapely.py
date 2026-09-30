import json
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import snap, unary_union
import shapely

def remove_holes(poly):
    if poly.is_empty or not hasattr(poly, 'interiors') or not poly.interiors:
        return poly
        
    from shapely.geometry import Point, LineString
    import shapely.ops
    
    current_poly = poly
    for interior in current_poly.interiors:
        pt_in = interior.coords[0]
        # Find nearest point on exterior
        nearest = shapely.ops.nearest_points(current_poly.exterior, Point(pt_in))[0]
        
        # Create a tiny slit (0.01m wide)
        line = LineString([pt_in, nearest.coords[0]])
        # cap_style=2 (flat), join_style=2 (mitre) to avoid rounded corners adding points
        slit = line.buffer(0.01, cap_style=2, join_style=2) 
        
        current_poly = current_poly.difference(slit)
        
        # difference might return MultiPolygon if the slit completely severs it
        if getattr(current_poly, 'geom_type', '') == 'MultiPolygon':
            current_poly = max(current_poly.geoms, key=lambda a: a.area)
            
    return current_poly

def heal_zones(zones_data, tolerance=0.5):
    if not zones_data: return []
    
    # 1. SNAP TO GRID & ORTHOGONALIZE
    polys = []
    for z in zones_data:
        coords = z['footprint']
        if len(coords) < 3: continue
        
        # Snap dense points to 0.5m grid
        snapped = [[round(x*2)/2, round(y*2)/2] for x, y in coords]
        
        p = Polygon(snapped)
        if not p.is_valid:
            p = p.buffer(0)
            
        if p.is_empty: continue
            
        # Heavy simplification to turn staircases into perfect orthogonal straight lines
        p = p.simplify(0.4, preserve_topology=True)
        
        polys.append({'name': z['name'], 'poly': p})
        
    if not polys: return zones_data
    
    # 2. DELETE INTERSECTIONS (Iterative Subtraction)
    # Sort from largest to smallest, so small zones don't overwrite big rooms
    polys.sort(key=lambda x: x['poly'].area, reverse=False)
    
    clean_polys = []
    for p_obj in polys:
        p = p_obj['poly']
        for c in clean_polys:
            if p.intersects(c):
                p = p.difference(c)
        if not p.is_empty:
            clean_polys.append(p)
        else:
            clean_polys.append(Polygon())
            
    for i in range(len(polys)):
        polys[i]['poly'] = clean_polys[i]
        
    # 3. FILL GAPS (Expand to cover internal empty spaces)
    all_union = unary_union([p['poly'] for p in polys if not p['poly'].is_empty])
    filled_union = all_union.buffer(1.5).buffer(-1.5)
    gaps = filled_union.difference(all_union)
    
    if not gaps.is_empty:
        gap_list = [gaps] if isinstance(gaps, Polygon) else list(gaps.geoms)
        for gap in gap_list:
            if gap.is_empty or gap.area < 0.1: continue
            best_idx = -1
            best_dist = float('inf')
            for i, p in enumerate(polys):
                if p['poly'].is_empty: continue
                d = p['poly'].distance(gap)
                if d < best_dist:
                    best_dist = d
                    best_idx = i
            if best_idx != -1:
                polys[best_idx]['poly'] = polys[best_idx]['poly'].union(gap)
                
    # 4. RE-EXTRACT COORDINATES
    res = []
    for p in polys:
        poly = p['poly']
        if poly.is_empty or poly.area < 2.0: continue  # Reject any zone smaller than 2 square meters
        
        if isinstance(poly, MultiPolygon):
            poly = max(poly.geoms, key=lambda a: a.area)
            
        # Remove any holes (e.g. bathroom inside a hallway) by cutting a slit
        poly = remove_holes(poly)
            
        # Final light simplification to clean up union artifacts
        poly = poly.simplify(0.05, preserve_topology=True)
        
        coords = list(poly.exterior.coords)
        fp = [[round(x, 2), round(y, 2)] for x, y in coords]
        if fp[0] == fp[-1]: fp = fp[:-1]
        
        res.append({
            'name': p['name'],
            'footprint': fp
        })
        
    return res
