const backendBase = 'https://topo-indices.onrender.com';
document.addEventListener('DOMContentLoaded', async () => {
  const enabled = await checkCookieSupport();
  if (!enabled) return;

  let userEmail = sessionStorage.getItem('userEmail');

  // UI elements
  const resultsCard = document.getElementById('results-card'),
        errorCard = document.getElementById('error-card'),
        resultsTitle = document.getElementById('results-title'),
        tableHead = document.getElementById('table-head'),
        resultsBody = document.getElementById('results-body'),
        dropZone = document.getElementById('drop-zone');

  let currentFiles = [];
  let currentK = 1;
  let filesProcessed = false;

  // Initial auth check
  checkAuthStatus();
  let isAdmin = false;

  async function checkCookieSupport() {
    try {
      console.log('[1/4] Clearing cookies');
      await fetch(`${backendBase}/clear-cookie`, { 
        credentials: 'include',
        cache: 'no-store' 
      });

      console.log('[2/4] Setting test cookie');
      await fetch(`${backendBase}/check-cookies`, {
        credentials: 'include',
        cache: 'no-store'
      });

      console.log('[3/4] Verifying cookie');
      const checkRes = await fetch(`${backendBase}/check-cookies`, {
        credentials: 'include',
        cache: 'no-store'
      });
    
      const data = await checkRes.json();
      console.log('[4/4] Cookie enabled:', data.cookie_enabled);
    
      if (!data.cookie_enabled) {
        console.log('Showing cookie dialog');
        showCookieDialog();
        return false;
      }
      return true;
    } catch (error) {
      console.error('Cookie check failed:', error);
      showCookieDialog();
      return false;
    }
  }
  
  async function retryCookieCheck() {
    try {
      // Simply hide the dialog without any checks
      const modal = bootstrap.Modal.getInstance(document.getElementById('cookieDialog'));
      modal.hide();
    } catch (error) {
      console.error('Dialog close error:', error);
    }
  }

  // Update checkAuthStatus function
  async function checkAuthStatus() {
    try {
        const res = await fetch(`${backendBase}/auth/check`, {
            credentials: 'include',
            headers: {'Cache-Control': 'no-store'}
        });
        
        if (res.ok) {
            const { email, is_admin } = await res.json();
            sessionStorage.setItem('userEmail', email);
            isAdmin = is_admin;  // Set admin status from backend
            initializeApp();
            
            // Disable used modes only for non-admins
            if (!isAdmin) {
                const usageRes = await fetch(`${backendBase}/usage-status`, {
                  credentials: 'include'
                });
                const usage = await usageRes.json();
                document.querySelectorAll('[name="mode"]').forEach(radio => {
                    radio.disabled = usage[radio.value];
                });
            }
        }
    } catch {
        startGoogleAuth();
    }
  }

  async function resetUserUsage() {
    const email = document.getElementById('reset-email').value;
    if (!email.includes('@')) {
      alert('Please enter a valid email');
      return;
    }

    try {
      const res = await fetch(`${backendBase}/admin/reset-usage`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email })
      });

      if (res.ok) {
        alert('Usage reset successfully');
        // Refresh mode availability
        const usageRes = await fetch(`${backendBase}/usage-status`);
        const usage = await usageRes.json();
        document.querySelectorAll('[name="mode"]').forEach(radio => {
          radio.disabled = usage[radio.value];
        });
      }
    } catch (error) {
      console.error('Reset failed:', error);
      alert('Reset operation failed');
    }
  }

  function showCookieDialog() {
    console.log('Attempting to show dialog');
    const modalElement = document.getElementById('cookieDialog');
    if (!modalElement) {
      console.error('Dialog element not found!');
      return;
    }
  
    console.log('Initializing modal');
    const modal = new bootstrap.Modal(modalElement, {
      backdrop: 'static',
      keyboard: false
    });
    modal.show();
  }

  function startGoogleAuth() {
    window.location.href = `${backendBase}/auth/google`;
  }

  function initializeApp() {
    bindFileHandlers();
    resetFileSelection();
  }

  function resetFileSelection() {
    document.getElementById('file-input').value = '';
    document.getElementById('file-list').textContent = '';
    currentFiles = [];
  }

  function bindFileHandlers() {
    const fileInput = document.getElementById('file-input');
    const chooseBtn = document.getElementById('choose-btn');
    const calculateBtn = document.getElementById('calculate-btn');

    if (fileInput) {
      fileInput.multiple = isAdmin; // This is the key change
    }
    if (dropZone) {
      dropZone.ondragover = null;
      dropZone.ondragleave = null;
      dropZone.ondrop = null;
    }

    if (chooseBtn && fileInput) {
      chooseBtn.onclick = () => fileInput.click();
    }

    if (fileInput) {
      fileInput.onchange = e => {
        const files = Array.from(e.target.files);
        updateFiles(files);
      };
    }

    // Drag and drop handlers
    if (dropZone) {
      dropZone.ondrop = e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
      
        const files = Array.from(e.dataTransfer.files);
        updateFiles(files);
      };
    }

    if (calculateBtn) {
      calculateBtn.onclick = runAnalysis;
    }
  }

  function updateFiles(files) {
    errorCard.classList.add('d-none');
    resultsCard.classList.add('d-none');

    const molFiles = files
    .filter(f => f.name.toLowerCase().endsWith('.mol'))
    .slice(0, isAdmin ? Infinity : 1); // Take only first file if not admin
  
    if (!isAdmin && files.length > 1) {
      // Optional: Add visual feedback instead of error message
      dropZone.classList.add('drag-error');
      setTimeout(() => dropZone.classList.remove('drag-error'), 1000);
    }

    currentFiles = molFiles;
    filesProcessed = false;
    const fileListElement = document.getElementById('file-list');
  
    if (fileListElement) {
      fileListElement.textContent = currentFiles.length > 0 
        ? (isAdmin ? currentFiles.map(f => f.name).join(', ') : currentFiles[0].name)
        : '';
    }

    document.getElementById('calculate-btn').disabled = !currentFiles.length || filesProcessed;
  }

  async function runAnalysis() {
    try {
        errorCard.classList.add('d-none');
        resultsCard.classList.add('d-none');
        const calculateBtn = document.getElementById('calculate-btn');
    
        // Disable during processing
        calculateBtn.disabled = true;
        filesProcessed = true;

        const mode = document.querySelector('input[name="mode"]:checked').value;
    
        if(mode === 'reverse_degree') {
          // Show k input dialog
          currentK = await new Promise((resolve) => {
          const modal = new bootstrap.Modal(document.getElementById('kValueDialog'));
          const confirmBtn = document.getElementById('confirmK');
        
          const handler = () => {
            const k = parseInt(document.getElementById('kInput').value) || 1;
            modal.hide();
            resolve(k);
            confirmBtn.removeEventListener('click', handler);
          };
        
          modal.show();
          confirmBtn.addEventListener('click', handler);
        });
      }
    
      const formData = new FormData();
      formData.append('mode', mode);
      if(mode === 'reverse_degree') {
        formData.append('k', currentK);
      }
      currentFiles.forEach(f => formData.append('files', f));

        const res = await fetch(`${backendBase}/upload`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });

        const data = await res.json();
        
        if (!res.ok) {
            if (data.error === 'limit_exceeded') {
                showEmailMessage(data.message);
                return;
            }
            throw new Error(data.error || 'Upload failed');
        }

        // Show results only if within limits
        displayResults(data);
        showLoadingState
        // revertUploadUI();
        
    } catch (error) {
      console.error('Analysis error:', error);
      showErrorState(error.message);
      restoreUI(); // Full reset on error
    } finally {
      // Re-enable if files exist
      document.getElementById('calculate-btn').disabled = true;
    }
  }

  function revertUploadUI() {
    if (dropZone) {
      // Preserve existing file input structure
      dropZone.innerHTML = `
        <input type="file" id="file-input" multiple accept=".mol" hidden>
        <div class="text-center">
          <p>Drag &amp; drop .mol files here or</p>
          <button id="choose-btn" class="btn btn-primary">Choose Files</button>
          <button id="calculate-btn" class="btn btn-success ms-2" ${currentFiles.length ? '' : 'disabled'}>Calculate</button>
          <div id="file-list" class="mt-2 small text-muted">${
            currentFiles.length > 0 
              ? (isAdmin 
                  ? currentFiles.map(f => f.name).join(', ') 
                  : currentFiles[0].name)
              : ''
          }</div>
        </div>`;

      // Rebind handlers without resetting files
      bindFileHandlers();
    }
  }

  function showEmailMessage(message) {
    // Hide other error displays
    resultsCard.classList.add('d-none');
    document.getElementById('results-body').innerHTML = '';
    
    const errorDiv = document.getElementById('error-message');
    errorDiv.innerHTML = message.replace('anthuvanjoseph21@gmail.com', 
        `<a href="mailto:anthuvanjoseph21@gmail.com">anthuvanjoseph21@gmail.com</a>`);
    errorCard.classList.remove('d-none');
  }
  
  function showErrorState(message) {
    errorCard.classList.add('d-none');
    resultsCard.classList.remove('d-none');
    
    resultsBody.innerHTML = `
      <tr><td colspan="100%" class="text-center p-4 text-danger">
        Error: ${message || 'Processing failed'}
      </td></tr>`;
  }

  function showLoadingState() {
    const originalContent = dropZone.innerHTML;
    dropZone.innerHTML = originalContent + `
      <div class="loading-overlay">
        <div class="text-center">
          <div class="spinner-border text-primary" role="status"></div>
          <p class="mt-2">Analyzing MOL structure...</p>
        </div>
      </div>`;
  }

  function displayResults(results) {
    if (results.length === 0) return;

    const mode = document.querySelector('input[name="mode"]:checked').value;
    const modeTitles = {
      degree: 'Degree Descriptors',
      degreesum: 'Degree Sum Descriptors',
      reverse_degree: 'Reverse Degree Descriptors',
      scaled_face_degree: 'Scaled Face Degree Descriptors',
      scaled_face_degree_sum: 'Scaled Face Degree Sum Descriptors'
    };

    let title = modeTitles[mode] || 'Analysis Results';
    if (mode === 'reverse_degree') {
      title += ` - \\(k = ${currentK}\\)`; // LaTeX formatting
    }

    resultsTitle.innerHTML = title;
    resultsTitle.classList.add('text-center');
  
    MathJax.typesetPromise([resultsTitle]).catch((err) => {
      console.log('MathJax typeset error:', err);
    }).finally(() => {
      resultsCard.classList.remove('d-none');
      errorCard.classList.add('d-none');
    });

    tableHead.innerHTML = `<tr>${
      Object.keys(results[0]).map(k => {
        const isFilename = k.toLowerCase() === 'filename';
        const headerText = isFilename ? k : k.toUpperCase();
        return `<th data-column="${k.toLowerCase()}">${headerText}</th>`;
      }).join('')
    }</tr>`;

    resultsBody.innerHTML = results.map(r => `
      <tr>${Object.entries(r).map(([key, value]) => {
        const isFilename = key.toLowerCase() === 'filename';
        const displayValue = isFilename ? value.replace(/\.mol$/i, '') : value;
        return `<td data-column="${key.toLowerCase()}">${formatValue(displayValue)}</td>`;
      }).join('')}</tr>`
    ).join('');
  }

  function formatValue(value) {
    if (typeof value === 'number') {
      return Number.isInteger(value) ? 
        value.toLocaleString() : 
        value.toFixed(4).replace(/\.?0+$/, '');
    }
    return value;
  }

  function restoreUI() {
    if (dropZone) {
      dropZone.innerHTML = `
        <input type="file" id="file-input" multiple accept=".mol" hidden>
        <div class="text-center">
          <p>Drag &amp; drop .mol files here or</p>
          <button id="choose-btn" class="btn btn-primary">Choose Files</button>
          <button id="calculate-btn" class="btn btn-success ms-2" disabled>Calculate</button>
          <div id="file-list" class="mt-2 small text-muted"></div>
        </div>`;

      document.getElementById('calculate-btn').disabled = true;
    
      setTimeout(() => {
        bindFileHandlers();
        if (currentFiles.length > 0) {
          document.getElementById('file-list').textContent = 
            isAdmin ? currentFiles.map(f => f.name).join(', ') : currentFiles[0].name;
        }
        document.getElementById('calculate-btn').disabled = 
          !currentFiles.length || filesProcessed;
      }, 50);
    }
  }
});

window.handleAuthCallback = async () => {
  try {
    const res = await fetch('https://topo-indices.onrender.com/auth/check', {
      credentials: 'include'
    });
    
    if (res.ok) {
      const { email } = await res.json();
      sessionStorage.setItem('userEmail', email);
      window.location.href = '/';
    } else {
      sessionStorage.removeItem('userEmail');
      window.location.href = '/?error=auth_failed';
    }
  } catch {
    window.location.href = '/?error=connection_failed';
  }
};