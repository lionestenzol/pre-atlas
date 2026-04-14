const pythonInput = document.getElementById('python-input');
const cppOutput = document.getElementById('cpp-output');
const btnConvert = document.getElementById('btn-convert');
const status = document.getElementById('status');
const verifyBadge = document.getElementById('verify-badge');
const outputCompare = document.getElementById('output-compare');
const patternsUsed = document.getElementById('patterns-used');
const warnings = document.getElementById('warnings');

// Ctrl+Enter to convert
pythonInput.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        doConvert();
    }
    // Tab inserts 4 spaces
    if (e.key === 'Tab') {
        e.preventDefault();
        const start = pythonInput.selectionStart;
        const end = pythonInput.selectionEnd;
        pythonInput.value = pythonInput.value.substring(0, start) + '    ' + pythonInput.value.substring(end);
        pythonInput.selectionStart = pythonInput.selectionEnd = start + 4;
    }
});

async function doConvert() {
    const code = pythonInput.value.trim();
    if (!code) {
        status.textContent = 'Enter some Python code first';
        return;
    }

    btnConvert.disabled = true;
    status.textContent = 'Converting...';
    verifyBadge.className = 'verify-badge verify-idle';
    verifyBadge.textContent = 'RUNNING';
    outputCompare.innerHTML = '';
    patternsUsed.innerHTML = '';
    warnings.innerHTML = '';

    try {
        const resp = await fetch('/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ python_code: code }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Conversion failed');
        }

        const data = await resp.json();

        // Show C++ output
        cppOutput.classList.remove('empty');
        cppOutput.textContent = data.cpp_code;

        // Show verification
        if (data.verification) {
            const v = data.verification;
            if (v.status === 'success' && v.match) {
                verifyBadge.className = 'verify-badge verify-match';
                verifyBadge.textContent = 'MATCH';
            } else if (v.status === 'mismatch') {
                verifyBadge.className = 'verify-badge verify-mismatch';
                verifyBadge.textContent = 'MISMATCH';
            } else {
                verifyBadge.className = 'verify-badge verify-error';
                verifyBadge.textContent = v.status.toUpperCase().replace('_', ' ');
            }

            // Show output comparison
            let compareHtml = '';
            if (v.python_output || v.cpp_output) {
                compareHtml += `
                    <div>
                        <div class="output-label">Python stdout</div>
                        <pre>${escapeHtml(v.python_output || '(empty)')}</pre>
                    </div>
                    <div>
                        <div class="output-label">C++ stdout</div>
                        <pre>${escapeHtml(v.cpp_output || '(empty)')}</pre>
                    </div>
                `;
            }
            if (v.cpp_compile_error) {
                compareHtml += `
                    <div>
                        <div class="output-label">Compile Error</div>
                        <pre>${escapeHtml(v.cpp_compile_error)}</pre>
                    </div>
                `;
            }
            if (v.python_error) {
                compareHtml += `
                    <div>
                        <div class="output-label">Python Error</div>
                        <pre>${escapeHtml(v.python_error)}</pre>
                    </div>
                `;
            }
            outputCompare.innerHTML = compareHtml;
        }

        // Show patterns used
        if (data.patterns_used && data.patterns_used.length > 0) {
            patternsUsed.innerHTML = data.patterns_used
                .map(p => `<span class="pattern-chip">${p}</span>`)
                .join('');
        }

        // Show warnings
        if (data.warnings && data.warnings.length > 0) {
            warnings.textContent = data.warnings.join(' | ');
        }

        status.textContent = `Converted — ${data.patterns_used.length} patterns applied`;

    } catch (err) {
        status.textContent = `Error: ${err.message}`;
        verifyBadge.className = 'verify-badge verify-error';
        verifyBadge.textContent = 'ERROR';
    } finally {
        btnConvert.disabled = false;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
