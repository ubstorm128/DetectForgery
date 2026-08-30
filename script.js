// Contact form mock submission
const API_BASE = "https://detectforgery.onrender.com";
function handleContactSubmit(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    const originalText = btn.textContent;
    btn.textContent = 'Sending...';
    btn.style.opacity = '0.7';
    setTimeout(() => {
        btn.textContent = 'Message Sent!';
        btn.style.background = 'var(--success)';
        btn.style.opacity = '1';
        e.target.reset();
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = 'var(--primary)';
        }, 3000);
    }, 1000);
}

// State for Dual-Upload Workflow
let frontData = null;
let backData = null;
let frontFile = null; 

// Drag and drop behavior
const dropzone = document.getElementById('dropzone');
if (dropzone) {
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.style.borderColor = 'var(--primary)'; dropzone.style.background = '#eff6ff'; });
    dropzone.addEventListener('dragleave', (e) => { e.preventDefault(); dropzone.style.borderColor = 'var(--border)'; dropzone.style.background = '#f8fafc'; });
    dropzone.addEventListener('drop', (e) => { e.preventDefault(); dropzone.style.borderColor = 'var(--border)'; dropzone.style.background = '#f8fafc'; if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]); });
}

async function loadTemplates() {
    try {
        const res = await fetch(`${API_BASE}/api/templates`);
        const templates = await res.json();
        const select = document.getElementById('document-type');
        if (templates.length > 0 && select) {
            select.innerHTML = '';
            templates.forEach(t => {
                // Filter out backend specific split configs from UI dropdown
                if (t === 'aadhaar_front' || t === 'aadhaar_back') return;
                const opt = document.createElement('option');
                opt.value = t;
                opt.textContent = t.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                select.appendChild(opt);
            });
            // Re-add generic aadhaar if it exists in another form
            if (templates.includes('aadhaar_front')) {
                const opt = document.createElement('option');
                opt.value = 'aadhaar';
                opt.textContent = 'Aadhaar (Dual Sided)';
                select.appendChild(opt);
            }
        }
    } catch (err) {
        console.error("Could not load templates", err);
    }
}

loadTemplates();

async function handleFile(file) {
    if (!file) return;
    
    const docType = document.getElementById('document-type').value;
    
    document.getElementById('section-upload').classList.add('hidden');
    document.getElementById('section-results').classList.add('hidden');
    document.getElementById('section-analyzing').classList.remove('hidden');
    
    let prog = 0;
    const interval = setInterval(() => {
        prog += 5;
        if (prog <= 100) {
            const p1 = Math.min(100, prog * 1.5);
            const p2 = Math.max(0, Math.min(100, (prog - 20) * 1.5));
            const p3 = Math.max(0, Math.min(100, (prog - 40) * 1.5));
            
            document.getElementById('prog-ocr').style.width = p1 + '%';
            document.getElementById('lbl-ocr').textContent = Math.round(p1) + '%';
            document.getElementById('prog-ela').style.width = p2 + '%';
            document.getElementById('lbl-ela').textContent = Math.round(p2) + '%';
            document.getElementById('prog-copy').style.width = p3 + '%';
            document.getElementById('lbl-copy').textContent = Math.round(p3) + '%';
        }
    }, 100);

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
        ['ocr', 'ela', 'copy'].forEach(k => {
            document.getElementById('prog-' + k).style.width = '100%';
            document.getElementById('lbl-' + k).textContent = '100%';
        });
        
        if (docType === 'aadhaar') {
            // Dual-sided logic
            if (data.detected_side === 'front') {
                frontData = data;
                frontFile = file;
                alert("Detected: Aadhaar FRONT. Please upload the BACK side now.");
                resetToUploadState("Upload Aadhaar BACK Side");
            } else if (data.detected_side === 'back') {
                backData = data;
                if (!frontData) {
                    alert("Detected: Aadhaar BACK. Please upload the FRONT side now.");
                    resetToUploadState("Upload Aadhaar FRONT Side");
                } else {
                    // We have both, perform cross-check
                    performCrossCheck();
                }
            } else {
                // Unknown side, ask the user to manually override
                const isFront = confirm("Could not auto-detect side. Is this the FRONT side?\n\n(Click OK for Front, Cancel for Back)");
                if (isFront) {
                    frontData = data;
                    frontFile = file;
                    resetToUploadState("Upload Aadhaar BACK Side");
                } else {
                    backData = data;
                    if (!frontData) {
                        resetToUploadState("Upload Aadhaar FRONT Side");
                    } else {
                        performCrossCheck();
                    }
                }
            }
            
            // If we somehow got both (e.g. they uploaded back first)
            if (frontData && backData) {
                performCrossCheck();
            }
        } else {
            // Normal single-sided logic
            setTimeout(() => showResults(data, file), 600);
        }
        
    } catch (err) {
        alert('Error analyzing image. Ensure the server is running.');
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
    
    ['ocr', 'ela', 'copy'].forEach(k => {
        document.getElementById('prog-' + k).style.width = '0%';
        document.getElementById('lbl-' + k).textContent = '0%';
    });
}

async function performCrossCheck() {
    document.getElementById('section-upload').classList.add('hidden');
    document.getElementById('section-analyzing').classList.remove('hidden');
    
    try {
        const reqBody = {
            front_text: frontData.ocr.text || "",
            back_text: backData.ocr.text || "",
            front_score: frontData.authenticity_score,
            back_score: backData.authenticity_score
        };
        
        const res = await fetch(`${API_BASE}/api/compare-sides`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqBody)
        });
        
        const compareData = await res.json();
        
        // Merge data for display (we use front file for the canvas)
        const mergedData = {
            authenticity_score: compareData.combined_authenticity_score,
            result: compareData.classification,
            checks: frontData.checks, // base on front for UI
            ocr: frontData.ocr
        };
        
        if (compareData.status === "FAIL") {
            mergedData.checks["cross_match"] = { score: 0 }; 
        } else {
            mergedData.checks["cross_match"] = { score: 100 };
        }
        
        setTimeout(() => showResults(mergedData, frontFile, compareData.anomalies), 600);
        
    } catch(e) {
        console.error(e);
        alert("Failed cross check.");
        resetApp();
    }
}

function showResults(data, file, extraAnomalies=[]) {
    document.getElementById('section-analyzing').classList.add('hidden');
    document.getElementById('section-results').classList.remove('hidden');
    
    const scoreCont = document.getElementById('score-container');
    const scoreEl = document.getElementById('risk-score');
    const classEl = document.getElementById('classification');
    
    scoreEl.textContent = data.authenticity_score;
    scoreCont.className = 'score-header ' + data.result.toLowerCase();
    classEl.textContent = data.result.replace('_', ' ').toUpperCase();
    
    const list = document.getElementById('checks-list');
    list.innerHTML = '';
    
    const checksData = [
        { name: 'OCR Consistency', key: 'ocr' },
        { name: 'QR Consistency', key: 'qr' },
        { name: 'Layout & Formatting', key: 'layout' },
        { name: 'Font Consistency', key: 'font_consistency' },
        { name: 'Image Tampering', key: 'tampering' },
        { name: 'Compression (DCT)', key: 'compression' },
        { name: 'Metadata', key: 'metadata' },
        { name: 'Photo Analysis', key: 'photo_analysis' },
        { name: 'Front/Back Cross-Match', key: 'cross_match' }
    ];
    
    if (data.checks) {
        checksData.forEach(c => {
            const checkResult = data.checks[c.key];
            if (checkResult) {
                const li = document.createElement('li');
                li.className = 'check-item';
                const score = checkResult.score || 0;
                const scoreClass = score >= 85 ? 'score-safe' : 'score-warn';
                li.innerHTML = `
                    <span class="check-name">${c.name}</span>
                    <span class="check-score ${scoreClass}">Score: ${score}</span>
                `;
                list.appendChild(li);
            }
        });
    }
    
    if (extraAnomalies && extraAnomalies.length > 0) {
        extraAnomalies.forEach(anomaly => {
            const li = document.createElement('li');
            li.className = 'check-item';
            li.innerHTML = `<span class="check-name" style="color:var(--danger);">⚠️ ${anomaly}</span>`;
            list.appendChild(li);
        });
    }
    
    const canvas = document.getElementById('image-canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        if (data.ocr && data.ocr.boxes) {
            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = Math.max(2, img.width / 300);
            data.ocr.boxes.forEach(b => {
                ctx.strokeRect(b.x, b.y, b.width, b.height);
            });
        }
    };
    img.src = URL.createObjectURL(file);
}

function resetApp() {
    frontData = null;
    backData = null;
    frontFile = null;
    document.getElementById('file-input').value = '';
    document.getElementById('section-results').classList.add('hidden');
    document.getElementById('section-analyzing').classList.add('hidden');
    document.getElementById('section-upload').classList.remove('hidden');
    document.querySelector('.dropzone-text').textContent = 'Click to browse or drag and drop';
    
    ['ocr', 'ela', 'copy'].forEach(k => {
        document.getElementById('prog-' + k).style.width = '0%';
        document.getElementById('lbl-' + k).textContent = '0%';
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