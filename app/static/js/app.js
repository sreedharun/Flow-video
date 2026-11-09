document.addEventListener('DOMContentLoaded', () => {
    // Dropdown toggle for custom language
    const langSelect = document.getElementById('language_select');
    const customLangGroup = document.getElementById('custom_language_group');
    if (langSelect && customLangGroup) {
        langSelect.addEventListener('change', () => {
            customLangGroup.style.display = langSelect.value === 'custom' ? 'block' : 'none';
        });
    }

    // Dropdown toggle for custom style
    const styleSelect = document.getElementById('style_select');
    const customStyleGroup = document.getElementById('custom_style_group');
    if (styleSelect && customStyleGroup) {
        styleSelect.addEventListener('change', () => {
            customStyleGroup.style.display = styleSelect.value === 'custom' ? 'block' : 'none';
        });
    }

    // Generate Script Button
    const btnGenerateScript = document.getElementById('btn-generate-script');
    const loadingCard = document.getElementById('script-loading');
    const editorSection = document.getElementById('script-editor-section');

    let currentJobId = null;

    if (btnGenerateScript) {
        btnGenerateScript.addEventListener('click', async () => {
            const topic = document.getElementById('topic').value.trim();
            if (!topic) {
                alert('Please enter a topic or video idea first.');
                document.getElementById('topic').focus();
                return;
            }

            const language = langSelect.value === 'custom'
                ? document.getElementById('custom_language').value.trim() || 'English'
                : langSelect.value;

            const style = styleSelect.value === 'custom'
                ? document.getElementById('custom_style').value.trim() || 'cinematic'
                : styleSelect.value;

            const numScenes = parseInt(document.getElementById('num_scenes').value, 10) || 4;
            const targetLength = parseInt(document.querySelector('input[name="target_length"]:checked').value, 10) || 5;
            const tone = document.getElementById('tone').value;
            const aspectRatio = document.querySelector('input[name="aspect_ratio"]:checked').value;
            const flowModel = document.getElementById('flow_model') ? document.getElementById('flow_model').value : 'omni_1.1_flash';
            const resolution = document.getElementById('resolution') ? document.getElementById('resolution').value : '360p';
            const flowProjectUrl = document.getElementById('flow_project_url') ? document.getElementById('flow_project_url').value.trim() : '';
            const characterDesc = document.getElementById('character_desc').value.trim();

            const formData = new FormData();
            formData.append('topic', topic);
            formData.append('language', language);
            formData.append('num_scenes', numScenes);
            formData.append('target_length', targetLength);
            formData.append('style', style);
            formData.append('tone', tone);
            formData.append('aspect_ratio', aspectRatio);
            formData.append('flow_model', flowModel);
            formData.append('resolution', resolution);
            formData.append('flow_project_url', flowProjectUrl);
            formData.append('character_desc', characterDesc);

            const refImageInput = document.getElementById('ref_image');
            if (refImageInput.files.length > 0) {
                formData.append('ref_image', refImageInput.files[0]);
            }

            btnGenerateScript.disabled = true;
            loadingCard.style.display = 'block';
            editorSection.style.display = 'none';

            try {
                const response = await fetch('/api/script/generate', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                if (!response.ok || data.status === 'error') {
                    throw new Error(data.message || 'Failed to generate script');
                }

                currentJobId = data.job_id;
                renderScriptEditor(data.script, language, targetLength);
                editorSection.style.display = 'block';
                editorSection.scrollIntoView({ behavior: 'smooth' });

            } catch (err) {
                alert('Error generating script: ' + err.message);
            } finally {
                btnGenerateScript.disabled = false;
                loadingCard.style.display = 'none';
            }
        });
    }

    function renderScriptEditor(script, language, targetLength) {
        document.getElementById('edit-title').value = script.title || '';
        document.getElementById('edit-character').value = script.character_desc || '';

        const container = document.getElementById('scenes-container');
        container.innerHTML = '';

        script.scenes.forEach(s => {
            const card = document.createElement('div');
            card.className = 'scene-edit-card';
            card.dataset.sceneNumber = s.scene_number;

            card.innerHTML = `
                <div class="scene-edit-header">
                    <span class="scene-title">Scene ${s.scene_number} (Clip duration: ${targetLength}s)</span>
                    <span class="badge badge-queued">Draft</span>
                </div>
                <div class="form-group" style="margin-bottom: 12px;">
                    <label><strong>Narration Text (${language})</strong> <span class="field-hint">- Spoken natural audio script</span></label>
                    <textarea class="edit-narration input-large" rows="2" dir="auto">${s.narration_text || ''}</textarea>
                </div>
                <div class="form-group">
                    <label><strong>English Video Prompt for Google Flow</strong> <span class="field-hint">- Visual description, camera movement, actions</span></label>
                    <textarea class="edit-prompt" rows="3">${s.video_prompt || ''}</textarea>
                </div>
            `;
            container.appendChild(card);
        });
    }

    function collectEditedScenes() {
        const title = document.getElementById('edit-title').value.trim();
        const characterDesc = document.getElementById('edit-character').value.trim();
        const sceneCards = document.querySelectorAll('.scene-edit-card');

        const scenes = [];
        sceneCards.forEach(card => {
            const sceneNumber = parseInt(card.dataset.sceneNumber, 10);
            const narrationText = card.querySelector('.edit-narration').value.trim();
            const videoPrompt = card.querySelector('.edit-prompt').value.trim();
            scenes.push({
                scene_number: sceneNumber,
                narration_text: narrationText,
                video_prompt: videoPrompt
            });
        });

        return { title, character_desc: characterDesc, scenes };
    }

    async function launchGeneration(singleSceneOnly) {
        if (!currentJobId) {
            alert('No active job found. Please generate a script first.');
            return;
        }

        const payload = collectEditedScenes();
        payload.job_id = currentJobId;
        payload.single_scene_only = singleSceneOnly;

        const clipCount = singleSceneOnly ? 1 : payload.scenes.length;

        // Check active provider to determine if confirmation is required
        try {
            const provResp = await fetch('/api/config/active-provider');
            if (provResp.ok) {
                const provData = await provResp.json();
                if (provData.provider === 'flow') {
                    const confirmed = confirm(`This will generate ${clipCount} clip(s) using Flow credits. Continue?`);
                    if (!confirmed) {
                        return;
                    }
                }
            }
        } catch (e) {
            console.warn("Could not check active provider:", e);
        }

        try {
            const resp = await fetch('/api/job/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();
            if (data.status === 'ok') {
                window.location.href = `/progress/${currentJobId}`;
            } else {
                alert('Failed to start video generation: ' + data.message);
            }
        } catch (e) {
            alert('Error launching job: ' + e.message);
        }
    }

    const btnTestSingle = document.getElementById('btn-test-single');
    if (btnTestSingle) {
        btnTestSingle.addEventListener('click', () => {
            launchGeneration(true);
        });
    }

    const btnStartFull = document.getElementById('btn-start-full');
    if (btnStartFull) {
        btnStartFull.addEventListener('click', () => {
            launchGeneration(false);
        });
    }
});
