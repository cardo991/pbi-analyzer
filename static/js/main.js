// Upload page functionality
document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileName = document.getElementById('file-name');
    const submitBtn = document.getElementById('submit-btn');
    const form = document.getElementById('upload-form');

    if (!dropZone) return;

    // File input change
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            showFiles(this.files);
        }
    });

    // Drag and drop
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', function() {
        this.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            showFiles(e.dataTransfer.files);
        }
    });

    // Click to upload
    dropZone.addEventListener('click', function(e) {
        if (e.target.tagName !== 'BUTTON') {
            fileInput.click();
        }
    });

    function showFiles(files) {
        if (files.length === 1) {
            fileName.textContent = files[0].name + ' (' + formatSize(files[0].size) + ')';
        } else {
            var totalSize = 0;
            for (var i = 0; i < files.length; i++) totalSize += files[i].size;
            fileName.textContent = files.length + ' files selected (' + formatSize(totalSize) + ')';
        }
        fileName.classList.remove('d-none');
        submitBtn.disabled = false;
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // Show loading on submit
    form.addEventListener('submit', function() {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Analyzing...';

        var overlay = document.createElement('div');
        overlay.className = 'spinner-overlay';
        overlay.innerHTML = '<div class="text-center text-white">' +
            '<div class="spinner-border text-primary mb-3" style="width:3rem;height:3rem;"></div>' +
            '<div class="fs-5">Analyzing your report...</div></div>';
        document.body.appendChild(overlay);
    });

    // Sync rules config from localStorage to hidden field
    try {
        var stored = localStorage.getItem('pbi-rules-config');
        if (stored) {
            var input = document.getElementById('rules-config-input');
            if (input) input.value = stored;
        }
    } catch(e) {}
});
