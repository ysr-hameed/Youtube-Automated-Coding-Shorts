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
        alert("Auth Failed. " + (data.error || "Check client_secrets.json"));
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

document.addEventListener('DOMContentLoaded', () => {
    refreshAuthStatus();
    // Set cron URL to absolute path for easy copying
    const cron = document.getElementById('cronUrl');
    if (cron) cron.value = `${window.location.origin}/api/cron/generate`;
});

function showPreview(url) {
    const section = document.getElementById('previewSection');
    const video = document.getElementById('videoPlayer');
    const codePreview = document.getElementById('codePreview');
    section.classList.remove('hidden');
    video.src = url;
    video.play();
    // Populate code preview with line numbers
    if (window.lastGeneratedCode) {
        const lines = window.lastGeneratedCode.split('\n');
        const formatted = lines.map(line => `<span class="line">${line}</span>`).join('\n');
        codePreview.innerHTML = formatted;
    }
}

function copyCron() {
    const cron = document.getElementById('cronUrl');
    cron.select();
    document.execCommand('copy');
    alert('Cron URL copied to clipboard');
}
