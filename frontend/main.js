let floorsData = [{ id: 'floor_0', name: 'Floor 0', imageSrc: null, zones: [] }];
let activeFloorIndex = 0;
let activeTool = 'select';

// Tool states
let drawPoints = [];
let combineSelection = [];
let splitStartPoint = null;
let currentMousePos = null;
let dragNode = null;

const METER_SCALE = 20; // Assume image width = 20 meters

const canvas = document.getElementById('cad-canvas');
const ctx = canvas.getContext('2d');
let bgImage = new Image();

// --- UI Binding ---
document.querySelectorAll('.tool-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        if (e.target.id === 'auto-snap-btn') {
            autoSnap();
            return;
        }
        document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        activeTool = e.target.dataset.tool;
        
        // Reset states
        drawPoints = [];
        combineSelection = [];
        splitStartPoint = null;
        dragNode = null;
        
        const hints = {
            'select': 'Drag vertices to adjust zone boundaries.',
            'draw': 'Click to add points. Double-click to finish drawing the zone.',
            'delete': 'Click inside a zone to delete it.',
            'combine': 'Click two touching zones to merge them into one.',
            'split': 'Click outside the zone, drag across, and click outside the other side to slice it.'
        };
        document.getElementById('tool-hint').innerText = hints[activeTool] || '';
        drawCanvas();
    });
});

function renderTabs() {
    const tabsContainer = document.getElementById('floor-tabs');
    tabsContainer.innerHTML = '';
    floorsData.forEach((floor, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'tab-btn' + (idx === activeFloorIndex ? ' active' : '');
        btn.innerText = floor.name;
        btn.onclick = () => {
            activeFloorIndex = idx;
            renderTabs();
            loadFloorToCanvas();
        };
        tabsContainer.appendChild(btn);
    });
    document.getElementById('active-floor-label').innerText = floorsData[activeFloorIndex].name;
}

document.getElementById('add-floor-btn').addEventListener('click', () => {
    const idx = floorsData.length;
    floorsData.push({ id: 'floor_' + idx, name: 'Floor ' + idx, imageSrc: null, zones: [] });
    activeFloorIndex = idx;
    renderTabs();
    loadFloorToCanvas();
});

document.getElementById('remove-floor-btn').addEventListener('click', () => {
    if (floorsData.length > 1) {
        floorsData.splice(activeFloorIndex, 1);
        activeFloorIndex = Math.max(0, activeFloorIndex - 1);
        renderTabs();
        loadFloorToCanvas();
    } else {
        alert("Cannot remove the last floor.");
    }
});

function loadFloorToCanvas() {
    const floor = floorsData[activeFloorIndex];
    if (floor.imageSrc) {
        bgImage.src = floor.imageSrc;
        bgImage.onload = () => drawCanvas();
    } else {
        bgImage.src = '';
        drawCanvas();
    }
}

// Convert meters to pixels
function m2p(x, y) {
    const scale = canvas.width / METER_SCALE;
    return { x: x * scale, y: y * scale };
}

// Convert pixels to meters
function p2m(x, y, snap=false) {
    const scale = canvas.width / METER_SCALE;
    let mx = x / scale;
    let my = y / scale;
    
    // Snap to 0.5m grid if enabled
    const snapCb = document.getElementById('snap-grid-cb');
    if (snap && snapCb && snapCb.checked) {
        mx = Math.round(mx * 2) / 2;
        my = Math.round(my * 2) / 2;
    }
    
    return { x: mx, y: my };
}

// Ensure polygon is closed for Turf
function closePolygon(coords) {
    let c = [...coords];
    if (c.length > 0 && (c[0][0] !== c[c.length-1][0] || c[0][1] !== c[c.length-1][1])) {
        c.push([...c[0]]);
    }
    return c;
}

// Turf Point in Polygon check
function isPointInZone(meterPt, zone) {
    if (zone.footprint.length < 3) return false;
    const pt = turf.point([meterPt.x, meterPt.y]);
    try {
        const poly = turf.polygon([closePolygon(zone.footprint)]);
        return turf.booleanPointInPolygon(pt, poly);
    } catch(e) { return false; }
}

function drawCanvas() {
    const parent = canvas.parentElement;
    
    let drawHeight = 300;
    if (bgImage.src && bgImage.width > 0) {
        const imgRatio = bgImage.height / bgImage.width;
        drawHeight = parent.clientWidth * imgRatio;
    }
    
    parent.style.height = drawHeight + 'px';
    canvas.width = parent.clientWidth;
    canvas.height = drawHeight;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (bgImage.src && bgImage.width > 0) {
        ctx.globalAlpha = 0.5;
        ctx.drawImage(bgImage, 0, 0, canvas.width, canvas.height);
        ctx.globalAlpha = 1.0;
    }
    
    // Draw grid if enabled
    const snapCb = document.getElementById('snap-grid-cb');
    if (snapCb && snapCb.checked) {
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        ctx.lineWidth = 1;
        const scale = canvas.width / METER_SCALE;
        // Draw vertical lines every 0.5m
        for (let x = 0; x <= METER_SCALE; x += 0.5) {
            ctx.moveTo(x * scale, 0);
            ctx.lineTo(x * scale, canvas.height);
        }
        // Draw horizontal lines every 0.5m
        const maxMetersY = canvas.height / scale;
        for (let y = 0; y <= maxMetersY; y += 0.5) {
            ctx.moveTo(0, y * scale);
            ctx.lineTo(canvas.width, y * scale);
        }
        ctx.stroke();
    }
    
    const floor = floorsData[activeFloorIndex];
    
    // Draw existing zones
    floor.zones.forEach((zone, zIdx) => {
        ctx.beginPath();
        zone.footprint.forEach((pt, pIdx) => {
            const p = m2p(pt[0], pt[1]);
            if (pIdx === 0) ctx.moveTo(p.x, p.y);
            else ctx.lineTo(p.x, p.y);
        });
        ctx.closePath();
        
        const isSelected = combineSelection.includes(zIdx);
        ctx.fillStyle = isSelected ? 'rgba(255, 165, 0, 0.4)' : 'rgba(0, 255, 136, 0.3)';
        ctx.fill();
        ctx.strokeStyle = isSelected ? '#ffa500' : '#00ff88';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        // Draw nodes only in select mode
        if (activeTool === 'select') {
            zone.footprint.forEach((pt, pIdx) => {
                const p = m2p(pt[0], pt[1]);
                ctx.beginPath();
                ctx.arc(p.x, p.y, 6, 0, 2*Math.PI);
                ctx.fillStyle = (dragNode && dragNode.zoneIdx === zIdx && dragNode.pointIdx === pIdx) ? 'red' : 'white';
                ctx.fill();
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 1;
                ctx.stroke();
            });
        }
        
        // Draw text
        if (zone.footprint.length > 0) {
            let cx = 0, cy = 0;
            zone.footprint.forEach(pt => { cx += pt[0]; cy += pt[1]; });
            cx /= zone.footprint.length;
            cy /= zone.footprint.length;
            const center = m2p(cx, cy);
            
            ctx.fillStyle = 'white';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(zone.name, center.x, center.y);
        }
    });
    
    // Draw in-progress line/points
    if (activeTool === 'draw' && drawPoints.length > 0) {
        ctx.beginPath();
        drawPoints.forEach((pt, i) => {
            const p = m2p(pt[0], pt[1]);
            if (i === 0) ctx.moveTo(p.x, p.y);
            else ctx.lineTo(p.x, p.y);
        });
        if (currentMousePos) {
            ctx.lineTo(currentMousePos.x, currentMousePos.y);
        }
        ctx.strokeStyle = 'yellow';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        drawPoints.forEach(pt => {
            const p = m2p(pt[0], pt[1]);
            ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, 2*Math.PI); ctx.fillStyle = 'yellow'; ctx.fill();
        });
    }
    
    if (activeTool === 'split' && splitStartPoint && currentMousePos) {
        const p1 = m2p(splitStartPoint[0], splitStartPoint[1]);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(currentMousePos.x, currentMousePos.y);
        ctx.strokeStyle = 'red';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.stroke();
        ctx.setLineDash([]);
    }
}

// --- Interaction Logic ---

canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const meterPt = p2m(mx, my, true);
    const floor = floorsData[activeFloorIndex];

    if (activeTool === 'select') {
        // Find nearest vertex to drag
        let found = false;
        for (let z = 0; z < floor.zones.length; z++) {
            for (let p = 0; p < floor.zones[z].footprint.length; p++) {
                const pt = floor.zones[z].footprint[p];
                const px = m2p(pt[0], pt[1]);
                if (Math.hypot(mx - px.x, my - px.y) < 10) {
                    dragNode = { zoneIdx: z, pointIdx: p };
                    found = true;
                    break;
                }
            }
            if (found) break;
        }
    } 
    else if (activeTool === 'delete') {
        for (let z = floor.zones.length - 1; z >= 0; z--) {
            if (isPointInZone(meterPt, floor.zones[z])) {
                floor.zones.splice(z, 1);
                break;
            }
        }
    }
    else if (activeTool === 'combine') {
        for (let z = floor.zones.length - 1; z >= 0; z--) {
            if (isPointInZone(meterPt, floor.zones[z])) {
                if (combineSelection.includes(z)) {
                    combineSelection = combineSelection.filter(idx => idx !== z);
                } else {
                    combineSelection.push(z);
                }
                break;
            }
        }
        
        if (combineSelection.length === 2) {
            // Attempt Union
            try {
                const z1 = floor.zones[combineSelection[0]];
                const z2 = floor.zones[combineSelection[1]];
                const p1 = turf.polygon([closePolygon(z1.footprint)]);
                const p2 = turf.polygon([closePolygon(z2.footprint)]);
                const union = turf.union(p1, p2);
                
                if (union && union.geometry.type === 'Polygon') {
                    // Success
                    const newFootprint = union.geometry.coordinates[0];
                    if (newFootprint.length > 0 && newFootprint[0][0] === newFootprint[newFootprint.length-1][0]) {
                        newFootprint.pop(); // Remove dup last point for our struct
                    }
                    
                    const newZone = { name: z1.name + '+' + z2.name, footprint: newFootprint };
                    
                    // Remove both, add new
                    const indices = combineSelection.sort((a,b) => b-a);
                    floor.zones.splice(indices[0], 1);
                    floor.zones.splice(indices[1], 1);
                    floor.zones.push(newZone);
                } else {
                    alert("Cannot combine zones (they might not overlap or union failed).");
                }
            } catch (err) {
                console.error(err);
                alert("Error combining zones.");
            }
            combineSelection = [];
        }
    }
    else if (activeTool === 'split') {
        splitStartPoint = [meterPt.x, meterPt.y];
    }
    
    drawCanvas();
});

canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    currentMousePos = {x: mx, y: my};
    
    if (activeTool === 'select' && dragNode) {
        const meterPt = p2m(mx, my, true);
        const floor = floorsData[activeFloorIndex];
        floor.zones[dragNode.zoneIdx].footprint[dragNode.pointIdx] = [meterPt.x, meterPt.y];
    }
    
    drawCanvas();
});

canvas.addEventListener('mouseup', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const meterPt = p2m(mx, my, true);
    const floor = floorsData[activeFloorIndex];

    if (activeTool === 'select') {
        dragNode = null;
    }
    else if (activeTool === 'draw') {
        // Add point
        drawPoints.push([meterPt.x, meterPt.y]);
    }
    else if (activeTool === 'split' && splitStartPoint) {
        const splitEndPoint = [meterPt.x, meterPt.y];
        
        // Find which polygon we intersected
        let targetZoneIdx = -1;
        const line = turf.lineString([splitStartPoint, splitEndPoint]);
        
        for (let z = 0; z < floor.zones.length; z++) {
            try {
                const poly = turf.polygon([closePolygon(floor.zones[z].footprint)]);
                // Check if line intersects
                if (turf.booleanIntersects(line, poly)) {
                    targetZoneIdx = z;
                    break;
                }
            } catch(err) {}
        }
        
        if (targetZoneIdx !== -1) {
            try {
                const targetPoly = turf.polygon([closePolygon(floor.zones[targetZoneIdx].footprint)]);
                const splitBox = turf.bboxPolygon(turf.bbox(line));
                
                // turf.lineSplit creates a feature collection of polygons if it works, or we can use an alternative:
                // Turf's lineSplit splits lines, not polygons perfectly. 
                // A better approach for polygon slicing is tricky. We'll use a thick line to difference.
                const thickLine = turf.buffer(line, 0.05, {units: 'meters'});
                const diff = turf.difference(targetPoly, thickLine);
                
                if (diff) {
                    if (diff.geometry.type === 'MultiPolygon') {
                        // Split successful!
                        const oldName = floor.zones[targetZoneIdx].name;
                        floor.zones.splice(targetZoneIdx, 1);
                        
                        diff.geometry.coordinates.forEach((polyCoords, i) => {
                            let fp = polyCoords[0];
                            if (fp[0][0] === fp[fp.length-1][0]) fp.pop();
                            floor.zones.push({ name: `${oldName}_${i+1}`, footprint: fp });
                        });
                    } else {
                        alert("Split did not fully cut across the zone.");
                    }
                }
            } catch (err) {
                console.error(err);
                alert("Splitting error.");
            }
        }
        
        splitStartPoint = null;
    }
    drawCanvas();
});

// Double click to close drawing
canvas.addEventListener('dblclick', () => {
    if (activeTool === 'draw' && drawPoints.length > 2) {
        // Remove the last point because dblclick triggers two mouseups
        drawPoints.pop();
        
        const floor = floorsData[activeFloorIndex];
        floor.zones.push({
            name: 'Zone ' + (floor.zones.length + 1),
            footprint: [...drawPoints]
        });
        drawPoints = [];
        drawCanvas();
    }
});

canvas.addEventListener('mouseleave', () => { 
    dragNode = null; 
    currentMousePos = null;
    drawCanvas(); 
});

function autoSnap() {
    const floor = floorsData[activeFloorIndex];
    let allPoints = [];
    floor.zones.forEach((z, zIdx) => {
        z.footprint.forEach((pt, pIdx) => {
            allPoints.push({zIdx, pIdx, pt});
        });
    });
    
    const threshold = 0.5; // 0.5 meters
    let snaps = 0;
    
    for(let i=0; i<allPoints.length; i++) {
        for(let j=i+1; j<allPoints.length; j++) {
            let p1 = allPoints[i].pt;
            let p2 = allPoints[j].pt;
            // Don't snap within the same zone if adjacent
            if (allPoints[i].zIdx === allPoints[j].zIdx) continue;
            
            let d = Math.hypot(p1[0]-p2[0], p1[1]-p2[1]);
            if(d > 0 && d < threshold) {
                floor.zones[allPoints[j].zIdx].footprint[allPoints[j].pIdx] = [p1[0], p1[1]];
                allPoints[j].pt = [p1[0], p1[1]]; // Update reference for future iterations
                snaps++;
            }
        }
    }
    drawCanvas();
    if (snaps > 0) alert(`AI Supervisor: Snapped ${snaps} vertices to perfectly align adjacent walls!`);
    else alert("AI Supervisor: All zones look properly aligned.");
}

// Handle Image Upload
document.getElementById('floor-plan-upload').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const url = URL.createObjectURL(file);
        floorsData[activeFloorIndex].imageSrc = url;
        loadFloorToCanvas();
    }
});

// ── Helpers for step status display ─────────────────────────────────────────
function setStep(stepEl, state) {
    // state: 'pending' | 'active' | 'done' | 'error'
    const icons = { pending: '⏸', active: '⏳', done: '✅', error: '❌' };
    const colors = { pending: '#666', active: '#aaa', done: '#00ff88', error: '#ff5555' };
    stepEl.style.color = colors[state];
    const text = stepEl.innerText.replace(/^[⏸⏳✅❌]\s*/, '');
    stepEl.innerText = (icons[state] || '⏸') + ' ' + text;
}

// AI Extract Button
document.getElementById('extract-geom-btn').addEventListener('click', async () => {
    const fileInput = document.getElementById('floor-plan-upload');
    if (!fileInput.files[0]) return alert("Please upload a floor plan first.");
    
    const btn        = document.getElementById('extract-geom-btn');
    const spinner    = document.getElementById('extract-spinner');
    const statusBox  = document.getElementById('extract-status');
    const previewBox = document.getElementById('extract-preview');
    const step1El    = document.getElementById('extract-step-1');
    const step2El    = document.getElementById('extract-step-2');
    const step3El    = document.getElementById('extract-step-3');

    btn.disabled = true;
    spinner.style.display = 'inline-block';

    // Reset status panel
    statusBox.style.display = 'block';
    previewBox.style.display = 'none';
    setStep(step1El, 'active');
    setStep(step2El, 'pending');
    setStep(step3El, 'pending');

    const formData = new FormData();
    formData.append('floor_plan', fileInput.files[0]);
    
    try {
        // The entire pipeline (SegFormer → OpenCV → Gemini) runs server-side in one call.
        // We update the step indicators at key UI moments.
        setTimeout(() => setStep(step2El, 'active'), 1200);  // OpenCV follows segmentation
        setTimeout(() => setStep(step3El, 'active'), 2500);  // Gemini naming is last

        const response = await fetch('/api/extract_floor_geometry', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || "Server error");
        }
        
        const data = await response.json();

        // Mark all steps done
        setStep(step1El, 'done');
        setStep(step2El, 'done');
        setStep(step3El, 'done');

        // Show two-panel image preview
        if (data.colored_plan_url || data.vector_plan_url) {
            document.getElementById('colored-plan-preview').src = data.colored_plan_url || '';
            document.getElementById('vector-plan-preview').src  = data.vector_plan_url  || '';
            previewBox.style.display = 'block';
        }

        // Load zones and switch canvas background to the vector overlay
        floorsData[activeFloorIndex].zones = data.zones || [];
        if (data.vector_plan_url) {
            floorsData[activeFloorIndex].imageSrc = data.vector_plan_url;
        }
        loadFloorToCanvas();
        
    } catch(err) {
        setStep(step1El, 'error');
        setStep(step2El, 'error');
        setStep(step3El, 'error');
        alert("Extraction Error: " + err.message);
    } finally {
        btn.disabled = false;
        spinner.style.display = 'none';
    }
});

// Run Final Simulation
document.getElementById('simulation-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    formData.append('floors_data_str', JSON.stringify(floorsData));
    
    const submitBtn = document.getElementById('simulate-btn');
    const btnSpinner = document.getElementById('btn-spinner');
    const welcomeState = document.getElementById('welcome-state');
    const loadingState = document.getElementById('loading-state');
    const resultsState = document.getElementById('results-state');
    
    submitBtn.disabled = true;
    btnSpinner.style.display = 'block';
    
    welcomeState.classList.add('hidden');
    resultsState.classList.add('hidden');
    loadingState.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/simulate', {
            method: 'POST',
            body: formData
        });
        
        let data;
        if (!response.ok) {
            try {
                data = await response.json();
                throw new Error(data.error || `Server error: ${response.statusText}`);
            } catch(ex) {
                throw new Error(`Server error: ${response.statusText}`);
            }
        } else {
            data = await response.json();
        }
        
        document.getElementById('error-banner').classList.add('hidden');
        
        const categoryBadge = document.getElementById('building-category');
        categoryBadge.innerText = data.category;
        categoryBadge.classList.remove('hidden');
        
        const getClassColor = (c) => c === 'A+' ? 'class-A-plus' : 'class-' + c;

        document.getElementById('badge-baseline').innerText = `Class ${data.baseline_class}`;
        document.getElementById('badge-baseline').className = `energy-class-badge ${getClassColor(data.baseline_class)}`;
        document.getElementById('kpi-baseline-demand').innerText = `${data.baseline_demand.toLocaleString('en-US', {maximumFractionDigits:0})} kWh/yr`;
        document.getElementById('kpi-baseline-spec').innerText = `${data.baseline_spec_demand.toFixed(1)} kWh/(m²·a)`;

        document.getElementById('badge-renovated').innerText = `Class ${data.renovated_class}`;
        document.getElementById('badge-renovated').className = `energy-class-badge ${getClassColor(data.renovated_class)}`;
        document.getElementById('kpi-renovated-demand').innerText = `${data.demand.toLocaleString('en-US', {maximumFractionDigits:0})} kWh/yr`;
        document.getElementById('kpi-renovated-spec').innerText = `${data.renovated_spec_demand.toFixed(1)} kWh/(m²·a)`;

        document.getElementById('kpi-cost').innerText = `€ ${data.cost.toLocaleString('en-US', {maximumFractionDigits:2})}`;
        document.getElementById('kpi-savings').innerText = `€ ${data.savings_eur.toLocaleString('en-US', {maximumFractionDigits:2})}`;
        document.getElementById('kpi-co2').innerText = `${data.co2_saved.toLocaleString('en-US', {maximumFractionDigits:0})} kg`;
        
        document.getElementById('schematic-img').src = data.schematic_url + '?t=' + new Date().getTime();
        
        loadingState.classList.add('hidden');
        resultsState.classList.remove('hidden');
        
    } catch (err) {
        document.getElementById('error-message-text').innerText = err.message;
        document.getElementById('error-banner').classList.remove('hidden');
        loadingState.classList.add('hidden');
        resultsState.classList.remove('hidden');
    } finally {
        submitBtn.disabled = false;
        btnSpinner.style.display = 'none';
    }
});

window.addEventListener('resize', drawCanvas);
renderTabs();



// Auto-Snap functionality
document.getElementById('auto-snap-btn').addEventListener('click', async () => {
    const btn = document.getElementById('auto-snap-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = 'Snapping...';
    btn.disabled = true;
    
    try {
        const formData = new FormData();
        formData.append('floors_data_str', JSON.stringify(floorsData));
        
        const response = await fetch('/api/auto_snap', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            floorsData = data.floors_data;
            drawCanvas();
        } else {
            alert('Auto-snap failed.');
        }
    } catch (e) {
        console.error(e);
        alert('Network error during Auto-Snap');
    }
    
    btn.innerHTML = originalText;
    btn.disabled = false;
});

// Re-draw canvas when grid snap checkbox is toggled
document.getElementById('snap-grid-cb').addEventListener('change', drawCanvas);
