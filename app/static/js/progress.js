document.addEventListener('DOMContentLoaded', () => {
    const terminalLogs = document.getElementById('terminal-logs');
    const overallBadge = document.getElementById('overall-badge');
    const completionCard = document.getElementById('completion-card');
    const btnCancel = document.getElementById('btn-cancel-job');

    if (btnCancel) {
        btnCancel.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to stop generating? Currently generating clip will be aborted.')) {
                return;
            }
            btnCancel.disabled = true;
            btnCancel.innerText = 'Cancelling...';
            try {
                const resp = await fetch(`/api/job/${jobId}/cancel`, { method: 'POST' });
                const res = await resp.json();
                if (res.status === 'ok') {
                    appendLog(new Date().toLocaleTimeString(), 'Job cancellation requested by user.', 'warning');
                } else {
                    alert('Error: ' + res.message);
                }
            } catch (err) {
                alert('Request failed: ' + err.message);
            }
        });
    }

    function appendLog(time, msg, level) {
        const line = document.createElement('div');
        line.className = `log-line log-${(level || 'info').toLowerCase()}`;
        line.innerHTML = `<span class="log-time">${time}</span><span class="log-msg">${escapeHtml(msg)}</span>`;
        terminalLogs.appendChild(line);
        terminalLogs.scrollTop = terminalLogs.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.innerText = text;
        return div.innerHTML;
    }

    function updateSceneUI(sceneNumber, status, clipPath, error) {
        const badge = document.getElementById(`scene-badge-${sceneNumber}`);
        const footer = document.getElementById(`scene-footer-${sceneNumber}`);

        if (badge) {
            badge.className = `scene-badge badge-${status}`;
            badge.innerText = status;
        }

        if (footer) {
            if (status === 'done') {
                const filename = clipPath ? clipPath.split('/').pop() : `scene_${String(sceneNumber).padStart(2, '0')}.mp4`;
                footer.innerHTML = `<span class="ready-file">✓ ${filename} ready</span>`;
            } else if (status === 'generating') {
                footer.innerHTML = `<div class="mini-spinner"></div> <span>Generating in Google Flow...</span>`;
            } else if (status === 'failed') {
                footer.innerHTML = `<span class="text-error">Generation failed (${error || 'Error'})</span>`;
            }
        }
    }

    function updateOverallStatus(status, zipUrl) {
        if (overallBadge) {
            overallBadge.className = `badge badge-${status}`;
            overallBadge.innerText = status.toUpperCase();
        }

        if (btnCancel) {
            if (['completed', 'failed', 'cancelled'].includes(status)) {
                btnCancel.style.display = 'none';
            } else {
                btnCancel.style.display = 'inline-flex';
                btnCancel.disabled = false;
                btnCancel.innerText = '🛑 Cancel Job';
            }
        }

        if (status === 'completed') {
            if (completionCard) {
                completionCard.style.display = 'block';
                completionCard.scrollIntoView({ behavior: 'smooth' });
            }
        }
    }

    // Set up Server-Sent Events
    let eventSource = null;
    try {
        eventSource = new EventSource(`/api/job/${jobId}/events`);
        eventSource.onmessage = (e) => {
            try {
                const event = JSON.parse(e.data);
                if (event.type === 'log') {
                    appendLog(event.timestamp, event.message, event.level);
                } else if (event.type === 'scene_status') {
                    updateSceneUI(event.scene_number, event.status, event.clip_path, event.error);
                } else if (event.type === 'job_status') {
                    updateOverallStatus(event.status, event.zip_url);
                    if (event.status === 'completed' || event.status === 'failed') {
                        if (eventSource) eventSource.close();
                    }
                }
            } catch (err) {
                console.error("Error parsing SSE event:", err);
            }
        };

        eventSource.onerror = (err) => {
            console.warn("SSE connection error, falling back to polling.", err);
            if (eventSource) eventSource.close();
            startPolling();
        };
    } catch (e) {
        startPolling();
    }

    // Fallback polling every 2.5 seconds
    let pollingInterval = null;
    function startPolling() {
        if (pollingInterval) return;
        pollingInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/job/${jobId}/status`);
                if (!resp.ok) return;
                const data = await resp.json();
                
                updateOverallStatus(data.status, data.zip_path);

                if (data.scenes) {
                    data.scenes.forEach(s => {
                        updateSceneUI(s.scene_number, s.status, s.clip_path, s.error_message);
                    });
                }

                if (data.logs && data.logs.length > 0) {
                    // Update terminal logs if needed
                }

                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(pollingInterval);
                }
            } catch (err) {
                console.error("Polling error:", err);
            }
        }, 2500);
    }
});
