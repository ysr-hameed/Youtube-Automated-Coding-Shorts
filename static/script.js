async function generateManual() {
    const btn = document.querySelector('.btn-primary');
    const originalText = btn.innerText;
    btn.innerText = "Generating...";
    btn.disabled = true;

    try {
        window.lastGeneratedCode = document.getElementById('code').value;
        const res = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: document.getElementById('question').value,
                code: document.getElementById('code').value,
                cursor_style: document.getElementById('cursor').value
                , auto_upload: document.getElementById('autoUpload') ? document.getElementById('autoUpload').checked : false
            })
        });
    const data = await res.json();
        if (data.success) {
            window.lastGeneratedCode = document.getElementById('code').value;
            showPreview(data.video_url);
            if (data.uploaded) {
                alert('✅ Video uploaded to YouTube: ' + (data.youtube_id ? ('https://youtu.be/' + data.youtube_id) : 'Uploaded'));
            }
        } else {
            alert('Error generating video: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert("Error generating video");
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

async function generateAI() {
    const btn = document.querySelector('.btn-magic');
    btn.innerText = "✨ Dreaming up content...";
    btn.disabled = true;

    try {
        const res = await fetch('/api/ai/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_upload: document.getElementById('autoUpload').checked })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('question').value = data.content.question;
            document.getElementById('code').value = data.content.code;
                if (data.content.title) document.getElementById('title').value = data.content.title;
                if (data.content.description) document.getElementById('description').value = data.content.description;
            window.lastGeneratedCode = data.content.code;
            showPreview(data.video_url);
            // If AI-generated video was auto-uploaded to YouTube
            if (data.uploaded) {
                alert('✅ AI Video uploaded to YouTube: ' + (data.youtube_id ? ('https://youtu.be/' + data.youtube_id) : 'Uploaded'));
            }
        } else {
            alert('Error generating AI video: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert("Error with AI generation");
    } finally {
        btn.innerText = "✨ Generate Viral Short";
        btn.disabled = false;
    }
}

async function authYouTube() {
    const res = await fetch('/api/auth/youtube', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
        alert("YouTube Authenticated! ✅");
        refreshAuthStatus();
    } else {
        if (data.auth_url) {
            window.location.href = data.auth_url;
        } else {
            alert("Auth Failed. " + (data.error || "Check client_secrets.json"));
        }
    }
}

async function refreshAuthStatus() {
    try {
    const res = await fetch('/api/auth/status');
        const data = await res.json();
    const btn = document.getElementById('btnYoutube');
        const status = document.getElementById('status');
        if (data.authenticated) {
            btn.innerText = '✅ Authenticated';
            btn.disabled = true;
            btn.classList.add('btn-authenticated');
            if (status) status.innerText = 'YouTube: Authenticated';
        } else {
            btn.innerText = '🔴 Auth YouTube';
            btn.disabled = false;
            btn.classList.remove('btn-authenticated');
            if (status) status.innerText = 'System Ready';
        }
    } catch (e) {
        console.warn('Error fetching auth status', e);
    }
}

async function resetSchedule() {
    if (!confirm('Are you sure you want to reset today\'s schedule? This will delete all current schedules and create new ones.')) return;
    try {
        const res = await fetch('/api/schedule/reset', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            alert('Schedule reset successfully!');
            refreshSchedule();
        } else {
            alert('Failed to reset schedule: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error resetting schedule');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    refreshAuthStatus();
    // Set cron URL to absolute path for easy copying
    const cron = document.getElementById('cronUrl');
    if (cron) cron.value = `${window.location.origin}/api/cron/generate`;
    // Load schedule info
    refreshSchedule();
    // Poll schedule periodically every minute
    setInterval(refreshSchedule, 60 * 1000);
});

async function refreshSchedule() {
    try {
        const res = await fetch('/api/schedule/today');
        const data = await res.json();
    const listUpcoming = document.getElementById('scheduleUpcoming');
    const listExecuted = document.getElementById('scheduleExecuted');
    if (!listUpcoming && !listExecuted) return;
        if (!data.success) {
            if (listUpcoming) listUpcoming.innerText = 'Error loading schedule';
            if (listExecuted) listExecuted.innerText = 'Error loading schedule';
                // show title and description if present from manual form
                const t = document.getElementById('title'); if (t && data.title) t.value = data.title;
                const desc = document.getElementById('description'); if (desc && data.description) desc.value = data.description;
            return;
        }
        const schedules = data.schedules || [];
        if (schedules.length === 0) {
            if (listUpcoming) listUpcoming.innerText = 'No scheduled runs for today.';
            if (listExecuted) listExecuted.innerText = 'No executed runs for today.';
            return;
        }

        const upcomingItems = [];
        const executedItems = [];
        schedules.forEach(s => {
            const scheduledAt = s.scheduled_at ? new Date(s.scheduled_at) : null;
            const executedAt = s.executed_at ? new Date(s.executed_at) : null;
            const tzOptions = { timeZone: 'Asia/Kolkata', hour12: true };
            const scheduledStr = scheduledAt ? scheduledAt.toLocaleTimeString(undefined, tzOptions) : 'n/a';
            const executedStr = executedAt ? executedAt.toLocaleTimeString(undefined, tzOptions) : null;
            let status = s.executed ? `✅ Executed at ${executedStr || 'unknown'} (IST)` : 'Scheduled (IST)';
            let extra = '';
            if (s.result && s.result.error) {
                const err = s.result.error || '';
                if (err.toLowerCase().includes('ai')) {
                    extra = '<span class="schedule-error"> - Failed by AI</span>';
                } else if (s.result && s.result.timeout) {
                    extra = '<span class="schedule-error"> - Timed out</span>';
                } else if (err) {
                    extra = `<span class="schedule-error"> - ${err}</span>`;
                }
            }
            const itemHtml = `<div class="schedule-item">${scheduledStr} — ${status}${extra}</div>`;
            if (s.executed) executedItems.push(itemHtml); else upcomingItems.push(itemHtml);
        });

        if (listUpcoming) listUpcoming.innerHTML = upcomingItems.length ? upcomingItems.join('') : '<div class="schedule-item">No upcoming runs for today.</div>';
        if (listExecuted) listExecuted.innerHTML = executedItems.length ? executedItems.join('') : '<div class="schedule-item">No executed runs for today.</div>';
    } catch (e) {
        console.warn('Failed to fetch schedule', e);
    }
}

function showPreview(url) {
    const section = document.getElementById('previewSection');
    const video = document.getElementById('videoPlayer');
    const codePreview = document.getElementById('codePreview');
    section.classList.remove('hidden');
    // Ensure the preview shows the generated video file (no autoplay)
    video.src = url;
    try { video.pause(); } catch(e){}
    try { video.load(); } catch(e){}
    // Do not autoplay; user can press play
    video.controls = true;
    // populate download link
    const downloadBtn = document.getElementById('downloadBtn');
    if (downloadBtn) {
        downloadBtn.href = url;
        // derive filename from url
        try {
            const parts = url.split('/');
            const fname = parts[parts.length-1] || 'video.mp4';
            downloadBtn.download = fname;
            downloadBtn.classList.remove('hidden');
        } catch(e) {
            downloadBtn.classList.remove('hidden');
        }
    }
    // Populate code preview with line numbers
    if (window.lastGeneratedCode) {
        const lines = window.lastGeneratedCode.split('\n');
        const formatted = lines.map(line => `<span class="line">${line}</span>`).join('\n');
        codePreview.innerHTML = formatted;
    }
    // Populate video meta area with title/description if available
    try {
        const meta = document.getElementById('videoMeta');
        if (meta) {
            const title = document.getElementById('title') ? document.getElementById('title').value : '';
            const desc = document.getElementById('description') ? document.getElementById('description').value : '';
            meta.innerHTML = `<div class="font-semibold">${title || 'Untitled'}</div><div class="text-xs text-gray-500">${desc ? desc.substring(0, 140) : ''}</div>`;
        }
    } catch(e) {}
}

function copyCron() {
    const cron = document.getElementById('cronUrl');
    cron.select();
    document.execCommand('copy');
    alert('Cron URL copied to clipboard');
}
