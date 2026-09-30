import plotly.graph_objects as go
import numpy as np
import os
import matplotlib.colors as mcolors


def point_to_segment_dist(px, py, ax, ay, bx, by):
    l2 = (bx - ax)**2 + (by - ay)**2
    if l2 == 0: return ((px - ax)**2 + (py - ay)**2)**0.5
    t = max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2))
    proj_x = ax + t * (bx - ax)
    proj_y = ay + t * (by - ay)
    return ((px - proj_x)**2 + (py - proj_y)**2)**0.5

def generate_schematic(floors_data, wwr, roof_shape, output_path, h=3.5, zone_energy=None):
    if zone_energy is None:
        zone_energy = {}
        
    fig = go.Figure()

    # Determine color scale mapping
    energies = list(zone_energy.values())
    min_e = min(energies) if energies else 0
    max_e = max(energies) if energies else 100
    if max_e == min_e:
        max_e = min_e + 1

    def get_color(energy):
        # Normalize between 0 and 1
        norm = (energy - min_e) / (max_e - min_e)
        # Blue (low) to Red (high)
        cmap = mcolors.LinearSegmentedColormap.from_list("", ["blue", "cyan", "yellow", "red"])
        r, g, b, _ = cmap(norm)
        return f'rgb({int(r*255)}, {int(g*255)}, {int(b*255)})'

    all_xs = []
    all_ys = []
    all_zs = []

    for floor_idx, floor_info in enumerate(floors_data):
        z0 = floor_idx * h
        z1 = (floor_idx + 1) * h
        zones = floor_info.get('zones', [])
        
        for zone in zones:
            name = f"Floor_{floor_idx}_{zone['name']}"
            is_balcony = 'balcony' in zone['name'].lower()
            
            name_upper = name.upper()
            energy = min_e
            for k, v in zone_energy.items():
                if name_upper in k:
                    energy = v
                    break
            color = get_color(energy) if not is_balcony else 'rgba(150, 150, 150, 0.8)'
            
            footprint = zone['footprint']
            if footprint[0] != footprint[-1]:
                footprint = footprint + [footprint[0]]
                
            xs = [p[0] for p in footprint]
            ys = [p[1] for p in footprint]
            all_xs.extend(xs)
            all_ys.extend(ys)
            all_zs.extend([z0, z1])
            
            # Draw Floor
            fig.add_trace(go.Scatter3d(
                x=xs, y=ys, z=[z0]*len(xs),
                mode='lines', surfaceaxis=2, surfacecolor=color,
                line=dict(color=color, width=4),
                name=name, hoverinfo='name', opacity=0.8
            ))
            
            if not is_balcony:
                # Draw Ceiling
                fig.add_trace(go.Scatter3d(
                    x=xs, y=ys, z=[z1]*len(xs),
                    mode='lines', surfaceaxis=2, surfacecolor=color,
                    line=dict(color=color, width=4),
                    hoverinfo='skip', showlegend=False, opacity=0.8
                ))
            
            # Draw Walls
            for j in range(len(footprint) - 1):
                p1 = footprint[j]
                p2 = footprint[j+1]
                
                if is_balcony:
                    # Draw a railing (1m high) instead of a full wall
                    wx = [p1[0], p2[0], p2[0], p1[0]]
                    wy = [p1[1], p2[1], p2[1], p1[1]]
                    wz = [z0, z0, z0 + 1.0, z0 + 1.0]
                    fig.add_trace(go.Mesh3d(
                        x=wx, y=wy, z=wz,
                        i=[0, 0], j=[1, 2], k=[2, 3],
                        opacity=0.6, color='gray',
                        hoverinfo='skip'
                    ))
                    continue

                
                wx = [p1[0], p2[0], p2[0], p1[0]]
                wy = [p1[1], p2[1], p2[1], p1[1]]
                wz = [z0, z0, z1, z1]
                
                # Two triangles: (0,1,2) and (0,2,3)
                i = [0, 0]
                j_idx = [1, 2]
                k = [2, 3]
                
                # Check if shared edge
                is_shared = False
                mid_pt = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2)
                for other_zone in zones:
                    if other_zone == zone: continue
                    other_fp = other_zone['footprint']
                    if other_fp[0] != other_fp[-1]:
                        other_fp = other_fp + [other_fp[0]]
                    for k_edge in range(len(other_fp)-1):
                        op1, op2 = other_fp[k_edge], other_fp[k_edge+1]
                        
                        # Check 3 points along the segment to handle T-junctions
                        pts_to_check = [
                            (p1[0]*0.25 + p2[0]*0.75, p1[1]*0.25 + p2[1]*0.75),
                            (p1[0]*0.5 + p2[0]*0.5, p1[1]*0.5 + p2[1]*0.5),
                            (p1[0]*0.75 + p2[0]*0.25, p1[1]*0.75 + p2[1]*0.25)
                        ]
                        
                        for cx, cy in pts_to_check:
                            dist = point_to_segment_dist(cx, cy, op1[0], op1[1], op2[0], op2[1])
                            if dist < 0.45:
                                is_shared = True
                                break
                        if is_shared: break
                    if is_shared: break
                
                if not is_shared:
                    # Exterior wall
                    fig.add_trace(go.Mesh3d(
                        x=wx, y=wy, z=wz,
                        i=i, j=j_idx, k=k,
                        opacity=0.4, color='rgb(230,230,225)',
                        hoverinfo='skip'
                    ))
                    
                    # Window
                    if wwr > 0:
                        dx = p2[0] - p1[0]
                        dy = p2[1] - p1[1]
                        L = (dx**2 + dy**2)**0.5
                        if L > 0.5:
                            margin_factor = (1.0 - wwr) / 2
                            win_p1_x = p1[0] + dx * margin_factor
                            win_p1_y = p1[1] + dy * margin_factor
                            win_p2_x = p2[0] - dx * margin_factor
                            win_p2_y = p2[1] - dy * margin_factor
                            win_z0 = z0 + h * margin_factor
                            win_z1 = z1 - h * margin_factor
                            
                            fig.add_trace(go.Mesh3d(
                                x=[win_p1_x, win_p2_x, win_p2_x, win_p1_x],
                                y=[win_p1_y, win_p2_y, win_p2_y, win_p1_y],
                                z=[win_z0, win_z0, win_z1, win_z1],
                                i=i, j=j_idx, k=k,
                                opacity=0.6, color='rgba(135,206,235, 0.6)',
                                hoverinfo='skip'
                            ))
                else:
                    # Interior wall
                    fig.add_trace(go.Mesh3d(
                        x=wx, y=wy, z=wz,
                        i=i, j=j_idx, k=k,
                        opacity=0.1, color='rgb(230,230,225)',
                        hoverinfo='skip'
                    ))

    floors = len(floors_data)
    top_z = floors * h
    
    if all_xs and all_ys and roof_shape in ['Gable', 'Hip']:
        top_floor = floors_data[-1]
        
        # Calculate GLOBAL center of the entire building for ONE single roof peak
        all_top_x = []
        all_top_y = []
        for zone in top_floor.get('zones', []):
            for pt in zone['footprint']:
                all_top_x.append(pt[0])
                all_top_y.append(pt[1])
                
        if all_top_x and all_top_y:
            global_mid_x = (min(all_top_x) + max(all_top_x)) / 2
            global_mid_y = (min(all_top_y) + max(all_top_y)) / 2
            
            # Use Shapely to get the absolute outer boundary of the entire floor
            try:
                from shapely.geometry import Polygon
                from shapely.ops import unary_union
                
                polys = []
                for zone in top_floor.get('zones', []):
                    coords = zone['footprint']
                    if len(coords) >= 3:
                        p = Polygon(coords)
                        if not p.is_valid: p = p.buffer(0)
                        polys.append(p)
                
                if polys:
                    unified = unary_union(polys)
                    
                    # unified could be a Polygon or MultiPolygon
                    geoms = [unified] if isinstance(unified, Polygon) else unified.geoms
                    
                    for geom in geoms:
                        # Draw roof over the exterior ring of each distinct building block
                        ext_coords = list(geom.exterior.coords)
                        if ext_coords[0] != ext_coords[-1]:
                            ext_coords.append(ext_coords[0])
                            
                        # Centroid of this specific building block for a nicer local roof peak
                        local_mid_x = geom.centroid.x
                        local_mid_y = geom.centroid.y
                        
                        for i in range(len(ext_coords)-1):
                            p1 = ext_coords[i]
                            p2 = ext_coords[i+1]
                            
                            rx = [p1[0], p2[0], local_mid_x, p1[0]]
                            ry = [p1[1], p2[1], local_mid_y, p1[1]]
                            rz = [top_z, top_z, top_z + 2.5, top_z]
                            
                            fig.add_trace(go.Scatter3d(
                                x=rx, y=ry, z=rz,
                                mode='lines',
                                surfaceaxis=2, 
                                surfacecolor='rgb(120,60,50)', 
                                line=dict(color='rgb(70,35,30)', width=2),
                                opacity=0.95,
                                name='Roof',
                                hoverinfo='skip'
                            ))
            except Exception as e:
                print("Roof union failed:", e)

    # Make background transparent and dark mode friendly
    fig.update_layout(
        scene=dict(
            xaxis=dict(showbackground=False, color='white', gridcolor='rgba(255,255,255,0.2)'),
            yaxis=dict(showbackground=False, color='white', gridcolor='rgba(255,255,255,0.2)'),
            zaxis=dict(showbackground=False, color='white', gridcolor='rgba(255,255,255,0.2)'),
            aspectmode='data'
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, b=0, t=0),
        showlegend=False
    )
    
    if output_path.endswith('.html'):
        fig.write_html(output_path)
    else:
        # Fallback to html anyway since frontend expects iframe now
        html_path = output_path.replace('.png', '.html')
        fig.write_html(html_path)
