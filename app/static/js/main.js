// Main JavaScript for IFC Analyzer

document.addEventListener('DOMContentLoaded', function() {
    // Enable tooltips everywhere
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Drag and drop file upload enhancement
    const fileInput = document.getElementById('file');
    if (fileInput) {
        const dropArea = fileInput.closest('.mb-3');
        
        // Add visual cues for drag and drop
        dropArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('border', 'border-primary');
        });
        
        dropArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            this.classList.remove('border', 'border-primary');
        });
        
        dropArea.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('border', 'border-primary');
            
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                
                // Trigger change event to activate validation
                const event = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(event);
            }
        });
        
        // Create a visual indication of file selected
        fileInput.addEventListener('change', function(e) {
            const fileName = this.files[0]?.name;
            if (fileName) {
                let fileInfo = this.nextElementSibling;
                if (!fileInfo || !fileInfo.classList.contains('file-info')) {
                    fileInfo = document.createElement('div');
                    fileInfo.className = 'alert alert-info mt-2 file-info';
                    this.parentNode.insertBefore(fileInfo, this.nextSibling);
                }
                fileInfo.innerHTML = `<strong>Selected:</strong> ${fileName}`;
            }
        });
    }
}); 