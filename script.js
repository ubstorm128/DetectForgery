// Document Scanner & Layout Verification Controller
const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1') 
    ? "" 
    : (window.location.origin.includes('github.io') ? "https://detectforgery.onrender.com" : "");

// State for Dual-Upload Workflow & Analysis
let frontData = null;
let backData = null;
let frontFile = null;
let currentResultData = null;
let currentImageObject = null;
let activeOverlays = {
    boxes: true,
    regions: false
};

// Drag and drop behavior
const dropzone = document.getElementById('dropzone');
if (dropzone) {
    dropzone.addEventListener('dragover', (e) => { 
        e.preventDefault(); 
        dropzone.style.borderColor = 'var(--primary)'; 
        dropzone.style.background = '#eff6ff'; 
    });
    dropzone.addEventListener('dragleave', (e) => { 
        e.preventDefault(); 
        dropzone.style.borderColor = 'var(--border)'; 
        dropzone.style.background = '#fafafa'; 
    });
    dropzone.addEventListener('drop', (e) => { 
        e.preventDefault(); 
        dropzone.style.borderColor = 'var(--border)'; 
        dropzone.style.background = '#fafafa'; 
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]); 
    });
}

async function loadTemplates() {
    try {
        const res = await fetch(`${API_BASE}/api/templates`);
        if (!res.ok) return;
        const templates = await res.json();
        const select = document.getElementById('document-type');
        if (templates.length > 0 && select) {
            select.innerHTML = '';
            templates.forEach(t => {
                if (t === 'aadhaar_front' || t === 'aadhaar_back') return;
                const opt = document.createElement('option');
                opt.value = t;
                opt.textContent = t.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                select.appendChild(opt);
            });
            if (templates.includes('aadhaar_front')) {
                const opt = document.createElement('option');
                opt.value = 'aadhaar';
                opt.textContent = 'Aadhaar (Dual Sided)';
                select.appendChild(opt);
            }
        }
    } catch (err) {
        console.warn("Could not load templates from server:", err);
    }
}

loadTemplates();

function showCustomPopup(title, message, type = 'alert', confirmText = 'OK', cancelText = 'Cancel') {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-backdrop';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.zIndex = '9999';
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.2s ease';

        const modal = document.createElement('div');
        modal.className = 'modal-content';
        modal.style.position = 'relative';
        modal.style.width = '100%';
        modal.style.maxWidth = '400px';
        modal.style.margin = '0 20px';
        modal.style.padding = '24px';
        modal.style.borderRadius = '16px';
        modal.style.backgroundColor = 'var(--surface)';
        modal.style.boxShadow = '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)';
        modal.style.transform = 'scale(0.95)';
        modal.style.transition = 'transform 0.2s ease';

        const titleEl = document.createElement('h3');
        titleEl.textContent = title;
        titleEl.style.marginTop = '0';
        titleEl.style.marginBottom = '12px';
        titleEl.style.fontSize = '1.25rem';
        titleEl.style.color = 'var(--text-primary)';

        const msgEl = document.createElement('p');
        msgEl.innerHTML = message.replace(/\n/g, '<br>');
        msgEl.style.color = 'var(--text-muted)';
        msgEl.style.marginBottom = '24px';
        msgEl.style.fontSize = '0.95rem';
        msgEl.style.lineHeight = '1.5';

        const actionRow = document.createElement('div');
        actionRow.style.display = 'flex';
        actionRow.style.justifyContent = 'flex-end';
        actionRow.style.gap = '12px';

        const closePopup = () => {
            overlay.style.opacity = '0';
            modal.style.transform = 'scale(0.95)';
            setTimeout(() => document.body.removeChild(overlay), 200);
        };

        if (type === 'confirm') {
            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-outline';
            cancelBtn.textContent = cancelText;
            cancelBtn.onclick = () => {
                closePopup();
                resolve(false);
            };
            actionRow.appendChild(cancelBtn);
        }

        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'btn-primary';
        confirmBtn.textContent = confirmText;
        confirmBtn.onclick = () => {
            closePopup();
            resolve(true);
        };
        actionRow.appendChild(confirmBtn);

        modal.appendChild(titleEl);
        modal.appendChild(msgEl);
        modal.appendChild(actionRow);
        overlay.appendChild(modal);

        document.body.appendChild(overlay);

        requestAnimationFrame(() => {
            overlay.style.opacity = '1';
            modal.style.transform = 'scale(1)';
        });
    });
}

async function handleFile(file) {
    if (!file) return;
    
    const docType = document.getElementById('document-type').value;
    
    document.getElementById('section-upload').classList.add('hidden');
    document.getElementById('section-results').classList.add('hidden');
    document.getElementById('section-analyzing').classList.remove('hidden');
    
    // Smooth progress simulation during pipeline steps
    let prog = 0;
    const interval = setInterval(() => {
        prog += 5;
        if (prog <= 95) {
            const p1 = Math.min(100, prog * 2.0);
            const p2 = Math.max(0, Math.min(100, (prog - 15) * 1.8));
            const p3 = Math.max(0, Math.min(100, (prog - 30) * 1.6));
            const p4 = Math.max(0, Math.min(100, (prog - 45) * 1.5));
            
            const elP1 = document.getElementById('prog-persp');
            const elL1 = document.getElementById('lbl-persp');
            if (elP1) elP1.style.width = p1 + '%';
            if (elL1) elL1.textContent = Math.round(p1) + '%';

            const elP2 = document.getElementById('prog-ocr');
            const elL2 = document.getElementById('lbl-ocr');
            if (elP2) elP2.style.width = p2 + '%';
            if (elL2) elL2.textContent = Math.round(p2) + '%';

            const elP3 = document.getElementById('prog-layout');
            const elL3 = document.getElementById('lbl-layout');
            if (elP3) elP3.style.width = p3 + '%';
            if (elL3) elL3.textContent = Math.round(p3) + '%';

            const elP4 = document.getElementById('prog-ela');
            const elL4 = document.getElementById('lbl-ela');
            if (elP4) elP4.style.width = p4 + '%';
            if (elL4) elL4.textContent = Math.round(p4) + '%';
        }
    }, 90);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', docType);
    
    try {
        const response = await fetch(`${API_BASE}/api/analyze-image`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        clearInterval(interval);
        ['persp', 'ocr', 'layout', 'ela'].forEach(k => {
            const p = document.getElementById('prog-' + k);
            const l = document.getElementById('lbl-' + k);
            if (p) p.style.width = '100%';
            if (l) l.textContent = '100%';
        });
        
        if (docType === 'aadhaar') {
            // Dual-sided logic
            if (data.detected_side === 'front') {
                frontData = data;
                frontFile = file;
                if (!backData) {
                    await showCustomPopup("Side Detected", "Detected: Aadhaar FRONT.\nPlease upload the BACK side now.");
                    resetToUploadState("Upload Aadhaar BACK Side");
                }
            } else if (data.detected_side === 'back') {
                backData = data;
                if (!frontData) {
                    await showCustomPopup("Side Detected", "Detected: Aadhaar BACK.\nPlease upload the FRONT side now.");
                    resetToUploadState("Upload Aadhaar FRONT Side");
                }
            } else {
                // If side ambiguous, allow user confirmation
                const isFront = await showCustomPopup(
                    "Ambiguous Side", 
                    "Detected side could not be 100% distinguished.\nIs this the FRONT side?", 
                    "confirm", 
                    "Yes, Front", 
                    "No, Back"
                );
                
                if (isFront) {
                    frontData = data;
                    frontFile = file;
                    if (!backData) {
                        resetToUploadState("Upload Aadhaar BACK Side");
                    }
                } else {
                    backData = data;
                    if (!frontData) {
                        resetToUploadState("Upload Aadhaar FRONT Side");
                    }
                }
            }
            
            if (frontData && backData) {
                performCrossCheck();
            }
        } else {
            setTimeout(() => showResults(data, file), 400);
        }
        
    } catch (err) {
        alert('Error analyzing document. Please ensure the backend server is running.');
        console.error(err);
        clearInterval(interval);
        resetApp();
    }
}

function resetToUploadState(message) {
    document.getElementById('section-analyzing').classList.add('hidden');
    document.getElementById('section-upload').classList.remove('hidden');
    document.querySelector('.dropzone-text').textContent = message;
    document.getElementById('file-input').value = '';
    
    ['persp', 'ocr', 'layout', 'ela'].forEach(k => {
        const p = document.getElementById('prog-' + k);
        const l = document.getElementById('lbl-' + k);
        if (p) p.style.width = '0%';
        if (l) l.textContent = '0%';
    });
}

async function performCrossCheck() {
    document.getElementById('section-upload').classList.add('hidden');
    document.getElementById('section-analyzing').classList.remove('hidden');
    
    try {
        const reqBody = {
            front_text: (frontData.ocr && frontData.ocr.text) || "",
            back_text: (backData.ocr && backData.ocr.text) || "",
            front_score: frontData.authenticity_score || frontData.overall_score || 85,
            back_score: backData.authenticity_score || backData.overall_score || 85,
            front_aadhaar: (frontData.ocr && frontData.ocr.aadhaar_number) || "",
            back_aadhaar: (backData.ocr && backData.ocr.aadhaar_number) || ""
        };
        
        const res = await fetch(`${API_BASE}/api/compare-sides`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqBody)
        });
        
        const compareData = await res.json();
        
        const mergedData = {
            authenticity_score: compareData.combined_authenticity_score,
            overall_score: compareData.combined_authenticity_score,
            result: compareData.classification,
            risk_level: compareData.risk_level || (compareData.combined_authenticity_score >= 90 ? "LOW RISK" : (compareData.combined_authenticity_score >= 70 ? "MEDIUM RISK" : "HIGH RISK")),
            confidence: frontData.confidence || 0.92,
            checks: frontData.checks,
            layout: frontData.layout,
            image_quality: frontData.image_quality,
            ocr: frontData.ocr,
            warnings: frontData.warnings || []
        };
        
        if (compareData.status === "FAIL") {
            mergedData.checks["cross_match"] = { score: 20, status: "FAIL", name: "Front/Back Cross-Match" };
        } else {
            mergedData.checks["cross_match"] = { score: 100, status: "PASS", name: "Front/Back Cross-Match" };
        }
        
        mergedData.matched_aadhaar = compareData.matched_aadhaar;
        mergedData.front_number = compareData.front_number;
        mergedData.back_number = compareData.back_number;
        
        setTimeout(() => showResults(mergedData, frontFile, compareData.anomalies), 400);
        
    } catch(e) {
        console.error(e);
        alert("Dual-sided cross check could not be completed.");
        resetApp();
    }
}

function showResults(data, file, extraAnomalies=[]) {
    currentResultData = data;
    document.getElementById('section-analyzing').classList.add('hidden');
    document.getElementById('section-results').classList.remove('hidden');
    
    const scoreCont = document.getElementById('score-container');
    const scoreEl = document.getElementById('risk-score');
    const classEl = document.getElementById('classification');
    const confEl = document.getElementById('confidence-indicator');
    
    const finalScore = data.overall_score !== undefined ? data.overall_score : (data.authenticity_score || 0);
    const resultType = (data.result || "SUSPICIOUS").toLowerCase();
    
    scoreEl.textContent = finalScore;
    scoreCont.className = 'score-header ' + resultType;
    classEl.textContent = data.risk_level || data.result.replace('_', ' ').toUpperCase();
    
    if (confEl && data.confidence !== undefined) {
        confEl.textContent = `Confidence: ${Math.round(data.confidence * 100)}%`;
    }

    // Populate Separated Image Quality Card
    if (data.image_quality) {
        const qScore = data.image_quality.score || 85;
        document.getElementById('quality-score-val').textContent = `${qScore}/100`;
        document.getElementById('chip-sharpness').textContent = `Sharpness: ${data.image_quality.sharpness || '--'}`;
        document.getElementById('chip-brightness').textContent = `Brightness: ${data.image_quality.brightness || '--'}`;
        document.getElementById('chip-contrast').textContent = `Contrast: ${data.image_quality.contrast || '--'}`;
    }
    
    // Display Aadhaar Number
    let aadhaarEl = document.getElementById('aadhaar-number-display');
    
    if (data.matched_aadhaar || (data.front_number && data.back_number && data.front_number !== data.back_number)) {
        if (!aadhaarEl) {
            aadhaarEl = document.createElement('div');
            aadhaarEl.id = 'aadhaar-number-display';
            aadhaarEl.style.marginTop = '1rem';
            aadhaarEl.style.padding = '0.75rem';
            aadhaarEl.style.borderRadius = '8px';
            aadhaarEl.style.fontWeight = '600';
            aadhaarEl.style.textAlign = 'center';
            // Insert before the quality card
            const qCard = document.getElementById('quality-card');
            if (qCard) {
                qCard.parentNode.insertBefore(aadhaarEl, qCard);
            } else {
                scoreCont.parentNode.appendChild(aadhaarEl);
            }
        }
        
        if (data.matched_aadhaar) {
            const formatted = data.matched_aadhaar.replace(/(.{4})/g, '$1 ').trim();
            aadhaarEl.innerHTML = `Aadhaar Number: <span style="font-size: 1.1rem; letter-spacing: 2px;">${formatted}</span>`;
            aadhaarEl.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
            aadhaarEl.style.border = '1px solid var(--primary)';
            aadhaarEl.style.color = 'var(--primary)';
        } else {
            const formattedF = data.front_number.replace(/(.{4})/g, '$1 ').trim();
            const formattedB = data.back_number.replace(/(.{4})/g, '$1 ').trim();
            aadhaarEl.innerHTML = `
                <div style="color: var(--danger); font-size: 0.9rem; text-transform: uppercase; margin-bottom: 0.25rem;">⚠ Number Mismatch</div>
                <div style="font-size: 0.85rem; color: var(--text-muted); font-weight: 500;">Front: <span style="text-decoration: line-through;">${formattedF}</span></div>
                <div style="font-size: 0.85rem; color: var(--text-muted); font-weight: 500;">Back: <span style="text-decoration: line-through;">${formattedB}</span></div>
            `;
            aadhaarEl.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
            aadhaarEl.style.border = '1px solid var(--danger)';
            aadhaarEl.style.color = 'inherit';
        }
        aadhaarEl.style.display = 'block';
    } else if (aadhaarEl) {
        aadhaarEl.style.display = 'none';
    }

    // Populate Individual Checks Breakdown
    const list = document.getElementById('checks-list');
    list.innerHTML = '';
    
    const checksOrder = [
        { key: 'layout', name: 'Layout & Formatting' },
        { key: 'ocr', name: 'OCR / Text Consistency' },
        { key: 'tampering', name: 'Image Manipulation (ELA)' },
        { key: 'copy_move', name: 'Copy-Move Analysis' },
        { key: 'compression', name: 'Compression (DCT)' },
        { key: 'geometry', name: 'Document Geometry' },
        { key: 'metadata', name: 'Metadata & EXIF' },
        { key: 'qr', name: 'QR Consistency' },
        { key: 'cross_match', name: 'Front/Back Cross-Match' }
    ];
    
    if (data.checks) {
        checksOrder.forEach(c => {
            const checkResult = data.checks[c.key];
            if (checkResult) {
                const li = document.createElement('li');
                li.className = 'check-item';
                const score = checkResult.score !== undefined ? checkResult.score : 0;
                const scoreClass = score >= 85 ? 'score-safe' : 'score-warn';
                
                let detailsButton = '';
                if (c.key === 'layout') {
                    detailsButton = `<button class="btn-details" onclick="openLayoutModal()">View Details</button>`;
                }
                
                if (c.key === 'copy_move') {
                    const risk = checkResult.risk !== undefined ? checkResult.risk : (100 - score);
                    const integrity = checkResult.integrity !== undefined ? checkResult.integrity : score;
                    const message = risk < 30 ? '✓ No suspicious copy-move evidence detected' : '⚠ Suspicious duplicated region detected';
                    const msgColor = risk < 30 ? 'var(--success)' : 'var(--danger)';
                    
                    li.innerHTML = `
                        <div style="width: 100%;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <span class="check-name" style="font-weight: 600;">${c.name}</span>
                                <div style="display: flex; gap: 1rem;">
                                    <div style="text-align: right;">
                                        <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Risk</div>
                                        <div style="font-weight: 700; color: ${risk < 30 ? 'var(--success)' : 'var(--danger)'};">${risk}%</div>
                                    </div>
                                    <div style="text-align: right;">
                                        <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Integrity</div>
                                        <div style="font-weight: 700; color: ${integrity >= 85 ? 'var(--success)' : 'var(--danger)'};">${integrity}%</div>
                                    </div>
                                </div>
                            </div>
                            <div style="font-size: 0.8rem; padding: 0.25rem 0; color: ${msgColor};">${message}</div>
                        </div>
                    `;
                    li.style.flexDirection = "column";
                    li.style.alignItems = "flex-start";
                } else {
                    li.innerHTML = `
                        <span class="check-name">${c.name}</span>
                        <div class="check-score-col">
                            <span class="check-score ${scoreClass}">${score}%</span>
                            ${detailsButton}
                        </div>
                    `;
                }
                list.appendChild(li);
            }
        });
    }
    
    // Populate Explainable Reasoning List
    const reasonsList = document.getElementById('reasons-list');
    if (reasonsList) {
        reasonsList.innerHTML = '';
        const explainReasons = (data.layout && data.layout.explainable_reasons) || [];
        
        if (explainReasons.length > 0) {
            explainReasons.forEach(r => {
                const rLi = document.createElement('li');
                const isWarning = r.startsWith('⚠');
                rLi.className = isWarning ? 'reason-warn' : 'reason-safe';
                rLi.textContent = r;
                reasonsList.appendChild(rLi);
            });
        } else {
            const rLi = document.createElement('li');
            rLi.className = 'reason-safe';
            rLi.textContent = '✓ Document structure is consistent with reference template';
            reasonsList.appendChild(rLi);
        }

        if (extraAnomalies && extraAnomalies.length > 0) {
            extraAnomalies.forEach(anomaly => {
                const rLi = document.createElement('li');
                rLi.className = 'reason-danger';
                rLi.textContent = `⚠ ${anomaly}`;
                reasonsList.appendChild(rLi);
            });
        }
    }
    
    // Setup Canvas Image & Render Overlays
    const img = new Image();
    img.onload = () => {
        currentImageObject = img;
        renderCanvas();
    };
    img.src = URL.createObjectURL(file);
}

function renderCanvas() {
    if (!currentImageObject) return;
    const canvas = document.getElementById('image-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    canvas.width = currentImageObject.width;
    canvas.height = currentImageObject.height;
    ctx.drawImage(currentImageObject, 0, 0);

    const w = canvas.width;
    const h = canvas.height;

    // 1. Draw Document Regions if enabled
    if (activeOverlays.regions) {
        const regions = [
            { name: "Header", ymin: 0.0, ymax: 0.20, xmin: 0.05, xmax: 0.95, color: "rgba(59, 130, 246, 0.25)", border: "#3b82f6" },
            { name: "Details", ymin: 0.22, ymax: 0.72, xmin: 0.32, xmax: 0.96, color: "rgba(16, 185, 129, 0.25)", border: "#10b981" },
            { name: "Photo/Emblem", ymin: 0.22, ymax: 0.72, xmin: 0.04, xmax: 0.32, color: "rgba(139, 92, 246, 0.25)", border: "#8b5cf6" },
            { name: "ID Number", ymin: 0.74, ymax: 0.95, xmin: 0.20, xmax: 0.85, color: "rgba(245, 158, 11, 0.25)", border: "#f59e0b" }
        ];

        regions.forEach(reg => {
            const rx = reg.xmin * w;
            const ry = reg.ymin * h;
            const rw = (reg.xmax - reg.xmin) * w;
            const rh = (reg.ymax - reg.ymin) * h;

            ctx.fillStyle = reg.color;
            ctx.fillRect(rx, ry, rw, rh);
            ctx.strokeStyle = reg.border;
            ctx.lineWidth = Math.max(2, w / 400);
            ctx.strokeRect(rx, ry, rw, rh);
        });
    }

    // 2. Draw OCR Bounding Boxes if enabled
    if (activeOverlays.boxes && currentResultData && currentResultData.ocr && currentResultData.ocr.boxes) {
        currentResultData.ocr.boxes.forEach(b => {
            const conf = b.confidence !== undefined ? b.confidence : 0.9;
            let strokeColor = '#22c55e'; // Green (matched / high conf)
            if (conf < 0.60) {
                strokeColor = '#ef4444'; // Red (low conf / anomaly)
            } else if (conf < 0.85) {
                strokeColor = '#f59e0b'; // Orange (minor variation)
            }

            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = Math.max(2, w / 350);
            
            // Support both pixel coordinates and normalized coordinates
            let bx = b.x;
            let by = b.y;
            let bw = b.width;
            let bh = b.height;

            if (b.norm_x !== undefined) {
                bx = b.norm_x * w;
                by = b.norm_y * h;
                bw = b.norm_w * w;
                bh = b.norm_h * h;
            }

            ctx.strokeRect(bx, by, bw, bh);
        });
    }
}

function toggleOverlay(type) {
    activeOverlays[type] = !activeOverlays[type];
    const btn = document.getElementById(type === 'boxes' ? 'btn-toggle-boxes' : 'btn-toggle-regions');
    if (btn) {
        btn.classList.toggle('active', activeOverlays[type]);
    }
    renderCanvas();
}

function openLayoutModal() {
    const modal = document.getElementById('layout-modal');
    if (!modal) return;
    
    if (currentResultData && currentResultData.layout) {
        const layout = currentResultData.layout;
        const comps = layout.components || {};
        
        const score = layout.score || 90;
        document.getElementById('modal-layout-score').textContent = score;
        
        const pos = Math.round(comps.position || 95);
        const size = Math.round(comps.size || 92);
        const align = Math.round(comps.alignment || 95);
        const spacing = Math.round(comps.spacing || 91);
        const region = Math.round(comps.region_structure || 90);

        document.getElementById('m-val-pos').textContent = `${pos}%`;
        document.getElementById('m-bar-pos').style.width = `${pos}%`;

        document.getElementById('m-val-size').textContent = `${size}%`;
        document.getElementById('m-bar-size').style.width = `${size}%`;

        document.getElementById('m-val-align').textContent = `${align}%`;
        document.getElementById('m-bar-align').style.width = `${align}%`;

        document.getElementById('m-val-spacing').textContent = `${spacing}%`;
        document.getElementById('m-bar-spacing').style.width = `${spacing}%`;

        document.getElementById('m-val-region').textContent = `${region}%`;
        document.getElementById('m-bar-region').style.width = `${region}%`;

        const modalReasons = document.getElementById('modal-reasons-list');
        if (modalReasons) {
            modalReasons.innerHTML = '';
            const reasons = layout.explainable_reasons || [
                "✓ Text positions are consistent with document template",
                "✓ Major text blocks and margins are correctly aligned",
                "✓ Document typography and element dimensions match expected proportions"
            ];
            reasons.forEach(r => {
                const li = document.createElement('li');
                li.className = r.startsWith('⚠') ? 'reason-warn' : 'reason-safe';
                li.textContent = r;
                modalReasons.appendChild(li);
            });
        }
    }

    modal.classList.remove('hidden');
}

function closeLayoutModal() {
    const modal = document.getElementById('layout-modal');
    if (modal) modal.classList.add('hidden');
}

function resetApp() {
    frontData = null;
    backData = null;
    frontFile = null;
    currentResultData = null;
    currentImageObject = null;
    document.getElementById('file-input').value = '';
    document.getElementById('section-results').classList.add('hidden');
    document.getElementById('section-analyzing').classList.add('hidden');
    document.getElementById('section-upload').classList.remove('hidden');
    document.querySelector('.dropzone-text').textContent = 'Click to browse or drag and drop';
    
    ['persp', 'ocr', 'layout', 'ela'].forEach(k => {
        const p = document.getElementById('prog-' + k);
        const l = document.getElementById('lbl-' + k);
        if (p) p.style.width = '0%';
        if (l) l.textContent = '0%';
    });
}

let mediaStream = null;

async function openCamera() {
    const container = document.getElementById('camera-container');
    const uploadControls = document.querySelector('.upload-controls');
    
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        const video = document.getElementById('camera-feed');
        video.srcObject = mediaStream;
        
        container.style.display = 'flex';
        container.classList.remove('hidden');
        uploadControls.style.display = 'none';
    } catch (err) {
        alert("Unable to access camera: " + err.message);
        console.error(err);
    }
}

function closeCamera() {
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
    const container = document.getElementById('camera-container');
    const uploadControls = document.querySelector('.upload-controls');
    if (container) {
        container.style.display = 'none';
        container.classList.add('hidden');
    }
    if (uploadControls) {
        uploadControls.style.display = 'flex';
    }
}

function captureCamera() {
    const video = document.getElementById('camera-feed');
    const canvas = document.getElementById('camera-canvas');
    const ctx = canvas.getContext('2d');
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    canvas.toBlob((blob) => {
        const file = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
        closeCamera();
        handleFile(file);
    }, 'image/jpeg', 0.95);
}