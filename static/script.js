async function generateManual() {
    const btn = document.querySelector('.btn-primary');
    const originalText = btn.innerText;
    btn.innerText = "Generating...";
    btn.disabled = true;

    try {
        const res = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: document.getElementById('question').value,
                code: document.getElementById('code').value,
                cursor_style: document.getElementById('cursor').value
            })
        });
        const data = await res.json();
        if (data.success) showPreview(data.video_url);
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
        const res = await fetch('/api/ai/generate', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showPreview(data.video_url);
            document.getElementById('question').value = data.content.question;
            document.getElementById('code').value = data.content.code;
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
    if (data.success) alert("YouTube Authenticated! ✅");
    else alert("Auth Failed. Check client_secrets.json");
}

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
